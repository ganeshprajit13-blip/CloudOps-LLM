# AWS VPC — Virtual Private Cloud Fundamentals

## 1. What is a VPC?

A **Virtual Private Cloud (VPC)** is a logically isolated, private network environment within the AWS cloud where you launch and run your AWS resources such as EC2 instances, RDS databases, and Lambda functions.

A VPC gives you full control over:
- IP address ranges (using CIDR notation, e.g., `10.0.0.0/16`)
- Subnets (public and private)
- Route tables
- Internet Gateways and NAT Gateways
- Network Access Control Lists (NACLs) and Security Groups
- VPC peering and VPN connections

Every AWS account is provisioned with a **Default VPC** in each region for quick use.

---

## 2. VPC CIDR Blocks

A VPC is defined by an IPv4 CIDR block. Common choices:
- `10.0.0.0/16` — 65,536 IP addresses
- `172.31.0.0/16` — Default VPC CIDR
- `192.168.0.0/24` — Small, 256 IP addresses

---

## 3. Default VPC vs Custom VPC

| Feature | Default VPC | Custom VPC |
| :--- | :--- | :--- |
| Created automatically | Yes, per region | No, you create it |
| Subnets | Public subnet in each AZ | You define public/private subnets |
| Internet Gateway | Attached automatically | Must attach manually |
| CIDR | 172.31.0.0/16 | Your choice |
| Use case | Quick testing | Production workloads |

---

## 4. VPC Core Components

- **Subnets**: Segments of your VPC IP range within a specific Availability Zone.
- **Route Tables**: Define how network traffic is directed within the VPC and to the internet.
- **Internet Gateway (IGW)**: Allows resources in public subnets to communicate with the internet.
- **NAT Gateway**: Allows private subnet EC2 instances to access the internet without exposing them publicly.
- **Security Groups**: Stateful, instance-level virtual firewalls.
- **NACLs (Network ACLs)**: Stateless, subnet-level firewall rules.
- **VPC Peering**: Connect two VPCs so resources can communicate using private IP addresses.

---

## 5. VPC in CloudOps

CloudOps inspects VPC configuration during network diagnostics, including:
- Subnet association of the EC2 instance
- Route table entries (missing IGW or NAT Gateway routes)
- Security Group inbound rules
- NACL subnet-level rules

The AI Troubleshooter produces missing_igw_route and missing_nat_route signals from VPC route table analysis.

---

## 6. Common VPC Mistakes

- Launching EC2 in a private subnet expecting public access (no IGW route)
- Missing 0.0.0.0/0 to igw-xxx in route table for public subnets
- Overlapping CIDR blocks when creating VPC peering connections
- Forgetting to enable DNS hostnames for public instance naming
- Associating a custom NACL that blocks ephemeral ports (1024-65535)
