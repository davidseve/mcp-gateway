# MCP Gateway Architecture Guide

> **Purpose:** End-to-end reference for how this project wires Red Hat Connectivity Link,
> the MCP Gateway operator, Gateway API, and Kuadrant policies together. Read this when
> returning to the project after a break and you need to remember what each chart does,
> what the operators create, and how traffic flows.

**Related docs:** [ADR-0001](adr/0001-connectivity-link-vs-upstream.md) (RHCL vs upstream),
[ADR-0002](adr/0002-gateway-dual-listener-design.md) (dual listeners),
[ADR-0003](adr/0003-gateway-exposure-strategy.md) (Route vs LoadBalancer),
[ADR-0004](adr/0004-auth-strategy.md) (auth strategy),
[versions.md](versions.md) (pinned component versions).

---



## 1. Big picture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  AI clients (Cursor, LangGraph, curl, …)                                    │
│  POST https://mcp-gateway.apps.<cluster>/mcp                                │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                    ┌───────────────▼────────────────┐
                    │  OpenShift Route (optional)     │  charts/gateway (route mode)
                    │  passthrough TLS → Gateway Svc  │
                    └───────────────┬────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────────────┐
│  Gateway API: Gateway "mcp-gateway" (Envoy dataplane)                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Listener "mcp"  — public MCP clients (HTTPS or HTTP)               │    │
│  │    ← AuthPolicy / RateLimitPolicy (charts/policies, optional)       │    │
│  │    ← HTTPRoute "mcp-gateway-route" (auto, by operator)              │    │
│  │    → Service "mcp-gateway" (broker)                                 │    │
│  ├─────────────────────────────────────────────────────────────────────┤    │
│  │  Listener "mcps" — internal backend routing (*.mcp.local)           │    │
│  │    ← HTTPRoute "kubernetes-mcp-server-route" (charts/mcp-servers)   │    │
│  │    → Service "kubernetes-mcp-server"                                │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                    ┌───────────────▼────────────────┐
                    │  MCP Broker (Deployment)        │  created by MCP Gateway operator
                    │  - federates tools with prefix  │  when MCPGatewayExtension is Ready
                    │  - routes tools/call internally │
                    └───────────────┬────────────────┘
                                    │
                    ┌───────────────▼────────────────┐
                    │  kubernetes-mcp-server          │  charts/kubernetes-mcp-server
                    │  tools exposed as k8s_*       │
                    └────────────────────────────────┘
```

**Mental model:** Helm charts declare *intent* (CRs). Operators and Gateway controllers
*reconcile* that intent into Envoy config, broker config, and running pods.

---



## 2. Deploy order


| Step | Make target                    | Chart                          | Namespace (default)     | What it installs                                   |
| ---- | ------------------------------ | ------------------------------ | ----------------------- | -------------------------------------------------- |
| 1    | `deploy-operators`             | `charts/operators`             | `connectivity-link`     | OLM Subscription, OperatorGroup, GatewayClass      |
| 2    | `deploy-k8s-mcp-server`        | `charts/kubernetes-mcp-server` | `kubernetes-mcp-server` | Backend MCP server (pods + Service)                |
| 3    | `deploy-gateway`               | `charts/gateway`               | `gateway-system`        | Gateway, MCPGatewayExtension, Route (route mode)   |
| 4    | `deploy-mcp-servers`           | `charts/mcp-servers`           | `gateway-system`        | HTTPRoute + MCPServerRegistration + ReferenceGrant |
| 5    | `deploy-policies` *(optional)* | `charts/policies`              | `gateway-system`        | AuthPolicy + RateLimitPolicy                       |


`make deploy-all` runs steps 1–4 only. Policies are a separate step because they are
disabled by default and require API key Secrets.

---



## 3. Chart-by-chart breakdown



### 3.1 `charts/operators` — platform foundation

Installs Connectivity Link via OLM. This brings:

- **MCP Gateway controller** — watches `MCPGatewayExtension` and `MCPServerRegistration`
- **Kuadrant policy controllers** — watches `AuthPolicy`, `RateLimitPolicy`, etc.
- **GatewayClass** `openshift-default` — required for Gateway API on OCP 4.22+

Nothing MCP-specific runs until step 3 (`deploy-gateway`).

---



### 3.2 `charts/gateway` — public entry point + broker binding



#### Objects created directly by Helm


| Resource              | Template                     | Purpose                                                               |
| --------------------- | ---------------------------- | --------------------------------------------------------------------- |
| `Gateway`             | `gateway.yaml`               | Two listeners: `mcp` (public) and `mcps` (internal)                   |
| `MCPGatewayExtension` | `mcp-gateway-extension.yaml` | Tells the MCP operator to attach to listener `mcp`                    |
| `Route`               | `route.yaml`                 | Only when `exposure.mode=route` (default)                             |




#### MCPGatewayExtension spec (the binding contract)

```yaml
spec:
  targetRef:
    kind: Gateway
    name: mcp-gateway
    sectionName: mcp          # must match a listener name on the Gateway
  httpRouteManagement: Enabled  # operator creates HTTPRoute automatically
