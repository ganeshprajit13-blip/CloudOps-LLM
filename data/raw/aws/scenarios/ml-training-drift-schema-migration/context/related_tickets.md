related_tickets.md

---

### **Related Tickets**

#### **1. DE-1482 - Schema Migration: Add user_id_v2 column to events_warehouse_db**
- **Assignee**: data-engineering-team
- **Status**: Closed
- **Description**: Deploy schema migration to add `user_id_v2` (UUID) column to `events` table in events_warehouse_db to support future user identity unification. Default value set to `00000000-0000-0000-0000-000000000000` for backward compatibility.
- **Comments**:
  > *“Migration ran successfully. Backfill script initiated but timed out connecting to user_lookup_table. Fallback to default UUID applied — only WARN logged. No alerting configured for backfill status.”*
  > *— Deployed at T-72h. No rollback needed — all services continued functioning normally.*

---

#### **2. FE-731 - Enable USE_USER_ID_V2 flag in feature-aggregator**
- **Assignee**: feature-engineering-team
- **Status**: Closed
- **Description**: Enable `USE_USER_ID_V2=true` feature flag in feature-aggregator ETL job to start consuming UUID-based user IDs instead of legacy integer `user_id`.
- **Comments**:
  > *“Flag enabled at T-40h. All feature queries returning valid JSON. Schema matches expectation. No anomalies detected in output sample.”*
  > *“AUC drop not yet visible — training pipeline is healthy.”*
  > *— This change was the trigger, but not the root cause. No one suspected the backfill failure.*

---

#### **3. MON-089 - Implement data drift detection on feature aggregation group cardinality**
- **Assignee**: unassigned
- **Status**: Backlog
- **Description**: Add monitoring to detect abnormal cardinality in grouped features (e.g., if >95% of records share a single user_id_v2 value). Trigger alert if group uniqueness drops below threshold (e.g., <10k unique users in daily batch).
- **Comments**:
  > *“This would have caught the placeholder UUID collapse 2 hours after FE-731 went live. We’re blind to silent aggregation corruption.”*
  > *“Proposal: Add histogram of group counts to feature store metadata and compare against historical baselines.”*
  > *“High priority for future ML observability roadmap.”*

---

#### **4. INF-2101 - Rotate TLS certs on feature-store-api**
- **Assignee**: infra-team
- **Status**: Closed
- **Description**: Routine TLS certificate rotation on feature-store-api cluster. Service restarted with zero downtime.
- **Comments**:
  > *“Restart occurred at T-38h — coincided with first AUC drop. ML team initially suspected this as root cause.”*
  > *“Logs show clean restart. No data loss. Feature queries resumed normally.”*
  > *— Red herring. Correlation ≠ causation.*

---

#### **5. ML-445 - Upgrade Redis cache TTL in model-serving layer**
- **Assignee**: model-ops-team
- **Status**: Closed
- **Description**: Increase Redis cache TTL from 5m to 15m to reduce cache misses during peak traffic. Eviction policy unchanged.
- **Comments**:
  > *“Cache eviction spike observed at T-35h — 12% increase in misses. ML team thought this caused feature staleness.”*
  > *“No model inputs changed — only cached inference outputs. Training pipeline unaffected.”*
  > *— Misdiagnosed as contributing to AUC decay.*

---

#### **6. REG-112 - Increase DynamoDB write capacity for model-registry**
- **Assignee**: model-registry-team
- **Status**: Closed
- **Description**: Throttling alerts observed during model versioning spikes. Provisioned write capacity increased by 40%.
- **Comments**:
  > *“Throttling resolved. Model versions registered successfully.”*
  > *“No impact on training data or feature ingestion — purely metadata operations.”*
  > *— Investigation team wasted 6 hours chasing this due to timing coincidence.*
