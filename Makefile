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

# Gateway ELB address (for Gateway API-based gateways)
GATEWAY_ELB    ?= $(shell $(OC) get gateway mcp-gateway -n $(GATEWAY_NS) -o jsonpath='{.status.addresses[0].value}' 2>/dev/null)
GATEWAY_URL    ?= http://$(GATEWAY_ELB):8080

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

deploy-gateway: ## Deploy Gateway + MCPGatewayExtension
	$(HELM) upgrade --install mcp-gateway charts/gateway \
		--namespace $(GATEWAY_NS) --create-namespace \
		--set global.clusterDomain=$(CLUSTER_DOMAIN) \
		--set gateway.listeners.mcp.hostname=mcp-gateway.$(CLUSTER_DOMAIN) \
		--wait --timeout 5m

deploy-mcp-servers: ## Register MCP servers in the gateway
	$(HELM) upgrade --install mcp-server-registrations charts/mcp-servers \
		--namespace $(MCP_SERVERS_NS) --create-namespace \
		--set global.clusterDomain=$(CLUSTER_DOMAIN) \
		--wait --timeout 3m

deploy-policies: ## Deploy AuthPolicy + RateLimitPolicy
	$(HELM) upgrade --install mcp-policies charts/policies \
		--namespace $(POLICIES_NS) \
		--wait --timeout 3m

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
	GATEWAY_NS=$(GATEWAY_NS) K8S_MCP_NS=$(K8S_MCP_NS) \
		GATEWAY_URL=$(GATEWAY_URL) \
		$(PYTEST) tests/ -v

test-k8s-mcp-direct: ## Test kubernetes-mcp-server directly (bypass gateway)
	GATEWAY_NS=$(GATEWAY_NS) K8S_MCP_NS=$(K8S_MCP_NS) \
		$(PYTEST) tests/test_gateway_health.py -v -k "k8s_mcp"

test-tools-list: ## Test tools/list through the gateway
	GATEWAY_NS=$(GATEWAY_NS) K8S_MCP_NS=$(K8S_MCP_NS) \
		GATEWAY_URL=$(GATEWAY_URL) \
		$(PYTEST) tests/test_mcp_tools_list.py -v

test-auth: ## Test auth policies
	GATEWAY_NS=$(GATEWAY_NS) K8S_MCP_NS=$(K8S_MCP_NS) \
		GATEWAY_URL=$(GATEWAY_URL) \
		$(PYTEST) tests/test_auth_policies.py -v

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
	@echo "Checking k8s-mcp-server pods..."
	$(OC) get pods -n $(K8S_MCP_NS) 2>/dev/null | head -5 || echo "No pods found"
