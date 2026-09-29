# AWS CloudWatch — Metrics, Alarms, and Monitoring

## 1. What is Amazon CloudWatch?

**Amazon CloudWatch** is AWS's built-in monitoring and observability service that collects metrics, logs, and events from AWS resources and applications. It provides:
- Real-time monitoring of EC2 instances, RDS, Lambda, and 70+ AWS services
- Custom metrics from your own applications
- CloudWatch Logs for log aggregation and analysis
- Alarms to trigger notifications or auto-scaling actions
- Dashboards for visualizing metrics

---

## 2. CloudWatch Metrics

A **metric** is a time-ordered set of data points representing the behavior of a resource over time.

### Key Metric Concepts
- **Namespace**: Category of metrics (e.g., `AWS/EC2`, `AWS/RDS`, `AWS/Lambda`)
- **Metric Name**: Specific measurement (e.g., `CPUUtilization`, `NetworkIn`)
- **Dimension**: Key-value pair to filter metrics (e.g., `InstanceId=i-0abc123`)
- **Period**: Time granularity of data points (60s, 300s, 3600s)
- **Statistic**: Aggregation function (Average, Maximum, Minimum, Sum, SampleCount)
- **Retention**: Metrics retained 15 months (granularity degrades over time)

---

## 3. EC2 Default CloudWatch Metrics

| Metric | Description | Namespace |
| :--- | :--- | :--- |
| CPUUtilization | CPU usage % across all vCPUs | AWS/EC2 |
| NetworkIn | Bytes received by instance | AWS/EC2 |
| NetworkOut | Bytes sent by instance | AWS/EC2 |
| DiskReadOps | Disk I/O read operations | AWS/EC2 |
| DiskWriteOps | Disk I/O write operations | AWS/EC2 |
| StatusCheckFailed | Instance or system check failure | AWS/EC2 |

**Note**: Memory utilization and disk space are NOT collected by default. Install the **CloudWatch Agent** to collect these.

---

## 4. CPUUtilization Metric

`CPUUtilization` is the most commonly monitored EC2 metric. It represents the percentage of allocated EC2 compute units currently in use.

- **Normal range**: Typically 0-40% for most workloads
- **Warning threshold**: Usually 70-80%
- **Critical threshold**: Usually 85-95%+

In **CloudOps**, the AI Troubleshooter queries `CPUUtilization` via `cloudwatch:GetMetricStatistics` for the last 15 minutes with 1-minute periods. The `high_cpu_utilization` signal is only raised when CURRENT readings actually exceed the configured threshold.

---

## 5. CloudWatch Alarms

A **CloudWatch Alarm** watches a single metric and performs one or more actions when the metric breaches a defined threshold.

### Alarm States
- **OK**: Metric within threshold
- **ALARM**: Metric breached threshold
- **INSUFFICIENT_DATA**: Not enough data points

### Alarm Actions
- Send notification via **SNS topic** (email, SMS, Lambda)
- Trigger **Auto Scaling** policy
- Stop, terminate, reboot, or recover an EC2 instance

### Creating an Alarm Example
1. Go to CloudWatch > Alarms > Create Alarm
2. Select metric: `AWS/EC2 > CPUUtilization` with dimension `InstanceId`
3. Set threshold: Greater than 80% for 2 out of 3 evaluation periods (each 5 minutes)
4. Set action: Send notification to SNS topic

---

## 6. CloudWatch Logs

**CloudWatch Logs** collects and stores log data from:
- EC2 instances (via CloudWatch Agent)
- AWS Lambda functions (automatic)
- VPC Flow Logs
- CloudTrail API events
- Application logs

Key concepts:
- **Log Group**: Collection of log streams (e.g., `/var/log/nginx/access.log`)
- **Log Stream**: Sequence of log events from a single source
- **Log Insights**: Interactive query language for log analysis
- **Metric Filters**: Extract metric values from log events

---

## 7. CloudWatch vs CloudTrail

| Aspect | CloudWatch | CloudTrail |
| :--- | :--- | :--- |
| Purpose | Performance monitoring | API audit and compliance |
| Data type | Metrics, logs, events | API call records |
| Answers | "Is my instance healthy?" | "Who changed this Security Group?" |
| Retention | Up to 15 months | 90 days (event history) or S3 |

---

## 8. Common CloudWatch Mistakes

- Not installing CloudWatch Agent — memory and disk metrics missing
- Alarm in INSUFFICIENT_DATA state — metric not publishing (instance stopped, agent not running)
- Too-short evaluation period — alarm triggers on brief spikes
- Not setting alarm actions — you know metrics are bad but nobody is notified
- Confusing CloudWatch with CloudTrail — CloudWatch is performance, CloudTrail is audit
