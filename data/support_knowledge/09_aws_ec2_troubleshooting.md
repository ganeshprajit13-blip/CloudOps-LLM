# Unreachable EC2 Website Troubleshooting Checklist

## 1. Step-by-Step EC2 Unreachable Website Diagnostic Checklist
When a website hosted on an Amazon EC2 instance becomes unreachable (HTTP/HTTPS connection timeout or connection refused), perform the following ordered troubleshooting steps:

### Step 1: Verify EC2 Instance State
- Check instance state in AWS Console or CLI: `aws ec2 describe-instances --instance-ids <id>`.
- **Target State**: Must be `running`. If `stopped` or `stopping`, hosted web services fail immediately.

### Step 2: Confirm Public IP Address & DNS Resolution
- Verify instance has an active Public IPv4 address or Elastic IP attached.
- Test basic IP reachability: `ping <public-ip>` or `traceroute <public-ip>`.

### Step 3: Inspect Security Group Inbound Firewall Rules
- Security Groups act as stateful firewalls. Verify Inbound Rules permit incoming traffic:
  - **HTTP**: TCP Port 80 from `0.0.0.0/0`.
  - **HTTPS**: TCP Port 443 from `0.0.0.0/0`.
- Missing Port 80/443 rules result in client HTTP connection timeouts.

### Step 4: Verify Subnet Route Table & Internet Gateway (IGW)
- Public instances require a route table entry: `0.0.0.0/0 -> igw-xxxxxxxx`.
- If missing, inbound public internet traffic cannot reach the instance.

### Step 5: Check Network ACLs (NACLs) & Host Firewalls
- Subnet Network ACLs must permit inbound and outbound TCP traffic on ports 80/443 and ephemeral ports (1024-65535).
- Inspect OS-level firewall (Windows Firewall or Linux `iptables`/`ufw`).

### Step 6: Verify Web Server Service Status via SSM
- Execute read-only SSM Run Command host checks:
  - **Windows**: `Get-Service W3SVC` (IIS Web Server) or `Get-Service Apache*`.
  - **Linux**: `sudo systemctl status nginx` or `sudo systemctl status httpd`.
- If service status is `Stopped`, start the service.

### Step 7: Check Listening Port Connectivity
- Verify web server process is actively bound to listening port:
  - **Windows**: `Get-NetTCPConnection -LocalPort 80 -State Listen`.
  - **Linux**: `sudo netstat -tuln | grep :80` or `ss -tulpn | grep :80`.

---

## 2. CloudOps Read-Only Automated Diagnostics
In CloudOps, the **AI Troubleshooter** (`/troubleshoot`) automates all 7 steps above by executing read-only AWS API queries and SSM PowerShell checks, presenting a 6-field diagnosis output with verifiable evidence.
