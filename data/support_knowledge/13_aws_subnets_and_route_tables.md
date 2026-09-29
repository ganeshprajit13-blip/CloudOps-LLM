# AWS Subnets and Route Tables

## 1. What is a Subnet?

A **subnet** (subnetwork) is a range of IP addresses within your VPC, confined to a single **Availability Zone (AZ)**. Subnets partition your VPC network into smaller segments for security, routing, and availability isolation.

Every EC2 instance, RDS database, and Lambda VPC function is launched inside a specific subnet.

---

## 2. Public Subnet vs Private Subnet

| Feature | Public Subnet | Private Subnet |
| :--- | :--- | :--- |
| Internet Access | Direct via Internet Gateway | Via NAT Gateway only (outbound) |
| EC2 Public IP | Requires public or Elastic IP | Uses private IP only |
| Route Table | 0.0.0.0/0 points to igw-xxx | 0.0.0.0/0 points to nat-xxx |
| Use Cases | Web servers, load balancers, bastion hosts | Databases, application servers, backend |

---

## 3. Subnet CIDR Blocks

Subnets are assigned a subset of the VPC CIDR range. Example for a `10.0.0.0/16` VPC:
- Public Subnet AZ-a: `10.0.1.0/24` (256 addresses)
- Public Subnet AZ-b: `10.0.2.0/24`
- Private Subnet AZ-a: `10.0.10.0/24`
- Private Subnet AZ-b: `10.0.11.0/24`

AWS reserves 5 IP addresses from every subnet (first 4 + last 1). A /24 subnet provides 251 usable addresses.

---

## 4. What is a Route Table?

A **Route Table** contains a set of rules (routes) that determine where network traffic is directed. Each subnet must be associated with exactly one route table.

### Route Table Entries

| Destination | Target | Meaning |
| :--- | :--- | :--- |
| 10.0.0.0/16 | local | All VPC-internal traffic stays local |
| 0.0.0.0/0 | igw-xxxxxxxx | Public internet via Internet Gateway |
| 0.0.0.0/0 | nat-xxxxxxxx | Outbound internet via NAT Gateway |

### Important Rules

- A **public subnet** must have a route `0.0.0.0/0 → igw-xxxxxxxx`
- A **private subnet** must have a route `0.0.0.0/0 → nat-xxxxxxxx` for internet egress
- The **main route table** (default) is automatically created with a VPC and only contains the local route

---

## 5. Route Table in CloudOps Diagnostics

CloudOps reads route tables using `ec2:DescribeRouteTables`. The AI Troubleshooter checks for:
- `missing_igw_route` — public subnet missing Internet Gateway entry
- `missing_nat_route` — private subnet missing NAT Gateway entry

These signals are used as evidence in the 6-field diagnosis output.

---

## 6. Subnet Auto-Assign Public IP

If **Auto-assign public IPv4 address** is enabled on a public subnet, EC2 instances launched in that subnet automatically receive a public IP. Without a public IP and without an Elastic IP, the instance cannot receive inbound internet traffic even if Security Group allows it.

---

## 7. Common Subnet and Route Table Mistakes

- Launching web server EC2 in a private subnet (missing public IP + IGW route)
- Route table associated with wrong subnet after restructuring VPC
- NAT Gateway placed in private subnet instead of public subnet
- No outbound route in private subnet route table — EC2 cannot download updates
- Duplicate or conflicting route entries
