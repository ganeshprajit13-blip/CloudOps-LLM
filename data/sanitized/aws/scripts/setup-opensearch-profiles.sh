#!/usr/bin/env bash
#
# Sets up AWS CLI profiles for local OpenSearch development.
#
# Creates two profiles by reading CDK stack outputs:
#   - opensearch-ingestion: For uploading logs (AOSS read-write)
#   - rca-agent:            For running the agent locally (Bedrock + AOSS read-only)
#
# Usage:
#   ./scripts/setup-opensearch-profiles.sh [--source-profile default] [--region us-east-1]
#
set -euo pipefail

SOURCE_PROFILE="default"
REGION="us-east-1"

while [[ $# -gt 0 ]]; do
  case $1 in
    --source-profile) SOURCE_PROFILE="$2"; shift 2 ;;
    --region)         REGION="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--source-profile PROFILE] [--region REGION]"
      echo ""
      echo "Sets up AWS CLI profiles for local OpenSearch development."
      echo ""
      echo "Options:"
      echo "  --source-profile  AWS profile to chain credentials from (default: default)"
      echo "  --region          AWS region (default: us-east-1)"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

echo "Reading stack outputs..."

INGESTION_ROLE_ARN=$(aws cloudformation describe-stacks \
  --stack-name RcaOpenSearchLogSearchStack \
  --profile "$SOURCE_PROFILE" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`DataIngestionRoleArn`].OutputValue' \
  --output text 2>/dev/null) || true

AGENT_ROLE_ARN=$(aws cloudformation describe-stacks \
  --stack-name RcaStack \
  --profile "$SOURCE_PROFILE" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`ExecutionRoleArn`].OutputValue' \
  --output text 2>/dev/null) || true

OPENSEARCH_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name RcaOpenSearchLogSearchStack \
  --profile "$SOURCE_PROFILE" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`CollectionEndpoint`].OutputValue' \
  --output text 2>/dev/null) || true

if [[ -z "$INGESTION_ROLE_ARN" || -z "$AGENT_ROLE_ARN" || -z "$OPENSEARCH_ENDPOINT" ]]; then
  echo "Error: Could not read stack outputs. Make sure both stacks are deployed:"
  echo "  npx cdk deploy RcaStack RcaOpenSearchLogSearchStack -c deployOpenSearch=true"
  exit 1
fi

echo ""
echo "Configuring profile: opensearch-ingestion"
aws configure set role_arn "$INGESTION_ROLE_ARN" --profile opensearch-ingestion
aws configure set source_profile "$SOURCE_PROFILE" --profile opensearch-ingestion
aws configure set region "$REGION" --profile opensearch-ingestion

echo "Configuring profile: rca-agent"
aws configure set role_arn "$AGENT_ROLE_ARN" --profile rca-agent
aws configure set source_profile "$SOURCE_PROFILE" --profile rca-agent
aws configure set region "$REGION" --profile rca-agent

echo ""
echo "Done. Two profiles configured:"
echo ""
echo "  opensearch-ingestion  — Upload logs to OpenSearch"
echo "  rca-agent             — Run the agent locally"
echo ""
echo "Upload sample data:"
echo "  AWS_PROFILE=opensearch-ingestion python scripts/upload_logs_to_opensearch.py \\"
echo "    --endpoint $OPENSEARCH_ENDPOINT --all"
echo ""
echo "Run the agent:"
echo "  AWS_PROFILE=rca-agent \\"
echo "  OPENSEARCH_ENDPOINT=$OPENSEARCH_ENDPOINT \\"
echo "  OPENSEARCH_INDEX=rca-logs \\"
echo "  OPENSEARCH_SERVERLESS=true \\"
echo "  LOG_SEARCH_BACKEND=opensearch \\"
echo "  RCA_AGENT_MODE=production \\"
echo "  python src/rca_agent.py volte-call-drop-handover"
