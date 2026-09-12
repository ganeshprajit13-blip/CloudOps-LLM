Defect Classification Pipeline Architecture

---

### System Overview and Purpose

The Defect Classification Pipeline is a batch-processing system designed to automate the triage of customer care transcripts for the ProSensor Hub product line, enabling rapid identification of operational and supply chain defects. With ~1,800 daily customer contacts across all product lines, manual classification is infeasible. The pipeline applies Standard Operating Procedure (SOP) rules to transcribed call data to assign defect categories (e.g., “thermal_management”, “connectivity_issue”, “sensor_drift”) and feed trends into the Ops Insights Dashboard.

The system’s critical purpose is to surface root causes of product failures — particularly those tied to supply chain changes — by accurately classifying symptom descriptions into standardized defect categories. However, due to an outdated SOP rule design that requires explicit thermal keywords (e.g., “overheating”, “hot”), 40% of thermal-related failures are misclassified. This masks a systemic thermal performance degradation caused by a March 15 supplier component change, leading to misdirected corrective actions and prolonged customer impact in warm-climate zones.

---

### Service Topology

#### 1. **Transcript Ingestion**
- **Care Transcript Pipeline**:
  Receives encrypted call recordings from the CRM system (Twilio/Zoom integration). Runs batched speech-to-text (AWS Transcribe) with speaker diarization. Outputs structured JSON transcripts with metadata: `customer_id`, `product_line`, `serial_number`, `installation_zone` (geocoded from billing address), `call_duration`, `call_timestamp`, `agent_id`.
  *Batch window*: Every 4 hours (00:00, 04:00, 08:00, 12:00, 16:00, 20:00 UTC).

- **NLP Extraction Service**:
  Uses spaCy + custom entity recognizers to extract:
  - Symptom phrases (e.g., “device keeps shutting down”, “readings are erratic”)
  - Failure modes (e.g., “WiFi drops”, “sensor offline”)
  - Sentiment score (0–1, negative if >0.7)
  - Urgency indicators (e.g., “never worked”, “my whole house is dark”)
  Outputs enriched transcript with NLP annotations: `symptoms: [str]`, `failure_modes: [str]`, `sentiment: float`, `urgency: enum{low, medium, high}`

#### 2. **Classification Engine**
- **Defect Classifier**:
  Core service that applies prioritized SOP rules to NLP-extracted entities.
  Rule evaluation:
  - Rules are ordered by priority (1 = highest).
  - Each rule: `trigger_keywords`, `exclude_keywords`, `confidence_threshold`, `category`
  - First rule with ≥ confidence_threshold match wins.
  - If no rule matches → “unclassified”
  - Outputs: `classification: str`, `confidence: float`, `matched_rule_id: str`, `matching_phrases: [str]`

- **SOP Rule Engine**:
  Manages rule lifecycle: versioned YAML definitions stored in S3 (`s3://ops-sop-rules/v4.2/rules.yaml`).
  Rules are loaded at pipeline start.
  **Critical Rule (v4.2)**:
  ```yaml
  id: thermal_management_v4
  category: thermal_management
  trigger_keywords: ["overheating", "hot", "heat", "too warm", "burning"]
  exclude_keywords: ["not hot", "cool", "air conditioned"]
  confidence_threshold: 0.85
  priority: 1
  ```
  *Issue*: Fails to match implicit thermal symptoms (e.g., “shuts down after 2 hours”, “stops working in the garage”).

#### 3. **Operational Analytics**
- **Ops Insights Dashboard**:
  Aggregates classified defects by:
  - Product line
  - Installation zone (latitude/longitude → climate zone mapping: “warm_climate” = avg. temp > 28°C)
  - Time series (hourly/daily volume)
  - Top 10 symptom phrases per category
  Dashboard refreshes hourly via scheduled Lambda.
  *Critical gap*: No geographic correlation overlay between defect category and climate zone — heatmaps show noise, not signal.

- **Batch Scheduler**:
  Orchestration service (Apache Airflow v2.6) with DAG:
  `ingest_transcripts → extract_nlp → classify_defects → update_dashboard → archive_raw`
  Each step is idempotent. Retries: 3. Timeout: 15 min per batch.

#### 4. **Supply Chain Integration**
- **Supply Chain Events Log**:
  Kafka topic (`supply_chain_events`) receiving updates from procurement system.
  Events include:
  - `component_swap`: `{product_line: "ProSensor Hub", component: "thermal_pad", old_spec: "ceramic_3.8W", new_spec: "polymer_1.2W", date: "2026-03-15", supplier: "ThermoTech Inc."}`
  - `batch_id`: Used to cross-reference serial numbers in transcripts
  *Current limitation*: No automated linkage between component change events and defect classification trends. Manual correlation required.

---

