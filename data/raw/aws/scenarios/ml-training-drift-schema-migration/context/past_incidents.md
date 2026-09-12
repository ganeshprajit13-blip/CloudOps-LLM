# Past Incidents

## 1. Related Incident: Feature Aggregation Bias from Timezone-Aware Partitioning Change (ML-2023-08-15)

**Date**: August 15, 2023
**Severity**: P0 — 38% drop in conversion rate across 3 major retailers
**Symptoms**:
- ML training jobs completed successfully with no errors
- Feature store queries returned valid JSON with all expected fields
- AUC dropped from 0.87 to 0.73 in 2 consecutive retraining cycles
- User-level feature distributions showed strong recency bias — recent events overweighted by 4x
- No alerts triggered on feature store ingestion or model performance monitors

**Root Cause**:
A schema migration changed the event partitioning key from `event_date` (UTC) to `event_date_local` (user timezone). The migration script correctly computed local dates for new events, but the backfill for historical records used a single hardcoded UTC-5 offset instead of per-user timezone lookup. For users outside Eastern Time, events were assigned to wrong date partitions. When the feature aggregator computed "last 7 days" rolling windows, it included 10-14 days of events for Pacific/Mountain users and only 5-6 days for users east of UTC. This created a systematic sampling bias.

**Resolution**:
- Rolled back partitioning key to `event_date` (UTC)
- Re-ran backfill with correct per-user timezone lookup
- Re-trained models on corrected partitions; AUC recovered within 24h
- Added partition distribution validation: event count variance across time partitions must be <10%

**Lessons Learned**:
- Schema migrations that change partition keys or grouping columns are high-risk for ML
- Backfill scripts must be validated against the same logic as forward-path writes
- Silent data distribution shifts (not errors) are the hardest class of ML data corruption to detect

---

## 2. Red Herring: TLS Certificate Rotation Caused Feature Store Restart (ML-2023-05-22)

**Date**: May 22, 2023
**Severity**: P2 — 15-minute outage in feature serving
**Symptoms**:
- Feature store API returned 503 errors for 12 minutes
- Model serving layer fell back to cached features (1-hour TTL)
- Training pipeline was unaffected (uses batch exports, not real-time API)
- ML engineers initially suspected feature corruption due to sudden drop in model confidence scores

**Root Cause**:
A routine TLS certificate rotation triggered an unhandled exception in the feature store’s Kubernetes ingress controller. The pod restarted, causing temporary unavailability. The certificate was renewed correctly, and the system recovered automatically.

**Resolution**:
- Added liveness probe for TLS certificate expiration status
- Implemented circuit breaker in model serving to avoid caching stale features beyond TTL
- No data corruption occurred

**Lessons Learned**:
- Service availability ≠ data integrity
- Training pipelines are insulated from real-time serving outages
- Model performance degradation during outages is due to fallback logic, not feature drift

---

## 3. Red Herring: Redis Cache Eviction Under Model Serving Load (ML-2023-09-08)

**Date**: September 8, 2023
**Severity**: P3 — increased latency, minor inference variance
**Symptoms**:
- Model inference latency increased by 300ms during peak hours
- Some users received inconsistent recommendations between refreshes
- ML monitoring showed slight variance in predicted probabilities (±0.03)

**Root Cause**:
Redis cache eviction policy (`allkeys-lru`) triggered during a traffic spike. High-cardinality user feature keys were evicted faster than they could be repopulated. Model serving fell back to computing features on-the-fly from the feature store, causing slight numerical precision differences due to floating-point aggregation variance.

**Resolution**:
- Switched Redis eviction policy to `volatile-lru` and increased cache size
- Added warm-up script to pre-populate top 10K user features after restarts
- Introduced feature fingerprinting to detect non-deterministic recomputation

**Lessons Learned**:
- Cache inconsistencies can mimic model drift but are deterministic and transient
- Feature variance from recomputation is noise, not systemic corruption
- Always verify if symptoms are reproducible across cold vs warm starts

---

## 4. Red Herring: DynamoDB Throttling in Model Registry (ML-2023-11-17)

**Date**: November 17, 2023
**Severity**: P2 — delayed model version registration
**Symptoms**:
- Training pipeline logs showed “Model version not registered” warnings
- Model version numbers skipped from v24 to v26
- ML engineers suspected training jobs were running on wrong versions

**Root Cause**:
DynamoDB table for model registry hit provisioned throughput limits during a batch retraining surge. Write requests were throttled, causing registration failures. Training jobs continued using local model artifacts and persisted metadata to S3 — but the registry didn’t reflect the true state.

**Resolution**:
- Enabled auto-scaling on DynamoDB table
- Added idempotent registration with retry logic and exponential backoff
- Introduced S3-as-source-of-truth for model versioning

**Lessons Learned**:
- Model version registry failures do not affect feature data or training logic
- Training success ≠ registry success
- Always audit feature lineage independently of model metadata

---

## 5. Red Herring: Data Pipeline Duplicate Events from Kafka Retries (ML-2022-12-03)

**Date**: December 3, 2022
**Severity**: P1 — 11% inflation in daily active user metrics
**Symptoms**:
- Feature aggregates (e.g., `purchases_last_7d`) were 10–15% higher than expected
- User counts in cohort tables were inflated
- Training data appeared “noisier” than usual

**Root Cause**:
A Kafka consumer in the event ingestion pipeline failed to commit offsets after processing. After a timeout, it reprocessed the same batch — causing 2x duplication of event records in the warehouse. The feature aggregator did not deduplicate by event_id.

**Resolution**:
- Added `event_id` deduplication at the feature aggregation layer
- Implemented idempotent writes in the warehouse ingestion job
- Introduced watermarking to detect late-arriving duplicates

**Lessons Learned**:
- Duplicate data inflates aggregates but doesn’t collapse distributions
- Per-user features remain distinct — no global averaging occurs
- Corrupted data with high variance ≠ corrupted data with zero variance

---

## Comparison Table: Distinguishing Failure Modes

| Symptom | ML-2023-08-15 (Partitioning) | ML-2023-05-22 (Red Herring) | ML-2023-09-08 (Red Herring) | ML-2023-11-17 (Red Herring) | ML-2022-12-03 (Red Herring) |
|--------|--------------------------|-----------------------------|-----------------------------|-----------------------------|-----------------------------|
| **Model AUC Drop** | Yes (0.87 → 0.73) | No | No | No | Minor (due to noise) |
| **Feature Variance** | Biased (recency skew) | Normal | Normal | Normal | High (duplicated values) |
| **Training Job Errors** | None | None | None | None | None |
| **Feature Store Errors** | None | 503s during outage | None | None | None |
| **Data Distribution** | Sampling bias by timezone | Unaffected | Unaffected | Unaffected | Inflated, but diverse |
| **Root Cause Type** | Silent schema/backfill issue | Service outage | Cache eviction | Registry failure | Duplicate events |
| **Reproducible on Fresh Data?** | Yes — same partition mapping | No — service restored | No — cache repopulates | No — version fixed | Yes — duplicates persist |
| **Detectable via Data Profile** | Yes — event count variance across partitions | No | No | No | Yes — duplicate event_id counts |

> **Key Diagnostic Tip**: When AUC drops sharply with no pipeline errors, investigate the data layer — check for recent schema migrations, column additions, or partition changes that could silently alter how features are computed. Compare feature distributions before and after the change window. Silent backfill failures and grouping column changes are the most dangerous because they produce valid-looking data with corrupted semantics.
