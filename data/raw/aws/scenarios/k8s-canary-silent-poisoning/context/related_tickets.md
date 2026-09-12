related_tickets.md

---

### Related Tickets

**JIRA-1187** | `inventory-service` gRPC connection pool interceptor bug | `dev-team/inventory` | `Closed` | `Resolved`
*Description*: Bug fix for gRPC connection interceptor that incorrectly initialized timeout to 100ms instead of 5000ms on 1-2% of connections due to race condition during service startup. Patched in v2.1.5.
*Comments*:
> Fixed in v2.1.5 by moving interceptor initialization to post-startup hook. Root cause: `ConnectionPoolManager` was reusing a stale config instance during concurrent initialization.
> This was the source of the silent timeouts that cascaded to order-service and payment-service. Canary system passed because inventory-service returned 200 OK — the issue was client-side timeout, not server error.

---

**JIRA-1203** | Implement distributed deadline tracing for gRPC calls | `sre/observability` | `Backlog` | `Unassigned`
*Description*: Add distributed tracing context for gRPC deadlines across service boundaries. Log actual client-side timeout values vs. configured server timeouts to detect mismatches.
*Comments*:
> This would have caught the 100ms vs 5000ms mismatch in real time. Currently, only server-side metrics are monitored. Need to instrument client-side gRPC interceptors in order-service, payment-service, and api-gateway to propagate and log `grpc-timeout` metadata.
> Proposal: Add OpenTelemetry span attribute `grpc.client.deadline_actual_ms` and alert if >20% of calls have deadline < 1000ms while server config is 5000ms.

---

**JIRA-1191** | Upgrade Redis cluster to v7.2 for improved TTL handling | `platform/infrastructure` | `Closed` | `Resolved`
*Description*: Upgrade Redis clusters in staging and prod to v7.2 to leverage new Lua script optimizations. Scheduled for maintenance window.
*Comments*:
> This was scheduled for the same day as the canary rollout. Team initially suspected Redis timeouts causing checkout failures. Logs confirmed no Redis errors during incident window. False lead.

---

**JIRA-1198** | Add new "Express Checkout" feature flag to API gateway | `product/checkout` | `In Progress` | `j.smith`
*Description*: Implement feature flag for new checkout flow that bypasses inventory-service validation. Targeting Q3 release.
*Comments*:
> This feature was under active development and deployed to canary environment. Team initially thought the flag was misconfigured and causing bypass logic errors. No relation to the gRPC timeout bug.

---

**JIRA-1201** | Migrate payment-service logging from JSON to structured protobuf | `platform/logging` | `Closed` | `Resolved`
*Description*: Refactor payment-service to emit structured logs using protobuf schema for better parsing in Loki.
*Comments*:
> Completed 2 hours before incident. Logs show correct 409 Conflict responses for duplicate IDs. Team reviewed these logs thinking the 409s were erroneous — but they were legitimate and correctly handled. Red herring.

---

**JIRA-1195** | Increase memory limits for order-service pods | `sre/infrastructure` | `Closed` | `Resolved`
*Description*: Order-service pods were hitting 85% memory usage during peak. Increased limits from 512Mi to 1Gi.
*Comments*:
> Memory usage normalized after change. Team initially suspected OOM kills causing timeouts. No OOM events occurred during incident. Latency spikes were due to gRPC deadline exhaustion, not resource pressure.
