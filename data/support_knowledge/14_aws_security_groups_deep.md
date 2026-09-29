# AWS Security Groups — Deep Dive

## 1. What is a Security Group?

An **AWS Security Group** is a stateful virtual firewall that controls inbound and outbound network traffic to and from your EC2 instances, RDS databases, Lambda functions in VPC, and other AWS resources.

Security Groups operate at the **Elastic Network Interface (ENI) level** — directly attached to each resource's network adapter.

---

## 2. Key Characteristics

- **Stateful**: If inbound traffic is allowed (e.g., HTTP on port 80), the return outbound response is automatically permitted without needing an explicit outbound rule.
- **Allow Rules Only**: You can only create ALLOW rules. There is no DENY rule in Security Groups. (Use NACLs for explicit DENY.)
- **Default Behavior**: All inbound traffic is BLOCKED by default. All outbound traffic is ALLOWED by default.
- **Dynamic Updates**: Rule changes apply immediately to all attached resources — no restart required.
- **Multiple Assignments**: A single EC2 instance can have up to 5 Security Groups attached simultaneously.

---

## 3. Inbound vs Outbound Rules

### Inbound Rules
Control traffic coming INTO the resource.

| Type | Protocol | Port | Source | Use Case |
| :--- | :--- | :--- | :--- | :--- |
| SSH | TCP | 22 | Your IP (1.2.3.4/32) | Linux EC2 admin |
| RDP | TCP | 3389 | Your IP (1.2.3.4/32) | Windows EC2 admin |
| HTTP | TCP | 80 | 0.0.0.0/0 | Public web server |
| HTTPS | TCP | 443 | 0.0.0.0/0 | Public web server SSL |
| Custom TCP | TCP | 8080 | SG-xxxxxx | Internal app traffic |

### Outbound Rules
Control traffic going OUT of the resource. Default: All traffic ALLOWED.

---

## 4. Security Group Sources

Sources for inbound rules can be:
- **IP CIDR**: `0.0.0.0/0` (all IPv4), `10.0.0.0/16` (VPC internal)
- **Another Security Group ID**: Allow traffic only from resources in SG-xxxxxxxx (useful for ALB → EC2)
- **My IP**: Restricts to your current public IP address

---

## 5. Security Group vs NACL Comparison

| Feature | Security Group | NACL |
| :--- | :--- | :--- |
| Level | Instance/ENI level | Subnet level |
| State | Stateful (return traffic auto-allowed) | Stateless (both inbound and outbound rules needed) |
| Rule types | ALLOW only | ALLOW and DENY |
| Rule order | All rules evaluated simultaneously | Rules evaluated in numeric order |
| Default inbound | Block all | Allow all (default NACL) |
| Applies to | Specific instances | All resources in subnet |

---

## 6. Common Security Group Mistakes

- Missing inbound rule for port 80 (HTTP) — web server unreachable
- Missing inbound rule for port 443 (HTTPS) — SSL connections rejected
- SSH port 22 open to `0.0.0.0/0` — security risk, restrict to known IPs
- Outbound rules accidentally deleted — EC2 cannot send any traffic
- Wrong Security Group attached to wrong EC2 instance
- Referencing deleted Security Group ID as a source rule

---

## 7. Security Group in CloudOps

CloudOps reads Security Group inbound rules via `ec2:DescribeSecurityGroups`. The AI Troubleshooter produces signals:
- `missing_port_80_rule` — HTTP port 80 not in inbound rules
- `missing_port_443_rule` — HTTPS port 443 not in inbound rules
- `missing_rdp_rule` — RDP port 3389 not in inbound rules
- `missing_ssh_rule` — SSH port 22 not in inbound rules

These signals are used as direct evidence in the diagnosis output.
