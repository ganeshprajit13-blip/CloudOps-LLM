Severity: P1
Reported by: Fleet Operations Team ([REDACTED_EMAIL])
Date: 2026-03-29 15:00 UTC

## Summary
Approximately 4,200 IoT devices in North America have become unresponsive over a 90-minute window, causing a sharp drop in fleet connectivity from 99.7% to 91.3%. The outage is geographically confined to the United States and Canada, with no reported impact in Europe, APAC, or South America. Devices are not reporting telemetry, and attempts to manually trigger a reconnect via the management console have yielded inconsistent results — some devices reconnect briefly before dropping again.

## Impact
- **Operational**: 8.4% of the global IoT fleet (all North American units) offline. Real-time monitoring of critical machinery (vibration, pressure, temperature) is interrupted across 17 industrial sites.
- **Financial**: Estimated $2.1M/hour in production downtime across three high-value manufacturing lines.
- **Reputational**: Two enterprise customers have escalated SLA breach concerns.
- **Secondary Effects**: Device registry service is logging 12,000+ “device offline” events per minute. Metrics aggregator is saturated with connection reset errors. Certificate rotator service is reporting failed renewal attempts on 3,800+ devices — all of which are also offline.

## Timeline
- **14:15 UTC**: First anomalies detected in regional connectivity dashboard — North America telemetry drops by 3%.
- **14:20 UTC**: First alerts triggered from device health monitor — “Connection timeout exceeded” for 100+ devices.
- **14:35 UTC**: Offline devices spike to 1,200. Operations team initiates incident response.
- **15:00 UTC**: 4,200 devices offline. Regional outage confirmed.
- **15:45 UTC**: Some devices begin reconnecting intermittently, but reconnections are unstable — devices drop again within 5–10 minutes.
- **17:15 UTC**: Offline count begins to decline gradually. By 18:00, ~1,800 devices remain offline.
- **19:30 UTC**: Connectivity returns to 99.1% — remaining offline devices are mostly in high-latency or low-signal locations.

## Available Information
- **Logs**:
  - auth-service: No errors or timeouts logged during the incident window. All requests appear successful.
  - Device-side logs (sampled): “TLS handshake failed,” “Connection timed out after 10s,” “No response from auth endpoint.”
  - Device registry: High volume of “device disconnected” events with no associated error codes.
  - Certificate rotator: “Renewal failed: device unreachable” — all failures correspond to offline devices.
- **Metrics**:
  - HTTP 200 rate from auth-service: 99.9% during incident.
  - Device connection attempt rate: Normal.
  - TLS handshake duration: Not instrumented.
- **Configuration**:
  - Feature flags are active but undocumented in runbooks.
  - Last auth-service deployment: 36 hours prior (v3.8.0).
  - Certificate validity: All device certificates are within 7-day renewal window.
- **External Dependencies**:
  - One third-party CT log service is referenced in internal architecture diagrams but not listed in dependency registry.
  - No alerts were triggered on this service’s public status page during the incident window.

## Open Questions
- Why are auth-service logs clean while devices report connection failures?
- Why is the outage isolated to North America?
- Why did the issue manifest 36 hours after the last deploy?
- Are the certificate rotator and device registry failures causes or consequences?
- Is this a network issue, a certificate issue, or an authentication service behavior change?

No external incident reports or customer complaints were filed prior to the alert. The team is currently reviewing all recent changes to device firmware and auth-service behavior, but no smoking gun has been identified.
