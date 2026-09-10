# ADR-0002: Gateway Dual-Listener Design (mcp + mcps)

## Status

Accepted

## Context

The MCP Gateway chart must expose client traffic and register in-cluster MCP backends
(kubernetes-mcp-server) via `MCPServerRegistration`. On OpenShift 4.22 we use Gateway API
with `gatewayClassName: openshift-default` and the separate `mcp-gateway` OLM operator
(0.7.1, channel `preview`).

During deployment on sandbox5235 we observed `no valid gateways for httproute` when
backend HTTPRoutes used hostnames that did not match the public MCP listener. The
controller requires a dedicated internal listener with a wildcard hostname for backend
registration routes.

Documentation sources consulted:

- [RHCL 1.4 — Install MCP Gateway](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/install_the_mcp_gateway/mcp-gateway-install)
- [OCP 4.22 — Configuring Gateway API](https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/ingress_and_load_balancing/configuring-gateway-api)
- [Kuadrant — Configure MCP Gateway Listener and Route](https://github.com/Kuadrant/mcp-gateway/blob/main/docs/guides/configure-mcp-gateway-listener-and-router.md)
- [Kuadrant 1.5 — Register MCP Servers](https://docs.kuadrant.io/1.5.x/mcp-gateway/docs/guides/register-mcp-servers/)

Note: RHCL 1.4 Gateway examples use listener name `mcps` for MCP traffic while
`MCPGatewayExtension` examples use `sectionName: mcp`. The Kuadrant upstream docs
(bundled in RHCL) define the coherent dual-listener pattern below.

## Options Considered

### Option 1: Single listener (RHCL §1.2 simplified example)

One listener (e.g. `mcps`) with a real cluster hostname for all traffic.

- **Pros:** Simpler Gateway spec, matches abbreviated RHCL Gateway example.
- **Cons:** Backend HTTPRoutes need hostnames matching the public listener; conflicts
  with MCPServerRegistration discovery pattern; caused `no valid gateways for httproute`
  in our cluster.

### Option 2: Dual listeners `mcp` + `mcps` (Kuadrant upstream)

- **`mcp`**: public client traffic; targeted by `MCPGatewayExtension` (`sectionName: mcp`).
- **`mcps`**: internal backend routing with wildcard hostname (e.g. `*.mcp.local`);
  targeted by MCPServerRegistration HTTPRoutes (`sectionName: mcps`).

- **Pros:** Documented upstream prerequisite for server registration; separates public
  endpoint from internal backend discovery; validated working on OCP 4.22.
- **Cons:** Two listeners to maintain; RHCL 1.4 prose is inconsistent on naming.

### Option 3: Single HTTPS wildcard listener (Kuadrant HTTPS mode)

One `HTTPS` listener with wildcard hostname for both client and backend routes.

- **Pros:** Required for TLS-only production; Kuadrant documents SNI/filter-chain
  constraints for HTTPS.
- **Cons:** More complex TLS/certificate setup; not needed for initial HTTP POC.

## Decision

Use **Option 2** as the default chart configuration:

| Listener | Hostname | Port | Used by |
|----------|----------|------|---------|
| `mcp` | `mcp-gateway.<clusterDomain>` | 8080 (HTTP) or 443 (HTTPS) | MCPGatewayExtension, auto `mcp-gateway-route` |
| `mcps` | `*.mcp.local` | 8080 | MCPServerRegistration HTTPRoutes |

Additionally:

- `gatewayClassName: openshift-default` (required on OCP 4.22; GatewayClass created by
  operators chart).
- **HTTPS (Option A):** TLS on the `mcp` listener (`tls.enabled: true`, port 443,
  `certificateSecret`); no separate `https` listener. MCPGatewayExtension keeps
  `sectionName: mcp`.
- MCP CRDs use `apiVersion: mcp.kuadrant.io/v1alpha1` (operator 0.7.1).

## Consequences

### Positive

- MCPServerRegistration and broker config work as documented upstream.
- Chart aligns with Kuadrant register-mcp-servers prerequisites.
- HTTPS enabled on `mcp` listener without a second public listener or MCPGatewayExtension change.

### Negative

- Public DNS for `mcp-gateway.<clusterDomain>` still required for production clients
  (Gateway ELB address alone is not enough without DNS or Host header overrides).
- RHCL 1.4 Gateway examples may confuse readers until Red Hat aligns docs with upstream.
- HTTPS listener requires operators to supply a TLS Secret in the Gateway namespace when `tls.enabled: true`.

## References

- [RHCL 1.4 MCP Gateway Install](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/install_the_mcp_gateway/mcp-gateway-install)
- [Kuadrant configure-mcp-gateway-listener-and-router.md](https://github.com/Kuadrant/mcp-gateway/blob/main/docs/guides/configure-mcp-gateway-listener-and-router.md)
- [Kuadrant register-mcp-servers (1.5)](https://docs.kuadrant.io/1.5.x/mcp-gateway/docs/guides/register-mcp-servers/)
