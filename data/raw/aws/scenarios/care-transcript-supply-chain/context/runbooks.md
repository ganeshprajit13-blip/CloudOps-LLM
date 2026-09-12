Defect Classification Operations Runbooks

---

**Service: defect-classifier (Automated Defect Triage Pipeline)**
*Description*: Batch-processing service that ingests customer care transcripts and classifies defects using rule-based SOP logic. Outputs classified defect categories (e.g., thermal_management, connectivity_issue, sensor_drift) for operational triage. Integrates with CRM and supply chain alert systems.

**Health Check Endpoints & Thresholds**:
- `/health` → HTTP 200 within 2s; CPU < 70%, memory < 80%
- `/metrics/classification-rate` → >95% of transcripts processed per batch (alert if <90% for 2 consecutive batches)
- `/metrics/precision-recall/<category>` → Precision ≥ 0.90, Recall ≥ 0.65 per category (alert if recall < 0.50 for 24h)
- `/metrics/manual-qa-error-rate` → ≤25% misclassification rate (alert if >25% for 48h)
- `/metrics/rule-firing-count` → No category should have >300% spike in rule firings vs. 7-day baseline

**Common Failure Patterns & Diagnostic Steps**:
1. **Low Recall in a Specific Defect Category**
   - Check: Are customers describing symptoms of a failure mode without using the keywords the SOP rule expects?
   - Query: `SELECT transcript_text, classification, region FROM transcripts WHERE product_line = 'ProSensor Hub' AND category NOT IN (<suspected_category>) AND created_at > <incident_start_date> ORDER BY created_at DESC LIMIT 100`
   - Action: Review transcript samples for symptom patterns that the SOP rule misses; validate if rule keyword list is too narrow for the actual customer language

2. **High Misclassification Across Multiple Categories**
   - Check: Is a single underlying failure mode being split across multiple classification buckets?
   - Query: `SELECT category, COUNT(*) FROM transcripts WHERE product_line = 'ProSensor Hub' AND created_at > <incident_start_date> GROUP BY category ORDER BY COUNT DESC`
   - Action: Cross-reference with geographic, environmental, and supplier change data; check if misclassified cases cluster by a non-obvious factor

3. **Rule Conflicts (multiple categories firing)**
   - Check: Are multiple SOP rules matching on the same symptom phrases?
   - Query: `SELECT transcript_id, category, confidence FROM classifications WHERE transcript_id IN (SELECT transcript_id FROM classifications GROUP BY transcript_id HAVING COUNT(DISTINCT category) > 1) ORDER BY transcript_id, confidence DESC`
   - Action: Review overlapping rules; add exclusivity clauses or priority ordering based on environmental/contextual signals

4. **NLP Entity Extraction Degradation**
   - Check: Are product names, regions, and symptoms being extracted correctly?
   - Query: `SELECT entity_type, entity_value, confidence FROM entities WHERE transcript_id IN (SELECT transcript_id FROM transcripts WHERE manual_qa_label != automated_label AND manual_qa_confirmed = true)`
   - Action: Re-run entity extraction on 50 misclassified transcripts; compare against ground truth

---

**Runbook: Classification Accuracy Investigation**
*Trigger*: Manual QA audit reveals >25% misclassification rate OR automated recall for any defect category drops below 0.50

**Diagnostic Decision Tree**:
1. Is misclassification concentrated in one category?
   → Yes → Go to Step 2
   → No → Check for new product line or seasonal pattern (see Runbook: Complaint Volume Spike)

2. Which category has the biggest gap between expected and actual volume?
   → Identify the underrepresented category → Check if its SOP rule keywords match the language customers actually use
   → No clear underrepresented category → Check for rule conflicts or NLP degradation

3. Are misclassified transcripts geographically clustered?
   → Yes → Cross-reference with environmental data (climate, humidity) and supplier/manufacturing change logs
   → No → Investigate SOP rule logic or NLP model drift

4. Are manual QA agents using the same SOP rules as the automated pipeline?
   → Yes → Root cause is systemic SOP blind spot
   → No → Train agents on latent symptom patterns

