# Past Incidents for RCA Comparison

## 1. Related Incident: gRPC Load Balancer Stickiness After Service Mesh Upgrade (2023-08-17)

**Date**: 2023-08-17
**Severity**: P1 (1.1% checkout failure rate, 22k affected users)
**Symptoms**:
- API gateway: 1.0–1.2% 502 errors on `/checkout`
- Order-service: Elevated latency (p99 jumped from 200ms to 1.8s) when calling inventory-service
- Inventory-service: CPU on 1 of 8 pods at 95%, other 7 pods at 15%
- Payment-service: Timeout-induced retries (not 409 conflicts)
- Canary analysis passed (aggregate error rate: 0.3%)

**Root Cause**:
A service mesh upgrade (Istio 1.17 → 1.18) changed the default gRPC load balancing policy from `round_robin` to `pick_first` for HTTP/2 connections. Because gRPC multiplexes requests over a single HTTP/2 connection, all requests from order-service were pinned to one inventory-service pod. That pod became saturated, causing slow responses and upstream timeouts. Other pods appeared idle.

**Resolution**:
- Rolled back Istio to 1.17
- Configured explicit `round_robin` LB policy for gRPC services
- Added per-pod request rate monitoring (not just aggregate)
- Updated canary analysis to include per-pod load distribution variance

**Lessons Learned**:
> Service mesh upgrades can silently change load balancing semantics for gRPC. Unlike deadline or timeout bugs, stickiness causes *latency spikes* (not hard timeouts at a fixed value) and affects specific pods (not random connections). Check per-pod metrics, not just aggregates. No 409 conflicts occur because requests eventually succeed — they're just slow.

---

## 2. Red Herring: Database Connection Leak in Order-Service (2023-05-12)

**Date**: 2023-05-12
**Severity**: P1 (1.2% 503 errors)
**Symptoms**:
- API gateway: 503 errors on `/checkout`
- Order-service: Increasing connection pool exhaustion, high GC pressure
- Inventory-service: Normal latency, 0% errors
- Payment-service: No 409 spikes
- Database alerts: Too many connections from order-service

**Root Cause**:
Order-service v1.8.3 had a memory leak in its database connection pool due to unreturned `sql.Rows` objects. After ~4 hours, connection exhaustion caused new requests to time out (30s), resulting in 503s to gateway.

**Resolution**:
- Rolled back order-service
- Fixed connection leak with proper `defer rows.Close()`
- Added connection pool metrics to Prometheus (active/inactive connections)

**Why it’s a red herring**:
Symptoms looked similar (5xx errors, degraded checkout), but root cause was internal to order-service, not downstream. Payment-service was unaffected. No 409 conflicts. Inventory-service was not involved. Canary system was not in play.

---

## 3. Red Herring: Network Partition Between Order-Service and Inventory-Service (2023-02-03)

**Date**: 2023-02-03
**Severity**: P1 (2.1% 504 gateway timeouts)
**Symptoms**:
- API gateway: 504 timeouts on /checkout
- Order-service: gRPC connection refused / connection reset errors
- Inventory-service: 100% 200 OK, but latency spiked to 8s (due to packet loss)
- Network team observed 3% packet loss between order-service and inventory-service pods in Zone B
- No 409s in payment-service

**Root Cause**:
A misconfigured network policy in K8s allowed egress from order-service but blocked return traffic from inventory-service in one availability zone. gRPC connections were established but responses dropped.

**Resolution**:
- Fixed network policy to allow bidirectional traffic on gRPC port
- Added network latency and packet loss alerts per pod pair
- Implemented service mesh (Istio) with mTLS and traffic mirroring

**Why it’s a red herring**:
Symptoms included timeouts and 5xx errors, but root cause was infrastructure (network), not application logic. No 409 conflicts occurred because payment-service was never reached. Inventory-service had no bugs — it was just unreachable. Canary promotion was unrelated.

---

## 4. Red Herring: Idempotency Key Collision Due to Clock Skew (2022-11-09)

