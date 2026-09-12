# System Architecture Document: Kubernetes Canary Silent Poisoning Investigation

## System Overview and Purpose

This system supports a high-throughput e-commerce checkout pipeline, orchestrating order creation, inventory validation, and payment processing through a microservices architecture deployed on Kubernetes. The platform employs progressive delivery (canary deployments via Flagger) to safely roll out new versions of critical services while minimizing customer impact. The primary goal is to maintain 99.95% availability for the checkout endpoint, with automated traffic shifting based on latency, error rate, and success metrics.

The architecture is designed for idempotency, retry resilience, and observability — yet the recent incident exposed a critical blind spot: a silent, connection-level gRPC bug in a canary deployment that bypassed all monitoring thresholds because the root cause service (inventory-service) never returned an error code, only delayed responses.

---

## Service Topology

### 1. **API Gateway (nginx-ingress + custom Lua plugin)**
- **Purpose**: Entry point for all external checkout requests. Enforces rate limiting, authentication, and request tracing.
- **Protocol**: HTTPS (TLS 1.3)
- **Key Behavior**: Returns 502 Bad Gateway when upstream (order-service) fails to respond within 5s timeout or returns non-2xx status.
- **Observability**: Logs all HTTP status codes, request IDs, client IPs, and upstream response times.

### 2. **Order-Service (gRPC client, Java/Spring Boot)**
- **Purpose**: Orchestrates checkout flow: validates cart, calls inventory-service, then payment-service.
- **Protocol**: gRPC to inventory-service (port 50051), REST to payment-service (port 8080)
- **Timeout Configuration**: 5000ms to inventory-service, 3000ms to payment-service
- **Retry Logic**: On gRPC deadline exceeded or 5xx responses, retries once with same idempotency key (for idempotent operations)
- **Key Behavior**: On receiving 409 Conflict from payment-service, misinterprets as transient failure → returns 502 to API Gateway.

### 3. **Inventory-Service (gRPC server, Go/Protobuf)**
- **Purpose**: Validates stock availability for SKUs. Stateless, cache-backed.
- **Protocol**: gRPC (port 50051)
- **Connection Pool**: Uses gRPC client connection pool with per-host keepalive settings.
- **Bug**: v2.1.4 introduced a faulty interceptor that, under rare race conditions, initializes a 100ms deadline (instead of 5000ms) on ~1-2% of new connections. All responses are still 200 OK with correct payload — just delayed beyond client timeout.
- **Observability**: Logs all requests as 200 OK. No latency outliers flagged in metrics. No errors logged.

### 4. **Payment-Service (REST, Node.js)**
- **Purpose**: Processes payments using idempotency keys to prevent duplicate charges.
- **Protocol**: REST (port 8080), HTTPS
- **Key Behavior**: Returns 409 Conflict when same idempotency key is reused within 15-minute window (correct, expected behavior).
- **Observability**: Logs 409s as “idempotency conflict” — not an error. Metrics show stable 0.1% 409 rate (baseline).

### 5. **Flagger (Canary Controller)**
- **Purpose**: Automated canary deployment engine. Controls traffic shifting from stable to canary version.
- **Analysis Criteria**:
  - HTTP error rate < 0.5%
  - p95 latency < 2000ms
  - Request volume stability
- **Monitoring Scope**: Only observes **inventory-service’s own HTTP error rate** (via Prometheus metrics endpoint `/metrics`). Does **not** observe downstream impact, gRPC deadline exceeded errors, or client-side timeouts.

### 6. **Observability Stack**
- **Tracing**: Jaeger (distributed tracing with B3 headers)
- **Metrics**: Prometheus + Grafana
  - `http_requests_total{status="502"}` — API Gateway
  - `grpc_client_handled_total{code="DeadlineExceeded"}` — Order-Service
  - `grpc_server_handled_total{code="OK"}` — Inventory-Service
  - `http_requests_total{status="409"}` — Payment-Service
- **Logs**: Loki + Grafana Loki (structured JSON logs)
- **Alerts**:
  - `API_Gateway_502_Rate > 0.5% for 5m`
  - `OrderService_Timeouts > 100/min for 2m`
  - `PaymentService_409_Rate > 0.5% for 5m` (baseline is 0.1%)

---

## Data/Request Flow Diagram (ASCII)

External Client
       |
       v
[API Gateway] ——(HTTPS)——> 502 on upstream failure
       |
       v
[Order-Service] ——(gRPC)——> [Inventory-Service v2.1.4 (canary)]
       |                         |
       | (5000ms timeout)        | (BUG: 1-2% conns use 100ms timeout)
       |                         | → Response delayed → gRPC DeadlineExceeded
       |                         |
       |← (DeadlineExceeded)←—(100ms timeout)———+
       |                                        |
       | (retry w/ same idempotency key)        |
       +———————————————→ [Payment-Service] ——(HTTP 409 Conflict)→
                                     |
                                     v
                          [Order-Service] → misinterprets 409 as failure
                                     |
                                     v
                          [API Gateway] → returns 502 to client

