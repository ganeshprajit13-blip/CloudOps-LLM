# Postmortem: Accidental Removal of HTTPS Inbound Rule from Production Security Group

*Category: Postmortems | Service: Security Group | Type: Postmortem*

## Incident Overview
On 2026-08-05, an operator accidentally executed a Terraform script that revoked the inbound TCP 443 rule from Security Group `sg-prod-ingress-01`.

## Impact
- Customer web requests to `https://app.cloudops.example.com` timed out.
- ALB health checks failed because backend target instances became unreachable on port 443.

## Detection & CloudTrail Audit
- Alarm `ALB-UnhealthyHostCount` triggered after 3 minutes.
- CloudTrail event search for `RevokeSecurityGroupIngress` identified the IAM user `devops-admin-alice` executing the API call at 14:02 UTC.

## Action Items & Preventive Controls
1. Applied IAM policy restriction preventing direct deletion of production ingress security group rules outside CI/CD pipeline.
2. Enabled AWS Config rule `vpc-sg-open-only-to-authorized-ports` to detect unauthorized security group rule modifications automatically.
