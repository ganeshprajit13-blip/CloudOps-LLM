#!/bin/bash
set -e

# Ingest scenario data into OpenSearch (KB context + logs)
# Uploads context to S3 for KB ingestion and logs directly to OpenSearch

SCENARIO_NAME="$1"
AGENT_NAME="${2:-rca-agent}"
REGION="${AWS_REGION:-us-east-1}"
INDEX_NAME="${OPENSEARCH_INDEX:-rca-logs}"

if [ -z "$SCENARIO_NAME" ]; then
  echo "Usage: $0 <scenario-name> [agent-name]"
  echo ""
  echo "Available scenarios:"
  ls -1 ../../../scenarios/ 2>/dev/null || ls -1 ../../scenarios/ 2>/dev/null || echo "  (run from deployment/agentcore directory)"
  exit 1
fi

# Find scenarios directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCENARIOS_DIR="$SCRIPT_DIR/../../../scenarios"
if [ ! -d "$SCENARIOS_DIR" ]; then
  SCENARIOS_DIR="$SCRIPT_DIR/../../scenarios"
fi

SCENARIO_PATH="$SCENARIOS_DIR/$SCENARIO_NAME"

if [ ! -d "$SCENARIO_PATH" ]; then
  echo "Error: Scenario not found: $SCENARIO_PATH"
  exit 1
fi

echo "Ingesting scenario: $SCENARIO_NAME"
echo "Scenario path: $SCENARIO_PATH"

# Get stack outputs
echo ""
echo "Fetching stack outputs..."
BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name RcaKnowledgeBaseStack \
  --query 'Stacks[0].Outputs[?ExportName==`'$AGENT_NAME'-kb-bucket`].OutputValue' \
  --output text \
  --region $REGION)

ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name RcaKnowledgeBaseStack \
  --query 'Stacks[0].Outputs[?ExportName==`'$AGENT_NAME'-opensearch-endpoint`].OutputValue' \
  --output text \
  --region $REGION)

if [ -z "$BUCKET_NAME" ] || [ "$BUCKET_NAME" == "None" ]; then
  echo "Error: Could not find S3 bucket. Deploy the stack first."
  exit 1
fi

echo "S3 Bucket: $BUCKET_NAME"
echo "OpenSearch Endpoint: $ENDPOINT"

# Upload context files to S3 (for KB ingestion)
echo ""
echo "=== Uploading context to S3 for Knowledge Base ==="
CONTEXT_DIR="$SCENARIO_PATH/context"
if [ -d "$CONTEXT_DIR" ]; then
  echo "Uploading: $CONTEXT_DIR"
  aws s3 sync "$CONTEXT_DIR" "s3://$BUCKET_NAME/scenarios/$SCENARIO_NAME/context/" \
    --region $REGION
  echo "Context uploaded to s3://$BUCKET_NAME/scenarios/$SCENARIO_NAME/context/"
else
  echo "No context directory found at $CONTEXT_DIR"
fi

# Ingest logs to OpenSearch
echo ""
echo "=== Ingesting logs to OpenSearch ==="
EVIDENCE_DIR="$SCENARIO_PATH/evidence"
if [ ! -d "$EVIDENCE_DIR" ]; then
  echo "No evidence directory found at $EVIDENCE_DIR"
  exit 0
fi

# Install awscurl if needed
pip install awscurl -q 2>/dev/null || true

LOG_INDEX="$INDEX_NAME"
ERRORS=0

