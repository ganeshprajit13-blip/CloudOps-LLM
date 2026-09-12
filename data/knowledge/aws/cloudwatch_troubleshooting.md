# CloudWatch Metrics, Alarms, & Logs Troubleshooting Guide

*Project-Created Authoritative Troubleshooting Knowledge*

## CloudWatch Monitoring Overview
Amazon CloudWatch monitors AWS resources and applications in real-time.

## Key Concepts & Diagnostic Scenarios

### 1. Alarm State Evaluation (`ALARM`, `OK`, `INSUFFICIENT_DATA`)
- **`ALARM`**: The metric has breached the configured threshold for the evaluation periods (e.g. CPUUtilization > 85% for 3 consecutive 5-minute periods).
- **`INSUFFICIENT_DATA`**: The alarm has just started, metric is not available, or insufficient data has reached CloudWatch.
  - Fix: Check if CloudWatch Agent is running on host or if log agent is sending metrics.

### 2. High EC2 Metric Investigation
- **CPUUtilization**: Measure CPU consumption across instance.
- **DiskSpaceUtilization / VolumeReadBytes**: Disk I/O bottlenecks.
- **StatusCheckFailed_Instance** vs **StatusCheckFailed_System**:
  - `StatusCheckFailed_System`: Issue on underlying AWS physical host hardware (Fix: Stop and Start EC2 instance to migrate host).
  - `StatusCheckFailed_Instance`: Operating system crash, kernel panic, or misconfigured network interface on EC2 (Fix: Reboot or check system logs).

### 3. CloudWatch Log Insights Queries
- Search error messages:
  `fields @timestamp, @message | filter @message like /Error|Exception|FAIL/ | sort @timestamp desc | limit 50`
