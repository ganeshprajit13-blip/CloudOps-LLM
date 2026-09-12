#!/bin/bash
set -e

# Delete scenario data from OpenSearch and S3
# Use this to clean up after testing a scenario

SCENARIO_NAME="$1"
AGENT_NAME="${2:-rca-agent}"
REGION="${AWS_REGION:-us-east-1}"
INDEX_NAME="${OPENSEARCH_INDEX:-rca-logs}"

if [ -z "$SCENARIO_NAME" ]; then
  echo "Usage: $0 <scenario-name> [agent-name]"
  echo ""
  echo "This will delete all data for the specified scenario from:"
  echo "  - OpenSearch logs index"
  echo "  - S3 bucket (context files)"
  exit 1
fi

echo "Deleting scenario data: $SCENARIO_NAME"
read -p "Are you sure? (y/N): " confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
  echo "Cancelled."
  exit 0
fi

# Get stack outputs
echo ""
echo "Fetching stack outputs..."
BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name RcaKnowledgeBaseStack \
  --query 'Stacks[0].Outputs[?ExportName==`'$AGENT_NAME'-kb-bucket`].OutputValue' \
  --output text \
  --region $REGION 2>/dev/null || echo "")

ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name RcaKnowledgeBaseStack \
  --query 'Stacks[0].Outputs[?ExportName==`'$AGENT_NAME'-opensearch-endpoint`].OutputValue' \
  --output text \
  --region $REGION 2>/dev/null || echo "")

# Delete from OpenSearch
if [ -n "$ENDPOINT" ] && [ "$ENDPOINT" != "None" ]; then
  echo ""
  echo "=== Deleting logs from OpenSearch ==="
  LOG_INDEX="$INDEX_NAME"

  pip install awscurl -q 2>/dev/null || true

  # Delete by query (all docs with this scenario)
  DELETED=$(awscurl --service aoss \
    --region $REGION \
    -X POST "${ENDPOINT}/${LOG_INDEX}/_delete_by_query" \
    -H "Content-Type: application/json" \
    -d '{
      "query": {
        "term": {
          "scenario": "'"$SCENARIO_NAME"'"
        }
      }
    }' 2>&1)

  COUNT=$(echo "$DELETED" | jq -r '.deleted // 0' 2>/dev/null || echo "0")
  echo "Deleted $COUNT log records from OpenSearch"

  # Refresh index
  awscurl --service aoss \
    --region $REGION \
    -X POST "${ENDPOINT}/${LOG_INDEX}/_refresh" >/dev/null 2>&1 || true
else
  echo "OpenSearch endpoint not found, skipping log deletion"
fi

# Delete from S3
if [ -n "$BUCKET_NAME" ] && [ "$BUCKET_NAME" != "None" ]; then
  echo ""
  echo "=== Deleting context from S3 ==="

  # List and delete
  if ! aws s3 rm "s3://$BUCKET_NAME/scenarios/$SCENARIO_NAME/" --recursive --region $REGION 2>&1; then
    echo "Warning: S3 deletion may have been incomplete" >&2
  fi
  echo "Deleted S3 files for scenario"
else
  echo "S3 bucket not found, skipping S3 deletion"
fi

# Trigger KB re-ingestion to remove deleted docs
echo ""
echo "=== Triggering KB re-sync ==="
KB_ID=$(aws bedrock-agent list-knowledge-bases \
  --query "knowledgeBaseSummaries[?name=='${AGENT_NAME}-knowledge-base'].knowledgeBaseId" \
  --output text \
  --region $REGION 2>/dev/null || echo "")

if [ -n "$KB_ID" ] && [ "$KB_ID" != "None" ]; then
  DS_ID=$(aws bedrock-agent list-data-sources \
    --knowledge-base-id "$KB_ID" \
    --query 'dataSourceSummaries[0].dataSourceId' \
    --output text \
    --region $REGION 2>/dev/null || echo "")

  if [ -n "$DS_ID" ] && [ "$DS_ID" != "None" ]; then
    echo "Starting KB re-ingestion to sync deletions..."
    aws bedrock-agent start-ingestion-job \
      --knowledge-base-id "$KB_ID" \
      --data-source-id "$DS_ID" \
      --region $REGION >/dev/null 2>&1 || true
    echo "KB re-ingestion started (runs in background)"
  fi
else
  echo "No Knowledge Base found, skipping KB sync"
fi

# Summary
echo ""
echo "=========================================="
echo "Scenario Deleted: $SCENARIO_NAME"
echo "=========================================="
echo ""
