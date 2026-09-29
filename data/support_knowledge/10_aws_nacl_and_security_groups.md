# AWS Network Access Control Lists (NACL) & Security Groups

## 1. What is an AWS NACL (Network Access Control List)?
A **Network Access Control List (NACL)** is an optional, stateless subnet-level security layer in an AWS Virtual Private Cloud (VPC) that acts as a firewall for controlling inbound and outbound traffic entering or leaving one or more subnets.

### Key Characteristics of AWS NACLs:
- **Subnet-Level Scope**: Applies to all EC2 instances and resources residing within the associated subnet.
- **Stateless Firewall**: Inbound and outbound traffic rules are evaluated independently. Returning traffic must be explicitly allowed by an outbound rule.
- **Allow & Deny Rules**: Supports both explicit **ALLOW** and explicit **DENY** rules (unlike Security Groups, which support ALLOW rules only).
- **Rule Order Processing**: Evaluates rules sequentially in numerical order (lowest rule number first) starting from Rule 1.

---

## 2. Why Use a NACL in a Subnet?
NACLs provide a defense-in-depth perimeter firewall for VPC subnets:
1. **Subnet Perimeter Defense**: Provides a first line of security before traffic reaches individual EC2 instances.
2. **Explicit Blocklists (Deny Rules)**: Allows network administrators to explicitly block malicious IP addresses or compromised subnet ranges.
3. **Compliance & Hardening**: Ensures strict isolation for sensitive database or application subnets.

---

## 3. NACL vs. Security Group Comparison

| Feature | Network Access Control List (NACL) | Security Group (SG) |
| :--- | :--- | :--- |
| **Operating Level** | **Subnet Level** (Applies to all resources in subnet). | **Instance / ENI Level** (Applies to individual network interfaces). |
| **State Nature** | **Stateless**: Response traffic requires explicit outbound rules. | **Stateful**: Allowed inbound traffic automatically permits return outbound traffic. |
| **Rule Types** | Supports both **ALLOW** and **DENY** rules. | Supports **ALLOW** rules only (all unspecified traffic is denied). |
| **Rule Evaluation** | Processed in **numerical order** (lowest number first). | All rules are evaluated simultaneously before permitting access. |
| **Default Config** | Default NACL allows all inbound/outbound traffic (`Rule *`). | Default SG blocks all inbound traffic; allows all outbound traffic. |

---

## 4. CloudOps Subnet & NACL Diagnostics
In **CloudOps**, NACL rules and route tables are evaluated during network connectivity diagnostics (`missing_nacl_rule` or `missing_default_route` signals) when investigating unreachable EC2 web applications or blocked subnet traffic.