**Date**: 2022-11-09
**Severity**: P2 (0.4% 409 conflicts, 0.2% 502s)
**Symptoms**:
- Payment-service: 409 Conflict spikes on idempotency keys
- Order-service: Retried requests, then returned 502
- Inventory-service: 100% 200 OK
- No canary deployment occurred
- Time stamps on idempotency keys showed 2–5s differences between services

**Root Cause**:
NTP was misconfigured on 3 order-service nodes in one cluster. Clock skew caused idempotency keys (based on timestamp + UUID) to be generated with timestamps that appeared “in the past” to payment-service, which rejected them as duplicates.

**Resolution**:
- Fixed NTP sync on all nodes
- Changed idempotency key generation to use UUIDv7 (time-ordered) + server-side clock validation
- Added clock skew alerting across services

**Why it’s a red herring**:
409 conflicts were real (not caused by retries from timeouts), but the root cause was clock drift, not connection pooling. The 502s were a side effect of order-service retry logic, not gRPC deadline misconfiguration. Canary system was not involved.

---

## 5. Related Incident: Envoy Sidecar Resource Limit Causing Request Drops (2023-01-15)

**Date**: 2023-01-15
**Severity**: P1 (0.9% 502s)
**Symptoms**:
- API gateway: 502 errors on `/checkout` and `/inventory-query`
- Order-service: gRPC "connection reset" errors (not deadline exceeded)
- Inventory-service: 100% 200 OK, normal latency
- Envoy sidecar memory at 95% on 3 inventory-service pods
- Canary was not involved — triggered by a cluster-wide Envoy upgrade

**Root Cause**:
Envoy sidecar proxy had its memory limit reduced from 256Mi to 128Mi in a cluster-wide resource policy change. Under sustained load, the sidecar OOMed and dropped in-flight requests. Kubernetes restarted the sidecar, but during the ~2s restart window, all requests to that pod failed.

**Resolution**:
- Reverted Envoy memory limit to 256Mi
- Added sidecar resource usage to pod monitoring dashboards
- Implemented graceful drain on sidecar OOM signal

**Why it’s different from canary-related bugs**:
Connection resets (not deadline exceeded) are the signature. Affects ALL requests to the pod during restart (not a subset of connections). Not deployment-specific — triggered by infrastructure policy change. No 409 conflicts because failures are hard errors, not retryable timeouts.

---

## Comparison Table: Distinguishing Failure Modes

| Indicator | **LB Stickiness** | **Red Herring: DB Leak** | **Red Herring: Network Partition** | **Red Herring: Clock Skew** | **Envoy Sidecar OOM** |
|----------|------------------------------|---------------------------|------------------------------------|-----------------------------|--------------------------------------|
| **Inventory-service error rate** | 0% (aggregate), 1 pod saturated | 0% | 0% | 0% | 0% (sidecar drops requests) |
| **Order-service errors** | Elevated latency, some timeouts | Connection pool exhausted | Connection refused/reset | gRPC DEADLINE_EXCEEDED | Connection reset |
| **Payment-service 409s** | ❌ No (slow, not timed out) | ❌ No | ❌ No | ✅ Yes (clock-based) | ❌ No (hard failures) |
| **Canary promotion involved** | ✅ Yes (mesh upgrade) | ❌ No | ❌ No | ❌ No | ❌ No |
| **Root cause location** | Service mesh LB policy | Client-side (order-service) | Network infrastructure | Client-side (time sync) | Sidecar resource limits |
| **Latency pattern** | High on 1 pod, normal on others | Increasing over time | Sporadic spikes | Normal | Normal except during restart |
| **Correlation key** | Per-pod request rate imbalance | High DB connections | Packet loss in network graph | Timestamp mismatch in logs | Sidecar memory + restart events |
| **Canary analysis passed?** | ✅ Yes (aggregate metrics OK) | N/A | N/A | N/A | N/A |

> **Key diagnostic insight**: When a canary-promoted service appears healthy by its own metrics but causes downstream failures, check what changed in both the service *and* its infrastructure (mesh config, sidecar versions, connection handling). Server-side 200 OK does not mean client-side success. Look for patterns in *which* connections fail — is it random, per-pod, or version-specific?