```



#### Objects created by the MCP Gateway operator (not in Helm)

When `MCPGatewayExtension` becomes **Ready**, the controller reconciles:


| Object           | Typical name         | Purpose                                              |
| ---------------- | -------------------- | ---------------------------------------------------- |
| `Deployment`     | `mcp-gateway`        | MCP broker/router pods                               |
| `Service`        | `mcp-gateway`        | Broker endpoint (port 8080)                          |
| `ServiceAccount` | —                    | For broker pods                                      |
| `HTTPRoute`      | `mcp-gateway-route`  | Routes `/mcp` on listener `mcp` → broker Service     |
| `EnvoyFilter`    | —                    | Configures Envoy external processor for MCP protocol |
| `Secret`         | `mcp-gateway-config` | Broker config; updated when servers are registered   |


With `httpRouteManagement: Disabled`, you manage the public HTTPRoute yourself (e.g. for
CORS or OAuth `.well-known` endpoints).

#### Dual listeners (why two?)

See [ADR-0002](adr/0002-gateway-dual-listener-design.md) for the full rationale.


| Listener | Hostname (default)           | Port                                | Who uses it                                              |
| -------- | ---------------------------- | ----------------------------------- | -------------------------------------------------------- |
| `mcp`    | `mcp-gateway.apps.<cluster>` | 443 HTTPS (route mode) or 8080 HTTP | Clients, `MCPGatewayExtension`, auto `mcp-gateway-route` |
| `mcps`   | `*.mcp.local`                | 8080 HTTP                           | Backend `HTTPRoute`s from `charts/mcp-servers`           |


**Why:** Public hostname and internal wildcard hostname serve different roles. Backend
HTTPRoutes must attach to `mcps` with `*.mcp.local` hostnames. Putting them on the public
listener caused `no valid gateways for httproute` in our OCP 4.22 testing.

#### External exposure

See [ADR-0003](adr/0003-gateway-exposure-strategy.md).


| Mode                | `GATEWAY_EXPOSURE` | How clients reach the Gateway                                                   |
| ------------------- | ------------------ | ------------------------------------------------------------------------------- |
| **Route** (default) | `route`            | OpenShift Route → ClusterIP Gateway Service; DNS via `*.apps.<domain>` wildcard |
| **LoadBalancer**    | `loadbalancer`     | Dedicated Gateway ELB; requires DNSPolicy or manual CNAME                       |


Route mode syncs `ingress-certs` from `openshift-ingress` (`make sync-wildcard-tls`) so
the Gateway listener can terminate TLS with the cluster wildcard cert.

---



### 3.3 `charts/mcp-servers` — register backends

For each entry in `values.yaml` → `servers`, Helm creates:


| Resource                | Example name                             | Namespace                                                           |
| ----------------------- | ---------------------------------------- | ------------------------------------------------------------------- |
| `HTTPRoute`             | `kubernetes-mcp-server-route`            | `gateway-system`                                                    |
| `MCPServerRegistration` | `kubernetes-mcp-server`                  | `gateway-system`                                                    |
| `ReferenceGrant`        | `allow-gateway-to-kubernetes-mcp-server` | `kubernetes-mcp-server` *(only if Service is in another namespace)* |




#### HTTPRoute (internal path to backend)

```yaml
spec:
  hostnames:
    - kubernetes-mcp-server.mcp.local   # must match mcps wildcard (*.mcp.local)
  parentRefs:
    - kind: Gateway
      name: mcp-gateway
      sectionName: mcps                # internal listener, NOT "mcp"
  rules:
    - matches:
        - path: { type: PathPrefix, value: /mcp }
      backendRefs:
        - name: kubernetes-mcp-server
          namespace: kubernetes-mcp-server
          port: 8080
