# IAM Permission & Access Denied Troubleshooting Guide

*Project-Created Authoritative Troubleshooting Knowledge*

## IAM Evaluation Logic
AWS Identity and Access Management (IAM) evaluates permissions using an explicit deny model:
1. Default: **Implicit Deny**.
2. If any policy contains an **Explicit Deny**, the request is denied regardless of allow policies.
3. Requests require an **Explicit Allow** from identity-based or resource-based policies.

## Common Access Denied Failure Modes

### 1. `AccessDenied` / `UnauthorizedOperation` Errors
- **Symptom**: EC2 instance or application receives `ClientError: An error occurred (AccessDenied) when calling the GetParameter operation`.
- **Diagnostic Steps**:
  1. Check EC2 Instance **IAM Role / Instance Profile**: Ensure instance is associated with an IAM Role.
  2. Inspect IAM Policy Statements: Verify policy contains correct `Action` (e.g., `ssm:GetParameter`), `Resource` ARN (e.g., `arn:aws:ssm:region:account:parameter/app/*`), and `Effect: Allow`.
  3. KMS Key Policy: If accessing encrypted resources (SSM Parameter, S3 Bucket, EBS Volume), ensure key policy permits `kms:Decrypt`.

### 2. Service Control Policies (SCPs) & Permission Boundaries
- In AWS Organizations, SCPs can override account-level IAM permissions. If an SCP denies an action or region, account root and IAM users/roles are blocked.
