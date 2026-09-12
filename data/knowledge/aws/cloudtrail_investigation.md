# CloudTrail Security & API Audit Investigation Guide

*Project-Created Authoritative Troubleshooting Knowledge*

## AWS CloudTrail Overview
AWS CloudTrail records AWS API calls and management events made across your account by IAM users, roles, or AWS services.

## Investigating "Who changed my AWS configuration?"

### 1. Identifying Recent Security Group & VPC Modifications
When troubleshooting unexpected network outages or security group modifications:
- Filter CloudTrail event history by **Event name**:
  - `AuthorizeSecurityGroupIngress`: Added inbound rule.
  - `RevokeSecurityGroupIngress`: Removed inbound rule.
  - `AuthorizeSecurityGroupEgress` / `RevokeSecurityGroupEgress`: Modified outbound rules.
  - `ModifySubnetAttribute`: Changed public IP assignment settings.
  - `ReplaceRoute`: Changed route table target (e.g. replaced IGW/NAT gateway route).

### 2. Key Event Fields to Analyze
- **`userIdentity`**: Contains `arn`, `userName`, `principalId`, or assumed role session name of the actor who initiated the change.
- **`eventTime`**: Exact UTC timestamp when the API call occurred.
- **`sourceIPAddress`**: IP address from which the API call was requested.
- **`requestParameters`**: Detailed JSON configuration changes (e.g. port range, target security group, CIDR block).

### 3. Example Inquiry
Query: "Who modified security group sg-0123456789abcdef0?"
Action: Search CloudTrail LookupEvents for `ResourceName=sg-0123456789abcdef0`. Inspect `userIdentity` and `eventTime` to pinpoint unauthorized or accidental rule deletions.
