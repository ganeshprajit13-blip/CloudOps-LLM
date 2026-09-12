# VoLTE Network Architecture

## System Overview and Purpose

The VoLTE (Voice over LTE) network delivers high-quality voice calls over the 4G LTE packet-switched data network using IP Multimedia Subsystem (IMS) protocols. Unlike legacy circuit-switched voice, VoLTE decouples radio access from call control, enabling seamless integration with data services and higher spectral efficiency. The architecture is designed for low-latency, high-reliability voice delivery, with call state managed by SIP signaling in the IMS core and radio connectivity managed by the Evolved Packet Core (EPC) and Radio Access Network (RAN).

The system's critical challenge lies in its loosely coupled design: radio handovers (managed by RAN and MME) operate independently of voice session state (managed by IMS). This separation enables scalability but introduces blind spots — particularly when radio failures occur without corresponding SIP teardown signals, resulting in silent call drops that evade standard monitoring.

## Service Topology

### Radio Access Network (RAN)
- **eNodeB (Cell Towers)**: Physical base stations providing radio coverage. Two vendors deployed:
  - **Ericsson (Vendor A)**: ~60% of towers; newer hardware, optimized X2 handover support.
  - **Nokia (Vendor B)**: ~40% of towers; legacy firmware; slower S1 fallback response times.
- **Handover Methods**:
  - **Direct (X2)**: eNodeB-to-eNodeB coordination; used when both towers are same-vendor or compatible. Latency: ~400ms.
  - **Indirect (S1)**: eNodeB → MME → Target eNodeB; triggered when direct handover fails (e.g., cross-vendor boundaries). Latency: ~800ms.

### Core Network (EPC)
- **Mobility Management Entity (MME)**:
  - Central handover orchestrator for S1 handovers.
  - Manages UE context, authentication, and mobility state.
  - **Critical Configuration**: `handover_prep_timer` — maximum time (in ms) MME waits for target eNodeB to acknowledge handover preparation.
- **Serving Gateway (S-GW)**:
  - Maintains user plane tunnels during handovers.
  - Forwards downlink packets to the target eNodeB after handover completion.
- **Home Subscriber Server (HSS)**:
  - Central database for user profiles, authentication keys, and VoLTE subscription status.
- **Policy and Charging Rules Function (PCRF)**:
  - Enforces QoS policies for voice traffic (e.g., QCI-1 bearer with 100ms latency budget).

### Voice System (IMS)
- **Proxy-CSCF (P-CSCF)**:
  - First SIP contact point for UE; relays INVITE/BYE messages to S-CSCF.
- **Serving-CSCF (S-CSCF)**:
  - Maintains active call state; initiates SIP BYE on call termination.
  - Communicates with MME via SIP over Diameter for supplementary services (e.g., emergency, call forwarding).
- **Call Detail Record (CDR) Mediation**:
  - Generates billing and analytics records based *only* on SIP signaling events (INVITE, 200 OK, BYE, 487 Request Terminated).
  - **Critical Gap**: Does not correlate with radio layer events (e.g., RRC Connection Release).

## Data/Request Flow Diagrams

### Normal VoLTE Call Flow (SIP + RAN)
[UE] --(INVITE)--> [P-CSCF] --(INVITE)--> [S-CSCF] --(SIP)--> [Remote UE]
   |                   |                         |
   | (RRC Conn Req)    |                         |
   +---> [eNodeB] -----> [MME] -----> [Target eNodeB] (X2/S1 Handover)
   |                   |                         |
   | (RRC Conn Rel)    |                         |
   +---> [eNodeB] -----> [MME] -----> [Target eNodeB]
   |                   |                         |
   | (BYE)             |                         |
   +---> [P-CSCF] <---- [S-CSCF] <---- [Remote UE]

### Silent Call Drop Flow (Root Cause Scenario)
[UE] --(Voice Active)--> [Ericsson eNodeB]
                         |
                         | (User drives into Nokia coverage)
                         v
