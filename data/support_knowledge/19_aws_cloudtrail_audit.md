# AWS CloudTrail — API Audit and Change Tracking

## 1. What is AWS CloudTrail?

**AWS CloudTrail** is an AWS governance, compliance, and security auditing service that records every API call and management event made in your AWS account. CloudTrail answers the question: **"Who did what, when, and from where?"**

CloudTrail captures:
- Which IAM user or role made the request
- Which AWS API action was called
- What resource was affected
- The timestamp of the action
- The source IP address of the request
- Whether the request succeeded or failed

---

## 2. What CloudTrail Records

CloudTrail records three types of events:

| Event Type | Description | Examples |
| :--- | :--- | :--- |
| Management Events | Control plane API calls | `RunInstances`, `StopInstances`, `AuthorizeSecurityGroupIngress`, `CreateVpc` |
| Data Events | Data plane operations | S3 object-level operations, Lambda invocations |
| Insights Events | Unusual API activity patterns | Spike in IAM API calls |

---

## 3. How to Find Who Changed a Security Group

To find out who changed a Security Group (added or removed a rule):

### Using CloudTrail Event History
1. Go to **AWS Console > CloudTrail > Event history**
2. Filter by **Event name**: `AuthorizeSecurityGroupIngress` (added inbound rule)
   or `RevokeSecurityGroupIngress` (removed inbound rule)
3. Set a time range covering when the change occurred
4. Inspect the event JSON for `userIdentity.arn` — this shows who made the change

### Key CloudTrail Security Group Events
- `AuthorizeSecurityGroupIngress` — Inbound rule added
- `RevokeSecurityGroupIngress` — Inbound rule removed
- `AuthorizeSecurityGroupEgress` — Outbound rule added
- `RevokeSecurityGroupEgress` — Outbound rule removed
- `CreateSecurityGroup` — New Security Group created
- `DeleteSecurityGroup` — Security Group deleted

### Using AWS CLI
```bash
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=AuthorizeSecurityGroupIngress \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-02T00:00:00Z
```

---

## 4. CloudTrail Event Structure

Each event contains:
```json
{
  "eventTime": "2024-01-15T14:32:00Z",
  "eventName": "AuthorizeSecurityGroupIngress",
  "userIdentity": {
    "type": "IAMUser",
    "arn": "arn:aws:iam::123456789012:user/john.doe",
    "userName": "john.doe"
  },
  "sourceIPAddress": "203.0.113.42",
  "requestParameters": {
    "groupId": "sg-0abc123def456",
    "ipPermissions": [...]
  }
}
```

---

## 5. CloudTrail Trails

By default, CloudTrail provides **90 days of Event History** in the console. To retain longer:
- Create a **Trail** that writes to an **S3 bucket** for unlimited retention
- Enable **CloudWatch Logs integration** to monitor CloudTrail events in real time
- Enable **CloudTrail Insights** to detect anomalous API activity

---

## 6. CloudTrail vs CloudWatch

| Aspect | CloudTrail | CloudWatch |
| :--- | :--- | :--- |
| Purpose | API auditing, change tracking | Performance monitoring |
| Data | Who changed what | Is my instance healthy? |
| Answers | "Who deleted my Security Group?" | "Is CPU at 90%?" |
| Key question | Compliance and forensics | Operations and alerting |
| Retention | 90 days (Event History) | Up to 15 months |

---

## 7. CloudTrail in CloudOps

CloudOps queries CloudTrail via `cloudtrail:LookupEvents` to correlate recent infrastructure changes with incident start times. Evidence includes:
- Recent Security Group modifications (within last 2 hours of incident)
- Recent EC2 state changes (stop/start/terminate events)
- Recent IAM permission changes

This correlation helps identify whether an infrastructure change caused the current incident.

---

## 8. Common CloudTrail Mistakes

- Assuming 90-day Event History is permanent (create a Trail + S3 bucket for long retention)
- Not enabling CloudTrail in all AWS regions (attackers may use regions you don't monitor)
- Forgetting to enable **log file validation** — detects if trail logs are tampered with
- Confusing CloudTrail with CloudWatch — CloudTrail is audit, CloudWatch is monitoring
- No alerts on sensitive CloudTrail events (e.g., root account login, IAM policy changes)
