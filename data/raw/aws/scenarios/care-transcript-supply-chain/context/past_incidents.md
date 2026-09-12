# Classification Pipeline Historical Incidents

## Incident: Humidity-Related Sensor Failures Misclassified as Hardware Defects (October 2024)
**Symptoms**: 180% spike in complaints classified as “hardware_failure” for ProSensor Hub. Geographic clustering in Gulf Coast and Pacific Northwest regions. Returned units passed all bench tests in the lab.

**Root Cause**: A conformal coating supplier changed their formula to reduce VOC emissions. The new coating had lower moisture resistance, allowing condensation to form on sensor PCBs in high-humidity environments (>80% RH). This caused intermittent sensor failures that customers reported as “device is broken” or “readings are garbage.” The classifier categorized these as hardware_failure because the SOP rule triggers on “broken” and “not working” keywords, but the actual failure mode was environmental — devices recovered when moved to dry environments.

**Resolution**: Added humidity and condensation indicators to the classification pipeline. Updated SOP: if returned units pass bench tests, cross-reference installation environment (humidity data, indoor/outdoor placement) before confirming hardware_failure. Added “intermittent in humid conditions” as a new sub-category under environmental_sensitivity.

**Lessons**: Environmental failure modes often masquerade as hardware defects when customers describe symptoms in absolute terms (“it’s broken”) rather than conditional terms (“it fails when...”). Classification rules must account for the gap between customer language and technical failure mode. Bench testing in controlled lab conditions can miss environmental triggers.

---

## Incident: WiFi Antenna Firmware Glitch (May 2024)
**Symptoms**: 160% increase in "connectivity_issue" complaints across Midwest and Northeast. Customers reported intermittent WiFi drops and device unresponsiveness.

**Root Cause**: Firmware v2.8 introduced a bug in the 5GHz WiFi power management module. Devices in homes with metal siding or dense building materials dropped connection under load. No thermal involvement.

**Resolution**: Rolled back firmware to v2.7. Issued OTA patch for affected units.

**Lessons**: Connectivity drops can be firmware-induced, not environmental. Always isolate hardware vs. software failure modes before updating classification rules. Misclassification of this incident as thermal would have led to incorrect component replacement.

---

## Incident: Warehouse Handling Damage (November 2024)
**Symptoms**: 120% spike in "hardware_failure" complaints from customers in the Pacific Northwest. Devices arrived with cracked PCBs and non-functional sensors.

**Root Cause**: New logistics partner used cheaper foam inserts that compressed under weight during long-haul transit. Units shipped in bulk pallets suffered mechanical stress. Complaints correlated with shipping origin (Midwest distribution center), not climate.

**Resolution**: Switched to high-density ESD foam. Added visual inspection step at outbound QA.

**Lessons**: Hardware failures can stem from logistics, not design. Geographic clustering due to shipping routes ≠ environmental failure. Temperature data must be cross-checked with shipment logs.

---

## Incident: Sensor Calibration Drift (February 2025)
**Symptoms**: Surge in "sensor_drift" complaints. Customers reported "readings are off by 15–30%" — especially in humid environments.

**Root Cause**: A new batch of humidity sensors from a secondary vendor had a calibration offset in high-moisture conditions. No thermal component. Affected units were shipped to coastal regions (Florida, Gulf Coast).

**Resolution**: Quarantined affected sensor batch. Recalibrated inventory. Updated incoming QC spec to include humidity stress test.

**Lessons**: Sensor drift ≠ thermal throttling. Both can produce "erratic readings", but root causes differ. Classification must distinguish between sensor failure, environmental interference, and thermal artifact.

---

## Incident: False "Firmware Bug" Flag (August 2024)
**Symptoms**: Spike in "firmware_bug" classifications after v3.0 launch. Customers complained “app shows offline but device is powered”.

**Root Cause**: Users mistook device sleep mode (introduced in v3.0 to extend battery life) for a crash. Device was functioning — just not broadcasting status. No actual bug.

**Resolution**: Updated user manual and in-app help. Added clarification to SOP: “device appears offline” ≠ “device failed”. Classification rule now requires confirmation of power state and sensor data latency.

**Lessons**: User perception ≠ system failure. Automated classifiers must differentiate behavioral changes from actual defects. Avoid over-labeling based on emotional language (“it’s broken!”).

---

## Incident: Seasonal Power Surge Damage (July 2023)
**Symptoms**: 90% increase in "hardware_failure" complaints during summer thunderstorms. Devices in rural areas fried.

**Root Cause**: Lack of surge protection in units shipped to regions with unstable grid power. Lightning-induced voltage spikes destroyed power regulators.

**Resolution**: Added transient voltage suppression (TVS) diodes to BOM. Issued retrofit kit for affected units.

**Lessons**: Environmental stress ≠ thermal stress. Power anomalies cause catastrophic failure, not throttling. Must not confuse thermal shutdown (reversible) with hardware burnout (permanent).

---

### Comparison Table: Distinguishing Failure Modes

| Failure Mode | Primary Symptom | Key Clues | Geographic Pattern | Environmental Trigger | Classification Trigger |
|--------------|------------------|-----------|---------------------|------------------------|-------------------------|
| **Humidity/Condensation** | Intermittent sensor failures, “readings are garbage” | Passes bench tests, fails in field, recovers in dry conditions | Gulf Coast, Pacific Northwest | High humidity (>80% RH) | Symptom + installation environment + bench test result |
| **WiFi Firmware Glitch** | Intermittent WiFi drop | “Connects then drops”, “works in other rooms”, “no heat reported” | Urban/suburban, metal-framed homes | None | Symptom + firmware version + no environmental keywords |
| **Warehouse Damage** | Physical damage, broken sensors | “Box was crushed”, “cracked casing”, “purchased in Midwest” | Correlates with shipping origin | None | Symptom + damage visual description + shipping origin |
| **Sensor Calibration Drift** | Sensor readings inaccurate | “Feels wrong”, “compared to thermometer”, “humidity high” | Coastal, humid regions | High humidity (>70% RH) | Symptom + humidity metadata + sensor batch ID |
| **False Firmware Bug** | Device appears offline | “Power light on”, “app says offline”, “no error code” | Nationwide | Sleep mode behavior | Symptom + power state confirmation + sleep mode flag |
| **Power Surge Damage** | Device completely dead, no power | “Struck by lightning”, “power outlet sparked”, “smell of burnt plastic” | Rural, areas with grid instability | Lightning, voltage spikes | Symptom + power surge event log |

> **Critical Insight**: Environmental failure modes (thermal, humidity, power) produce symptoms that customers describe in generic terms (“broken”, “stops working”, “readings off”). The key differentiator is whether the failure is *intermittent and condition-dependent* vs. *permanent*. Always cross-reference complaint patterns with geographic/environmental data and supplier change logs — customer language alone is insufficient for accurate classification.
