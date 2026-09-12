related_tickets.md

---

### **Related Tickets**

#### **JIRA-10472**
**Assignee**: Dev Team - Auth Services
**Status**: Resolved
**Description**: Deploy auth-service v3.8.0 with Certificate Transparency validation behind feature flag `ct_validation_enabled=true` for North American regions (us-*, ca-*)
**Comments**:
> Deployed at 02:00 Day 1 as part of security hardening initiative. Feature flag is scoped to NA only. No monitoring added for external CT service latency.
> *Note: Feature flag documentation was added to Confluence 48h after deploy — too late for on-call teams to reference during incident.*
> *Link to commit: https://git.example.com/auth-service/commit/abc123*

---

#### **JIRA-10511**
**Assignee**: Observability Team
**Status**: Backlog
**Description**: Implement external dependency latency monitoring and alerting for auth-service CT validation calls
**Comments**:
> This ticket was created post-incident during RCA. Proposed solution:
> - Add distributed tracing for CT validation calls
> - Set alert threshold at 5s latency (P95) with 1m window
> - Integrate with PagerDuty and include feature flag context in alert payload
> *Currently unassigned; prioritized as P1 for next sprint.*
> *Suggested metric: `auth_ct_validation_latency_seconds`*

---

#### **JIRA-10489**
**Assignee**: Device Registry Team
**Status**: In Progress
**Description**: Optimize device registry query performance to reduce connection handshake latency
**Comments**:
> Team observed high DB load during incident and assumed registry was bottleneck.
> Logs show registry queries are sub-100ms even during peak disconnects.
> This ticket is a red herring — registry errors were symptom of devices failing to connect, not cause.
> *Work paused pending RCA outcome.*

---

#### **JIRA-10495**
**Assignee**: Certificate Rotator Team
**Status**: Resolved
**Description**: Rotate all device certificates in NA region ahead of TLS 1.3 enforcement
**Comments**:
> Certificates were rotated on Day 1 at 01:00 — 1h before auth-service deploy.
> All rotated certs are valid and properly signed.
> Incident timeline shows devices failed *after* cert rotation — correlation ≠ causation.
> *Team received blame in initial triage; cleared after log analysis.*

---

#### **JIRA-10503**
**Assignee**: Metrics Aggregator
**Status**: In Review
**Description**: Add support for streaming device telemetry with retry backoff metadata
**Comments**:
> This ticket was opened to improve telemetry accuracy during outages — but the backoff logic is already implemented client-side.
> Aggregator saw 1.2M dropped packets during incident, but this is a *result* of disconnections, not a root cause.
> *Work continues, but scope will be revised post-RCA.*

---

#### **JIRA-10518**
**Assignee**: NA Regional Ops
**Status**: Closed
**Description**: Investigate intermittent connectivity drops in Ontario factories (reported by customer)
**Comments**:
> Two customer tickets filed on Day 1 afternoon — both resolved by rebooting local gateways.
> No correlation to fleet-wide outage.
> *Incident responders initially merged these into main ticket — later de-duplicated.*
> *Customer satisfied after manual reconnect.*
