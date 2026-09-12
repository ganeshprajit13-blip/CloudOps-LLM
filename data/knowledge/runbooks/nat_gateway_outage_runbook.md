# Runbook: NAT Gateway Egress Failure & Private Subnet Internet Outage

*Category: Runbook | Service: VPC / NAT Gateway*

## 1. Symptom & Scope
- Instances in private subnet `subnet-private-1a` cannot access internet endpoint APIs or S3 via public internet.
- Internal VPC traffic (`10.0.0.0/16`) remains fully operational.

## 2. Diagnostic Steps
1. Verify NAT Gateway state:
   `aws ec2 describe-nat-gateways --nat-gateway-ids nat-0123456789abcdef0`
   Check if status is `failed` or `deleting`.
2. Verify Private Subnet Route Table:
   `aws ec2 describe-route-tables --route-table-ids rtb-private1`
   Confirm destination `0.0.0.0/0` points to target `nat-0123456789abcdef0`.
3. Check Elastic IP Association: Confirm NAT Gateway has active Elastic IP (`eipalloc-xxxxxx`).

## 3. Remediation Procedure
- If NAT Gateway was deleted or failed, provision a replacement NAT Gateway in public subnet `subnet-public-1a`.
- Update private subnet route table to point `0.0.0.0/0` to the new NAT Gateway ID.
