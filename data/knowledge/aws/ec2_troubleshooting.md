# EC2 Instance Troubleshooting Guide

*Project-Created Authoritative Troubleshooting Knowledge*

## Common Failure Modes & Diagnostic Steps

### 1. Unreachable EC2 Instance (SSH / HTTP / HTTPS Timeout)
- **Symptom**: Connection timed out when attempting SSH (port 22) or web traffic (port 80/443) to EC2 instance.
- **Diagnostic Steps**:
  1. Check **Instance State**: Ensure instance status is `running` and both System Status Check and Instance Status Check are `2/2 checks passed`.
  2. Verify **Public IP / Elastic IP**: Confirm whether the instance has a public IP assigned if connecting directly from the internet.
  3. Inspect **Security Group Rules**: Verify that inbound security group rules allow traffic on required ports (e.g., TCP 22, TCP 80, TCP 443) from your source IP.
  4. Inspect **Subnet Route Table**: Ensure public subnets have a default route (`0.0.0.0/0`) target pointing to an **Internet Gateway (IGW)** (`igw-xxxxxx`).
  5. Inspect **Network ACLs (NACLs)**: Remember that NACLs are stateless. Check both inbound AND outbound rules for ephemeral port ranges (`1024-65535`).

### 2. High CPU Utilization & Performance Degradation
- **Symptom**: CloudWatch alarm `CPUUtilization > 90%` triggering on EC2 instance.
- **Diagnostic Steps**:
  1. Check **CloudWatch CPUMetrics**: Identify if CPU usage is sustained or a transient burst.
  2. For **T2/T3 Burstable Instances**: Check `CPUCreditBalance` and `CPUSurpass`. If CPU credits are exhausted, performance will be throttled down to baseline.
  3. Inspect running processes via SSH/Session Manager: Run `top`, `htop`, or `ps aux --sort=-%cpu` to identify CPU-hogging processes.
  4. Remediate by scaling vertically (e.g., resizing instance type) or scaling horizontally via Auto Scaling Groups (ASG).
