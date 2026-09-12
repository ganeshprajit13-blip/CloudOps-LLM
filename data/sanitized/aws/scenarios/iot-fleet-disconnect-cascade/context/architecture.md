# System Architecture: IoT Fleet Management Platform

## System Overview and Purpose

The IoT Fleet Management Platform enables real-time telemetry collection and remote management of 50,000 industrial sensors deployed across factories, oil rigs, and warehouses. Sensors report vibration, temperature, and pressure data every 30 seconds over TLS-secured MQTT connections. The platform ensures secure device authentication, telemetry ingestion, state tracking, certificate lifecycle management, and operational visibility. Core objectives include high availability (99.7%+ uptime), secure device onboarding, and scalable telemetry processing under global operational loads.

The system is architected as a microservice ecosystem with clear separation of concerns: authentication, device registry, metrics aggregation, certificate rotation, and alerting. Each service operates independently but relies on tightly coupled data flows and shared configuration states.

---

## Service Topology

### 1. **auth-service**
- **Purpose**: Authenticates device TLS connections using X.509 client certificates. Validates certificate chain, revocation status, and (since v3.8.0) Certificate Transparency (CT) logs via external third-party endpoint.
- **Critical Behavior**: Synchronous CT validation during TLS handshake. If CT server response exceeds 10s, connection is terminated client-side before server logs error.
- **Feature Flag**: `ct_validation_enabled` — region-scoped (us-*, ca-* only). Default: `false`.
- **Timeout**: 10s client-side TLS handshake timeout. Server-side timeout irrelevant — no log entry generated on timeout.
- **Dependencies**: Device registry (read-only), ct.cloudflare.com (external, TLS endpoint).

### 2. **device-registry**
- **Purpose**: Central source of truth for device identity, location, status, and certificate metadata. Serves as read-only reference for auth-service and certificate-rotator.
- **Data Model**: Device ID, region, certificate serial, last seen timestamp, active status.
- **Dependencies**: None (writes from certificate-rotator; reads by auth-service, metrics-aggregator).

### 3. **metrics-aggregator**
- **Purpose**: Ingests and aggregates telemetry from connected devices. Tracks connection success/failure rates, latency, and device count per region.
- **Alerting Trigger**: Device count drops >1% in 5min → P1 alert.
- **Observability Gap**: Only sees downstream effects — cannot distinguish between network outage, auth failure, or device reboot.

### 4. **certificate-rotator**
- **Purpose**: Automated rotation of device certificates every 90 days. Generates new certs, pushes to device-registry, and triggers device reconnection.
- **Trigger**: Scheduled batch job every 02:00 UTC.
- **Interaction**: Writes to device-registry; does not communicate directly with auth-service.

### 5. **alerting-engine**
- **Purpose**: Correlates alerts from metrics-aggregator, device-registry, and external service monitors. Routes alerts to on-call teams via Slack/PagerDuty.
- **Known Flaw**: Does not correlate regional device drop with auth-service deployment history or external service health.

### 6. **ct.cloudflare.com** *(External Dependency)*
- **Purpose**: Public Certificate Transparency log server. Provides auditable proof of certificate issuance.
- **SLA**: No formal SLA — operated by Cloudflare as a public service.
- **Latency**: Normally <500ms; degraded during infrastructure incident (15–30s).

---

## Data/Request Flow Diagram

[Device] ---(TLS Handshake)---→ [auth-service] ---(CT Log Query)--→ [ct.cloudflare.com]
   |                                    |
   | (10s timeout → fail)               | (15–30s latency → timeout)
   |                                    |
   |                                    V
   |                            [No server log entry — timeout occurs client-side]
   |
   V
[metrics-aggregator] ←--- (Failed connection events) ---→ [alerting-engine]
   |
   V
[device-registry] ←--- (Device status update) --- [certificate-rotator]

