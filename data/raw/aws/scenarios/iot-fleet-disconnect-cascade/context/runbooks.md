# Runbooks.md

## Service Descriptions & Health Check Endpoints

### auth-service
- **Purpose**: Handles device authentication and TLS handshake validation for IoT fleet connections. Supports optional security validation extensions and OCSP stapling for regulatory compliance.
- **Health Check Endpoint**: `GET /health`
- **Expected Response**: `200 OK` with JSON body: `{ "status": "healthy", "version": "x.x.x" }`
- **Thresholds**:
  - **Success Rate**: >99.5% of connection attempts succeed within 5s
  - **Latency P95**: <200ms for standard auth flow
  - **Error Rate**: <0.1% of connection attempts result in 5xx or timeout
- **Known Feature Flags**: Security validation feature flags (check feature-flags-service for current state), `ocsp_stapling_mode`, `legacy_tls_compat`, `rate_limit_per_device`

### device-registry-service
- **Purpose**: Tracks device state (online/offline), last seen timestamp, and connection metadata.
- **Health Check Endpoint**: `GET /status`
- **Expected Response**: `200 OK` with JSON body: `{ "devices_online": XXXXX, "total_devices": 50000, "last_updated": "ISO8601" }`
- **Thresholds**:
  - **Online Rate**: >99.5% of registered devices
  - **Sync Lag**: <30s between auth-service connection events and registry updates

### metrics-aggregator-service
- **Purpose**: Aggregates device connection success/failure metrics and telemetry ingestion rates.
- **Health Check Endpoint**: `GET /metrics/health`
- **Expected Response**: `200 OK` with JSON body: `{ "ingestion_rate": XXX, "connection_success_rate": 0.997, "last_sample": "ISO8601" }`
- **Thresholds**:
  - **Connection Success Rate**: >99.5% over 5m window
  - **Drop Rate**: <0.5% of expected telemetry packets

### cert-rotator-service
- **Purpose**: Rotates device certificates on a scheduled basis (every 7 days). Does not affect real-time connectivity.
- **Health Check Endpoint**: `GET /health`
- **Expected Response**: `200 OK` with JSON body: `{ "status": "healthy", "next_rotation": "ISO8601", "pending_rotations": 0 }`
- **Note**: Errors here are **symptomatic** of device disconnections — devices cannot reach the service to validate new certs if disconnected.

### mqtt-broker-cluster
- **Purpose**: Manages persistent MQTT sessions for device telemetry and command delivery.
- **Health Check Endpoint**: `GET /broker/health`
- **Expected Response**: `200 OK` with JSON body: `{ "status": "healthy", "active_connections": XXXXX, "memory_usage_pct": XX }`
- **Thresholds**:
  - **Active Connections**: >48,000 (normal fleet size)
  - **Memory Usage**: <80% (above 85% triggers auto-restart)
  - **Message Backlog**: <10,000 undelivered messages

### firmware-ota-service
- **Purpose**: Manages over-the-air firmware updates for devices. Coordinates update windows and rollback triggers.
- **Health Check Endpoint**: `GET /ota/status`
- **Expected Response**: `200 OK` with JSON body: `{ "active_rollouts": X, "pending_updates": XXX, "rollback_count": X }`
- **Note**: Active firmware rollouts can cause temporary disconnections during device restart cycles (typically 2-5 min per device).

---

## Common Failure Patterns & Diagnostic Steps

### Pattern 1: Geographic Spike in Device Disconnections
- **Symptoms**:
  - Sudden drop in online devices concentrated in a single region
  - Metrics aggregator shows regional drop in connection success rate
  - Device registry shows many devices with "last_seen > 10m"
- **Diagnostic Steps**:
  1. Identify the geographic scope — is it one region, one country, or one warehouse provider?
  2. Check for recent deployments to auth-service or related infrastructure in the affected region
  3. Check for external dependency issues — DNS, third-party validation services, network providers
  4. Review auth-service feature flag configuration for any region-scoped flags
  5. Check if cert-rotator or firmware-ota has a scheduled activity in the region
  6. Query device connection logs for the specific error type (timeout vs refused vs invalid cert)
  7. Cross-reference with network monitoring for packet loss or routing changes

