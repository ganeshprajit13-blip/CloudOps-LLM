# AWS NAT Gateway & Internet Gateway Architecture

## 1. What is an AWS NAT Gateway?
A **NAT Gateway** (Network Address Translation Gateway) is a highly available, managed AWS network service that enables EC2 instances in a **private subnet** to connect outbound to the internet or other AWS services, while blocking unsolicited inbound connections from the internet.

### Key Characteristics of NAT Gateway:
- **Outbound Egress Only**: Enables private instances to download software patches, OS updates, and external API data without exposing public IP addresses.
- **Private Subnet Protection**: Private instances do not require public IP addresses. The NAT Gateway maps private IP addresses to its assigned Elastic IP (EIP) address.
- **Managed High Availability**: AWS automatically scales NAT Gateway bandwidth up to 100 Gbps across availability zones.

---

## 2. NAT Gateway vs. Internet Gateway (IGW)

| Feature | Internet Gateway (IGW) | NAT Gateway |
| :--- | :--- | :--- |
| **Primary Purpose** | Connects VPC to the public internet for public resources. | Provides outbound internet access for private resources. |
| **Subnet Location** | Attached at the VPC level; routed in **Public Subnets**. | Deployed inside a **Public Subnet** with an Elastic IP. |
| **Traffic Direction** | Supports both inbound & outbound IPv4/IPv6 traffic. | Supports **outbound traffic only** (blocks inbound connections). |
| **IP Requirement** | EC2 instances require a **Public IPv4 address**. | EC2 instances use **Private IPs** only. |

---

## 3. How NAT Gateway Works in a VPC Network Flow
1. **Private Subnet Route Table**: Configured with a default route (`0.0.0.0/0`) pointing to the NAT Gateway ID (`nat-xxxxxxxx`).
2. **Traffic Outbound Flow**:
   - Private EC2 Instance (`10.0.2.15`) sends an HTTP request to `0.0.0.0/0`.
   - Route table forwards packet to NAT Gateway (`nat-xxxxxxxx`) in the Public Subnet.
   - NAT Gateway substitutes source IP with its Elastic IP (`54.210.12.34`) and sends packet to Internet Gateway (`igw-xxxxxxxx`).
   - External internet service responds back to NAT Gateway's Elastic IP.
   - NAT Gateway routes return packet back to Private EC2 (`10.0.2.15`).

---

## 4. Troubleshooting NAT Gateway & Private Egress
- **Missing Route Table Entry**: If a private subnet's route table lacks a `0.0.0.0/0 -> nat-xxxxxxxx` route, outbound internet requests timeout (`missing_nat_route`).
- **NAT Gateway State**: Ensure NAT Gateway status is `available` (not `pending` or `failed`).
- **Public Subnet IGW Route**: The public subnet hosting the NAT Gateway MUST have a route to an Internet Gateway (`0.0.0.0/0 -> igw-xxxxxxxx`).