### Data/Request Flow Diagram (ASCII)

[Call Recordings]
        ↓ (every 4h)
[Care Transcript Pipeline] → JSON: {customer_id, serial_number, installation_zone, transcript_text}
        ↓
[NLP Extraction Service] → Enriched JSON: {symptoms: [...], failure_modes: [...], sentiment: 0.82, urgency: high}
        ↓
[Defect Classifier] → Applies SOP Rule v4.2 → Classification: "connectivity_issue" (false positive)
        ↓
[Batch Scheduler] → Aggregates 4h batch → Writes to analytics DB
        ↓
[Ops Insights Dashboard] → Displays: "connectivity_issue ↑ 120%", "sensor_drift ↑ 95%", "thermal_management ↑ 8%" ← MISLEADING
        ↑
[Supply Chain Events Log] → Kafka: {"component_swap": "polymer_1.2W", "date": "2026-03-15"} ← UNLINKED

*Note: True root cause ("thermal_management") is buried under 40% misclassification. Geographic clustering (warm zones) is visible in raw data but not surfaced in dashboard.*

---

### Key Configuration Parameters

| Parameter | Service | Meaning | Current Value | Risk |
|---------|---------|---------|---------------|------|
| `trigger_keywords` | SOP Rule Engine | Words that trigger category assignment | `["overheating", "hot", "heat"]` | ❌ Too narrow — excludes implicit thermal symptoms |
| `confidence_threshold` | Defect Classifier | Minimum confidence for rule match | 0.85 | ❌ Too high for symptom-based classification; reduces recall |
| `priority` | SOP Rule Engine | Order of rule evaluation | `thermal_management = 1` | ⚠️ Correct priority, but rule is ineffective |
| `installation_zone` | Transcript Ingestion | Geocoded region from customer address | `["warm_climate", "temperate", "cold_climate"]` | ✅ Accurate — underutilized |
| `batch_interval` | Batch Scheduler | Frequency of pipeline runs | `4 hours` | ✅ Appropriate for volume |
| `link_component_change_to_transcripts` | Supply Chain Integration | Auto-match serial numbers to component batch ID | `false` | ❌ Critical gap — prevents automated RCA |

---

### Monitoring and Alerting Setup

#### Current Monitoring:
- **Pipeline Health**:
  - CloudWatch alarms on:
    - `BatchFailureCount > 0` → PagerDuty alert
    - `NLP_Extraction_Latency > 150s` → Slack alert
    - `Unclassified_Transcripts > 10%` → Slack alert
- **Classification Metrics**:
  - Dashboard tracks: `classification_accuracy` (based on 5% manual sample audit), `top_categories`, `volume_by_zone`
- **SOP Rule Version**:
  - S3 object versioning enabled; audit trail via CloudTrail

#### Critical Gaps:
1. **No Recall/Precision Tracking**:
   - Only precision (false positives) is measured via manual audit.
   - **Recall is unknown** — we don’t know how many true thermal cases are missed.
   - *Impact*: 0.31 recall for thermal_management is invisible → team believes issue is “low volume”.

2. **No Geographic Correlation Alert**:
   - No alert when “connectivity_issue” or “sensor_drift” spikes in warm_climate zones.
   - *Impact*: True signal (thermal failures in warm zones) is buried as noise.

3. **No Supply Chain Event Correlation**:
   - No automated trigger when component change occurs + defect category spikes in same product line.
   - *Impact*: Requires manual cross-referencing — delays RCA by 3–5 days.

4. **No Feedback Loop**:
   - Ops team cannot flag misclassifications back into rule engine.
   - Rules are updated quarterly — no agile feedback.

---

### Recent Changes or Maintenance Windows

| Date | Change | Impact | Notes |
|------|--------|--------|-------|
| 2026-03-15 | Supplier switched thermal pads (ceramic → polymer) | Triggered thermal throttling in warm zones | Not logged in system until March 22 |
| 2026-03-20 | Customer care volume for ProSensor Hub ↑ 240% | Dashboard overloaded, 2 delayed batches | No escalation to RCA team |
| 2026-03-22 | Ops team initiated “WiFi antenna recall” | Misdirected effort — 0% improvement | Based on misclassified “connectivity_issue” |
| 2026-03-25 | SOP Rule v4.2 deployed (Feb 1 update) | No change to thermal rule | Last update was Feb 1 — no revision since component change |
| 2026-03-28 | Manual audit revealed 40% misclassification | Internal memo circulated | No action taken to fix pipeline |
| 2026-04-01 | Maintenance window: Airflow DAG restart | Pipeline resumed normally | No rule or logic update performed |

*Note: No change to the defect classifier’s logic since February 1 — despite known component change and rising failure volume. The system is operating as designed, but the design is fundamentally flawed for detecting implicit thermal failures.*
