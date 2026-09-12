# Security Group & Network Firewall Troubleshooting Guide

*Project-Created Authoritative Troubleshooting Knowledge*

## Security Group Fundamentals
Security Groups act as stateful virtual firewalls for EC2 instances and network interfaces (ENIs).

Key Properties:
- **Stateful Behavior**: Return traffic is automatically allowed regardless of outbound rules.
- **Rule Evaluation**: All inbound rules are evaluated before deciding whether to allow traffic.
- **Default Behavior**: By default, new Security Groups deny all inbound traffic and allow all outbound traffic.

## HTTPS Port 443 Blocking & Connectivity Issues

### Troubleshooting HTTPS Traffic (Port 443)
If HTTPS requests to an application or web server fail with a connection timeout:

1. **Inbound Rule Verification**:
   - Check if an inbound rule exists for **Protocol**: `TCP`, **Port Range**: `443` (HTTPS).
   - Verify the **Source CIDR / Security Group ID**.
   - If behind an Application Load Balancer (ALB), the EC2 instance Security Group should allow TCP 443 or target HTTP port ONLY from the ALB's Security Group ID (e.g., `sg-alb123`), rather than `0.0.0.0/0`.
   
2. **Best Practices for Security Group Management**:
   - Do **NOT** automatically recommend exposing administrative ports (e.g., SSH 22, RDP 3389, DB 3306/5432) to `0.0.0.0/0`.
   - Restrict administrative access to specific corporate CIDR ranges, bastion hosts, or AWS Systems Manager Session Manager.
   - For public-facing web servers or ALBs, inbound TCP 80 and TCP 443 from `0.0.0.0/0` is standard, but backend application instances should restrict inbound access strictly to the ALB Security Group.

3. **Security Group vs Network ACL Comparison**:
   - Security Groups operate at the instance ENI level (stateful).
   - Network ACLs operate at the Subnet level (stateless). If NACL blocks port 443 or return ephemeral ports, Security Group rules will not override NACL block.
