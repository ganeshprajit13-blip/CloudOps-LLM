# AWS Common Troubleshooting — IIS, High CPU, Disk, Connectivity

## 1. IIS Stopped — Website Unreachable on Windows EC2

**Symptom**: Website was working previously but now returns connection refused or connection timeout. EC2 instance state is `running`.

### Root Cause
Microsoft IIS (Internet Information Services) — the Windows web server — has stopped. This can happen due to:
- Application pool crash or memory error
- Windows update restart
- Manual stop or script error
- Out of disk space (IIS logs filling disk)

### Diagnosis via CloudOps / SSM
CloudOps checks IIS status using SSM Run Command:
```powershell
Get-Service W3SVC
```
If status returns `Stopped`, IIS is the root cause.

### Resolution Steps
```powershell
# Start IIS web server
Start-Service W3SVC

# Or restart all IIS services
iisreset /restart

# Check IIS event logs for crash reason
Get-EventLog -LogName Application -Source *IIS* -Newest 20
```

### Prevention
- Configure IIS Application Pool to restart automatically on crash
- Set up a CloudWatch alarm on `StatusCheckFailed` metric
- Monitor disk usage — IIS logs fill C: drive on busy servers

---

## 2. High CPU Utilization on EC2

**Symptom**: `CPUUtilization` CloudWatch metric is at 90-100%. Instance may be slow or unresponsive.

### Common Causes
| Cause | Diagnosis |
| :--- | :--- |
| Runaway process | Top process consuming all CPU |
| Traffic spike | Sudden increase in requests |
| Infinite loop in application | Application bug |
| CPU credit exhaustion (T instance) | t2/t3 burstable credit depleted |
| Malware / crypto miner | Unauthorized process |

### Diagnosis Commands
```bash
# Linux
top -bn1 | head -20        # See top CPU processes
ps aux --sort=-%cpu | head  # Sort by CPU usage

# Windows (via PowerShell/SSM)
Get-Process | Sort-Object CPU -Descending | Select-Object -First 10 Name, CPU, Id
```

### Resolution
- Identify and kill runaway process (`kill <PID>` on Linux, `Stop-Process` on Windows)
- Scale vertically to larger instance type if consistently >70%
- Add Auto Scaling Group for horizontal scaling during traffic spikes
- Check T instance CPU credit balance in CloudWatch (T2/T3 instances throttle at 0 credits)

---

## 3. Disk Space Full

**Symptom**: Applications crash, log writes fail, database errors. EC2 unresponsive.

### Diagnosis
```bash
# Linux
df -h                          # Check disk usage by mount point
du -sh /* 2>/dev/null | sort -rh | head -20   # Find largest directories

# Windows (PowerShell/SSM)
Get-PSDrive -PSProvider FileSystem
```

### Common Culprits
- `/var/log` — Application and system logs accumulating
- IIS logs at `C:\inetpub\logs\LogFiles\`
- Database transaction logs
- Docker container images and unused layers
- Large temp files from failed jobs

### Resolution
```bash
# Linux: clear old logs
sudo journalctl --vacuum-time=7d    # Keep only 7 days of systemd journal
sudo find /var/log -name "*.gz" -delete  # Remove compressed old logs

# Extend EBS volume: modify in AWS Console, then on OS:
sudo growpart /dev/xvda 1
sudo resize2fs /dev/xvda1          # ext4
```

---

## 4. Instance Stopped Unexpectedly

**Symptom**: EC2 instance in `stopped` state, but you did not stop it.

### Common Causes
- Auto Scaling Group scale-in terminated the instance
- AWS scheduled maintenance required stop/start
- Root volume detached (EBS error)
- CloudWatch alarm triggered EC2 stop action
- Spot instance interrupted (two-minute termination notice)

### Diagnosis
1. Check **CloudTrail** for `StopInstances` or `TerminateInstances` events
2. Check **CloudWatch** logs and alarms that trigger EC2 actions
3. Check if instance was in an **Auto Scaling Group**
4. Verify **Spot Instance** vs On-Demand

---

## 5. Network Connectivity Issues — General Checklist

When any EC2 resource is unreachable, check in this order:

1. **Instance state** — Must be `running`
2. **Public IP** — Must have public IP or Elastic IP for internet access
3. **Security Group** — Inbound rule for required port (80, 443, 22, 3389) must exist
4. **Route Table** — Public subnet must have `0.0.0.0/0 → igw-xxx`
5. **NACL** — Must allow inbound port and outbound ephemeral ports (1024-65535)
6. **Operating system firewall** — Windows Firewall or Linux iptables/ufw
7. **Application/service** — Is web server or application actually running?
8. **DNS** — Does hostname resolve to correct IP?

---

## 6. CloudOps Automated Diagnostics

The CloudOps AI Troubleshooter automates all checks above:
- Checks EC2 instance state via `ec2:DescribeInstances`
- Checks Security Group rules via `ec2:DescribeSecurityGroups`
- Checks Route Tables via `ec2:DescribeRouteTables`
- Checks NACLs via `ec2:DescribeNetworkAcls`
- Checks service status via SSM Run Command (`Get-Service W3SVC`, `systemctl status nginx`)
- Checks CPU via `cloudwatch:GetMetricStatistics`
- Produces signals: `stopped_instance`, `missing_port_80_rule`, `high_cpu_utilization`, `iis_stopped`
