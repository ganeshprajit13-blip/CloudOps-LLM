Severity: P1
Reported by: SRE On-Call
Date: 2026-03-27

Summary:
API gateway is reporting a sustained 0.8% error rate (502 Bad Gateway) on the checkout endpoint, starting at 14:00 UTC. The issue coincides with the auto-promotion of inventory-service v2.1.4 via Flagger at 13:45 UTC. No infrastructure-level outages or resource exhaustion events are detected. Customer support has received an uptick in checkout failure reports, correlating with the error spike.

Impact:
- 0.8% of checkout requests are failing (approx. 400–500 failed transactions/hour)
- Affected users experience partial checkout abandonment; no data loss
- Payment service is generating 409 Conflict responses at elevated rates, indicating retry behavior
- Order-service is logging intermittent gRPC deadline exceeded errors when calling inventory-service
- No alerts triggered on inventory-service CPU, memory, or HTTP error rates (all within thresholds)

Timeline:
- 13:30 UTC: inventory-service v2.1.4 canary deployment begins (10% traffic)
- 13:33 UTC: First signs of timeout anomalies observed in order-service logs
- 13:45 UTC: Flagger auto-promotes inventory-service v2.1.4 to 100% traffic (based on 0.2% error rate in canary analysis)
- 14:00 UTC: Global 502 error rate on API gateway rises to 0.8% and stabilizes
- 14:05 UTC: On-call team paged; initial investigation initiated

Available Information:
- inventory-service logs: 100% 200 OK responses; no errors, no warnings; average latency 120ms
- order-service logs: intermittent “deadline exceeded” errors when calling inventory-service; retry logic active; 409 Conflict responses received from payment-service
- payment-service logs: elevated 409 Conflict responses (duplicate idempotency keys); no other errors
- api-gateway logs: 502 responses correlate with order-service timeouts; no upstream connection failures logged
- Flagger analysis: passed all configured metrics (HTTP error rate, latency percentiles, request volume stability)
- No network policy changes, service mesh updates, or cluster node issues detected
- Canary deployment configuration: monitors only HTTP error rate and latency of inventory-service; no client-side behavior or downstream impact metrics

Next Steps Required:
Clarification needed on whether the gRPC client timeout configuration in order-service is being respected or overridden, and whether inventory-service is correctly propagating or respecting request deadlines. No clear failure point is visible in the service that is being promoted.
