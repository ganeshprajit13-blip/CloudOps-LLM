Severity: P1
Reported By: ML Platform Operations Team
Date: 2026-03-28T14:30:00Z

**Summary**
ML recommendation models have experienced a sudden and sustained degradation in predictive performance, with AUC dropping from 0.89 to 0.72 over the past 36 hours. Training pipelines completed without errors, and no recent code deployments or configuration changes were made to the model trainer, feature store, or serving infrastructure. Multiple B2B retailers have reported significant declines in recommendation relevance and click-through rates. The degradation is consistent across all models trained since T-36h, while models trained prior to that window remain unaffected.

**Impact**
- AUC degradation: 0.89 → 0.72 (19% relative drop)
- Model precision: 0.84 → 0.68
- 8 active retailers have filed formal complaints regarding recommendation quality
- Estimated daily revenue loss: $45,000 due to reduced CTR and conversion
- No service outages or errors observed in any downstream or upstream systems
- Feature serving latency, throughput, and error rates remain within normal bounds

**Timeline**
- T-72h: Schema migration initiated in events warehouse database (no alerts raised)
- T-40h: Feature flag `USE_USER_ID_V2` enabled in feature-aggregator configuration
- T-36h: First retraining job completed with AUC of 0.72; metrics collected but not flagged as anomalous
- T-24h: Second retraining job confirmed same degradation pattern; ML engineers began internal investigation
- T-12h: Retailer complaint volume increased by 300% YoY; customer success team escalated
- T-0h: Incident formally opened; cross-team triage initiated

**Available Information**
- All training jobs report “SUCCESS” status with no warnings or exceptions in logs
- Feature store API returns 200 OK for all feature queries; payload sizes and schemas appear unchanged
- Feature validation service reports “pass” on all schema and distribution checks
- Data-quality-monitor shows no anomalies in record count, null rates, or timestamp drift
- Training-metrics-collector confirms stable input data volume (within ±3% of baseline)
- Model-serving latency and throughput unchanged; no cache misses or throttling spikes detected
- Recent feature store queries from model-trainer show consistent field names and data types
- No recent changes to model architecture, hyperparameters, or training data sampling logic
- TLS certificates rotated 48h ago (investigated and rolled back — no impact observed)
- Redis cache eviction events observed at T-45h (investigated — unrelated to feature values)
- DynamoDB throttling occurred briefly at T-42h in model registry (resolved within 2m; no model metadata changes)

**Open Questions**
- What changed in the feature aggregation logic at T-40h?
- Are there any silent fallbacks or default behaviors in the feature aggregator or warehouse queries?
- Why do historical models still perform well despite the same underlying data?
- Is the feature store returning different aggregate values for the same user identifiers?
- Are there any undocumented schema evolution patterns in the events warehouse?

No team has identified a clear source of corruption. All systems appear healthy — the degradation is purely statistical and latent.
