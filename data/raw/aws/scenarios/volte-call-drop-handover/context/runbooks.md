VoLTE Operations Runbooks

---

**Runbook: VoLTE Call Quality Investigation**

**Service Description**:
The VoLTE service delivers voice over the LTE data network via the IMS (IP Multimedia Subsystem). Call quality is measured by call success rate, MOS score, and drop rate. Health is monitored via IMS signaling, RAN radio metrics, and CDR completeness.

**Health Check Endpoints & Thresholds**:
- `IMS_SIP_SUCCESS_RATE`: >99.5% (over 5-min window)
- `MOS_AVERAGE`: >3.8 (calculated from RTP payload analysis)
- `CDR_GENERATION_RATE`: >99.8% (compared to total call attempts)
- `SIP_RESPONSE_TIME_P95`: <150ms
- `RAN_RADIO_DROP_RATE`: <0.3% (per cell, 15-min avg)
- `X2_HANDOVER_SUCCESS_RATE`: >97% (per vendor pair)

**Initial Checks**:
1. Verify call success rate via IMS analytics dashboard — if <99.5%, investigate SIP signaling failures.
2. Check IMS core health:
   - SIP server CPU <70%, memory <80%
   - No SIP 4xx/5xx error spikes (e.g., 480 Temporarily Unavailable, 503 Service Unavailable)
3. Review tower capacity:
   - PRB utilization <80% per cell (via OMC)
   - No congestion alerts in RAN performance reports
4. Audit recent voice system deployments:
   - Check deployment logs for IMS or SBC changes in last 72 hours
5. Query CDR database for missing records:
   - `SELECT COUNT(*) FROM cdr WHERE call_end_reason = 'TIMEOUT' AND duration_minutes > 10`
   - If >5% of calls show timeout termination, suspect silent drops

**Common Causes**:
- Network congestion (tower capacity >80%)
- Voice system overload (CPU >75%, memory >85%)
- Transport network issues (packet loss >1%, latency >100ms)
- Device software issues (specific phone models with known VoLTE bugs)
- Silent handover failure (no CDR generated, no logs, metrics appear healthy)
- MME overload during high-mobility events (concerts, sporting events, rush hour)
- X2 interface instability causing excessive S1 fallback
- Codec negotiation failure on specific handset models

**Escalation**:
If all above checks pass and user complaints persist → escalate to RAN Engineering with focus on cross-vendor handover boundaries. Provide:
- List of high-complaint zones (GPS-tagged)
- CDR timeout rate by cell pair
- Date of last mobility controller config change

---

**Runbook: Handover Failure Investigation**

**Service Description**:
Handover manages seamless voice continuity as users move between cells. Two paths exist:
- Direct (X2 interface): Tower-to-tower (preferred)
- Indirect (S1): Through Mobility Management Entity (MME) — fallback

**Health Check Endpoints & Thresholds**:
- `X2_HANDOVER_SUCCESS_RATE`: >97%
- `S1_HANDOVER_SUCCESS_RATE`: >95%
- `HANDOVER_PREP_TIMER`: Configured value (check against vendor pair response times)
- `HANDOVER_EXECUTION_TIMER`: 5000ms (fixed, non-configurable)
- `S1_HANDOVER_ABORT_RATE`: <0.5%
- `MME_QUEUE_DEPTH`: <500 pending requests
- `MME_CPU_UTILIZATION`: <70%
- `X2_LINK_FLAP_RATE`: <3 state changes per hour per link

**Checks**:
1. Review handover success rates by tower pair:
   - Filter for specific vendor transitions (use vendor tags in cell metadata)
   - Note whether failures are concentrated on specific vendor pairs or spread across all pairs
2. Check X2 interface health:
   - X2 link status: UP (via MME or RAN OMC)
   - X2 error counters: <5 errors/hour per link
   - X2 flap count: <3 state changes/hour (flapping causes excessive S1 fallback)
3. Check MME health and capacity:
   - MME CPU utilization <70%
   - MME queue depth <500
   - If MME is overloaded, S1 handover response times increase regardless of timer config
4. Query mobility controller logs for handover aborts:
   - `SELECT * FROM mobility_logs WHERE event = 'HANDOVER_PREP_ABORT' AND timestamp > '<incident_start>'`
   - Check the `reason` field: TIMER_EXPIRED, MME_OVERLOAD, TARGET_REFUSED, RESOURCE_UNAVAILABLE
5. Analyze signal strength at handover boundaries:
   - RSRP < -110 dBm at time of handover attempt
   - RSRQ < -10 dB during transition
