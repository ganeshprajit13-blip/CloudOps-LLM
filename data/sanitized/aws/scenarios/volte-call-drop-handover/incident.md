**Title**: VoLTE Call Quality Degradation in Metro Region
**Severity**: P1
**Reported By**: Customer Experience Analytics Team
**Date**: April 6, 2025

**Summary**:
A sharp and sustained increase in customer complaints has been observed regarding VoLTE calls abruptly going silent during active conversations, particularly while users are in motion (e.g., driving). The issue is concentrated in the metro region and has escalated over the past week. Users report that calls initiate normally, but without warning, audio drops entirely—often with no disconnect tone or indication on the device. Despite extensive diagnostics, no clear technical root cause has been identified.

**Impact**:
- Estimated ~80 calls per day experience silent termination (based on CSAT and ticket correlation)
- Customer Satisfaction (CSAT) scores dropped 18% week-over-week
- VoLTE-related support tickets increased by 340% compared to the previous week
- Social media sentiment analysis shows a 7x increase in branded complaints mentioning “sudden silence” and “dropped calls while driving”
- No corresponding increase in dropped call metrics in core billing or voice signaling systems

**Timeline**:
- March 27–28: Normal operational baseline; no anomalous trends in call quality or support volume
- March 29: Routine network optimization activities completed across the metro region (details pending review)
- March 30 – April 5: Gradual but consistent rise in customer complaints; initial alerts triggered on April 3
- April 6: Formal incident escalation initiated after CSAT and ticket trends crossed critical thresholds

**Available Information**:
- Call success rate remains at 99.7% — within normal thresholds
- IMS (IP Multimedia Subsystem) uptime: 99.99%; no errors, alarms, or session failures logged
- Cell tower utilization: 45–60% across all affected sectors — no congestion observed
- Coverage maps show no new outages, interference, or signal degradation in complaint hotspots
- Device-level diagnostics (via telemetry) show no pattern of handset-specific failures
- No firmware updates, hardware replacements, or software patches deployed in the core network during this period
- Handover events between towers appear to complete successfully in monitoring tools — no handover failure counters elevated
- Voice call records do not reflect termination events for affected calls — sessions remain open for ~15 minutes before timeout

**Open Questions**:
- Are all cell towers or regions affected equally, or is this concentrated in certain areas?
- Were there any configuration changes, firmware updates, or optimization exercises in the past 2 weeks?
- Do affected users report consistent patterns (e.g., specific routes, times of day, or tower transitions)?
- Are there any non-standard inter-vendor handover zones in the metro region?

No system-level alarms or error logs have been triggered. The issue appears invisible to standard monitoring frameworks, yet the customer impact is severe and unmistakable.
