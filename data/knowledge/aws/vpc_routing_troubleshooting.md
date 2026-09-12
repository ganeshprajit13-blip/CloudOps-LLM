# VPC Routing & Internet Access Troubleshooting Guide

*Project-Created Authoritative Troubleshooting Knowledge*

## VPC Architecture & Routing Rules

### 1. Public Subnet Routing (Internet Access)
For resources in a Public Subnet to access or be accessed from the internet:
- **Subnet Route Table**: Must contain a default route `0.0.0.0/0` with target `igw-xxxxxx` (Internet Gateway).
- **Public IP**: The EC2 instance or ENI must have an assigned IPv4 Public IP or Elastic IP (EIP).
- **Internet Gateway State**: The IGW must be attached to the VPC.

### 2. Private Subnet Outbound Internet Access (NAT Gateway)
For instances in a Private Subnet (without public IPs) to reach the internet (e.g. for software updates, external APIs):
- **Subnet Route Table**: Private subnet route table must have a default route `0.0.0.0/0` pointing to a **NAT Gateway** (`nat-xxxxxx`) located in a **Public Subnet**.
- **NAT Gateway State**: Must be in `available` state and have an Elastic IP attached.
- **Common Failure Mode**: If NAT Gateway is deleted, failed, or placed in a private subnet, instances in private subnets lose internet connectivity.
- **Symptom**: Private instances can communicate with local VPC resources (`10.0.0.0/16`), but `curl https://aws.amazon.com` or package updates time out.

### 3. Route Table Evaluation Order
AWS VPC route tables evaluate routes using **Longest Prefix Match**:
1. Most specific route wins (e.g., `10.0.1.0/24` local VPC traffic).
2. Default route `0.0.0.0/0` handles all unmatched outbound internet traffic.
