# ROADMAP - MCP Gateway Learning Project

## Phase 0 -- Scaffold

- [x] Project structure (AGENTS.md, Makefile, Helm skeletons, tests, docs)
- [x] Cursor / Claude rules for MCP Gateway conventions
- [x] Git repo initialized
- [x] ADR-0001: Connectivity Link vs upstream install
- [x] Version matrix in docs/versions.md

## Phase 1 -- Operator + Gateway (Helm)

- [x] `charts/operators/` -- Subscription for Connectivity Link via OLM
- [x] `charts/operators/` -- MCP Gateway operator (`mcp-gateway`, channel `preview`)
- [x] `charts/operators/` -- GatewayClass `openshift-default` for OCP Gateway API
- [x] `charts/gateway/` -- Gateway object + MCPGatewayExtension CR
- [x] Makefile targets: `deploy-operators`, `deploy-gateway`
- [ ] ADR: namespace strategy (single vs multi-namespace)

## Phase 2 -- Deploy kubernetes-mcp-server as Backend

- [x] `charts/kubernetes-mcp-server/` -- Wrapper Helm chart (OCI dependency)
- [x] Configure: `openshift: true`, ingress, RBAC with `view` role
- [x] Fix: `toolsets` as TOML array (upstream compat)
- [x] Makefile targets: `deploy-k8s-mcp-server`, `test-k8s-mcp-direct`
- [x] Validate: direct `tools/list` call to k8s-mcp-server endpoint

## Phase 3 -- Register kubernetes-mcp-server in the Gateway

- [x] `charts/mcp-servers/` -- HTTPRoute + MCPServerRegistration with `prefix: k8s_`
- [x] Dual-listener Gateway (`mcp` public + `mcps` internal `*.mcp.local`)
- [x] ReferenceGrant for cross-namespace backend Service refs
- [x] Makefile targets: `deploy-mcp-servers`, `test-tools-list`
- [x] Validate: `tools/list` through gateway shows `k8s_*` prefixed tools

## Phase 3.1 -- HTTPS via OpenShift Route (MaaS pattern) — default

> **Context:** On OCP/AWS, `*.apps.<cluster>` DNS is managed by the ingress operator.
> A Gateway LoadBalancer gets its **own ELB**; hostnames under `*.apps` still resolve
> to the **router**, not the Gateway. The MaaS pattern (Route + ClusterIP + wildcard
> cert) reuses cluster DNS/TLS without manual Route53 or DNSPolicy.
>
> See [ADR-0003](adr/0003-gateway-exposure-strategy.md).

**Goal:** Expose `https://mcp-gateway.apps.<cluster>/mcp` with valid TLS and automatic DNS.

**Decision:** `exposure.mode: route` (default) — OpenShift Route passthrough + `ingress-certs`.

### Implemented

- [x] `exposure.mode: route` — ClusterIP Gateway Service + OpenShift Route
- [x] Gateway listener HTTPS:443 with `ingress-certs` (wildcard `*.apps.<domain>`)
- [x] Makefile: `sync-wildcard-tls`, `GATEWAY_EXPOSURE=route`, `GATEWAY_URL=https://...`
- [x] Tests without `GATEWAY_RESOLVE_IP` workaround (public hostname resolves correctly)
- [x] ADR-0003: Route vs LoadBalancer vs hybrid

### Validate

- [x] Redeploy on cluster: `make deploy-gateway` (default route mode)
- [x] `curl https://mcp-gateway.apps.<cluster>/mcp` (no `--resolve`)
- [x] `make test-tools-list`

## Phase 3.2 -- LoadBalancer + DNSPolicy (optional / advanced)

> **When to use:** Dedicated Gateway ELB without ingress router hop; multicluster RHCL
> patterns; environments where Route passthrough is not acceptable.

**Goal:** `exposure.mode: loadbalancer` with automatic Route53 via RHCL `DNSPolicy`.

### Planned

- [ ] Document `GATEWAY_EXPOSURE=loadbalancer` deploy path (HTTP POC on ELB:8080)
- [ ] HTTPS: cert-manager `Certificate` for listener hostname (manual or separate chart)
- [ ] RHCL `DNSPolicy` + AWS provider Secret with `route53:ListHostedZones` (broader IAM than cert-manager ACME user)
- [ ] Fallback: manual Route53 CNAME to Gateway ELB
- [ ] Tests: `GATEWAY_RESOLVE_IP` until DNSPolicy Ready
- [ ] Evaluate bare-metal: `router-certs-default` vs `ingress-certs` for route mode

### Not planned: Hybrid (Option 3)

Route **and** LoadBalancer active at the same time — two public entry points, two TLS
paths, duplicate ops. Deferred unless a consumer explicitly needs both a `*.apps` URL
and a dedicated ELB hostname. See ADR-0003.

### Follow-up

- [x] Evaluate RHCL `DNSPolicy` — blocked on OpenTLC: cert-manager IAM lacks `ListHostedZones`; Phase 3.2 scope
- [ ] Document workaround for broken helm download in `ocp-on-aws` (upstream issue)

## Phase 4 -- Policies (Auth + Rate Limiting)

- [x] `charts/policies/` -- AuthPolicy (API key) + RateLimitPolicy (global + burst)
- [x] AuthPolicy: `when` predicate skips `/.well-known` (OAuth discovery prep)
- [x] RateLimitPolicy: global (60 req/min) + burst (10 req/s) + optional per-identity
- [x] `make create-api-key` target for API key Secret creation
- [x] `MCPVirtualServer` template scaffold (discovery-level tool filtering)
- [x] Test matrix:
  - No auth -> 401
  - Valid API key -> all `k8s_*` tools
  - Invalid key -> 401/403
  - Burst throttling -> 429
- [x] `tests/test_auth_policies.py` -- Auth policy tests (skip when no AuthPolicy)
- [x] `tests/test_rate_limit.py` -- Rate limit tests (skip when no RateLimitPolicy)
- [x] ADR-0004: auth strategy (API key now, OCP OAuth Phase 5)

## Phase 5 -- OAuth + Identity-Based Filtering + Observability

### OAuth via OCP native OAuth server

- [ ] AuthPolicy `jwt` with `issuerUrl: https://oauth-openshift.apps.<cluster>` (OCP OAuth)
- [ ] Alternative: AuthPolicy `kubernetesTokenReview` for ServiceAccount token validation
- [ ] ADR: OCP OAuth vs external Keycloak for MCP Gateway
- [ ] Per-identity rate limiting (`counters: auth.identity.username`) with OCP identity
- [ ] Identity-based tool filtering: MCPVirtualServer + AuthPolicy wristband
  - Wristband header `x-mcp-authorized` with `allowed-capabilities` claim
  - IdP `resource_access` roles mapped to tool names
  - Execution-level blocking (not just discovery filtering)

### Observability + Advanced

- [ ] Prometheus metrics from broker (`/metrics` endpoint)
- [ ] Full E2E pytest suite
- [ ] Multi-server aggregation with prefix-based namespacing
- [ ] MCP 2026-07-28 stateless protocol testing
- [ ] MCPVirtualServer with real tool subsets (k8s-readonly, k8s-debug profiles)
- [ ] Integration with RHOAI MCP catalog (developer preview)

## Backlog / Docs

- [ ] Update `AGENTS.md` and `docs/versions.md` (API `v1alpha1`, separate `mcp-gateway` operator)
- [ ] Document two-listener Gateway design (ADR or workarounds.md)
- [ ] Workaround: corrupt helm in `ocp-on-aws` install script

> ArgoCD GitOps can be added as a future phase once the Helm charts are stable.
