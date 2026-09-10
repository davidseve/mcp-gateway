# ADR-0004: Authentication Strategy

## Status

Accepted

## Context

The MCP Gateway needs edge authentication to protect the public `/mcp` endpoint.
The MCP broker itself has no built-in auth — it delegates to the Gateway's Envoy
dataplane via Kuadrant `AuthPolicy`.

We need a strategy that:
- Works immediately for POC/development (no external IdP dependency)
- Has a clear upgrade path to production-grade OAuth/OIDC
- Integrates with OpenShift's existing identity infrastructure

## Options Considered

### Option 1: API key only

`AuthPolicy` with `apiKey` authentication. Keys stored as labeled Secrets
in the Gateway namespace. Clients send `Authorization: Bearer <key>`.

- **Pros:** Zero external dependencies; works immediately; simple to rotate
  (create/delete Secrets); sufficient for single-user or small-team POC.
- **Cons:** No identity information (all keys are equivalent); no token
  expiry or refresh; no per-user rate limiting or tool filtering without
  mapping keys to identities manually.

### Option 2: External IdP (Keycloak / RHSSO)

`AuthPolicy` with `jwt` authentication pointing to a Keycloak instance.
Clients obtain tokens via OAuth2 flows, gateway validates JWT signatures.

- **Pros:** Full OAuth2/OIDC support; per-user identity; `resource_access`
  roles enable tool-level filtering via wristband; standard protocol.
- **Cons:** Requires deploying and managing Keycloak; additional operational
  complexity for a learning project; overkill for POC phase.

### Option 3: OCP native OAuth server

`AuthPolicy` with `jwt` pointing to `oauth-openshift.apps.<cluster>` or
`kubernetesTokenReview` validating OCP ServiceAccount / user tokens.

- **Pros:** No external IdP — uses OpenShift's built-in OAuth server;
  tokens tied to OCP users/ServiceAccounts; natural for OCP-native workloads;
  `kubernetesTokenReview` validates tokens against the API server directly.
- **Cons:** Less portable (OCP-specific); OCP OAuth issuer quirks (custom
  JWKS endpoint); ServiceAccount tokens may not carry `resource_access`
  roles for MCP tool filtering without additional RBAC mapping.

## Decision

**Phase 4 (current):** Use **Option 1 — API key** as the default authentication method.

- Both `authPolicy.enabled` and `rateLimitPolicy.enabled` default to `true`.
- `when` predicate skips `/.well-known/*` paths (preparation for future OAuth).
- `make create-api-key` target automates Secret creation with proper labels.
- Rate limiting includes global (60 req/min) and burst (10 req/s) by default.

**Phase 5 (planned):** Evaluate **Option 3 — OCP native OAuth** as the production
upgrade path. Specifically:

- `jwt` with `issuerUrl` pointing to `oauth-openshift.apps.<cluster>`
- Or `kubernetesTokenReview` for ServiceAccount token validation
- Identity-based features (per-user rate limits, MCPVirtualServer tool filtering)
  become available once auth resolves to a named identity

Option 2 (external Keycloak) remains available but is not the default path for this
project since the cluster already provides an OAuth server.

## Consequences

### Positive

- API key auth works immediately with zero dependencies beyond the operator.
- `/.well-known` skip prepares the gateway for OAuth upgrade without breaking changes.
- Burst rate limiting protects the broker from rapid-fire clients even without
  per-identity counters.
- MCPVirtualServer scaffold is in place for discovery-level tool filtering.

### Negative

- API key mode provides no per-user identity — rate limiting is global only.
- Per-identity rate limiting (`counters: auth.identity.username`) requires auth
  that resolves to a named identity (Phase 5).
- Tool-level execution filtering (wristband + AuthPolicy authz) requires an IdP
  with `resource_access` roles — not achievable with API keys alone.

## References

- [Kuadrant AuthPolicy API](https://docs.kuadrant.io/1.5.x/kuadrant-operator/doc/reference/authpolicy/)
- [Kuadrant RateLimitPolicy API](https://docs.kuadrant.io/1.5.x/kuadrant-operator/doc/reference/ratelimitpolicy/)
- [MCPVirtualServer](https://docs.kuadrant.io/dev/mcp-gateway/docs/reference/mcpvirtualserver/)
- [User-based tool filter](https://docs.kuadrant.io/dev/mcp-gateway/docs/guides/user-based-tool-filter/)
- [OCP OAuth server](https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/authentication_and_authorization/)