6. Validate target tower resource availability:
   - PRB usage on target cell <75% at time of handover request
7. Check for recent configuration changes to mobility parameters:
   - Any timer adjustments, threshold changes, or optimization runs in the last 72h

**Known Issues**:
- Ericsson-Nokia direct handover incompatibility (18% failure rate, stable for 6+ months)
- System automatically falls back to S1 path — S1 success depends on MME capacity and timer configuration
- Cross-vendor handovers have inherently longer response times than same-vendor due to protocol translation overhead

**Timers**:
- `handover_prep_timer`: Time MME waits for target tower response during S1 fallback (configurable per deployment)
- `handover_execution_timer`: Time phone takes to complete handover (fixed at 5000ms)

**Diagnostic Queries**:
- `SELECT avg(response_time_ms), count(*) FROM s1_handover WHERE status = 'FAILED' GROUP BY vendor_pair, hour ORDER BY hour DESC LIMIT 24`
- `SHOW CONFIG handover_prep_timer` (on MME CLI)
- `grep -i "timer expired\|abort\|overload" /var/log/mme/handover.log | wc -l`

**Escalation**:
If S1 handover abort rate >1% → escalate immediately to Core Network Engineering.
Provide:
- Handover abort reason breakdown (timer expired vs MME overload vs target refused)
- MME queue depth and CPU graphs for the incident window
- List of affected cell pairs with vendor information
- Timeline of recent mobility controller configuration changes

---

**Runbook: Missing Call Detail Records (CDR)**

**Service Description**:
CDRs are generated only upon SIP signaling completion (BYE or CANCEL). If the call ends due to radio loss without SIP teardown, CDR is not created until session timeout (15 minutes). These are logged as "timeout termination" and represent silent drops.

**Trigger Conditions**:
- CDR generated on:
  - SIP INVITE → SIP 200 OK → SIP BYE → CDR created
- CDR NOT generated on:
  - SIP INVITE → SIP 200 OK → Radio disconnect (no BYE) → Session timeout after 15 min → CDR created with `call_end_reason=TIMEOUT`

**Checks**:
1. Query for timeout-terminated CDRs:
   - `SELECT COUNT(*) FROM cdr WHERE call_end_reason = 'TIMEOUT' AND duration_minutes BETWEEN 10 AND 15 AND call_type = 'VoLTE'`
   - Normal rate: <0.2% of total calls
2. Correlate timeout CDRs with:
   - Cell handover events (join with mobility logs)
   - Location data: Are timeouts concentrated on highway corridors or vendor boundaries?
3. Check for SIP BYE absence:
   - `SELECT COUNT(*) FROM sip_signaling WHERE message = 'INVITE' AND NOT EXISTS (SELECT 1 FROM sip_signaling WHERE message = 'BYE' AND call_id = sip_signaling.call_id)`
4. Validate IMS session cleanup:
   - `SELECT avg(session_lifetime_sec) FROM ims_sessions WHERE state = 'TERMINATED'` — should be <120s; >900s indicates silent drops

**Common Failure Patterns**:
- Silent drops from failed S1 handover (no SIP BYE sent)
- Radio link loss before SIP layer can notify IMS
- MME overload causing handover to timeout silently
- Timer misconfiguration on MME causing handover to abort
- X2 flapping causing repeated handover retries that exhaust resources

**Diagnostic Commands**:
- `SELECT c.call_id, c.duration_minutes, m.event, m.timestamp FROM cdr c JOIN mobility_logs m ON c.call_id = m.call_id WHERE c.call_end_reason = 'TIMEOUT' AND m.event = 'HANDOVER_PREP_ABORT'`
- `SELECT cell_id, COUNT(*) as timeout_count FROM cdr WHERE call_end_reason = 'TIMEOUT' GROUP BY cell_id ORDER BY timeout_count DESC LIMIT 10`

**Escalation**:
If timeout CDR rate exceeds 0.5% AND correlates with handover failure zones → escalate to Core Network Engineering with:
- Top 10 cells with timeout CDRs
- Handover abort logs from MME
- Correlation between abort reasons and affected cell pairs

---

**Runbook: MME Capacity and Performance**

**Service Description**:
The Mobility Management Entity (MME) handles S1 handover signaling and UE context management. During high-mobility events or after configuration changes, MME can become a bottleneck.

