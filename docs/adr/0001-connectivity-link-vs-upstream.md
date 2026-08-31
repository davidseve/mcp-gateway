# ADR-0001: Red Hat Connectivity Link vs Upstream Kuadrant Install

## Status

Accepted

## Context

We need to deploy the MCP Gateway on OpenShift for learning purposes. There are two
paths to install it:

1. **Red Hat Connectivity Link 1.4** -- the productized operator available via OLM
   on OpenShift, which bundles MCP Gateway 0.7.0 as a Technology Preview feature.
2. **Upstream Kuadrant/mcp-gateway** -- the open-source project (currently at v0.9.0)
   installable via `kubectl apply -k` on any Kubernetes cluster.

Key considerations:
- This is a learning project targeting OpenShift (Red Hat sandbox clusters).
- We want to use the same stack that Red Hat customers would use in production.
- We need Auth/Rate Limiting integration, which comes naturally with Connectivity Link.
- The upstream has newer features (0.9.0 vs 0.7.0 bundled) but less OCP integration.

## Options Considered

### Option 1: Red Hat Connectivity Link 1.4 (OLM)
- **Pros:** Productized operator, OLM lifecycle, integrated with Kuadrant policies
  (AuthPolicy, RateLimitPolicy), matches what Red Hat customers use, OCP docs available.
- **Cons:** Bundles MCP Gateway 0.7.0 (not latest 0.9.0), Technology Preview only,
  requires OpenShift (not portable to vanilla K8s).

### Option 2: Upstream Kuadrant/mcp-gateway (kubectl)
- **Pros:** Latest features (v0.9.0, MCP 2026-07-28 protocol), portable to any K8s,
  faster iteration on upstream fixes.
- **Cons:** No OLM lifecycle management, manual policy setup, no Red Hat support,
  diverges from the productized experience we want to learn.

## Decision

Use **Red Hat Connectivity Link 1.4** (Option 1) as the primary deployment path.

This aligns with the project's goal of learning the productized MCP Gateway experience.
The v1 API (MCPGatewayExtension, MCPServerRegistration) is the same between RHCL 1.4
and upstream, so charts are portable if we later want to test with upstream.

## Consequences

### Positive
- Charts and patterns match what Red Hat customers use
- Kuadrant policies (Auth, RateLimit) work out of the box
- OLM handles operator lifecycle

### Negative
- Limited to MCP Gateway 0.7.0 features (no 2026-07-28 protocol yet)
- Technology Preview: possible API changes in future RHCL releases

### Neutral
- CRD API is v1 in both; migration to upstream for advanced testing is straightforward

## References

- [RHCL 1.4 Release Notes](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/release_notes/rhcl-release-notes)
- [Installing MCP Gateway (RHCL)](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.3/html/installing_the_mcp_gateway/mcp-gateway-install)
- [Kuadrant/mcp-gateway GitHub](https://github.com/Kuadrant/mcp-gateway)
- [MCP Gateway 0.8 Release Blog](https://kuadrant.io/blog/mcp-gateway-0.8/)
