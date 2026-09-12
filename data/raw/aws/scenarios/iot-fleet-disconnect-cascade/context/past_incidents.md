# Past Incidents

## Incident: OCSP Responder Timeout During EU Fleet Expansion (Aug 22, 2023)

- **Date**: August 22, 2023
- **Severity**: P1 — 2,800 devices offline (5.6% of fleet), Europe only
- **Symptoms**:
  - Spike in "TLS handshake timeout" errors in EU device logs
  - auth-service logs showed elevated latency but no outright failures
  - Device registry showed 3,000+ devices cycling between "connecting" and "offline"
  - Metrics aggregator reported 65% drop in telemetry from EU region
- **Root Cause**:
  - OCSP stapling was enabled for EU region as part of compliance hardening
  - The third-party OCSP responder (ocsp.sectigo.com) experienced degraded performance (8s avg response)
  - auth-service made synchronous OCSP check during TLS negotiation — but only for EU devices
  - Unlike a full handshake block, auth-service *did* log partial connection attempts before timeout
- **Resolution**:
  - Switched OCSP validation to async staple-and-cache mode
  - Added OCSP responder latency monitoring with 3s circuit breaker
  - Devices reconnected over 20min as stapled responses were cached
- **Lessons Learned**:
  - External certificate validation services are a reliability risk when called synchronously
  - Regional rollouts of security features need canary monitoring
  - OCSP stapling with caching is safer than real-time validation
  - Auth-service logged partial attempts — different from cases where client times out before server sees anything

---

## Incident: Certificate Rotator Overload (Nov 2, 2022)

- **Date**: November 2, 2022
- **Severity**: P2 — 2,100 devices offline, global
- **Symptoms**:
  - Certificate rotator service CPU spiked to 98%
  - Device logs showed "invalid certificate" errors
  - Device registry reported batch renewal failures
  - auth-service showed "certificate not found" errors
- **Root Cause**:
  - Automated certificate rotation script ran simultaneously across all devices due to misconfigured cron job
  - 50k concurrent TLS renegotiations overwhelmed certificate rotator's DB connection pool
  - Certificates were *not* expired — rotator failed to retrieve them from vault
- **Resolution**:
  - Throttled rotation to 500 devices/minute
  - Added staggered renewal window based on device ID hash
  - Implemented circuit breaker on vault connection
- **Lessons Learned**:
  - Bulk certificate operations must be rate-limited and randomized
  - "Invalid cert" errors can be caused by retrieval failures, not expiration
  - auth-service errors were red herrings — root cause was upstream service overload

---

## Incident: NTP Synchronization Drift (Jul 18, 2022)

- **Date**: July 18, 2022
- **Severity**: P2 — 1,800 devices offline, global
- **Symptoms**:
  - Device logs showed "TLS certificate expired" errors
  - auth-service rejected connections due to "invalid notBefore/notAfter" timestamps
  - Affected devices clustered in time zones with poor NTP access
- **Root Cause**:
  - Firmware bug in 5000 older sensors caused internal clock to drift >12h due to failed NTP sync
  - TLS certs had 15min window tolerance — drift pushed device time outside validity period
  - No alerting on device clock drift thresholds
- **Resolution**:
  - Rolled out firmware patch enforcing local time sync fallback
  - Added clock drift alerting in device telemetry pipeline
  - Increased TLS validity window tolerance to 30min for legacy devices
- **Lessons Learned**:
  - Time synchronization is critical for TLS — even if certs are valid, device clock matters
  - "Certificate expired" errors can be caused by client-side time drift, not server-side issues
  - Device telemetry must include clock offset as a metric

---

## Incident: DNS Resolution Failure in AWS Region (Jan 5, 2023)

- **Date**: January 5, 2023
- **Severity**: P1 — 3,500 devices offline, all regions
- **Symptoms**:
  - Device logs showed "DNS resolution failed" for auth-service endpoint
  - auth-service was healthy and reachable from internal tools
  - Device registry showed "unreachable host" errors
  - Network monitoring showed elevated packet loss in us-east-1
- **Root Cause**:
  - AWS Route 53 experienced transient DNS propagation delay in us-east-1
  - Devices cached old DNS record pointing to decommissioned IP
  - TTL was set to 300s — devices did not refresh for 5+ minutes
  - All regions affected because auth-service used global DNS alias
- **Resolution**:
  - Reduced DNS TTL to 60s
  - Implemented DNS failover to secondary resolver
  - Added health check to device startup that validates DNS resolution
- **Lessons Learned**:
  - Global services must use low-TTL DNS with failover
  - "Service unreachable" errors can be DNS, not service down
  - Device-side DNS caching behavior must be tested in failover scenarios

---

## Incident: Firewall Rule Change Blocking Port 8883 (Sep 12, 2022)

- **Date**: September 12, 2022
- **Severity**: P2 — 2,900 devices offline, only in European warehouses
- **Symptoms**:
  - Device logs showed "connection refused"
  - auth-service logs showed *no* connection attempts from EU region
  - Network team confirmed firewall rules were unchanged
- **Root Cause**:
  - Third-party logistics provider updated their warehouse firewall to block non-standard MQTT ports
  - Devices used port 8883 (MQTT over TLS) — blocked as "unapproved protocol"
  - Rule change was undocumented and not communicated to IoT team
  - Only devices in that specific logistics provider's warehouses affected
- **Resolution**:
  - Switched to port 443 for all devices
  - Implemented port fallback logic in device firmware
  - Created vendor communication checklist for network changes
- **Lessons Learned**:
  - External network policies (even non-cloud) can break IoT connectivity
  - "Connection refused" ≠ service down — could be network policy
  - Device connectivity must be resilient to port restrictions

---

## Incident: MQTT Broker Memory Leak After Upgrade (Apr 3, 2023)

- **Date**: April 3, 2023
- **Severity**: P2 — 1,200 devices with intermittent connectivity, all regions
- **Symptoms**:
  - Devices reported sporadic "connection reset" errors
  - MQTT broker memory usage climbed steadily post-upgrade (v2.1.0 → v2.2.0)
  - auth-service logged normal connection rates — handshakes succeeded
  - Device registry showed devices flip-flopping between online/offline
- **Root Cause**:
  - MQTT broker v2.2.0 had a memory leak in persistent session handling
  - After 18h, broker OOMed and restarted, dropping all active connections
  - Devices reconnected, but broker leaked again within hours
- **Resolution**:
  - Rolled back MQTT broker to v2.1.0
  - Vendor patched memory leak in v2.2.1
  - Added broker memory monitoring with auto-restart at 85% threshold
- **Lessons Learned**:
  - Post-upgrade monitoring must include memory trend analysis (not just immediate health)
  - "Connection reset" after successful auth points to post-handshake infrastructure
  - Intermittent issues that worsen over time suggest resource leaks
