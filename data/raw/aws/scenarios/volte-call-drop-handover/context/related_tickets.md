**Related Support Tickets**

**Ticket #4521** (April 3, 2025)
**Assignee**: Customer Support Team
**Status**: Closed - User Issue
**Description**: Customer in downtown metro area reports VoLTE calls drop daily during commute on Highway 101 northbound. Call begins normally but goes silent after 5–10 minutes. Route crosses from Ericsson tower sector 42A to Nokia tower sector 18C.
**Comments**: Coverage maps show strong signal throughout route. Device diagnostic shows no anomalies. User confirmed issue persists with multiple phones. Attributed to in-car signal interference. Closed as customer-side issue.

---

**Ticket #4547** (April 4, 2025)
**Assignee**: Field Support Engineer
**Status**: Open - Monitoring
**Description**: Customer reports VoLTE calls drop consistently while driving. Switching to 3G resolves issue. Requested to keep VoLTE enabled for diagnostic tracing.
**Comments**: User confirmed issue occurs only on cross-vendor handover zones. No errors in device logs. Voice session remains active after audio loss. Suggested to correlate with mobility controller handover logs. Awaiting telemetry data from next 72h.

---

**Ticket #4589** (April 5, 2025)
**Assignee**: Enterprise Account Team
**Status**: Escalated to Network Operations
**Description**: Enterprise client (200 users) reports widespread VoLTE call drops among sales team traveling between offices. All routes cross Ericsson-Nokia boundaries. Voice system logs show 99.7% success rate.
**Comments**: CDRs show no dropped calls. Sessions remain active 10–15 minutes after users report silence. Suspect hidden handover failure. Escalated to Mobility Controller team for timer and handover success rate analysis.

---

**Ticket #4612** (April 5, 2025)
**Assignee**: IMS Platform Team
**Status**: Open - Zombie Session Investigation
**Description**: User experienced “silent call” while walking between buildings. Phone showed active call for 10+ minutes with no audio. User force-closed app to terminate.
**Comments**: IMS session remained active for 14m 32s before timeout. No BYE or ERROR signaling received. Confirmed as “zombie session” — consistent with unreported radio disconnection. Correlating with handover events from mobility controller.

---

**Ticket #4628** (April 6, 2025)
**Assignee**: Billing & CDR Team
**Status**: Open - Root Cause Analysis
**Description**: CDR mediation system reports 80 missing call records per day over past week. System health checks pass. No errors in ingestion pipeline.
**Comments**: Missing CDRs correspond to sessions that were never terminated via SIP BYE. All affected calls originated in Ericsson-Nokia handover zones. Suspected link to silent radio drop + IMS session timeout. Forwarded to Mobility Controller team for configuration review.

---

**Ticket #MOB-771** (April 7, 2025)
**Assignee**: Network Optimization Team
**Status**: Closed - Completed
**Description**: Routine performance tuning: Reduced handover_prep_timer on all MMEs from 2000ms to 500ms to improve handover latency during peak hours. Deployed March 29.
**Comments**: Approved per standard optimization protocol. No impact assessment performed for cross-vendor handover scenarios. Post-deploy monitoring focused only on average handover success rate — did not segment by vendor pair. This change is the confirmed root cause.

---

**Ticket #MON-1034** (April 8, 2025)
**Assignee**: Unassigned
**Status**: Backlog - Priority High
**Description**: Implement real-time monitoring for silent VoLTE call drops: detect IMS sessions active >5 minutes with no RTP activity + associated radio link failure events in handover zones.
**Comments**: Proposed solution: Correlate SIP session duration, RTP packet loss, and RRC connection release events across vendor boundaries. Requires new correlation engine. Needs funding and engineering bandwidth. High impact if implemented — would have caught this incident on Day 1.

---

**Ticket #FW-2201** (April 3, 2025)
**Assignee**: Firmware Team
**Status**: In Progress
**Description**: Upgrade firmware on 120 Ericsson macro towers to v4.2.1 to fix GPS sync drift. Scheduled for weekend rollout.
**Comments**: Unrelated to VoLTE drop issue. GPS drift affects timing alignment but not handover signaling. No impact on MME timers or IMS sessions. Customer reported no call issues tied to this upgrade.

---

**Ticket #QOS-887** (April 5, 2025)
**Assignee**: QoS Engineering
**Status**: Closed - Won’t Fix
**Description**: Feature request: Add “call quality score” to customer app based on MOS values.
**Comments**: Requested by marketing team for customer-facing app. MOS scores are already calculated internally but not exposed. Not relevant to silent drop root cause. Declined due to low ROI and resource constraints.
