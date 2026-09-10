# AGENTS.md - MCP Gateway Learning Project

> Single source of truth for AI-assisted development on this project.
> Any AI tool (Cursor, Claude Code, etc.) working on this repo should read this file first.

@docs/versions.md
@README.md

## Project Overview

**Name**: MCP Gateway Learning Project
**Target Platform**: Red Hat OpenShift (4.17+)
**Product**: Red Hat Connectivity Link 1.4 (MCP Gateway - Technology Preview)
**Upstream**: [Kuadrant/mcp-gateway](https://github.com/Kuadrant/mcp-gateway) v0.9.0

**Objective**: Learn to deploy, configure, and manage the MCP Gateway on OpenShift,
using the kubernetes-mcp-server as a real backend to test authentication, authorization,
tool filtering, and rate limiting through the gateway.

## Architecture

```
AI Agents (Cursor, LangGraph, etc.)
        |
        | MCP over HTTP (streamable / stateless)
        v
┌─────────────────────────────┐
│  MCP Gateway (Envoy + Broker)│
│  - AuthPolicy               │
│  - RateLimitPolicy           │
└──────────┬──────────────────┘
           |  HTTPRoute + MCPServerRegistration (prefix: k8s_)
           v
┌─────────────────────────────┐
│  kubernetes-mcp-server       │
│  15 tools: pods, resources,  │
│  events, namespaces, helm... │
└─────────────────────────────┘
```

## Key CRDs

| CRD | API Group | Purpose |
|-----|-----------|---------|
| Gateway | gateway.networking.k8s.io | Envoy ingress listener |
| MCPGatewayExtension | mcp.kuadrant.io/v1alpha1 | Binds MCP broker to a Gateway |
| MCPServerRegistration | mcp.kuadrant.io/v1alpha1 | Registers backend MCP server |
| HTTPRoute | gateway.networking.k8s.io | Routes traffic to backend |
| AuthPolicy | kuadrant.io | Auth on gateway (OAuth/API key) |
| RateLimitPolicy | kuadrant.io | Rate limiting |

## Version Pinning Policy

All operators and components are deployed with explicit pinned versions.
See `docs/versions.md` for the full version matrix.

- Connectivity Link: **1.4**
- MCP Gateway (RHCL bundled): **0.7.0**
- MCPGatewayExtension / MCPServerRegistration API: **v1**
- kubernetes-mcp-server Helm chart: **0.1.0** (OCI: `ghcr.io/containers/charts/kubernetes-mcp-server`)

## Quick Commands

```bash
make help                     # Show all targets
make deploy-operators         # Install Connectivity Link operator
make deploy-k8s-mcp-server    # Deploy kubernetes-mcp-server
make deploy-gateway           # Deploy Gateway + MCPGatewayExtension
make deploy-mcp-servers       # Register MCP servers in gateway
make deploy-policies          # Deploy AuthPolicy + RateLimitPolicy
make deploy-all               # Full stack deploy
make test                     # Run all tests
make test-k8s-mcp-direct      # Test k8s-mcp-server directly
make test-tools-list          # Test tools/list through gateway
make test-auth                # Test auth policies
make undeploy-all             # Tear down everything
make lint                     # Helm lint all charts
```

## Project Structure

```
charts/
  operators/          - Connectivity Link Subscription + OperatorGroup
  kubernetes-mcp-server/ - Wrapper chart for upstream k8s-mcp-server
  gateway/            - Gateway + MCPGatewayExtension
  mcp-servers/        - MCPServerRegistration + HTTPRoute
  policies/           - AuthPolicy + RateLimitPolicy
tests/                - pytest: health, tools/list, auth policies
docs/
  architecture.md     - End-to-end architecture guide (charts, CRDs, traffic flows)
  adr/                - Architecture Decision Records
  versions.md         - Component version matrix
  ROADMAP.md          - Learning phases
scripts/
  lib/agent-run.sh    - Long-running script wrapper
```

## Critical Patterns

- **Helm-first**: All resources deployed via Helm charts for iteration
- **No hardcoded namespaces**: Use `{{ .Release.Namespace }}` in templates
- **Version pinning**: Explicit versions in Chart.yaml dependencies and values.yaml
- **Idempotent tests**: Tests can re-run after cluster reinstall
- **ADRs for decisions**: Document architecture choices in `docs/adr/`

## Long-Running Scripts

For deploys and validates that take >30s, use `scripts/lib/agent-run.sh`:
- `make deploy-quiet` wraps deploy in agent-run.sh
- `make validate-smoke` runs quick health checks
- Check `.agent-status/` for JSON status files
- Check `.logs/` for full output logs

## References

- [Connectivity Link 1.4 - MCP Gateway](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/pdf/mcp_gateway/)
- [Installing MCP Gateway](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.3/html/installing_the_mcp_gateway/mcp-gateway-install)
- [Registering MCP Servers](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/registering_mcp_servers_and_creating_policies/)
- [OCP 4.22 MCP Server + Gateway](https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/ai_applications/mcp-server)
- [Kuadrant/mcp-gateway GitHub](https://github.com/Kuadrant/mcp-gateway)
- [kubernetes-mcp-server GitHub](https://github.com/containers/kubernetes-mcp-server)