### Pattern 2: Sporadic Reconnects Followed by Re-Disconnects
- **Symptoms**:
  - Some devices reconnect briefly, then go offline again after 5–15 minutes
  - Exponential backoff pattern visible in device logs (1m → 2m → 4m → 8m retries)
- **Diagnostic Steps**:
  1. Identify devices that reconnect → check what changes between successful and failed attempts
  2. Monitor external service latency in real-time — brief recovery windows cause temporary success
  3. Check if any feature flag or configuration is intermittently affecting the connection path
  4. Look for resource exhaustion patterns (memory, connections, file descriptors) in upstream services
  5. Check MQTT broker session state — stale sessions can cause reconnect/disconnect loops

### Pattern 3: High Error Rates in Device Registry or Cert Rotator
- **Symptoms**:
  - `device-registry-service` reports 1000+ devices as "offline"
  - `cert-rotator-service` reports "failed to reach device" errors
- **Diagnostic Steps**:
  1. **DO NOT** assume registry or rotator is broken — these are downstream effects
  2. Trace error origin: Are these errors triggered by "connection refused" or "timeout" from devices?
  3. Check auth-service and MQTT broker for upstream connection failures
  4. Use device IDs from registry errors to query auth-service connection attempts
  5. Check for firmware OTA activity that might be restarting devices in batches

### Pattern 4: No Errors in auth-service Logs During Outage
- **Symptoms**:
  - auth-service logs show 0 errors, 0 timeouts, 0 5xx responses
  - But client devices report "TLS handshake failed" or "connection timeout"
- **Diagnostic Steps**:
  1. This pattern indicates failure *before* auth-service can log the request
  2. Possible causes: DNS failure, network-level block, or a pre-auth validation step timing out client-side
  3. Check if any pre-authentication validation step (external or internal) is adding latency or blocking before the main auth flow completes
  4. Enable **debug-level tracing** on auth-service: `log_level=debug`
  5. Check client-side timeout settings — short timeouts may drop connections before server responds

### Pattern 5: MQTT Broker Degradation
- **Symptoms**:
  - Devices authenticate successfully but lose connection shortly after
  - "Connection reset" or "session expired" errors in device logs
  - MQTT broker memory or CPU trending upward over hours
- **Diagnostic Steps**:
  1. Check MQTT broker memory and CPU trends (not just current values — look for upward trends)
  2. Review recent broker version upgrades or configuration changes
  3. Check persistent session count — are sessions accumulating without cleanup?
  4. Look for message backlog growth indicating consumer-side issues
  5. If broker recently upgraded, compare resource usage to pre-upgrade baseline

### Pattern 6: Firmware OTA-Related Disconnections
- **Symptoms**:
  - Device disconnections correlate with firmware rollout schedule
  - Devices come back online with new firmware version after 2-5 minutes
  - Disconnection rate matches OTA batch size
- **Diagnostic Steps**:
  1. Check firmware-ota-service for active rollouts
  2. Verify rollout batch size and timing — are disconnections within expected OTA window?
  3. If devices do NOT come back online after OTA, check for firmware compatibility issues
  4. Look for rollback triggers in OTA service logs

### Pattern 7: Rate Limiting or Connection Throttling
- **Symptoms**:
  - Gradual increase in "connection rejected" or "429 Too Many Requests" errors
  - Affects devices that reconnect frequently (e.g., after a previous outage)
  - auth-service logs show rate limit triggers
- **Diagnostic Steps**:
  1. Check `rate_limit_per_device` feature flag and current thresholds
  2. Are devices in a reconnect storm? (previous outage → mass reconnect → rate limit → re-disconnect)
  3. Temporarily increase rate limits during recovery window
  4. Check if any anti-DDoS or WAF rules are triggering on legitimate reconnection traffic

---

## Troubleshooting Decision Tree

Start: "Large number of devices offline"
    │
    ▼
Is the outage isolated to a specific region? → NO → Check global infrastructure (DNS, MQTT broker, auth-service deployment)
    │
    ▼
YES → Identify the region and scope
    │
    ├── US/Canada only → Check recent auth-service deployments and any region-specific configuration changes
    ├── Europe only → Check warehouse network providers, firewall rules, OCSP configuration
    ├── Single warehouse → Check local network (firewall, port blocking, ISP issues)
    └── All regions → Check global DNS, MQTT broker health, cert-rotator batch jobs
    │
    ▼
