# AWS Cloud Infrastructure & Troubleshooting Guide

## 1. Amazon EC2 & Host Telemetry
- **Instance States**: `running`, `stopped`, `stopping`, `terminated`. If an instance is `stopped`, all hosted web applications and network connections fail immediately.
- **Status Checks**:
  - `SystemStatusCheck`: Evaluates AWS hardware, hypervisor, and network infrastructure.
  - `InstanceStatusCheck`: Evaluates operating system boot integrity and network responsiveness.
- **CPU Saturation Troubleshooting**:
  - CloudWatch metric `CPUUtilization` > 80% indicates CPU strain; > 95% indicates severe saturation.
  - Causes: Infinite process loops, unoptimized database queries, worker thread contention, or DDoS traffic.
  - Host Check via SSM: Execute `Get-Process | Sort-Object CPU -Descending` to identify top CPU-consuming process IDs.

---

## 2. VPC, Subnets & Internet Routing
- **VPC Subnet Types**:
  - **Public Subnet**: Subnet route table contains a default route (`0.0.0.0/0`) pointing to an Internet Gateway (`igw-xxxx`).
  - **Private Subnet**: Default route (`0.0.0.0/0`) points to a NAT Gateway (`nat-xxxx`).
- **Unreachable Website Symptom (Missing IGW Route)**:
  - If a public EC2 instance is located in a subnet whose route table lacks a route to an Internet Gateway, incoming public IPv4 traffic cannot reach the instance, resulting in connection timeouts (`missing_default_route` signal).

---

## 3. Security Groups & Port Management
Security Groups act as stateful virtual firewalls. By default, all inbound traffic is blocked unless explicitly permitted by an Inbound Rule.

### Key Operational Ports:
- **Port 80 (TCP / HTTP)**: Standard unencrypted web traffic. Missing rule causes HTTP connection timeouts.
- **Port 443 (TCP / HTTPS)**: Encrypted SSL/TLS web traffic. Missing rule causes HTTPS connection timeouts.
- **Port 3389 (TCP / RDP)**: Windows Remote Desktop Protocol. Missing rule prevents administrator Remote Desktop connections (`missing_port_3389_rule` signal).
- **Port 22 (TCP / SSH)**: Linux Secure Shell management.

---

## 4. Web Server & Service Troubleshooting (HTTP/HTTPS & RDP)
- **HTTP/HTTPS Unreachable Website Troubleshooting Steps**:
  1. Verify EC2 Instance state is `running`.
  2. Confirm instance has a valid Public IPv4 address attached.
  3. Inspect Security Group Inbound Rules for TCP Port 80 and Port 443.
  4. Check Subnet Route Table for default route `0.0.0.0/0 -> igw-xxxx`.
  5. Run SSM PowerShell host check to verify web server service status: `Get-Service W3SVC` (IIS web server on Windows) or `systemctl status nginx/httpd` (Linux).
  6. Verify web server is actively listening on target port: `Get-NetTCPConnection -LocalPort 80 -State Listen`.
- **RDP / 3389 Connection Timeout Troubleshooting Steps**:
  1. Confirm Security Group permits inbound TCP Port 3389 from client IP address.
  2. Inspect Windows service status via SSM: `Get-Service TermService`.
  3. Verify Remote Desktop service is listening on port 3389.

---

## 5. AWS CloudWatch, CloudTrail & Load Balancers
- **CloudWatch**: Collects performance metrics (`CPUUtilization`, `NetworkIn`, `DiskReadBytes`) and aggregates log streams.
- **CloudTrail**: Audit log recording administrative API calls (e.g. `AuthorizeSecurityGroupIngress`, `StopInstances`). Used to correlate configuration changes with incident timelines.
- **Application Load Balancer (ALB)**: Routes incoming HTTP traffic across target groups. If target instances fail health checks (e.g. HTTP ping returns non-200), ALB returns HTTP `502 Bad Gateway` or `503 Service Unavailable`.
