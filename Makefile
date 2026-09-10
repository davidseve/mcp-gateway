.PHONY: help deploy-all undeploy-all lint test
.DEFAULT_GOAL := help

HELM       ?= helm
OC         ?= oc
PYTEST     ?= pytest
CLUSTER_DOMAIN ?= $(shell $(OC) get ingress.config cluster -o jsonpath='{.spec.domain}' 2>/dev/null)

# Namespaces
OPERATOR_NS     ?= connectivity-link
GATEWAY_NS      ?= gateway-system
K8S_MCP_NS      ?= kubernetes-mcp-server
MCP_SERVERS_NS  ?= gateway-system
POLICIES_NS     ?= gateway-system

# Gateway access
# route (default): OpenShift Route + ClusterIP — DNS via *.apps wildcard (MaaS pattern)
# loadbalancer: dedicated Gateway ELB — Phase 3.2 (DNSPolicy / manual CNAME)
GATEWAY_EXPOSURE       ?= route
GATEWAY_TLS            ?= false
GATEWAY_TLS_SECRET     ?= $(if $(filter route,$(GATEWAY_EXPOSURE)),ingress-certs,mcp-gateway-tls)
GATEWAY_MCP_HOST       ?= mcp-gateway.$(CLUSTER_DOMAIN)
GATEWAY_ELB            ?= $(shell $(OC) get gateway mcp-gateway -n $(GATEWAY_NS) -o jsonpath='{.status.addresses[0].value}' 2>/dev/null)
GATEWAY_RESOLVE_IP     ?= $(if $(filter loadbalancer,$(GATEWAY_EXPOSURE)),$(shell dig +short $(GATEWAY_ELB) 2>/dev/null | head -1),)
GATEWAY_URL            ?= $(if $(filter route,$(GATEWAY_EXPOSURE)),https://$(GATEWAY_MCP_HOST),$(if $(filter true,$(GATEWAY_TLS)),https://$(GATEWAY_MCP_HOST),http://$(GATEWAY_ELB):8080))
GATEWAY_TEST_ENV       = GATEWAY_NS=$(GATEWAY_NS) K8S_MCP_NS=$(K8S_MCP_NS) \
	GATEWAY_URL=$(GATEWAY_URL) GATEWAY_RESOLVE_IP=$(GATEWAY_RESOLVE_IP)

# ─── Help ───────────────────────────────────────────────────────────────────────

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-26s\033[0m %s\n", $$1, $$2}'

# ─── Deploy ─────────────────────────────────────────────────────────────────────

deploy-operators: ## Install Connectivity Link operator via OLM
	$(HELM) upgrade --install connectivity-link-operators charts/operators \
		--namespace $(OPERATOR_NS) --create-namespace \
		--wait --timeout 5m

deploy-k8s-mcp-server: ## Deploy kubernetes-mcp-server backend
	$(HELM) dependency update charts/kubernetes-mcp-server
	$(HELM) upgrade --install kubernetes-mcp-server charts/kubernetes-mcp-server \
		--namespace $(K8S_MCP_NS) --create-namespace \
		--set kubernetes-mcp-server.ingress.host=kubernetes-mcp-server.$(CLUSTER_DOMAIN) \
		--wait --timeout 5m

deploy-gateway: ## Deploy Gateway + MCPGatewayExtension (GATEWAY_EXPOSURE=route|loadbalancer)
	$(if $(filter route,$(GATEWAY_EXPOSURE)),$(MAKE) sync-wildcard-tls,)
	$(HELM) upgrade --install mcp-gateway charts/gateway \
		--namespace $(GATEWAY_NS) --create-namespace \
		--set global.clusterDomain=$(CLUSTER_DOMAIN) \
		--set exposure.mode=$(GATEWAY_EXPOSURE) \
		--set gateway.listeners.mcp.hostname=$(GATEWAY_MCP_HOST) \
		--set gateway.listeners.mcp.tls.enabled=$(if $(filter route,$(GATEWAY_EXPOSURE)),true,$(GATEWAY_TLS)) \
		--set gateway.listeners.mcp.tls.certificateSecret=$(GATEWAY_TLS_SECRET) \
		--wait --timeout 5m

sync-wildcard-tls: ## Copy ingress wildcard cert to gateway namespace (route exposure)
	@echo "Syncing $(GATEWAY_TLS_SECRET) from openshift-ingress to $(GATEWAY_NS)..."
	@$(OC) get secret $(GATEWAY_TLS_SECRET) -n openshift-ingress -o json | \
		python3 -c "import sys,json; s=json.load(sys.stdin); m=s['metadata']; \
		[m.pop(k,None) for k in ('uid','resourceVersion','creationTimestamp','ownerReferences','managedFields')]; \
		m['namespace']='$(GATEWAY_NS)'; print(json.dumps(s))" | $(OC) apply -f -

deploy-mcp-servers: ## Register MCP servers in the gateway
	$(HELM) upgrade --install mcp-server-registrations charts/mcp-servers \
		--namespace $(MCP_SERVERS_NS) --create-namespace \
		--set global.clusterDomain=$(CLUSTER_DOMAIN) \
		--wait --timeout 3m

deploy-policies: ## Deploy AuthPolicy + RateLimitPolicy (enabled by default)
	$(HELM) upgrade --install mcp-policies charts/policies \
		--namespace $(POLICIES_NS) \
		--wait --timeout 3m

create-api-key: ## Create an API key Secret for AuthPolicy (MCP_API_KEY_NAME=name MCP_API_KEY_VALUE=key)
	@if [ -z "$(MCP_API_KEY_VALUE)" ]; then \
		echo "Usage: make create-api-key MCP_API_KEY_VALUE=your-secret-key [MCP_API_KEY_NAME=my-key]"; \
		exit 1; \
	fi
	$(OC) create secret generic $(or $(MCP_API_KEY_NAME),mcp-api-key) \
		-n $(OPERATOR_NS) \
		--from-literal=api_key=$(MCP_API_KEY_VALUE) \
		--dry-run=client -o yaml | \
		$(OC) apply -f -
	$(OC) label secret $(or $(MCP_API_KEY_NAME),mcp-api-key) \
		-n $(OPERATOR_NS) \
		mcp.kuadrant.io/secret=true \
		authorino.kuadrant.io/managed-by=authorino \
		--overwrite
	@echo "API key created in namespace $(OPERATOR_NS) (Authorino watches Secrets here)"

deploy-all: deploy-operators deploy-k8s-mcp-server deploy-gateway deploy-mcp-servers ## Deploy full stack (no policies)
	@echo "Full stack deployed. Run 'make deploy-policies' to add auth/rate-limit."

# ─── Undeploy ───────────────────────────────────────────────────────────────────

undeploy-policies: ## Remove policies
	-$(HELM) uninstall mcp-policies --namespace $(POLICIES_NS)

undeploy-mcp-servers: ## Remove MCP server registrations
	-$(HELM) uninstall mcp-server-registrations --namespace $(MCP_SERVERS_NS)

undeploy-gateway: ## Remove Gateway + MCPGatewayExtension
	-$(HELM) uninstall mcp-gateway --namespace $(GATEWAY_NS)

undeploy-k8s-mcp-server: ## Remove kubernetes-mcp-server
	-$(HELM) uninstall kubernetes-mcp-server --namespace $(K8S_MCP_NS)

undeploy-operators: ## Remove Connectivity Link operator
	-$(HELM) uninstall connectivity-link-operators --namespace $(OPERATOR_NS)

undeploy-all: undeploy-policies undeploy-mcp-servers undeploy-gateway undeploy-k8s-mcp-server undeploy-operators ## Tear down everything

# ─── Test ───────────────────────────────────────────────────────────────────────

test: ## Run all tests
	$(GATEWAY_TEST_ENV) $(PYTEST) tests/ -v

test-k8s-mcp-direct: ## Test kubernetes-mcp-server directly (bypass gateway)
	GATEWAY_NS=$(GATEWAY_NS) K8S_MCP_NS=$(K8S_MCP_NS) \
		$(PYTEST) tests/test_gateway_health.py -v -k "k8s_mcp"

test-tools-list: ## Test tools/list through the gateway
	$(GATEWAY_TEST_ENV) $(PYTEST) tests/test_mcp_tools_list.py -v

test-auth: ## Test auth policies
	$(GATEWAY_TEST_ENV) $(PYTEST) tests/test_auth_policies.py -v

test-ratelimit: ## Test rate limiting policies
	$(GATEWAY_TEST_ENV) $(PYTEST) tests/test_rate_limit.py -v

# ─── Lint ───────────────────────────────────────────────────────────────────────

lint: ## Helm lint all charts
	@for chart in charts/*/; do \
		echo "Linting $$chart..."; \
		$(HELM) lint $$chart || true; \
	done

template: ## Helm template all charts (dry-run)
	@for chart in charts/*/; do \
		echo "=== $$chart ==="; \
		$(HELM) template test $$chart 2>/dev/null || echo "(skipped — needs values)"; \
	done

# ─── Long-Running Wrappers ─────────────────────────────────────────────────────

deploy-quiet: ## Deploy all via agent-run.sh (for AI agent use)
	bash scripts/lib/agent-run.sh "make deploy-all" deploy-all

validate-smoke: ## Quick smoke test (for AI agent use)
	@echo "Checking operator CSV..."
	$(OC) get csv -n $(OPERATOR_NS) 2>/dev/null | head -5 || echo "No CSV found"
	@echo "Checking gateway pods..."
	$(OC) get pods -n $(GATEWAY_NS) 2>/dev/null | head -10 || echo "No pods found"
	@echo "Checking gateway route..."
	$(OC) get route mcp-gateway -n $(GATEWAY_NS) 2>/dev/null || echo "No route found (loadbalancer exposure?)"
	@echo "Checking k8s-mcp-server pods..."
	$(OC) get pods -n $(K8S_MCP_NS) 2>/dev/null | head -5 || echo "No pods found"