**Key Flow Notes**:
- Device initiates connection → auth-service blocks on CT validation → client times out at 10s → no server-side error logged.
- Device enters exponential backoff: 1m → 2m → 4m → 8m → 16m retry intervals.
- Failed devices remain in “disconnected” state in device-registry but no root cause is inferred.
- Certificate-rotator runs silently every 02:00 UTC — unrelated to incident timing.

---

## Key Configuration Parameters

| Parameter | Value | Description | Risk |
|---------|-------|-------------|------|
| `ct_validation_enabled` | `true` for `region=us-*`, `ca-*`; `false` elsewhere | Enables synchronous CT log validation during TLS handshake. | **Critical**: Undocumented regional segmentation. No rollback plan. |
| `tls_handshake_timeout` | `10s` | Client-side timeout for TLS negotiation. | **Critical**: Too short for external dependency latency. No fallback or async mode. |
| `ct_log_endpoint` | `https://ct.cloudflare.com/logs` | External CT log server URL. | **Critical**: Single point of failure. No fallback or caching. |
| `device_retry_backoff_base` | `60s` | Base interval for exponential backoff after failed connect. | **Critical**: Causes staggered cascade — delays detection and recovery. |
| `auth_service_version` | `v3.8.0` | Deployed T-36h. Includes CT validation feature. | **Critical**: No change log entry in runbooks. No feature flag documentation. |

---

## Monitoring and Alerting Setup

### **Present Monitoring**
- **auth-service**: CPU, memory, request rate, TLS handshake count (success/fail counters via Prometheus).
- **device-registry**: DB latency, device count, last-seen timestamps.
- **metrics-aggregator**: Device online/offline count, telemetry ingestion rate, region-based device counts.
- **External Services**: ct.cloudflare.com ping/uptime (every 5min via synthetic check).
- **Alerting Rules**:
  - `Device online count < 99% of baseline` → P1
  - `auth-service error rate > 5%` → P2
  - `ct.cloudflare.com response time > 5s` → P3

### **Critical Gaps**
1. **No correlation between auth-service deployment and device disconnects** — deployment events not ingested into alerting engine.
2. **Feature flag state not exposed in monitoring** — no dashboard shows `ct_validation_enabled=true` per region.
3. **Client-side timeouts not logged** — auth-service does not emit “TLS handshake timed out by client” events.
4. **External dependency latency not alertable** — only uptime is monitored, not latency degradation.
5. **No regional segmentation visibility** — alerts show “North America drop” but no link to feature flag scope.
6. **No 36-hour delay alerting** — no system flags deployments that precede incidents by >24h.

---

## Recent Changes and Maintenance Windows

| Timestamp | Change | Owner | Notes |
|----------|--------|-------|-------|
| **T-36h (02:00 Day 1)** | Deployed auth-service v3.8.0 | Security Team | Added CT validation behind feature flag `ct_validation_enabled=true` for `region=us-*`, `ca-*`. **No runbook update**, no team notification, no rollback plan documented. |
| **T-35h (03:00 Day 1)** | Device registry schema migration | Platform Team | Added `region` field to device metadata. Compatible with v3.8.0. |
| **T-12h (14:00 Day 1)** | Maintenance window: metrics-aggregator scale-up | SRE Team | Added 2 new replicas. Unrelated to auth-service. |
| **T-1h (13:15 Day 2)** | Certificate-rotator batch job ran | Automation Bot | Rotated certs for 12,000 devices scheduled for renewal. **Did not trigger reconnects until next telemetry window**. |
| **T-0 (14:15 Day 2)** | ct.cloudflare.com degradation begins | Cloudflare (External) | Latency spikes to 15–30s. No public incident report issued until T+4h. |
| **T+180min (17:15 Day 2)** | ct.cloudflare.com recovers | Cloudflare | Latency returns to <1s. Devices reconnect gradually via exponential backoff. |

**Post-Incident Discovery**:
- Feature flag scope was configured via environment variable in Helm chart, not documented in Confluence.
- Security team assumed CT validation was “low risk” due to “rare external failures.”
- No testing was performed under high-latency CT server conditions.
- No one reviewed the 36-hour gap between deploy and incident — assumed coincidence.
