# MCP Gateway Learning Project

Learn to deploy, configure, and manage Red Hat's MCP Gateway on OpenShift,
using the kubernetes-mcp-server as a real backend to test authentication,
authorization, tool filtering, and rate limiting.

## Architecture

```
AI Agents (Cursor, LangGraph, custom)
        │
        │ MCP over HTTP (streamable / stateless)
        ▼
┌───────────────────────────────┐
│  MCP Gateway (Envoy + Broker) │    ← Gateway + MCPGatewayExtension
│  ┌──────────┐ ┌─────────────┐│
│  │AuthPolicy│ │RateLimitPol.││    ← Kuadrant policy attachment
│  └──────────┘ └─────────────┘│
└───────────┬───────────────────┘
            │ HTTPRoute + MCPServerRegistration (prefix: k8s_)
            ▼
┌───────────────────────────────┐
│  kubernetes-mcp-server        │    ← 15+ tools: pods, resources,
│  (on OpenShift, view RBAC)    │       events, namespaces, helm...
└───────────────────────────────┘
```

## Prerequisites

- OpenShift 4.17+ cluster with admin access
- `oc` CLI logged in
- `helm` 3.x
- `make`
- Python 3.11+ with `pytest` (for tests)

## Quick Start

```bash
# Deploy everything
make deploy-all

# Or step by step:
make deploy-operators         # Install Connectivity Link operator
make deploy-k8s-mcp-server    # Deploy kubernetes-mcp-server backend
make deploy-gateway           # Deploy Gateway + MCPGatewayExtension
make deploy-mcp-servers       # Register servers in gateway
make deploy-policies          # Deploy auth + rate limit policies

# Validate
make test                     # Run all tests

# Gateway URL (default: route mode — same pattern as rhoai-platform-ops MaaS)
# https://mcp-gateway.apps.<cluster-domain>/mcp
# Optional: GATEWAY_EXPOSURE=loadbalancer for dedicated ELB (Phase 3.2 — see ROADMAP)

# Tear down
make undeploy-all
```

## Project Structure

```
charts/
  operators/              Connectivity Link Subscription + OperatorGroup
  kubernetes-mcp-server/  Wrapper chart for upstream k8s-mcp-server (OCI)
  gateway/                Gateway + MCPGatewayExtension
  mcp-servers/            MCPServerRegistration + HTTPRoute
  policies/               AuthPolicy + RateLimitPolicy
tests/                    pytest: health, tools/list, auth policies
docs/
  adr/                    Architecture Decision Records
  versions.md             Component version matrix
  ROADMAP.md              Learning phases
  workarounds.md          Known issues and workarounds
```

## Key CRDs

| CRD | API | Purpose |
|-----|-----|---------|
| Gateway | gateway.networking.k8s.io | Envoy ingress listener |
| MCPGatewayExtension | mcp.kuadrant.io/v1alpha1 | Bind MCP broker to Gateway |
| MCPServerRegistration | mcp.kuadrant.io/v1alpha1 | Register backend MCP server |
| HTTPRoute | gateway.networking.k8s.io | Route to backend server |
| AuthPolicy | kuadrant.io | Authentication (OAuth/API key) |
| RateLimitPolicy | kuadrant.io | Rate limiting |

## Documentation

- [Architecture guide](docs/architecture.md) — how charts, CRDs, operators, and traffic fit together
- [Red Hat Connectivity Link 1.4 - MCP Gateway](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/pdf/mcp_gateway/)
- [Installing MCP Gateway](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.3/html/installing_the_mcp_gateway/mcp-gateway-install)
- [Registering MCP Servers and Policies](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/registering_mcp_servers_and_creating_policies/)
- [OCP 4.22 - MCP Server + Gateway](https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/ai_applications/mcp-server)
- [Kuadrant/mcp-gateway (upstream)](https://github.com/Kuadrant/mcp-gateway)
- [containers/kubernetes-mcp-server](https://github.com/containers/kubernetes-mcp-server)
- [MCP Specification](https://spec.modelcontextprotocol.io/)

## Version Matrix

See [docs/versions.md](docs/versions.md) for the full component version table.