# Process each log file
for LOG_FILE in "$EVIDENCE_DIR"/*.log "$EVIDENCE_DIR"/*.json; do
  [ -f "$LOG_FILE" ] || continue

  FILENAME=$(basename "$LOG_FILE")
  SERVICE_NAME=$(echo "$FILENAME" | sed 's/\.log$//' | sed 's/\.json$//')

  echo "Processing: $FILENAME (service: $SERVICE_NAME)"

  # Determine if JSON or plain text
  if [[ "$LOG_FILE" == *.json ]]; then
    # JSON logs: each line is a JSON object
    LINE_NUM=0
    while IFS= read -r line || [ -n "$line" ]; do
      [ -z "$line" ] && continue
      LINE_NUM=$((LINE_NUM + 1))

      # Parse JSON and add metadata
      DOC=$(echo "$line" | jq -c '. + {
        "source_file": "'"$FILENAME"'",
        "service": "'"$SERVICE_NAME"'",
        "scenario": "'"$SCENARIO_NAME"'"
      }' 2>/dev/null)

      if [ -n "$DOC" ]; then
        if ! awscurl --service aoss \
          --region $REGION \
          -X POST "${ENDPOINT}/${LOG_INDEX}/_doc" \
          -H "Content-Type: application/json" \
          -d "$DOC" > /dev/null 2>&1; then
          echo "  Warning: Failed to ingest JSON line $LINE_NUM from $FILENAME" >&2
          ERRORS=$((ERRORS + 1))
        fi
      else
        echo "  Warning: Failed to parse JSON at line $LINE_NUM in $FILENAME" >&2
        ERRORS=$((ERRORS + 1))
      fi
    done < "$LOG_FILE"
    echo "  Ingested $LINE_NUM records"
  else
    # Plain text logs: parse each line
    LINE_NUM=0
    while IFS= read -r line || [ -n "$line" ]; do
      [ -z "$line" ] && continue
      LINE_NUM=$((LINE_NUM + 1))

      # Try to extract timestamp and level from common formats
      TIMESTAMP=""
      LEVEL=""
      MESSAGE="$line"

      # Try ISO format: 2024-03-15T14:00:00
      if [[ $line =~ ([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}) ]]; then
        TIMESTAMP="${BASH_REMATCH[1]}"
      # Try space format: 2024-03-15 14:00:00
      elif [[ $line =~ ([0-9]{4}-[0-9]{2}-[0-9]{2}\ [0-9]{2}:[0-9]{2}:[0-9]{2}) ]]; then
        TIMESTAMP="${BASH_REMATCH[1]}"
      fi

      # Try to extract log level
      if [[ $line =~ (ERROR|WARN|INFO|DEBUG|CRITICAL|FATAL) ]]; then
        LEVEL="${BASH_REMATCH[1]}"
      fi

      # Build JSON document
      DOC=$(jq -n \
        --arg ts "$TIMESTAMP" \
        --arg level "$LEVEL" \
        --arg msg "$MESSAGE" \
        --arg src "$FILENAME" \
        --arg svc "$SERVICE_NAME" \
        --arg scenario "$SCENARIO_NAME" \
        '{
          timestamp: (if $ts != "" then $ts else null end),
          level: (if $level != "" then $level else null end),
          message: $msg,
          source_file: $src,
          service: $svc,
          scenario: $scenario
        }')

      if ! awscurl --service aoss \
        --region $REGION \
        -X POST "${ENDPOINT}/${LOG_INDEX}/_doc" \
        -H "Content-Type: application/json" \
        -d "$DOC" > /dev/null 2>&1; then
        echo "  Warning: Failed to ingest line $LINE_NUM from $FILENAME" >&2
        ERRORS=$((ERRORS + 1))
      fi

    done < "$LOG_FILE"
    echo "  Ingested $LINE_NUM records"
  fi
done

# Refresh index
echo ""
echo "Refreshing index..."
awscurl --service aoss \
  --region $REGION \
  -X POST "${ENDPOINT}/${LOG_INDEX}/_refresh" >/dev/null 2>&1 || true

# Get KB ID for re-ingestion
echo ""
echo "=== Triggering KB re-ingestion ==="
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
    echo "Starting KB ingestion job..."
    aws bedrock-agent start-ingestion-job \
      --knowledge-base-id "$KB_ID" \
      --data-source-id "$DS_ID" \
      --region $REGION >/dev/null 2>&1 || true
    echo "KB ingestion job started (runs in background)"
  fi
else
  echo "No Knowledge Base found. Deploy the CDK stack first: npx cdk deploy --all"
fi

if [ "$ERRORS" -gt 0 ]; then
  echo ""
  echo "WARNING: $ERRORS ingestion error(s) occurred" >&2
fi

# Summary
echo ""
echo "=========================================="
echo "Scenario Ingestion Complete: $SCENARIO_NAME"
echo "=========================================="
echo ""
echo "Ingested:"
echo "  - Context files to S3 (for KB)"
echo "  - Log files to OpenSearch (for evidence search)"
echo ""
echo "To search logs:"
echo "  awscurl --service aoss --region $REGION \\"
echo "    -X GET '${ENDPOINT}/${LOG_INDEX}/_search' \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"query\": {\"bool\": {\"must\": [{\"match\": {\"message\": \"timeout\"}}], \"filter\": [{\"term\": {\"scenario\": \"$SCENARIO_NAME\"}}]}}}'"
echo ""