**Health Check Endpoints & Thresholds**:
- `MME_CPU_UTILIZATION`: <70% (sustained)
- `MME_MEMORY_UTILIZATION`: <80%
- `MME_QUEUE_DEPTH`: <500 pending requests
- `S1_HANDOVER_RESPONSE_TIME_P95`: <1500ms
- `ACTIVE_UE_CONTEXTS`: <100,000 per MME instance

**Checks**:
1. Check MME resource utilization trends (not just current snapshot):
   - CPU trending upward over hours suggests growing load
   - Queue depth spikes correlate with handover failure spikes
2. Check for MME configuration changes:
   - Recent timer adjustments, capacity changes, or software updates
3. Compare S1 handover response times before and after suspected change:
   - `SELECT avg(response_time_ms), percentile(response_time_ms, 95) FROM s1_handover WHERE timestamp BETWEEN '<before>' AND '<after>' GROUP BY hour`
4. Check if failures are vendor-specific or universal:
   - Vendor-specific failures suggest target tower response issue or timer config
   - Universal failures suggest MME capacity issue

**Common Causes**:
- High-mobility events (concerts, sporting events) creating S1 handover storms
- Timer misconfigurations reducing tolerance for normal response times
- MME software bugs after upgrade
- Insufficient MME scaling for fleet growth

**Escalation**:
If MME queue depth >1000 OR CPU >85% → immediate P1 escalation to Core Network Engineering.

---

**Runbook: X2 Interface Monitoring**

**Service Description**:
X2 is the direct tower-to-tower interface for handovers. When X2 is healthy, handovers are fast and reliable. When X2 fails, traffic falls back to S1 through the MME.

**Health Check Endpoints & Thresholds**:
- `X2_LINK_STATUS`: UP
- `X2_ERROR_RATE`: <5 errors/hour per link
- `X2_FLAP_RATE`: <3 state changes/hour
- `X2_HANDOVER_LATENCY_P95`: <200ms

**Checks**:
1. Check X2 link status for affected tower pairs
2. Review X2 error and flap counters
3. If X2 is down or flapping → all handovers between those towers route through S1
4. Check physical layer: fiber optic health, SFP module status, CRC errors
5. Correlate X2 issues with specific geographic areas or tower sites

**Common Causes**:
- Faulty SFP modules or fiber damage
- Software incompatibility between vendor-specific X2 implementations
- Network configuration changes affecting X2 routing
- Tower site power issues affecting network equipment

---

**Decision Tree: Silent VoLTE Drop Investigation**

User reports: "Calls go silent during driving"
      |
      v
Is call success rate >99.5%? → NO → Standard call failure investigation (SIP errors, bearer issues)
      |
      v
YES → Are there spikes in CDRs with call_end_reason='TIMEOUT'?
      |
      ├── NO → Check device logs, codec issues, or transport layer problems
      |
      v
YES → Where are timeout CDRs concentrated?
      |
      ├── Spread across all cells → Check for IMS session timer misconfiguration or global MME issue
      ├── Concentrated on specific physical sites → Check X2 interface, fiber, SFP modules
      |
      v
Concentrated on vendor boundary cells → Investigate handover path
      |
      v
Check S1 handover abort rate and reasons:
      |
      ├── Reason: MME_OVERLOAD → Check MME capacity, queue depth, CPU
      ├── Reason: TARGET_REFUSED → Check target tower resources, PRB utilization
      ├── Reason: RESOURCE_UNAVAILABLE → Check radio resource allocation
      ├── Reason: TIMER_EXPIRED → Check handover timer configuration and recent changes
      |
      v
For each dominant abort reason → Investigate recent configuration changes and compare against vendor response time requirements.
Cross-reference with CMDB change log, vendor pair performance baselines, and MME processing metrics.
Monitor S1 abort rate for 4h post-remediation.

**Escalation Procedures**:
- **Tier 1 (Network Operations)**: Escalate if CDR timeout rate >0.5% or handover success <95%
- **Tier 2 (RAN Engineering)**: Escalate if issue is vendor-boundary-specific — provide vendor pair analysis and MME logs
- **Tier 3 (Core Network Engineering)**: Escalate if MME configuration change is confirmed — requires config review and change advisory board (CAB) post-mortem
- **Critical Escalation**: If user impact exceeds CSAT threshold (>10% drop) → P1 incident, notify regional service managers

**Post-Action**:
- Any config rollback must be documented in CMDB with change ID.
- Deploy monitoring alert for handover prep timer deviations from baseline
- Add to weekly RAN optimization checklist: "Validate handover timer values against cross-vendor response time P95 before any mobility tuning"
