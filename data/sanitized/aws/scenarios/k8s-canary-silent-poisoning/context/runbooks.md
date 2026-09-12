# Runbooks.md

## Service Descriptions and Health Checks

### inventory-service
- **Purpose**: Manages product inventory levels and availability checks for checkout flows. Exposes gRPC interface to order-service.
- **Health Check Endpoint**: `GET /health` (HTTP), `POST /grpc.health.v1.Health/Check` (gRPC)
- **Health Thresholds**:
  - HTTP 200 OK within 500ms → Healthy
  - gRPC HealthCheck response within 100ms → Healthy
  - **Critical**: gRPC connection error rate > 0.1% over 5m (not visible in HTTP logs)
- **Key Metric**: gRPC client-side vs server-side error rate divergence
- **Note**: Server-side logs may show healthy responses even when clients experience failures. Always cross-reference with caller-side metrics.

### order-service
- **Purpose**: Orchestrates checkout flow: validates inventory, reserves stock, triggers payment.
- **Health Check Endpoint**: `GET /health`, `POST /order/v1/Health/Check`
- **Health Thresholds**:
  - HTTP 200 OK for checkout endpoint > 99.5% over 5m
  - gRPC timeout rate to inventory-service < 0.5% over 5m
  - 409 Conflict rate from payment-service < 0.1% over 5m
- **Key Metric**: gRPC deadline exceeded errors to downstream services → may trigger retry storms

### payment-service
- **Purpose**: Processes payments with idempotency key enforcement.
- **Health Check Endpoint**: `GET /health`, `POST /payment/v1/Health/Check`
- **Health Thresholds**:
  - HTTP 200 OK > 99.9% over 5m
  - HTTP 409 Conflict rate < 0.1% over 5m (normal for duplicate idempotency keys)
  - **Alert**: 409 rate > 0.5% over 5m → indicates retry storms from upstream
- **Note**: 409s are correct behavior — high volume indicates downstream retry logic failure.

### api-gateway
- **Purpose**: External entry point for checkout API; aggregates responses from order-service.
- **Health Check Endpoint**: `GET /health`
- **Health Thresholds**:
  - HTTP 502 Bad Gateway rate < 0.1% over 5m
  - End-to-end checkout success rate > 99.7%
- **Key Metric**: 502s correlate with order-service gRPC timeouts → downstream failure propagation

---

## Common Failure Patterns and Diagnostic Steps

| Pattern | Symptoms | Likely Root Cause |
|--------|----------|------------------|
| **502s on checkout after canary promotion** | api-gateway: 0.5–1% 502s; order-service: gRPC errors calling inventory-service; inventory-service: no errors | Investigate what changed in the promoted service — check connection handling, interceptors, sidecar config |
| **Downstream timeouts but upstream service looks healthy** | Caller reports deadline exceeded; callee logs show normal responses | Server-side success does not mean client-side success — investigate connection-level behavior |
| **409 spikes in payment-service** | payment-service 409s rise sharply; no new idempotency key collisions in business data | Likely caused by retry storms from upstream timeout failures — trace back to the original timeout source |
| **Canary analysis passes despite user-facing errors** | Flagger reports promoted service error rate = 0%; downstream errors rising | Canary metrics may only monitor the promoted service — check if downstream impact is measured |

### Diagnostic Steps for 502 Spike Pattern
1. Check api-gateway 502 rate → confirm spike correlates with a recent deployment or promotion event.
2. Query downstream service logs (e.g., order-service) for timeout or connection errors — filter by affected endpoint.
3. Cross-reference timestamps with upstream service deployment events (Flagger rollout history, helm releases).
4. If 409 conflicts present — trace idempotency keys back to retry events; identify the original failure that triggered retries.
5. Verify upstream service logs — if they show 100% success, the issue is likely invisible to the upstream service itself.
6. **Critical**: Compare client-side error patterns with server-side metrics. If they diverge, investigate connection-level behavior (interceptors, sidecar config, load balancing, connection pooling).

---

## Troubleshooting Decision Tree

