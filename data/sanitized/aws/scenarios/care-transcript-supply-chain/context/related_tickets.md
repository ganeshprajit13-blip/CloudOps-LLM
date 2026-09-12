**Related Support and Operations Tickets**

**Ticket #7823** (March 22, 2025)
**Source**: Customer care escalation
**Product**: ProSensor Hub
**Zone**: Southeast US (FL)
**Complaint**: "My ProSensor Hub keeps shutting down in the middle of the afternoon. It's mounted in my garage and the readings go haywire before it turns off. I have to unplug it and wait 20 minutes before it comes back."
**Classification**: hardware_failure (confidence: 0.73)
**Agent notes**: Customer did not mention heat or overheating. Classified per SOP as hardware_failure.
**Assignee**: J. Rivera (Customer Care)
**Status**: Closed — Escalated to Ops

---

**Ticket #7856** (March 23, 2025)
**Source**: Customer care escalation
**Product**: ProSensor Hub
**Zone**: Southwest US (AZ)
**Complaint**: "The sensor readings are completely wrong — it says my workshop is 65°F but it's obviously much hotter in there. The humidity readings are also way off. Started happening about a week ago."
**Classification**: sensor_drift (confidence: 0.81)
**Agent notes**: Sensor readings inaccurate. No mention of overheating or device shutdown.
**Assignee**: M. Chen (Customer Care)
**Status**: Closed — Escalated to Product

---

**Ticket #7901** (March 25, 2025)
**Source**: Customer care escalation
**Product**: ProSensor Hub
**Zone**: Southeast US (GA)
**Complaint**: "My ProSensor Hub drops WiFi every couple of hours. I've reset my router, moved the hub closer, nothing helps. It worked fine for 3 months before this started. Is there a firmware issue?"
**Classification**: connectivity_issue (confidence: 0.77)
**Agent notes**: Customer suspects firmware issue. WiFi drops intermittent. Low confidence classification — could be hardware_failure.
**Assignee**: T. Nguyen (Customer Care)
**Status**: Closed — Escalated to Engineering

---

**Ticket #7934** (March 26, 2025)
**Source**: Ops team (internal)
**Subject**: Firmware rollback not reducing ProSensor Hub complaints
**Detail**: "We rolled back firmware to v3.1.2 on March 20 for all ProSensor Hub units. No change in complaint volume after 6 days. Complaints continue to cluster in Southeast and Southwest US."
**Assignee**: K. Patel (Ops Lead)
**Status**: Open — Root cause investigation ongoing
**Comments**:
> “Firmware rollback confirmed via telemetry. No behavioral change in failure patterns. Thermal throttling still present in logs — suspect hardware or environmental trigger.”

---

**Ticket #7952** (March 28, 2025)
**Source**: QA team
**Subject**: Manual classification audit reveals 40% misclassification rate for ProSensor Hub
**Detail**: "Audit of 120 randomly sampled ProSensor Hub tickets from March 18–27 shows only 32% were correctly classified as 'thermal_management'. 48% labeled 'hardware_failure', 22% 'sensor_drift', 15% 'connectivity_issue' — all incorrect under true root cause."
**Assignee**: L. Wong (QA Manager)
**Status**: Open — Priority: High
**Comments**:
> “SOP rule for 'thermal_management' requires explicit mention of 'overheating', 'hot', or 'heat'. 94% of true thermal cases lack these keywords. Automated classifier inherits this flaw. Recommend updating classification logic to infer thermal events from symptom clusters + geolocation.”

---

**Ticket #8012** (March 29, 2025)
**Source**: Supply Chain
**Subject**: Supplier component change: ProSensor Hub thermal interface pad material switch (V2.3 → V2.4)
**Detail**: "On March 15, supplier 'ThermoTech Inc.' switched from ceramic-based thermal pads (3.8 W/mK) to polymer-based pads (1.2 W/mK) for ProSensor Hub production. Approved under cost-reduction initiative (35% savings). No thermal performance validation in warm-climate environments performed."
**Assignee**: R. Desai (Supply Chain Manager)
**Status**: Open — Critical
**Comments**:
> “This change was not flagged for field impact review. Thermal pads were tested only in 25°C lab conditions. No testing in >35°C environments. Immediate recall and revert to V2.3 pads recommended.”

---

**Ticket #8045** (March 30, 2025)
**Source**: Data Science
**Subject**: [BACKLOG] Implement geospatial symptom clustering model for defect classification
**Detail**: "Build ML model to detect thermal failure clusters using transcript text patterns, geolocation, ambient temp data, and device telemetry. Train on historical tickets to identify latent thermal failure signatures (e.g., 'shuts down in afternoon', 'erratic readings', 'requires reboot') without relying on explicit thermal keywords."
**Assignee**: Unassigned
**Status**: Backlog — Priority: High
**Comments**:
> “This would have flagged the pattern 7 days before Ops even noticed the rollout. Requires access to customer location data, weather API integration, and transcript NLP pipeline. Estimated 3-week sprint.”

---

**Ticket #7988** (March 24, 2025)
**Source**: Product Team
**Subject**: Add new color option for ProSensor Hub casing (Charcoal Gray)
**Detail**: "Customer feedback requested darker casing option. Design approved. Production to begin April 1. Packaging and marketing assets updated."
**Assignee**: S. Kim (Product Designer)
**Status**: In Progress
**Comments**:
> “No relation to performance issues. Pure aesthetic change. Ignore in RCA.”

---

**Ticket #7999** (March 27, 2025)
**Source**: Warehouse Operations
**Subject**: Review pallet stacking protocol for ProSensor Hub units
**Detail**: "Received anecdotal report of units damaged during shipping. Investigating whether improper stacking caused PCB stress or connector misalignment."
**Assignee**: D. Morales (Logistics Lead)
**Status**: Closed — No issue found
**Comments**:
> “Inspected 50 returned units. No physical damage. All failures occurred after installation. Ruled out shipping as root cause.”
