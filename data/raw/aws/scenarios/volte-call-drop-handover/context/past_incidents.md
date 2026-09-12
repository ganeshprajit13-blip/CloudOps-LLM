VoLTE Historical Incidents

---

**Incident: S1 Handover Path Congestion During Stadium Events (Mar 15, 2025)**
**Symptoms**: VoLTE calls dropped during handover near stadium venues during large sporting events. Users report "call went silent then reconnected after 10 seconds." CDR records showed elevated timeout-terminated calls in specific cell clusters. Call success rate dipped to 98.9% in affected zones.
**Root Cause**: S1 handover path through the MME became congested when 40,000+ users moved between cells simultaneously. MME processing queue backed up, causing S1 handover response times to exceed 3000ms. Handover prep timer (2000ms) expired before MME could respond.
**Resolution**: Added MME capacity (scaled from 2 to 4 instances). Implemented load-based handover routing to distribute S1 requests. Added MME queue depth monitoring.
**Lessons**: MME congestion under high-density mobility looks similar to timer misconfiguration — both result in handover prep timeouts. Differentiate by checking MME queue depth and CPU, not just timer values. Congestion-driven failures affect ALL vendor pairs equally, not just cross-vendor.

---

**Incident: IMS Session Timeout Misconfiguration (Feb 18, 2025)**
**Symptoms**: Calls end abruptly after 12 minutes with no warning. Users report "call disconnected out of nowhere." Similar CSAT and ticket spikes.
**Root Cause**: IMS session timer misconfigured to 720 seconds (12 min) instead of 900 seconds. Normal VoLTE calls with brief silence (e.g., pause in conversation) triggered premature session cleanup.
**Resolution**: Adjusted IMS session timer to 900s. Added alert for session cleanup events exceeding 10% of total active calls.
**Lessons**: Session timers can cause phantom call drops that mimic coverage issues. Unlike handover failures, these show up in IMS session logs — but were missed due to focus on radio metrics.

---

**Incident: Cell Tower Power Reduction (Jan 12, 2025)**
**Symptoms**: Regional drop in VoLTE call quality. Users report static and silence during driving. "Radio link failure" events increased 200% in affected zones.
**Root Cause**: Energy optimization initiative reduced transmit power on 400 low-traffic towers by 3dB to cut electricity costs. Signal degraded at edge of coverage, triggering radio link timeouts.
**Resolution**: Restored power levels. Implemented power reduction policy requiring signal margin validation before deployment.
**Lessons**: Radio-level changes cause visible ERROR logs in tower logs and RRC connection failures. Unlike silent handover timer issues, this affected all handover types — not just cross-vendor. Coverage maps would have flagged this.

---

**Incident: SIP Re-INVITE Timeout (Dec 5, 2024)**
**Symptoms**: 15% of VoLTE calls experience 5–10 second delays before audio starts, then drop. "SIP 408 Timeout" errors in proxy logs.
**Root Cause**: P-CSCF re-INVITE timeout reduced from 15s to 5s to improve call setup speed. Failed to account for slow media negotiation on legacy handsets.
**Resolution**: Increased timeout to 12s. Added media negotiation latency monitoring.
**Lessons**: SIP-level timeouts produce clear error codes and are logged in voice proxy systems. This was a signaling failure, not a radio handover failure. Call success rate dipped to 98.2% — unlike silent handover cases.

---

**Incident: GPS Clock Drift in eNodeBs (Oct 22, 2024)**
**Symptoms**: Intermittent handover failures, "timing advance out of sync" errors. Calls dropped only during high-speed movement.
**Root Cause**: GPS receivers on 80 Nokia eNodeBs drifted by 300ms due to firmware bug. Handover timing windows failed because of clock misalignment between towers.
**Resolution**: Patched GPS firmware, synchronized clocks via NTP.
**Lessons**: Timing-related handover failures produce clear ERROR logs in tower logs and MME handover request rejections. Unlike silent timer issues, this affected all vendor pairs and was detectable via timestamp anomalies.

---

**Incident: Subscriber Profile Corruption (Sep 8, 2024)**
**Symptoms**: 5% of users experience "call failed" on VoLTE setup. "Bearer setup failed" and "QCI-1 invalid" errors.
**Root Cause**: HSS batch update corrupted QCI-1 (VoLTE) profile settings for 120K subscribers.
**Resolution**: Restored HSS snapshot, re-provisioned affected users.
**Lessons**: Authentication or bearer failures are immediately visible in core network logs. Not silent. Always accompanied by explicit error codes. Correlates with specific IMSI ranges, not geographic zones.

---

**Incident: X2 Interface Flapping Between Co-Located Towers (Jul 29, 2024)**
**Symptoms**: Intermittent VoLTE call drops in dense urban areas. Both Ericsson and Nokia towers affected. X2 link status toggled UP/DOWN every 30-60 seconds.
**Root Cause**: Fiber optic link between co-located tower sites had a faulty SFP module causing CRC errors. X2 interface flapped, causing direct handover to fail and fallback to S1.
**Resolution**: Replaced SFP module. Added X2 link flap monitoring (alert if >3 state changes per hour).
**Lessons**: X2 flapping forces S1 fallback — which may succeed or fail depending on MME load and timer config. Unlike timer issues, X2 flapping is visible in network monitoring and affects specific physical links, not vendor boundaries.