Start: API Gateway reports 502 spike
│
├─ Is 502 spike correlated with recent deployment or promotion? → YES
│   └─ Which service was recently deployed/promoted?
│       └─ Check Flagger rollout history and deployment events
│           └─ Confirm: Did the canary analysis pass? What metrics were evaluated?
│               → If canary only checked server-side HTTP errors → downstream impact may be invisible
│
├─ Is 502 spike correlated with 409 spike in payment-service? → YES
│   └─ Are 409s clustered around same order IDs? → YES
│       └─ Do those order IDs have multiple payment attempts? → YES
│           └─ Trace back: what caused the initial failure that triggered retries?
│               → Check caller-side logs for timeout or connection errors
│
├─ Is upstream service reporting healthy metrics while downstream shows errors? → YES
│   └─ Server-side and client-side metrics diverge
│       → Investigate connection-level behavior between services
│       → Check: interceptor config, connection pool settings, sidecar proxy behavior, load balancing policy
│
└─ No correlation to deployment? → Check network policies, service mesh sidecars, or DNS misconfig

---

## Key Diagnostic Commands and Queries

### Prometheus / Grafana Queries
# Order-service gRPC timeout rate (to inventory-service)
rate(order_service_grpc_client_deadline_exceeded_total[5m]) > 0.01

# Payment-service 409 Conflict rate
rate(payment_service_http_responses{status="409"}[5m]) > 0.005

# API Gateway 502 rate
rate(api_gateway_http_responses{status="502"}[5m]) > 0.008

# inventory-service gRPC server-side success rate (should be 100%)
rate(inventory_service_grpc_server_handled_total{code="OK"}[5m]) / rate(inventory_service_grpc_server_handled_total[5m]) == 1

# Check deployment version for recently promoted service
kube_deployment_metadata{deployment="<service-name>"} * on(deployment) group_left(version) <service>_version_info

### Kubernetes / CLI Commands
# View canary rollout history for a service
kubectl -n production get flaggerdeployments.<service-name> -o yaml

# Get logs from downstream service during spike (filter timeout/connection errors)
kubectl -n production logs -l app=<downstream-service> --since=15m | grep -iE "deadline exceeded|timeout|connection"

# Check gRPC config in a service container
kubectl -n production exec -it <pod-name> -- cat /app/config/grpc-client.yaml

# Check network connectivity between services
kubectl -n production run -it --rm debug --image=busybox --restart=Never -- nc -vz <service>.<namespace>.svc.cluster.local <port>

# Search for interceptor or connection config in service source
kubectl -n production exec -it <pod-name> -- grep -r "deadline\|timeout\|interceptor" /app/pkg/

### Logging Queries (Loki)
# Downstream service: gRPC timeouts in a time window
{app="<downstream-service>"} |= "deadline exceeded" |~ "<upstream-service>" | json | line_format "{{.timestamp}} {{.message}}"

# Payment-service: 409s with order IDs (indicates retry storms)
{app="payment-service"} |= "409 Conflict" | json | label_format order_id="{{.order_id}}" | count_over_time(1m) > 5

# Upstream service: any connection-level error logs
{app="<upstream-service>"} |= "error" |~ "connection" |~ "timeout"

---

## Escalation Procedures

### Tier 1: SRE On-Call
- Confirm 502 spike and correlation with canary promotion.
- Run Prometheus queries for order-service timeouts and payment-service 409s.
- Check Flagger deployment history and analysis metrics.
- If inventory-service HTTP error rate = 0% but upstream errors exist → escalate to Tier 2.

### Tier 2: Platform / gRPC Specialists
- Pull the recently promoted service container image and diff against the last known-good version.
- Inspect gRPC client/server initialization code — connection pooling, interceptor chain, dial options.
- Check service mesh and sidecar configuration for changes coinciding with the deployment.
- Reproduce locally: run the promoted version under load and monitor client-side timeout behavior.
- Compare connection-level behavior between old and new versions using trace data.

### Tier 3: Engineering / Product
- Roll back the promoted service to the last known-good version via Flagger:
  ```bash
  kubectl -n production rollout undo flaggerdeployment.<service-name>

- Notify product team with root cause summary.
- Coordinate with QA: Update canary test suite to cover the identified failure mode.
- Post-mortem: Review what canary metrics would have caught this and add them.

### Emergency Rollback Protocol
1. **Pause Flagger**: `kubectl -n production annotate flaggerdeployment.<service-name> flagger.app/pause=true`
2. **Rollback**: `kubectl -n production rollout undo deployment/<service-name>`
3. **Confirm**: Monitor api-gateway 502s and downstream error rates — must drop below 0.1% within 5m.
4. **Notify**: Slack channel #incident-response with rollback confirmation and monitoring status.
5. **Lock**: Prevent new deployments until post-mortem completes.

> **Note**: When a canary-promoted service appears healthy by its own metrics but causes downstream failures, the root cause is often in connection-level behavior invisible to standard HTTP monitoring. Always validate client-side metrics during canary analysis.
