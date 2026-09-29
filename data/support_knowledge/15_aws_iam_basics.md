# AWS IAM — Identity and Access Management

## 1. What is AWS IAM?

**AWS IAM (Identity and Access Management)** is the AWS service that controls who is authenticated (signed in) and authorized (has permissions) to use AWS resources. IAM is global — not region-specific.

IAM allows you to:
- Create and manage **Users**, **Groups**, and **Roles**
- Attach **Policies** that define what actions are allowed or denied
- Enforce **Multi-Factor Authentication (MFA)**
- Grant **temporary credentials** via STS (Security Token Service)

---

## 2. IAM Core Concepts

### IAM User
A **User** is an identity for a person or application that interacts with AWS. Users have permanent long-term credentials (access key ID + secret access key, or password for console).

### IAM Group
A **Group** is a collection of IAM users. Attach policies to a group instead of individual users for easier management.

Example: `Developers` group with `AmazonEC2ReadOnlyAccess` policy.

### IAM Role
An **IAM Role** is an identity with permission policies that can be assumed by:
- AWS services (e.g., EC2 instance role, Lambda execution role)
- IAM users in the same or different account
- External identity providers (SAML, OIDC)

Roles use **temporary credentials** (no permanent keys). This is the recommended approach for granting AWS service permissions.

### IAM Policy
A **Policy** is a JSON document that defines permissions. Policies are attached to users, groups, or roles.

Example policy that allows EC2 read-only access:
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": "ec2:Describe*",
    "Resource": "*"
  }]
}
```

---

## 3. IAM Policy Types

| Type | Description |
| :--- | :--- |
| AWS Managed Policy | Pre-built policies managed by AWS (e.g., `AmazonS3ReadOnlyAccess`) |
| Customer Managed Policy | Custom policies you create and manage |
| Inline Policy | Policies embedded directly into a user/group/role (not reusable) |
| Resource-based Policy | Attached to a resource (e.g., S3 bucket policy) |

---

## 4. IAM Role — EC2 Instance Profile

When an EC2 instance needs to call AWS APIs (e.g., read from S3, publish to CloudWatch), you attach an **Instance Profile** with an IAM Role. The EC2 instance then uses temporary credentials provided by the Instance Metadata Service (IMDS).

This is far more secure than embedding access keys in application code.

---

## 5. Principle of Least Privilege

IAM best practice: **grant only the minimum permissions needed** for a task.

- Avoid using `*` (wildcard) on resource ARNs in production
- Use condition keys to restrict by IP, time, or MFA status
- Regularly audit IAM permissions with **IAM Access Analyzer**

---

## 6. IAM in CloudOps

CloudOps uses a **read-only IAM role** with the following permissions for telemetry collection:
- `ec2:Describe*` — EC2 and VPC inspection
- `cloudwatch:GetMetricStatistics` — CPU and metric collection
- `cloudtrail:LookupEvents` — Audit log inspection
- `ssm:SendCommand` + `ssm:GetCommandInvocation` — Host-level checks

CloudOps never assumes write permissions. The system is advisory-only.

---

## 7. Common IAM Mistakes

- Attaching `AdministratorAccess` to non-admin users
- Sharing access keys between multiple team members
- Not rotating access keys regularly (rotate every 90 days)
- Not enabling MFA for root account and privileged users
- Forgetting to attach instance profile to EC2 — application cannot call AWS APIs