**Key Diagnostic Queries**:
- `SELECT region, automated_label, COUNT(*) FROM transcripts WHERE product_line = 'ProSensor Hub' AND created_at > <incident_start_date> GROUP BY region, automated_label ORDER BY COUNT DESC LIMIT 20`
- `SELECT DISTINCT transcript_text, automated_label, region FROM transcripts WHERE automated_label IN (<high_volume_categories>) AND product_line = 'ProSensor Hub' AND created_at > <incident_start_date> ORDER BY created_at DESC LIMIT 50`

**Escalation**:
- If misclassification rate >25% for 48h → Escalate to Data Science team with [transcript sample set + geographic heatmap + supplier/manufacturing change log]
- If a specific category's recall drops below 0.40 → Escalate immediately with evidence of what the SOP rule is missing

---

**Runbook: Complaint Volume Spike Investigation**
*Trigger*: >150% increase in complaint volume for ProSensor Hub over 7-day window

**Diagnostic Decision Tree**:
1. Is spike isolated to one product line?
   → Yes → Proceed to Step 2
   → No → Check for campaign, pricing, or shipping event

2. Is spike geographically clustered?
   → Yes → Cross-reference with environmental data (temperature, humidity) and supplier/manufacturing change logs
   → No → Check warehouse handling, firmware releases, or marketing campaigns

3. Were there supplier or manufacturing changes in last 30 days?
   → Yes → Correlate change date with complaint onset; check component specs for degradation risk
   → No → Check manufacturing line changes, firmware releases, or seasonal patterns

4. Do transcripts describe intermittent or condition-dependent failures?
   → Yes → Investigate environmental factors (thermal, humidity, power) — check what conditions trigger the failure
   → No → Investigate permanent failure modes (hardware damage, firmware bugs)

**Key Diagnostic Queries**:
- `SELECT region, COUNT(*) FROM transcripts WHERE product_line = 'ProSensor Hub' AND created_at > <incident_start_date> GROUP BY region ORDER BY COUNT DESC`
- `SELECT * FROM supplier_changes WHERE product_line = 'ProSensor Hub' AND change_date > <incident_start_date> - INTERVAL '30 days' ORDER BY change_date DESC`

**Escalation**:
- If supplier/manufacturing change confirmed + geographic clustering + classification anomaly → Escalate to VP Engineering within 24h
- If no clear root cause after 72h → Initiate emergency component audit and lab testing on returned units

---

**Runbook: SOP Rule Tuning**
*Trigger*: Category precision < 0.85 or recall < 0.60 for >48h

**Process**:
1. Pull 200 transcripts classified as target category (e.g., thermal_management)
   - Manually label: TP, FP, FN
   - Flag: False negatives where symptom is present but keyword is absent

2. Pull 200 transcripts NOT classified as target category
   - Manually label: FN (missed true positives) vs TN (genuine negatives)
   - Identify patterns: what phrases do customers use to describe the failure mode?

3. Expand rule logic:
   - Add symptom-based triggers that customers actually use (identified from FN review)
   - Add environmental/contextual signals (geographic region, installation type, time-of-day patterns)
   - Add temporal context: filter by complaint onset window
   - Test expanded rules against held-out sample before deploying

4. Test rules on 1000 held-out transcripts → validate recall > 0.70, precision > 0.85

**Key Diagnostic Commands**:
- `python3 rule_tester.py --category thermal_management --sample-size 200 --output report.html`
- `sql "SELECT COUNT(*) FROM transcripts WHERE automated_label = 'thermal_management' AND manual_qa_label != 'thermal_management'"`
- `sql "SELECT COUNT(*) FROM transcripts WHERE manual_qa_label = 'thermal_management' AND automated_label != 'thermal_management'"`

**Escalation**:
- If recall cannot be improved to >0.65 after rule tuning → Escalate to Data Science to build ML classifier using NLP embeddings (BERT) trained on manual QA labels
- If rule changes impact >3 other categories → Schedule change review with Ops, QA, and Supplier Engineering teams

---