```



#### MCPServerRegistration (federation contract)

```yaml
spec:
  prefix: "k8s_"
  path: "/mcp"
  targetRef:
    kind: HTTPRoute
    name: kubernetes-mcp-server-route
```

The operator reads the HTTPRoute, discovers the backend Service, and writes an entry
into `mcp-gateway-config`. The broker then:

1. Connects to the upstream via internal routing (`kubernetes-mcp-server.mcp.local`)
2. Runs `initialize` + `tools/list` asynchronously
3. Exposes tools to clients as `k8s_<original_tool_name>`



#### What the operator does (not Helm)


| Effect                              | Detail                                       |
| ----------------------------------- | -------------------------------------------- |
| Updates `mcp-gateway-config` Secret | Adds upstream hostname, prefix, path         |
| Broker reload                       | Starts/updates `MCPManager` for the upstream |
| Tool federation                     | Prefixes tool names (`k8s_pods_list`, etc.)  |


**Prerequisite:** `MCPGatewayExtension` must be **Ready** in the same Gateway namespace.
Without it, `MCPServerRegistration` stays `NotReady`.

#### Gateway controller effect (not a new CR)

The Gateway API controller programs Envoy on listener `mcps` so traffic to
`kubernetes-mcp-server.mcp.local/mcp` reaches the backend Service.

---



### 3.4 `charts/policies` — edge auth, rate limiting, and tool filtering

Policies attach to the **Gateway** CR, not to HTTPRoutes or MCP CRs. Kuadrant programs
Envoy filters at the gateway edge.

#### Objects created by Helm

| Resource          | Default         | What it does                                                                                        |
| ----------------- | --------------- | --------------------------------------------------------------------------------------------------- |
| `AuthPolicy`      | `enabled: true` | Requires `Authorization: Bearer <api-key>`; keys from Secrets labeled `mcp.kuadrant.io/secret=true` |
| `RateLimitPolicy` | `enabled: true` | Global (60 req/min) + burst (10 req/s); optional per-identity counters                              |
| `MCPVirtualServer` | `virtualServers: []` | Curated tool subsets; clients select via `X-Mcp-Virtualserver` header                          |

#### AuthPolicy

```yaml
spec:
  defaults:
    when:
      - predicate: "!request.path.contains('/.well-known')"  # OAuth discovery prep
    rules:
      authentication:
        api-key:
          apiKey:
            selector:
              matchLabels:
                mcp.kuadrant.io/secret: "true"
          credentials:
            authorizationHeader:
              prefix: Bearer
