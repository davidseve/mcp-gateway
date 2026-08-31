# ROADMAP - MCP Gateway Learning Project

## Phase 0 -- Scaffold (current)

- [x] Project structure (AGENTS.md, Makefile, Helm skeletons, tests, docs)
- [x] Cursor / Claude rules for MCP Gateway conventions
- [x] Git repo initialized
- [x] ADR-0001: Connectivity Link vs upstream install
- [x] Version matrix in docs/versions.md

## Phase 1 -- Operator + Gateway (Helm)

- [ ] `charts/operators/` -- Subscription for Connectivity Link via OLM
- [ ] `charts/gateway/` -- Gateway object + MCPGatewayExtension CR
- [ ] Makefile targets: `deploy-operators`, `deploy-gateway`, `wait-ready`
- [ ] ADR: namespace strategy (single vs multi-namespace)

## Phase 2 -- Deploy kubernetes-mcp-server as Backend

- [ ] `charts/kubernetes-mcp-server/` -- Wrapper Helm chart (OCI dependency)
- [ ] Configure: `openshift: true`, ingress, RBAC with `view` role
- [ ] Makefile targets: `deploy-k8s-mcp-server`, `test-k8s-mcp-direct`
- [ ] Validate: direct `tools/list` call to k8s-mcp-server endpoint

## Phase 3 -- Register kubernetes-mcp-server in the Gateway

- [ ] `charts/mcp-servers/` -- HTTPRoute + MCPServerRegistration with `prefix: k8s_`
- [ ] Makefile targets: `deploy-mcp-servers`, `test-tools-list`
- [ ] Validate: `tools/list` through gateway shows `k8s_pods_list`, `k8s_resources_get`, etc.

## Phase 4 -- Policies (Auth + Permissions Testing)

- [ ] `charts/policies/` -- AuthPolicy (API key, then OAuth) + RateLimitPolicy
- [ ] Test matrix:
  - No auth -> 401
  - Valid API key -> all `k8s_*` tools
  - Identity-based tool filtering (user A: read-only, user B: full)
  - Rate limiting -> burst throttling
- [ ] `tests/test_auth_policies.py` -- Automated permission tests
- [ ] ADR: auth strategy

## Phase 5 -- Observability + Advanced

- [ ] Prometheus metrics from broker (`/metrics` endpoint)
- [ ] Full E2E pytest suite
- [ ] Multi-server aggregation with prefix-based namespacing
- [ ] MCP 2026-07-28 stateless protocol testing
- [ ] MCPVirtualServer experiments
- [ ] Integration with RHOAI MCP catalog (developer preview)

> ArgoCD GitOps can be added as a future phase once the Helm charts are stable.