> **Note**: The bug is invisible to inventory-service logs and metrics. It only manifests as a client-side timeout in order-service, which triggers retries that cause 409s in payment-service — a legitimate, non-buggy behavior.

---

## Key Configuration Parameters

| Service | Parameter | Value | Meaning | Risk |
|--------|-----------|-------|---------|------|
| **Order-Service** | `inventory_service_timeout_ms` | 5000 | Max time to wait for inventory-service response | Too high for fast detection; masks upstream latency issues |
| **Order-Service** | `retry_enabled` | true | Enables one retry on gRPC DeadlineExceeded | Causes cascading 409s in payment-service |
| **Inventory-Service (v2.1.4)** | `grpc_keepalive_time_ms` | 10000 | gRPC keepalive interval | Unaffected |
| **Inventory-Service (v2.1.4)** | `grpc_client_deadline_ms` | **100** (bug) | **Incorrectly set on 1-2% of connections due to interceptor race** | Root cause — never logged as error |
| **Flagger** | `success_threshold` | 0.5% error rate | Canary promotion threshold | **Critical gap**: Only checks inventory-service’s own HTTP errors — ignores gRPC client-side timeouts |
| **Flagger** | `metrics_provider` | `prometheus` | Queries `/metrics` endpoint of inventory-service | **Missing**: No downstream metrics (e.g., order-service timeouts) |
| **Payment-Service** | `idempotency_window_s` | 900 (15m) | Time window to reject duplicate keys | Correct; not a bug |

---

## Monitoring and Alerting Setup (Including Gaps)

### ✅ Existing Monitoring

- **Service-Level Metrics**: All services expose Prometheus metrics (gRPC, HTTP codes, latency percentiles)
- **Distributed Tracing**: Full trace propagation via B3 headers; Jaeger can visualize end-to-end flow
- **Error Alerts**: Alerts on API Gateway 502s, Order-Service timeouts, Payment-Service 409s
- **Infrastructure**: CPU, memory, pod restarts, node health monitored

### ❌ Critical Gaps

| Gap | Impact |
|-----|--------|
| **Flagger only monitors inventory-service’s own HTTP error rate** | The bug never produces 5xx — only delayed 200s — so Flagger sees 0% error and promotes blindly |
| **No cross-service dependency metrics in Flagger** | No alerting on “inventory-service causing order-service timeouts” — even though this is the actual failure mode |
| **gRPC DeadlineExceeded not counted as “error” in inventory-service** | Inventory-service logs all as OK. gRPC error is client-side — not tracked on server |
| **No SLO for end-to-end checkout latency** | Only per-service SLOs exist. E2E checkout SLI (e.g., 99% < 4s) was never defined |
| **No anomaly detection on downstream error spikes** | Payment-service 409s increased from 0.1% → 0.8% — but no alert triggered because 409 is “expected” |
| **No correlation engine** | No automated system links order-service timeout spikes → payment-service 409 spikes → API Gateway 502 spikes → inventory-service rollout |

### Recommended Fixes
- Add Flagger custom metrics: `order_service_grpc_deadline_exceeded_count` (via service mesh or sidecar proxy)
- Define end-to-end SLO: “99.9% of checkout requests complete in < 4s”
- Introduce correlation alerts: “If inventory-service rollout coincides with order-service timeout spike + payment-service 409 spike → auto-pause deployment”
- Instrument gRPC server to log **client deadline exceeded** as a warning (even if response is 200)

---

## Recent Changes or Maintenance Windows

| Time (UTC) | Change | Owner | Notes |
|------------|--------|-------|-------|
| 13:30 | **inventory-service v2.1.4 canary deployed** | DevOps Team | Deployed via Flagger with 10% traffic. Release notes: “Optimized inventory cache warmup”. No mention of gRPC interceptor changes. |
| 13:30 | **Flagger analysis window configured** | SRE Team | Analysis window: 5m. Metrics: HTTP error rate only. No downstream metrics included. |
| 13:45 | **Flagger auto-promoted inventory-service to 100%** | Flagger (automated) | Passed all thresholds (0.0% error rate). No alerts triggered. |
| 13:40 | **Order-Service logging updated** | Dev Team | Added debug logging for gRPC deadlines — but only enabled in staging. Not in prod. |
| 13:20 | **Payment-Service idempotency window reduced from 20m → 15m** | Payment Team | Not related to incident. Baseline 409 rate increased slightly — but still within expected range. |

> **Note**: The root cause (100ms gRPC deadline) was introduced in v2.1.4 during refactoring of the gRPC interceptor chain. The bug only triggers under high connection churn and race conditions during connection pool initialization — making it undetectable in QA or manual testing.
