# AgentCore Deployment

Deploy the Deep Research RCA Agent on Amazon Bedrock AgentCore.

## Quick Start

```bash
npm install
npx cdk bootstrap  # first time only

# Deploy everything (Amplify + Cognito + AgentCore + KB + Athena)
npx cdk deploy --all -c adminEmail=you@example.com
```

Or use the deploy script (builds and deploys frontend automatically):

```bash
./scripts/deploy.sh --admin-email you@example.com
```

## Optional: OpenSearch Serverless (~$350/month)

For sub-second log queries, add OpenSearch:

```bash
npx cdk deploy --all -c deployOpenSearch=true -c adminEmail=you@example.com
```

Or via the deploy script:

```bash
./scripts/deploy.sh --admin-email you@example.com --deploy-opensearch
```

## Security

| Component | Security Control |
|-----------|-----------------|
| **OpenSearch Serverless** | SigV4 auth + scoped AOSS data access policies |
| **Agent execution role** | Read-only AOSS, Bedrock invocation, assumable by AgentCore + account principals |
| **Data ingestion role** | Read-write AOSS only, assumable by account principals |
| **DynamoDB** | AWS-managed encryption, scoped IAM access |
| **S3** | Block public access, SSL enforced |

## Configuration

| Context Variable | Default | Description |
|-----------------|---------|-------------|
| `agentName` | `rca-agent` | Resource name prefix |
| `memoryRetentionDays` | `90` | AgentCore memory retention |
| `adminEmail` | - | Admin email for Cognito (receives temp password) |
| `syncSampleData` | `false` | Auto-upload sample scenarios to KB on deploy |
| `knowledgeBaseId` | - | Use existing KB instead of creating one |
| `deployOpenSearch` | `false` | Add OpenSearch Serverless (~$350/mo) |

## What Gets Deployed

| Stack | Resources | Cost |
|-------|-----------|------|
| `RcaStack` | AgentCore Runtime + Amplify + Cognito + DynamoDB + IAM | Usage-based |
| `RcaKnowledgeBaseStack` | Bedrock KB with S3 Vectors | ~$0.10/GB |
| `RcaAthenaLogSearchStack` | S3 + Glue + Athena | ~$5/TB scanned |
| `RcaOpenSearchLogSearchStack` (opt-in) | OpenSearch Serverless | ~$350/month min |

## Local Development with OpenSearch

```bash
# Set up AWS CLI profiles (reads stack outputs automatically)
./scripts/setup-opensearch-profiles.sh

# Upload sample data
AWS_PROFILE=opensearch-ingestion python scripts/upload_logs_to_opensearch.py \
  --endpoint <CollectionEndpoint> --all

# Run the agent locally
AWS_PROFILE=rca-agent \
OPENSEARCH_ENDPOINT=<CollectionEndpoint> \
OPENSEARCH_INDEX=rca-logs \
OPENSEARCH_SERVERLESS=true \
LOG_SEARCH_BACKEND=opensearch \
RCA_AGENT_MODE=production \
python src/rca_agent.py volte-call-drop-handover
```

## Cleanup

```bash
npx cdk destroy --all
```
