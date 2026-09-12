# Runbook: EC2 High CPU Utilization Remediation

*Category: Runbook | Service: EC2*

## 1. Initial Alarm Verification
- **Trigger**: CloudWatch Alarm `EC2-High-CPU-Utilization` fired for instance `i-0a1b2c3d4e5f6g7h8`.
- **Severity**: High (Sev-2)

## 2. Immediate Diagnostic Procedure
1. Check CPU metric in CloudWatch Console: `AWS/EC2 CPUUtilization`.
2. Connect to EC2 instance via AWS SSM Session Manager:
   `aws ssm start-session --target i-0a1b2c3d4e5f6g7h8`
3. Inspect running process tree:
   `ps aux --sort=-%cpu | head -n 10`
4. Inspect memory & load average:
   `uptime` && `free -h`

## 3. Mitigation Options
- **Option A (Transient Rogue Process)**: Terminate runaway process if non-critical (`kill -9 <PID>`).
- **Option B (Sustained Load Spike)**: Scale out by increasing Auto Scaling Group desired capacity by +1 instance.
- **Option C (Under-provisioned Instance)**: Upgrade instance type (e.g. `t3.medium` to `t3.large`).
