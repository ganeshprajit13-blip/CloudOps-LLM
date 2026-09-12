# Architecture.md

## System Overview and Purpose

This architecture supports a B2B SaaS ML platform that delivers personalized recommendation models to e-commerce retailers. The system ingests user event data, transforms it into features via an automated pipeline, and trains daily recommendation models using a centralized feature store. Model performance is measured by AUC, with targets above 0.87. The system is designed for high availability and silent operational continuity — no errors should halt training or feature computation, even in the presence of data corruption. This design choice, while ensuring pipeline resilience, creates blind spots for silent data drift — as demonstrated in this incident.

---

## Service Topology

### 1. `events-warehouse-db` (PostgreSQL)
- **Role**: Central event datastore containing 180M+ user interaction records (e.g., clicks, purchases). Schema is owned by Data Engineering.
- **Key Tables**: `user_events`, `users` (deprecated), `user_lookup` (mapping table for migration).
- **Critical Behavior**: During schema migrations, defaults are applied silently to historical rows when backfills fail. No validation hooks exist for placeholder UUIDs.

### 2. `feature-aggregator` (Python/Spark ETL job)
- **Role**: Daily batch job that reads from `events-warehouse-db` and computes aggregated user features (e.g., avg_clicks_per_day, purchase_frequency). Outputs to feature store.
- **Key Configuration**: `USE_USER_ID_V2` feature flag (default: false). When enabled, groups by `user_id_v2` instead of `user_id`.
- **Behavior**: No data validation on cardinality of grouping keys. Assumes UUIDs are unique per user. No alerting on low entropy in grouping columns.

### 3. `feature-store` (S3 + Athena + Glue Catalog)
- **Role**: Central repository for precomputed features. Accessed by training and serving systems via SQL-compatible interfaces.
- **Data Format**: Parquet files partitioned by date. Schema registered in Glue Catalog.
- **Behavior**: No schema evolution validation. Accepts any Parquet schema. Features are immutable once written.

### 4. `model-trainer` (Kubernetes-managed PyTorch pods)
- **Role**: Trains recommendation models daily using features from `feature-store`. Triggers automatically on new feature versions.
- **Behavior**: No data quality checks (e.g., feature entropy, user count, null rates). Training completes successfully even with degenerate features. AUC is the only metric monitored.

### 5. `model-registry` (DynamoDB)
- **Role**: Tracks model versions, training metadata, and deployment status. Used by serving layer to select active models.
- **Behavior**: No correlation between model AUC and feature version used. Only logs training success/failure, not data quality.

### 6. `model-serving` (Redis + Flask API)
- **Role**: Serves model predictions to retailer websites in real-time.
- **Caching**: Uses Redis to cache per-user predictions. TTL = 1 hour.
- **Behavior**: No fallback logic for low-confidence predictions. No monitoring of prediction variance across users.

### 7. `alerting-dashboard` (Grafana + Prometheus)
- **Role**: Aggregates system-wide metrics and triggers alerts.
- **Monitored**: Service health, latency, error rates, feature store query latency, Redis cache hit ratio.
- **Missing**: Feature-level statistics (e.g., unique user_id_v2 count, feature entropy, group cardinality).

---

## Data/Request Flow Diagram

[User Events] → [events-warehouse-db]
                     ↓
             [feature-aggregator] ←─ USE_USER_ID_V2 flag
                     ↓
             [feature-store (S3/Parquet)]
                     ↓
             [model-trainer] → [model-registry]
                     ↓
             [model-serving] → [Retailer Websites]
                     ↑
             [Redis Cache] (prediction caching)

Monitoring: Prometheus → Grafana (service metrics only)
Alerts: Only on HTTP 5xx, timeouts, job failures — NOT on data drift

---

## Key Configuration Parameters

| Parameter | Service | Value | Meaning | Risk |
|---------|---------|-------|---------|------|
| `USE_USER_ID_V2` | feature-aggregator | `false` → `true` (T-40h) | Switches feature grouping from legacy `user_id` (int) to `user_id_v2` (UUID) | No validation on cardinality; enabling it without data validation causes silent collapse |
| `DEFAULT_USER_ID_V2` | events-warehouse-db | `00000000-0000-0000-0000-000000000000` | Default UUID for historical records during migration | Used for 180M+ records; no detection mechanism for placeholder prevalence |
| `FEATURE_STORE_RETENTION_DAYS` | feature-store | 90 | Retains features for 90 days; enables rollback | No automated rollback trigger on AUC drop |
| `TRAINING_MIN_USER_COUNT` | model-trainer | `0` (disabled) | Minimum unique users required to train | Disabled — allows training on degenerate data |
| `REDIS_CACHE_TTL` | model-serving | `3600` | Cache TTL in seconds | Masks degradation — stale predictions serve until cache expires |
| `ALERT_ON_JOB_FAILURE` | alerting-dashboard | `true` | Triggers if ETL or training job fails | Does not alert on successful jobs with bad data |

---

## Monitoring and Alerting Setup

### Present Alerts
- HTTP 5xx errors on feature-store or model-serving endpoints
- Feature-aggregator job timeout or crash
- Model-trainer container OOM kills
- Redis cache miss rate > 80%
- DynamoDB throttling > 100 requests/sec
- TLS cert expiration warnings

### Critical Gaps
| Gap | Impact |
|-----|--------|
| No alert on low cardinality in grouping keys (e.g., < 10K unique `user_id_v2` values) | Silent data collapse undetected — root cause invisible |
| No feature entropy or uniqueness metrics exposed to monitoring | AUC drop is the only signal — too late |
| No correlation between feature version and model performance over time | No ability to trace degradation to a specific feature update |
| No data quality checks in feature-aggregator (e.g., % of records with placeholder UUID) | Aggregator is a black box — assumes input is valid |
| No model registry hook to auto-revert model on AUC drop > 10% | No automated rollback mechanism |
| No schema change audit trail linking `events-warehouse-db` migration to feature flag change | Teams operate in isolation — no cross-team impact visibility |

---

## Recent Changes or Maintenance Windows

| Date | Service | Change | Owner | Notes |
|------|---------|--------|-------|-------|
| T-72h | `events-warehouse-db` | Added `user_id_v2` column with default placeholder UUID | Data Engineering | Migration script ran successfully. Backfill script failed silently due to lookup table timeout — only one WARN log in CloudWatch. No rollback or validation. |
| T-72h | `events-warehouse-db` | `user_lookup` table connection pool exhausted during backfill | Data Engineering | No retry logic or fallback validation. Default UUID applied to all 180M records. |
| T-40h | `feature-aggregator` | Enabled `USE_USER_ID_V2=true` | Feature Engineering | Deployed as part of “Q3 Feature Flag Rollout.” No data validation step. No coordination with Data Engineering. |
| T-45h | `feature-store` | AWS Glue Catalog schema auto-updated to include `user_id_v2` | Infra Team | Schema evolution enabled — no validation of data integrity before exposure. |
| T-30h | `model-serving` | Redis cache rotated due to TLS cert renewal | SRE | Caused 15m cache miss storm — falsely suspected as root cause during initial triage. |
| T-24h | `model-registry` | DynamoDB provisioned throughput increased by 50% | Infra Team | Throttling alerts triggered — investigated but unrelated. |

> **Note**: All changes were approved via standard deployment workflows. No cross-team impact review was performed. The schema migration and feature flag enablement were treated as independent, low-risk changes — despite their latent coupling.
