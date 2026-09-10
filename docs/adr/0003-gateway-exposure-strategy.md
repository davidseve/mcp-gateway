# ADR-0003: Gateway External Exposure Strategy

## Status

Accepted

## Context

On OCP/AWS, hostnames under `*.apps.<clusterDomain>` resolve automatically via the
cluster ingress operator (Route53 wildcard). However, a Gateway API resource with
`gatewayClassName: openshift-default` creates a **separate LoadBalancer Service** with
its own ELB by default. Traffic to `mcp-gateway.apps.<cluster>` therefore hits the
**ingress router**, not the MCP Gateway — unless DNS is updated or a different
exposure pattern is used.

The [rhoai-platform-ops MaaS module](https://github.com/davidseve/rhoai-platform-ops)
solves this with **OpenShift Route + ClusterIP Gateway Service + wildcard cert**
(`ingress-certs`), not with RHCL `DNSPolicy`.

During Phase 3.1 we initially used LoadBalancer + cert-manager `Certificate`, which
required `GATEWAY_RESOLVE_IP` workarounds in tests because public DNS pointed to the
wrong ELB.

## Options Considered

### Option 1: Route + ClusterIP (MaaS pattern) — **default**

- Gateway annotated with `networking.istio.io/service-type: ClusterIP`
- OpenShift `Route` (passthrough TLS) to `{gateway}-{gatewayClass}` Service
- Gateway listener TLS uses `ingress-certs` (wildcard `*.apps.<domain>`) copied from
  `openshift-ingress`
- External URL: `https://mcp-gateway.apps.<cluster>/mcp` — DNS automatic

- **Pros:** No Route53 manual CNAME; reuses cluster Let's Encrypt wildcard; matches
  MaaS/RHOAI operational pattern; tests work without DNS hacks.
- **Cons:** Traffic passes through ingress router; passthrough requires cert sync to
  gateway namespace; not a dedicated public ELB for the Gateway.

### Option 2: LoadBalancer + DNSPolicy (Phase 3.2)

- Gateway Service type LoadBalancer (dedicated ELB)
- TLS via cert-manager `Certificate` (per-hostname Let's Encrypt)
- RHCL `DNSPolicy` creates Route53 CNAME to Gateway ELB

- **Pros:** Direct ELB exposure; cloud-native Gateway API ingress; no router hop.
- **Cons:** Requires Route53 IAM beyond cert-manager ACME scope on OpenTLC; more moving
  parts; manual CNAME fallback if DNSPolicy unavailable.

### Option 3: Hybrid (deferred — not planned)

Route for external clients **and** LoadBalancer ELB kept active simultaneously.

- **Pros:** Friendly URL via Route plus direct ELB for integrations that bypass router.
- **Cons:** Two entry points, two TLS paths, duplicate monitoring; easy to misconfigure
  DNS/certs; no clear benefit for this learning project unless a consumer explicitly
  requires a dedicated ELB while keeping `*.apps` URL.

## Decision

Use **Option 1 (Route + ClusterIP)** as the default (`exposure.mode: route`).

Implement **Option 2** as an optional `exposure.mode: loadbalancer` for Phase 3.2
(DNSPolicy evaluation + cert-manager).

Do **not** implement Option 3 unless a concrete requirement emerges.

## Consequences

### Positive

- `make deploy-gateway` and `make test` work on OpenTLC/AWS without manual DNS.
- Aligns with team knowledge from rhoai-platform-ops MaaS deployments.
- Chart values `exposure.mode` makes the trade-off explicit.

### Negative

- `sync-wildcard-tls` Makefile step copies `ingress-certs` on each deploy (imperative).
- Bare-metal clusters may use `router-certs-default` instead of `ingress-certs`
  (document platform-specific secret name).
- LoadBalancer mode remains for advanced/cloud-native scenarios but is not default.

## References

- [MaaS Gateway and Route](https://github.com/davidseve/rhoai-platform-ops/blob/main/modules/maas/docs/GATEWAY-AND-ROUTE.md)
- [RHCL DNSPolicy](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/deploying_red_hat_connectivity_link/rhcl-config-deploy-gateway-policies)
- ADR-0002 (dual-listener design)
