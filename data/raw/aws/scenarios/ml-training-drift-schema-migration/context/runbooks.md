# Runbooks for ml-training-drift-schema-migration RCA

## Service Descriptions and Health Checks

### 1. events-warehouse-db (PostgreSQL)
- **Description**: Centralized event warehouse storing user interaction events. Serves as primary source for feature engineering. Schema changes are managed via automated migration scripts.
- **Health Check Endpoint**: `GET /health/db` (internal API gateway endpoint)
- **Health Thresholds**:
  - Query latency (p95): < 500ms
  - Replication lag: < 5s
  - Connection pool utilization: < 85%
  - Table row count consistency (vs. source systems): ±0.5%
- **Key Metrics**:
  - Row counts and schema version: `SELECT * FROM schema_migrations ORDER BY applied_at DESC LIMIT 5;`
  - Column cardinality checks: `SELECT COUNT(DISTINCT <column>) FROM user_events;`
  - Recent migration status: check `data_ops_jobs` for completion status of backfill jobs

### 2. feature-aggregator (Python/Spark ETL)
- **Description**: Scheduled ETL job that ingests raw events, computes aggregated user features, and writes to feature store. Controlled by dynamic feature flags.
- **Health Check Endpoint**: `GET /health/aggregator` (HTTP)
- **Health Thresholds**:
  - Job runtime: 20–45 minutes (historical baseline)
  - Output feature count: 150M–180M records (per run)
  - Feature cardinality: grouping column should have high distinct count relative to record count
- **Key Metrics**:
  - Feature distribution: `SELECT COUNT(DISTINCT <grouping_column>) FROM feature_store.user_features WHERE timestamp > NOW() - INTERVAL '48h';`
  - Feature flag state: check which flags were recently toggled and their impact on aggregation logic
  - Log search: filter for flag enablement events and grouping behavior changes

### 3. ml-training-pipeline (Kubernetes-based)
- **Description**: Automated retraining pipeline that pulls features from feature store, trains XGBoost models, and registers metrics in model registry.
- **Health Check Endpoint**: `GET /health/training` (internal)
- **Health Thresholds**:
  - Training job status: SUCCEEDED
  - AUC-ROC (validation): > 0.85
  - Feature coverage (grouping column): > 90% non-zero distinct values
  - **Critical Alert**: AUC drops > 0.08 from baseline within 2 consecutive runs
- **Key Metrics**:
  - `SELECT auc_roc, feature_version FROM model_registry.metrics ORDER BY trained_at DESC LIMIT 5;`
  - Log search: check for feature version changes or aggregation logic modifications in the training window

### 4. feature-store (Redis + PostgreSQL)
- **Description**: Central feature repository serving training and serving workloads. Features are versioned and timestamped.
- **Health Check Endpoint**: `GET /health/store`
- **Health Thresholds**:
  - Read latency (p95): < 100ms
  - Feature version drift: No unexpected version changes in last 72h
  - **Critical Alert**: Any feature version shows unexpectedly low cardinality in grouping columns
- **Key Metrics**:
  - `SELECT COUNT(DISTINCT grouping_key), COUNT(*) FROM features WHERE created_at > NOW() - INTERVAL '3d';`

---

## Common Failure Patterns and Diagnostic Steps

### Pattern 1: Silent Data Corruption from Schema Changes
- **Symptoms**: Training jobs succeed, AUC drops, no pipeline errors, feature count matches expectations.
- **Diagnostic Steps**:
  1. Check feature distribution in feature store — compare cardinality and variance vs. historical baseline.
  2. Query events warehouse for recent schema migrations: `SELECT * FROM schema_migrations WHERE applied_at > NOW() - INTERVAL '7d'`.
  3. For each recent migration, verify associated backfill jobs completed successfully — check `data_ops_jobs` table.
  4. Search backfill job logs for warnings, timeouts, or fallback behaviors.
  5. Compare column value distributions before and after migration window.

### Pattern 2: Feature Flag Change Altering Aggregation Logic
- **Symptoms**: Feature distributions shift immediately after a flag toggle; model accuracy degrades in subsequent training runs.
- **Diagnostic Steps**:
  1. Determine which feature flags were changed in the degradation window via config management audit logs.
  2. Correlate flag change time with first degradation in AUC.
  3. Check if the flag change altered which columns, tables, or grouping keys the aggregator uses.
  4. Validate that the underlying data supports the new aggregation logic (sufficient cardinality, complete backfill, etc.).

### Pattern 3: Incomplete Backfill After Schema Migration
- **Symptoms**: Schema change completed successfully, but dependent backfill job silently failed or partially completed.
- **Diagnostic Steps**:
  1. Locate migration scripts and associated backfill scripts in Git repo.
  2. Check backfill job exit codes and logs — a script that exits 0 may still have failed on most records.
  3. Search logs for connection errors, timeouts, or fallback behaviors during the backfill window.
  4. Compare expected vs actual record counts for the migrated column.
  5. Check if downstream consumers (feature aggregator, training pipeline) validate data quality before use.