```

The `when` predicate skips `/.well-known/*` paths so future OAuth discovery endpoints
work without auth. API keys are stored in Secrets with label `mcp.kuadrant.io/secret=true`.

**Important:** The chart does **not** create API key Secrets. Create them with:

```bash
make create-api-key MCP_API_KEY_VALUE=your-secret-key
```

#### RateLimitPolicy

Three independent limits (first to trip returns 429):

| Limit | Default | Purpose |
|-------|---------|---------|
| `global` | 60 req/min | Shared across all clients |
| `burst` | 10 req/s (enabled) | Prevents rapid-fire saturation |
| `per-identity` | 30 req/min (disabled) | Per-user quota via `auth.identity.username`; requires auth that resolves to a named identity |

#### MCPVirtualServer (discovery-level tool filtering)

Creates curated "views" of the tool catalog. Clients request a view via header:

```
X-Mcp-Virtualserver: gateway-system/k8s-readonly
```

The broker returns only the tools listed in that virtual server's `spec.tools[]`.

**Limitation:** Filters `tools/list` (discovery) only. Does **not** block `tools/call`
(execution). For execution-level filtering, combine with AuthPolicy wristband + IdP
roles (Phase 5 — see [ROADMAP](ROADMAP.md)).

**Phase 5 planned:** OAuth via OCP native OAuth server (`oauth-openshift`), per-identity
rate limiting, and identity-based tool filtering with wristband headers. See
[ADR-0004](adr/0004-auth-strategy.md).

---



## 4. Traffic flows



### 4.1 Client `initialize` (no tools yet)

```
Client
  → Route (if route mode) / ELB (if loadbalancer)
  → Gateway listener "mcp"
  → [AuthPolicy] [RateLimitPolicy]  (if enabled)
  → HTTPRoute "mcp-gateway-route"
  → Service "mcp-gateway" (broker)
  → broker responds with gateway capabilities
```



### 4.2 Client `tools/list` (federated backends)

```
Client → listener "mcp" → broker
  broker aggregates cached tools from all Ready MCPServerRegistrations
  returns tools prefixed with k8s_, myserver_, etc.
```



### 4.3 Client `tools/call` (e.g. `k8s_pods_list`)

```
Client → listener "mcp" → broker
  broker strips prefix "k8s_"
  broker re-routes internally: changes :authority to kubernetes-mcp-server.mcp.local
  → listener "mcps"
  → HTTPRoute "kubernetes-mcp-server-route"
  → Service kubernetes-mcp-server:8080
  → MCP server executes tool
  → response returns through broker to client
```

Clients **never** call `*.mcp.local` directly. That hostname exists only for internal
Envoy routing between broker and backends.

---



## 5. Complete object inventory



### Created by Helm (this repo)


| Chart                   | Kubernetes objects                                                           |
| ----------------------- | ---------------------------------------------------------------------------- |
| `operators`             | Subscription, OperatorGroup, GatewayClass                                    |
| `kubernetes-mcp-server` | Deployment, Service, RBAC, etc. (upstream chart)                             |
| `gateway`               | Gateway, MCPGatewayExtension, Route *(route mode)* |
| `mcp-servers`           | HTTPRoute, MCPServerRegistration, ReferenceGrant *(cross-ns)*                |
| `policies`              | AuthPolicy, RateLimitPolicy, MCPVirtualServer *(if configured)*              |




### Created by operators / controllers (not in Helm)


| Controller                                      | Objects / effects                                                                                            |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| MCP Gateway operator                            | Deployment, Service, ServiceAccount, HTTPRoute `mcp-gateway-route`, EnvoyFilter, Secret `mcp-gateway-config` |
| MCP Gateway operator (on MCPServerRegistration) | Updates `mcp-gateway-config`; broker discovers upstreams                                                     |
| Gateway API (openshift-default)                 | Envoy route programming for accepted HTTPRoutes                                                              |
| Kuadrant (AuthPolicy / RateLimitPolicy)         | Envoy WASM filters for auth and rate limiting                                                                |


---



## 6. Key CRDs quick reference


| CRD                     | API group                   | Created by         | Points to                          |
| ----------------------- | --------------------------- | ------------------ | ---------------------------------- |
| `Gateway`               | `gateway.networking.k8s.io` | Helm `gateway`     | Listeners `mcp` + `mcps`           |
| `MCPGatewayExtension`   | `mcp.kuadrant.io/v1alpha1`  | Helm `gateway`     | Gateway listener `mcp`             |
| `MCPServerRegistration` | `mcp.kuadrant.io/v1alpha1`  | Helm `mcp-servers` | HTTPRoute to backend               |
| `HTTPRoute`             | `gateway.networking.k8s.io` | Helm + operator    | Gateway listener + backend Service |
| `AuthPolicy`            | `kuadrant.io`               | Helm `policies`    | Gateway                            |
| `RateLimitPolicy`       | `kuadrant.io`               | Helm `policies`    | Gateway                            |
| `MCPVirtualServer`      | `mcp.kuadrant.io/v1alpha1`  | Helm `policies`    | Curated tool subset (discovery)    |
| `ReferenceGrant`        | `gateway.networking.k8s.io` | Helm `mcp-servers` | Cross-namespace Service refs       |


---



## 7. Verification checklist

After a full deploy, run these commands to confirm each layer:

```bash
# Operators
oc get subscription -n connectivity-link
oc get gatewayclass openshift-default

# Gateway + extension
oc get gateway mcp-gateway -n gateway-system
oc get mcpgatewayextension -n gateway-system
oc get route mcp-gateway -n gateway-system          # route mode only

# Operator-managed resources
oc get httproute mcp-gateway-route -n gateway-system
oc get deploy,svc mcp-gateway -n gateway-system
oc get secret mcp-gateway-config -n gateway-system

# Backend registration
oc get mcpserverregistration -n gateway-system
oc get httproute kubernetes-mcp-server-route -n gateway-system
oc describe mcpserverregistration kubernetes-mcp-server -n gateway-system

# Policies (if deployed)
oc get authpolicy,ratelimitpolicy -n gateway-system

# Functional tests
make test
make test-auth    # requires AuthPolicy + MCP_API_KEY
```



### Smoke test (manual)

```bash
# Initialize (capture session ID from response headers)
curl -sD /tmp/h -X POST "$GATEWAY_URL/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'

SESSION=$(grep -i mcp-session-id /tmp/h | awk '{print $2}' | tr -d '\r')

# List federated tools
curl -s -X POST "$GATEWAY_URL/mcp" \
  -H "Content-Type: application/json" \
  -H "mcp-session-id: $SESSION" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
```

Expect tools prefixed with `k8s_` when `kubernetes-mcp-server` is registered.

---



## 8. Troubleshooting


| Symptom                                     | Likely cause                                       | Check                                                                             |
| ------------------------------------------- | -------------------------------------------------- | --------------------------------------------------------------------------------- |
| `MCPServerRegistration` NotReady            | No Ready `MCPGatewayExtension`                     | `oc get mcpgatewayextension -n gateway-system`                                    |
| HTTPRoute `no valid gateways for httproute` | Backend route on wrong listener/hostname           | HTTPRoute must use `sectionName: mcps` and `*.mcp.local` hostname                 |
| No `mcp-gateway-route`                      | Extension not Ready or operator missing            | Operator pods, extension status                                                   |
| Client gets wrong host / connection refused | DNS points to ingress router, not Gateway          | Use route mode or fix ELB DNS ([ADR-0003](adr/0003-gateway-exposure-strategy.md)) |
| `tools/list` empty                          | Backend not registered or broker still discovering | MCPServerRegistration Ready + broker logs                                         |
| 401 on all requests                         | AuthPolicy enabled without API key Secret          | Create Secret with label `mcp.kuadrant.io/secret=true`                            |
| Cross-namespace backend fails               | Missing ReferenceGrant                             | `oc get referencegrant -n <backend-ns>`                                           |


---



## 9. Namespaces (defaults)


| Namespace               | Contents                                                             |
| ----------------------- | -------------------------------------------------------------------- |
| `connectivity-link`     | OLM operator install                                                 |
| `gateway-system`        | Gateway, MCPGatewayExtension, broker, registrations, policies, Route |
| `kubernetes-mcp-server` | Backend MCP server + ReferenceGrant                                  |
| `openshift-ingress`     | Source of `ingress-certs` wildcard (route mode)                      |


---



## 10. Further reading

- [Kuadrant — Configure MCP Gateway Listener and Route](https://github.com/Kuadrant/mcp-gateway/blob/main/docs/guides/configure-mcp-gateway-listener-and-router.md)
- [Kuadrant — Register MCP Servers](https://docs.kuadrant.io/1.5.x/mcp-gateway/docs/guides/register-mcp-servers/)
- [RHCL 1.4 — MCP Gateway Install](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/install_the_mcp_gateway/mcp-gateway-install)
- [RHCL — Registering MCP Servers and Policies](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/registering_mcp_servers_and_creating_policies/)
- [OCP 4.22 — MCP Server + Gateway](https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/ai_applications/mcp-server)

