# AWS CloudTrail & CloudWatch Architecture

## 1. What is AWS CloudTrail?
**AWS CloudTrail** is an AWS service that provides governance, compliance, operational auditing, and risk auditing of your AWS account. It records all API calls, administrative actions, and user activities made across your AWS infrastructure.

### Key Capabilities of CloudTrail:
- **Event History & API Logging**: Logs user identity, timestamp, source IP address, request parameters, and response elements for API actions (e.g. `AuthorizeSecurityGroupIngress`, `StopInstances`, `CreateVpc`).
- **Security & Change Attribution**: Identifies *who* made a infrastructure change, *when* it occurred, and *which* AWS resource was modified.
- **CloudOps Correlation**: CloudOps inspects CloudTrail event history for the last 1-2 hours to correlate recent human administrative changes with observed incident start times.

---

## 2. What is AWS CloudWatch?
**AWS CloudWatch** is a monitoring and observability platform that collects performance metrics, collects and aggregates log files, and sets automated alarm triggers for AWS resources.

### Key Capabilities of CloudWatch:
- **Metrics**: Tracks quantitative resource utilization metrics over time (e.g., `CPUUtilization`, `NetworkIn`, `DiskReadBytes`, `StatusCheckFailed`).
- **Log Streams**: Aggregates log streams from EC2 instances, web servers, Lambda functions, RDS, and Application Load Balancers.
- **Alarms**: Triggers notifications or auto-scaling actions when metrics breach predefined thresholds (e.g., CPU > 85% for 5 minutes).

---

## 3. Comparison: CloudTrail vs. CloudWatch

| Feature | AWS CloudTrail | AWS CloudWatch |
| :--- | :--- | :--- |
| **Primary Focus** | API Audit Logging & Governance ("Who did what"). | Performance Monitoring & Observability ("How is it performing"). |
| **Data Type** | Management & Data Event Logs (JSON API call records). | Numeric Metrics, Log Streams, Alarms & Dashboard Widgets. |
| **Use Case** | Security auditing, change tracking, compliance. | Metric analysis, CPU monitoring, log aggregation, alerting. |
| **CloudOps Role** | Identifies recent configuration change events. | Supplies real-time telemetry metrics (`CPUUtilization`). |