---

## Troubleshooting Decision Tree

AUC dropped below 0.85?
├─ Are training jobs reporting SUCCEEDED? → YES
│  ├─ Are feature counts in feature store correct? → YES
│  │  ├─ Is feature cardinality (distinct values in grouping columns) abnormally low? → YES
│  │  │  ├─ Were any feature flags toggled in the degradation window? → YES
│  │  │  │  ├─ Did the flag change alter which columns the aggregator groups by?
│  │  │  │  │  └─ YES → Check if the target column has valid data (run distribution query)
│  │  │  │  │     → If column has low cardinality → investigate upstream: schema migration + backfill status
│  │  │  │  └─ NO → Check aggregation logic for other recent changes
│  │  │  └─ NO → Check for data sampling bias, label leakage, or partition changes
│  │  └─ Feature cardinality normal → Investigate model overfitting, feature drift, or data quality
│  └─ NO → Check model registry versioning or training data split
└─ NO → Investigate serving latency or cache issues (red herring)

---

## Key Diagnostic Commands and Queries

### PostgreSQL (events-warehouse-db)
-- Check recent schema migrations
SELECT migration_name, applied_at, status
FROM schema_migrations
WHERE applied_at > NOW() - INTERVAL '7 days'
ORDER BY applied_at DESC;

-- Check backfill job status
SELECT job_name, status, error_message, completed_at
FROM data_ops_jobs
WHERE completed_at > NOW() - INTERVAL '7 days'
ORDER BY completed_at DESC;

-- Profile column value distribution (replace <column> with recently added/modified columns)
SELECT
  COUNT(*) AS total_records,
  COUNT(DISTINCT <column>) AS distinct_values,
  ROUND((COUNT(DISTINCT <column>) * 100.0 / COUNT(*)), 2) AS cardinality_pct
FROM user_events
WHERE event_timestamp > NOW() - INTERVAL '72 hours';

### Feature Store (PostgreSQL)
-- Analyze feature cardinality in recent outputs
SELECT
  COUNT(*) AS total_features,
  COUNT(DISTINCT <grouping_column>) AS distinct_groups,
  ROUND((COUNT(DISTINCT <grouping_column>) * 100.0 / COUNT(*)), 2) AS coverage_pct
FROM feature_store.user_features
WHERE created_at > NOW() - INTERVAL '48 hours';

-- Compare cardinality across feature versions
SELECT feature_version, COUNT(DISTINCT <grouping_column>)
FROM feature_store.user_features
WHERE created_at > NOW() - INTERVAL '7d'
GROUP BY feature_version;

### Log Queries (ELK / Loki)
# Search for backfill failures or warnings
"data_ops" AND ("timeout" OR "fallback" OR "connection refused" OR "WARN")

# Search for feature flag changes
"feature_flag" AND "value:true" AND ("enabled" OR "toggled")

# Search for aggregation behavior changes
"feature_aggregator" AND ("grouping" OR "distinct" OR "cardinality")

### ML Pipeline (Prometheus + Logs)
# AUC trend over last 7 days
ml_model_auc_roc[7d]

# Feature cardinality metrics (if exported)
feature_store_distinct_values[48h]

---

## Escalation Procedures

### Tier 1: ML Team Detects AUC Drop
- **Action**: Confirm degradation across 2+ consecutive retraining runs.
- **Escalate to**: Feature Engineering Team (via Slack channel #ml-ops-alerts)

### Tier 2: Feature Engineering Confirms Low Entropy in Features
- **Action**: Run diagnostic queries on feature store — compare cardinality with baseline.
- **Escalate to**: Data Engineering Team (via PagerDuty incident with severity P2)
- **Include**:
  - Query results showing feature cardinality anomaly
  - Time of any recent feature flag changes
  - Link to any recent migration scripts and backfill job logs

### Tier 3: Data Engineering Confirms Data Layer Issue
- **Action**: Roll back any recently toggled feature flags that altered aggregation logic.
- **Initiate**: Data validation and rehydration plan if corruption is confirmed.
- **Escalate to**: Platform Engineering + SRE (P1 incident)
- **Required**:
  - Root cause identification (which migration/backfill/flag caused the issue)
  - Impact assessment (how many records affected, time window)
  - Fix plan (re-run backfill, revert flag, retrain models)
  - Prevention plan (validation gates to add)

### Tier 4: Post-Mortem & Prevention
- **Action**:
  - Mandate: All schema migrations with backfills require automated validation step
  - Implement: Feature flag pre-flight checks — validate data quality before enabling flags that change aggregation
  - Add: Monitoring alerts on feature cardinality drops
  - Document: “Schema Migration Playbook” with mandatory backfill validation checklist
- **Owner**: Data Engineering Lead
- **Deadline**: 7 calendar days post-incident

> **Note**: ML accuracy degradation with no pipeline errors often indicates a data layer issue. Schema migrations, backfill failures, and feature flag changes can interact across teams to create silent corruption. Enforce data quality validation at the boundary between data engineering and feature engineering.