[Ericsson eNodeB] --(Handover Request)--> [MME]
                         |
                         | (MME sends Handover Required to Nokia eNodeB)
                         | (Nokia eNodeB takes 800ms to respond — legacy firmware)
                         |
                         v
[MME] --(handover_prep_timer=500ms EXPIRED)--> ABORT HANDOVER
                         |
                         | (No BYE sent to S-CSCF — SIP session remains active)
                         v
[UE] remains connected to Ericsson eNodeB — signal degrades
                         |
                         v
[Ericsson eNodeB] --(RRC Connection Release)--> [UE] (Radio drop)
                         |
                         | (No SIP BYE — session not terminated)
                         v
[IMS] --(Session remains active for 15 min)--> Timeout (no CDR generated)
                         |
                         v
USER EXPERIENCE: Call goes silent — no error, no disconnect tone

## Key Configuration Parameters and Meanings

| Parameter | Service | Default | Changed Value | Meaning |
|---------|---------|---------|---------------|---------|
| `handover_prep_timer` | MME | 2000ms | **500ms** (Mar 29) | Maximum time MME waits for target eNodeB to respond to handover preparation request. If exceeded, MME aborts handover and retains UE on source cell. |
| `x2_handover_enabled` | eNodeB | true | true | Enables direct tower-to-tower handover. Only works reliably between same-vendor towers. |
| `s1_handover_timeout` | eNodeB | 1500ms | 1500ms | Time eNodeB waits for MME response during S1 handover. Not the root cause. |
| `qci_1_preemption` | PCRF | enabled | enabled | Ensures voice bearer gets priority; unrelated to handover failure. |
| `sip_session_timeout` | S-CSCF | 900s (15 min) | 900s | Duration before IMS terminates orphaned SIP sessions. Only cleans up silent drops — does not detect them. |

## Monitoring and Alerting Setup

### Current Monitoring
- **Call Success Rate**: Monitored at IMS level — based on SIP INVITE → 200 OK success. **99.7%** — appears healthy.
- **RRC Connection Success Rate**: Monitored per eNodeB — >99.5% — no alerts.
- **MME Handover Success Rate**: Monitored globally — 98.2% — no alerts because aborts are counted as “successful fallback” (not failures).
- **CDR Volume**: Monitored hourly — no drop detected.
- **CSAT & Support Tickets**: Unmonitored as system KPIs — only reviewed reactively.

### Critical Gaps
1. **No correlation between radio events and SIP sessions**: RRC Connection Release events are not logged in IMS or CDR systems.
2. **MME handover aborts are not flagged as failures**: System treats aborted S1 handovers as “normal fallback” — no alerting on high abort rates.
3. **No vendor-specific handover success tracking**: No dashboards differentiate Ericsson→Nokia handovers from same-vendor handovers.
4. **No real-time silence detection**: No audio packet loss monitoring or RTP stream analysis integrated into VoLTE monitoring stack.
5. **CSAT and social sentiment not ingested**: User complaints are treated as “customer experience” — not system health indicators.

## Recent Changes or Maintenance Windows

- **Mar 29, 02:00 UTC**: Network Optimization Team executed routine “capacity tuning” on MME cluster.
  - **Change**: `handover_prep_timer` reduced from **2000ms → 500ms**.
  - **Justification**: “Improved handover latency in high-density urban zones based on lab simulations.”
  - **Scope**: Applied to all MME instances — no vendor-specific exceptions.
  - **Testing**: Only same-vendor (Ericsson→Ericsson) handovers tested; cross-vendor (Ericsson→Nokia) scenarios were excluded from test plan.
- **Mar 30–Apr 6**: No other maintenance windows. No firmware updates, no hardware replacements.
- **Apr 7**: CSAT dropped 18%; support tickets increased 340%. Initial investigation focused on coverage maps and tower load — all within thresholds. Root cause remained hidden until handover abort logs were manually correlated with cross-vendor boundary data.
