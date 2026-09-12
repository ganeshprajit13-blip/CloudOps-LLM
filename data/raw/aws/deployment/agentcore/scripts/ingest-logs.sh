#!/bin/bash
set -e

# Ingest custom logs from any source into OpenSearch
# Use this to ingest logs from external systems, devices, or custom sources

LOG_PATH="$1"
SCENARIO_TAG="$2"
SERVICE_NAME="$3"
AGENT_NAME="${4:-rca-agent}"
REGION="${AWS_REGION:-us-east-1}"
INDEX_NAME="${OPENSEARCH_INDEX:-rca-logs}"

if [ -z "$LOG_PATH" ] || [ -z "$SCENARIO_TAG" ]; then
  echo "Usage: $0 <log-file-or-dir> <scenario-tag> [service-name] [agent-name]"
  echo ""
  echo "Arguments:"
  echo "  log-file-or-dir  Path to log file or directory containing logs"
  echo "  scenario-tag     Tag to identify these logs (e.g., 'external-device-1')"
  echo "  service-name     Optional service name (defaults to filename)"
  echo "  agent-name       Optional agent name (default: rca-agent)"
  echo ""
  echo "Examples:"
  echo "  $0 /var/log/app.log my-investigation"
  echo "  $0 ./collected-logs/ device-crash-2024 iot-gateway"
  echo "  $0 ~/downloads/exported.json custom-scenario api-service"
  exit 1
fi

if [ ! -e "$LOG_PATH" ]; then
  echo "Error: Path not found: $LOG_PATH"
  exit 1
fi

echo "Ingesting logs with scenario tag: $SCENARIO_TAG"

# Get OpenSearch endpoint
ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name RcaKnowledgeBaseStack \
  --query 'Stacks[0].Outputs[?ExportName==`'$AGENT_NAME'-opensearch-endpoint`].OutputValue' \
  --output text \
  --region $REGION 2>/dev/null || echo "")

if [ -z "$ENDPOINT" ] || [ "$ENDPOINT" == "None" ]; then
  echo "Error: Could not find OpenSearch endpoint. Deploy the stack first."
  exit 1
fi

echo "OpenSearch Endpoint: $ENDPOINT"

# Install awscurl if needed
pip install awscurl -q 2>/dev/null || true

LOG_INDEX="$INDEX_NAME"
ERRORS=0

# Function to ingest a single log file
ingest_file() {
  local LOG_FILE="$1"
  local SVC_NAME="$2"

  local FILENAME=$(basename "$LOG_FILE")
  local DEFAULT_SVC=$(echo "$FILENAME" | sed 's/\.log$//' | sed 's/\.json$//')
  SVC_NAME="${SVC_NAME:-$DEFAULT_SVC}"

  echo "Processing: $LOG_FILE (service: $SVC_NAME)"

  local LINE_NUM=0
  local FILE_ERRORS=0

  # Determine if JSON or plain text
  if [[ "$LOG_FILE" == *.json ]] || head -1 "$LOG_FILE" | jq . >/dev/null 2>&1; then
    # JSON logs
    while IFS= read -r line || [ -n "$line" ]; do
      [ -z "$line" ] && continue
      LINE_NUM=$((LINE_NUM + 1))

      DOC=$(echo "$line" | jq -c '. + {
        "source_file": "'"$FILENAME"'",
        "service": "'"$SVC_NAME"'",
        "scenario": "'"$SCENARIO_TAG"'"
      }' 2>/dev/null)

      if [ -n "$DOC" ]; then
        if ! awscurl --service aoss \
          --region $REGION \
          -X POST "${ENDPOINT}/${LOG_INDEX}/_doc" \
          -H "Content-Type: application/json" \
          -d "$DOC" > /dev/null 2>&1; then
          echo "  Warning: Failed to ingest JSON line $LINE_NUM from $FILENAME" >&2
          FILE_ERRORS=$((FILE_ERRORS + 1))
        fi
      else
        echo "  Warning: Failed to parse JSON at line $LINE_NUM in $FILENAME" >&2
        FILE_ERRORS=$((FILE_ERRORS + 1))
      fi
    done < "$LOG_FILE"
  else
    # Plain text logs
    while IFS= read -r line || [ -n "$line" ]; do
      [ -z "$line" ] && continue
      LINE_NUM=$((LINE_NUM + 1))

      local TIMESTAMP=""
      local LEVEL=""

      # Extract timestamp
      if [[ $line =~ ([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}) ]]; then
        TIMESTAMP="${BASH_REMATCH[1]}"
      elif [[ $line =~ ([0-9]{4}-[0-9]{2}-[0-9]{2}\ [0-9]{2}:[0-9]{2}:[0-9]{2}) ]]; then
        TIMESTAMP="${BASH_REMATCH[1]}"
      fi

      # Extract log level
      if [[ $line =~ (ERROR|WARN|INFO|DEBUG|CRITICAL|FATAL) ]]; then
        LEVEL="${BASH_REMATCH[1]}"
      fi

      DOC=$(jq -n \
        --arg ts "$TIMESTAMP" \
        --arg level "$LEVEL" \
        --arg msg "$line" \
        --arg src "$FILENAME" \
        --arg svc "$SVC_NAME" \
        --arg scenario "$SCENARIO_TAG" \
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
        FILE_ERRORS=$((FILE_ERRORS + 1))
      fi

    done < "$LOG_FILE"
  fi

  echo "  Ingested $LINE_NUM records"
  if [ "$FILE_ERRORS" -gt 0 ]; then
    echo "  ($FILE_ERRORS errors)" >&2
  fi
  ERRORS=$((ERRORS + FILE_ERRORS))
}

# Process file or directory
TOTAL_FILES=0
if [ -d "$LOG_PATH" ]; then
  echo ""
  echo "Processing directory: $LOG_PATH"
  for LOG_FILE in "$LOG_PATH"/*.log "$LOG_PATH"/*.json "$LOG_PATH"/*.txt; do
    [ -f "$LOG_FILE" ] || continue
    ingest_file "$LOG_FILE" "$SERVICE_NAME"
    TOTAL_FILES=$((TOTAL_FILES + 1))
  done
else
  ingest_file "$LOG_PATH" "$SERVICE_NAME"
  TOTAL_FILES=1
fi

# Refresh index
echo ""
echo "Refreshing index..."
awscurl --service aoss \
  --region $REGION \
  -X POST "${ENDPOINT}/${LOG_INDEX}/_refresh" >/dev/null 2>&1 || true

if [ "$ERRORS" -gt 0 ]; then
  echo ""
  echo "WARNING: $ERRORS ingestion error(s) occurred" >&2
fi

# Summary
echo ""
echo "=========================================="
echo "Log Ingestion Complete"
echo "=========================================="
echo ""
echo "Processed $TOTAL_FILES file(s)"
echo "Scenario tag: $SCENARIO_TAG"
echo ""
echo "To search these logs:"
echo "  awscurl --service aoss --region $REGION \\"
echo "    -X GET '${ENDPOINT}/${LOG_INDEX}/_search' \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"query\": {\"bool\": {\"must\": [{\"match\": {\"message\": \"error\"}}], \"filter\": [{\"term\": {\"scenario\": \"$SCENARIO_TAG\"}}]}}}'"
echo ""
echo "To delete these logs later:"
echo "  ./delete-scenario.sh $SCENARIO_TAG"
echo ""