Check auth-service logs for the affected region:
    │
    ├── Errors present → Follow the specific error type (cert invalid, rate limit, 5xx)
    └── No errors → Failure is occurring before auth-service can log it
         │
         ▼
    Check for pre-auth failures:
         ├── DNS resolution errors in device logs → DNS/Route53 issue
         ├── "Connection refused" → Network/firewall/port issue
         ├── "TLS handshake timeout" → External validation dependency or network latency
         └── "Connection reset" → Post-auth issue, check MQTT broker
    │
    ▼
If TLS handshake timeout with no auth-service errors:
    │
    ├── Check for external dependency calls during TLS path (OCSP, CRL, or other validation services)
    ├── Review recent feature flag or configuration changes that might introduce external calls
    ├── Monitor external service latency
    └── Check client-side timeout configuration
    │
    ▼
Determine root cause category:
    ├── External dependency degradation → Disable/circuit-break the external call, monitor recovery
    ├── Feature flag misconfiguration → Disable flag, verify scope documentation
    ├── Network/infrastructure → Engage network team, check provider status pages
    └── Resource exhaustion → Identify leaking resource, restart/rollback affected service

---

## Key Diagnostic Commands and Queries

### auth-service
# Check feature flag configuration (via config API)
curl -H "Authorization: Bearer $TOKEN" https://auth-service.internal/api/v1/config/feature-flags

# Check recent deployments
curl -H "Authorization: Bearer $TOKEN" https://auth-service.internal/api/v1/admin/deployments?limit=5

# Enable debug logging temporarily
curl -X POST -H "Authorization: Bearer $TOKEN" https://auth-service.internal/api/v1/admin/log-level -d '{"level": "debug"}'

# Query connection attempt distribution by result
curl "https://auth-service.internal/api/v1/metrics/connections?group_by=result&duration=1h"

### Metrics Aggregator
# Query connection success rate by region (last 15m)
curl "https://metrics-aggregator.internal/api/v1/metrics?metric=connection_success_rate&region=us-*&start=-15m"

# Identify devices with >5 failed connection attempts in 1h
curl "https://metrics-aggregator.internal/api/v1/failure-trends?threshold=5&duration=1h&region=us-*"

### Device Registry
# List devices offline >10m in a specific region
curl "https://device-registry.internal/api/v1/devices?status=offline&duration_gt=600&region=us-*|ca-*"

# Cross-reference with deployment timeline
curl "https://device-registry.internal/api/v1/devices?last_seen_gt=2026-03-29T14:00:00Z&region=us-*" | jq '.[] | .device_id' > offline_devices.txt

### MQTT Broker
# Check broker health and memory
curl "https://mqtt-broker.internal/broker/health"

# Check active session count trend
curl "https://mqtt-broker.internal/broker/sessions?metric=count&duration=24h"

### External Service Checks
# Generic external dependency latency check
curl -s -o /dev/null -w "Connect: %{time_connect}s, TLS: %{time_appconnect}s, Total: %{time_total}s\n" https://<external-service-url>

---

## Escalation Procedures

### Level 1: Initial Alert (Operations Team)
- Confirm geographic pattern and scope
- Check all service health endpoints
- Review recent deployments and feature flag changes across all services
- If external dependency is suspected → escalate to Level 2

### Level 2: Engineering On-Call (Auth-Service / Platform Team)
- Identify the specific failure path (pre-auth, during-auth, post-auth)
- If feature flag related → disable the flag and monitor recovery
- If external dependency → enable circuit breaker or disable the external call
- If infrastructure → engage appropriate infrastructure team
- Document timeline of flag/config changes and impact

### Level 3: Platform/Security Team (Post-Containment)
- Audit the change that caused the incident
- Review change management process — was the change flagged as high-risk?
- Implement monitoring and circuit breakers for any external dependencies in critical path
- Update runbooks with specific diagnostic steps for the identified failure mode

### Level 4: Executive Review (CISO + CTO)
- Review gap between deployment and incident detection
- Evaluate canary monitoring and smoke test coverage
- Determine policy updates for feature flag rollouts with external dependencies
