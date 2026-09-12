#!/usr/bin/env bash
# deploy.sh — Deploys the full RCA agent stack following the FAST pattern.
#
# Deploys: Amplify (frontend) + Cognito (auth) + AgentCore (runtime) +
#          Knowledge Base (RAG) + Athena (log search).
#
# Optional: --deploy-opensearch adds OpenSearch Serverless (~$350/month).
#
# Steps:
#   1. Generate scenario manifest (frontend/public/scenarios.json)
#   2. Build the frontend (initial build, placeholder env vars)
#   3. Deploy CDK stacks (Amplify + Cognito + AgentCore + KB + Athena)
#   4. Read CloudFormation outputs
#   5. Ingest scenario context into Knowledge Base
#   6. Upload scenario evidence logs to Athena S3 bucket
#   7. Update Amplify environment variables with real values
#   8. Rebuild frontend with real env vars and deploy to Amplify via zip upload

set -euo pipefail

# ---------------------------------------------------------------------------
# Project root (resolve from script location)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

AGENT_NAME="rca-agent"
REGION="${AWS_REGION:-${CDK_DEFAULT_REGION:-us-east-1}}"
STACK_NAME="RcaStack"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
ADMIN_EMAIL=""
CDK_EXTRA_CONTEXT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --admin-email)
      ADMIN_EMAIL="$2"
      CDK_EXTRA_CONTEXT="${CDK_EXTRA_CONTEXT} -c adminEmail=${ADMIN_EMAIL}"
      shift 2
      ;;
    --admin-email=*)
      ADMIN_EMAIL="${1#*=}"
      CDK_EXTRA_CONTEXT="${CDK_EXTRA_CONTEXT} -c adminEmail=${ADMIN_EMAIL}"
      shift
      ;;
    --deploy-opensearch)
      CDK_EXTRA_CONTEXT="${CDK_EXTRA_CONTEXT} -c deployOpenSearch=true"
      shift
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--admin-email <email>] [--deploy-opensearch]"
      exit 1
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
step() {
  echo ""
  echo "========================================================================"
  echo "  $1"
  echo "========================================================================"
  echo ""
}

cfn_output_by_key() {
  # cfn_output_by_key <stack-name> <output-key>
  local stack="$1"
  local key="$2"
  aws cloudformation describe-stacks \
    --stack-name "$stack" \
    --query "Stacks[0].Outputs[?OutputKey==\`${key}\`].OutputValue" \
    --output text \
    --region "$REGION"
}

cfn_output_by_export() {
  # cfn_output_by_export <stack-name> <export-name>
  local stack="$1"
  local export_name="$2"
  aws cloudformation describe-stacks \
    --stack-name "$stack" \
    --query "Stacks[0].Outputs[?ExportName==\`${export_name}\`].OutputValue" \
    --output text \
    --region "$REGION"
}

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------
step "Preflight checks"

for cmd in aws bun npx zip curl; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "Error: '$cmd' not found in PATH."
    exit 1
  fi
done

# Find a Python with PyYAML (needed for scenario manifest generation).
# Prefer 'python' (pyenv) over 'python3' (system) since the project venv
# is typically wired through pyenv.
PYTHON=""
for candidate in python python3; do
  if command -v "$candidate" &>/dev/null && "$candidate" -c "import yaml" 2>/dev/null; then
    PYTHON="$candidate"
    break
  fi
done
if [ -z "$PYTHON" ]; then
  echo "Error: No Python with PyYAML found. Install PyYAML: pip install pyyaml"
  exit 1
fi
echo "Python:        $PYTHON ($(command -v "$PYTHON"))"

echo "AWS Region:    $REGION"
echo "Agent Name:    $AGENT_NAME"
echo "Stack Name:    $STACK_NAME"
echo "Admin Email:   ${ADMIN_EMAIL:-<none>}"
echo "Project Root:  $PROJECT_ROOT"

# Verify AWS credentials
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || true)
if [ -z "$ACCOUNT_ID" ]; then
  echo "Error: AWS credentials not configured. Run 'aws configure' or set AWS_PROFILE."
  exit 1
fi
echo "AWS Account:   $ACCOUNT_ID"

# ---------------------------------------------------------------------------
# Step 1: Generate scenario manifest
# ---------------------------------------------------------------------------
step "Step 1/8: Generating scenario manifest"

$PYTHON "$PROJECT_ROOT/scripts/generate_scenario_manifest.py" \
  --output "$PROJECT_ROOT/frontend/public/scenarios.json"

# ---------------------------------------------------------------------------
# Step 2: Build frontend (initial build with placeholder env vars)
# ---------------------------------------------------------------------------
step "Step 2/8: Building frontend (initial)"

cd "$PROJECT_ROOT/frontend"
bun install
bun run build
cd "$PROJECT_ROOT"

echo "Frontend built to frontend/dist/"

# ---------------------------------------------------------------------------
# Step 3: Deploy CDK stack (single parent with nested stacks)
# ---------------------------------------------------------------------------
step "Step 3/8: Deploying CDK stack"

cd "$PROJECT_ROOT/deployment/agentcore"

# Ensure CDK dependencies are installed
if [ ! -d "node_modules" ]; then
  npm install
fi

npx cdk deploy --all \
  $CDK_EXTRA_CONTEXT \
  --require-approval never

cd "$PROJECT_ROOT"

echo "CDK deployment complete."

# ---------------------------------------------------------------------------
# Step 4: Read CloudFormation outputs (all from single parent stack)
# ---------------------------------------------------------------------------
step "Step 4/8: Reading CloudFormation outputs"

COGNITO_USER_POOL_ID=$(cfn_output_by_key "$STACK_NAME" "UserPoolId")
COGNITO_APP_CLIENT_ID=$(cfn_output_by_key "$STACK_NAME" "AppClientId")
COGNITO_DOMAIN=$(cfn_output_by_key "$STACK_NAME" "CognitoDomain")
AMPLIFY_APP_ID=$(cfn_output_by_key "$STACK_NAME" "AmplifyAppId")
STAGING_BUCKET=$(cfn_output_by_key "$STACK_NAME" "StagingBucketName")
AMPLIFY_URL=$(cfn_output_by_key "$STACK_NAME" "AmplifyUrl")
RUNTIME_ARN=$(cfn_output_by_key "$STACK_NAME" "AgentRuntimeArn")

# AgentCore API expects the URL-encoded full ARN in the path (see bedrock_agentcore SDK)
ENCODED_ARN=$($PYTHON -c "from urllib.parse import quote; print(quote('${RUNTIME_ARN}', safe=''))")
AGENTCORE_ENDPOINT="https://bedrock-agentcore.${REGION}.amazonaws.com/runtimes/${ENCODED_ARN}/invocations"

echo "Cognito User Pool ID:  $COGNITO_USER_POOL_ID"
echo "Cognito App Client ID: $COGNITO_APP_CLIENT_ID"
echo "Cognito Domain:        $COGNITO_DOMAIN"
echo "Amplify App ID:        $AMPLIFY_APP_ID"
echo "Amplify URL:           $AMPLIFY_URL"
echo "Staging Bucket:        $STAGING_BUCKET"
echo "Runtime ARN:           $RUNTIME_ARN"
echo "AgentCore Endpoint:    $AGENTCORE_ENDPOINT"

# Sanity check — fail early if any critical value is empty
for var_name in COGNITO_USER_POOL_ID COGNITO_APP_CLIENT_ID COGNITO_DOMAIN AMPLIFY_APP_ID STAGING_BUCKET RUNTIME_ARN; do
  eval val="\$$var_name"
  if [ -z "$val" ] || [ "$val" = "None" ]; then
    echo "Error: Failed to read $var_name from CloudFormation outputs."
    exit 1
  fi
done

# ---------------------------------------------------------------------------
# Step 5: Ingest scenario context into Knowledge Base
# ---------------------------------------------------------------------------
step "Step 5/8: Ingesting scenario context into Knowledge Base"

KB_BUCKET=$(cfn_output_by_export "RcaKnowledgeBaseStack" "${AGENT_NAME}-kb-bucket")
KB_ID=$(cfn_output_by_export "RcaKnowledgeBaseStack" "${AGENT_NAME}-kb-id")
KB_DS_ID=$(cfn_output_by_export "RcaKnowledgeBaseStack" "${AGENT_NAME}-datasource-id")

if [ -z "$KB_BUCKET" ] || [ "$KB_BUCKET" = "None" ]; then
  echo "Warning: Knowledge Base bucket not found. Skipping KB ingestion."
else
  echo "KB Bucket:      $KB_BUCKET"
  echo "KB ID:          $KB_ID"
  echo "Data Source ID: $KB_DS_ID"

  # Upload scenario context files pre-split into small chunks.
  # S3 Vectors has a 2048-byte filterable metadata limit per record. Bedrock KB
  # stores the full chunk text as filterable metadata, so each S3 object must be
  # small enough to fit. We split markdown files at paragraph boundaries into
  # ~800 byte chunks with NONE chunking strategy (no further splitting by Bedrock).
  SCENARIOS_DIR="$PROJECT_ROOT/scenarios"
  echo "Splitting and uploading context documents..."
  $PYTHON -c "
import os, subprocess, sys
scenarios_dir = '$SCENARIOS_DIR'
bucket = '$KB_BUCKET'
region = '$REGION'
total = 0
for scenario in sorted(os.listdir(scenarios_dir)):
    ctx = os.path.join(scenarios_dir, scenario, 'context')
    if not os.path.isdir(ctx):
        continue
    for fname in sorted(os.listdir(ctx)):
        if not fname.endswith('.md'):
            continue
        content = open(os.path.join(ctx, fname)).read()
        base = fname.replace('.md', '')
        paras = content.split('\n\n')
        chunk, n = '', 0
        for p in paras:
            if len(chunk.encode()) + len(p.encode()) > 800 and chunk:
                n += 1
                key = f'{scenario}-{base}-{n}.md'
                subprocess.run(
                    ['aws', 's3', 'cp', '-', f's3://{bucket}/{key}',
                     '--region', region, '--quiet'],
                    input=chunk.encode(), check=True)
                total += 1
                chunk = p
            else:
                chunk = chunk + '\n\n' + p if chunk else p
        if chunk:
            n += 1
            key = f'{scenario}-{base}-{n}.md'
            subprocess.run(
                ['aws', 's3', 'cp', '-', f's3://{bucket}/{key}',
                 '--region', region, '--quiet'],
                input=chunk.encode(), check=True)
            total += 1
    print(f'  {scenario}: done')
print(f'Uploaded {total} context chunks.')
"

  # Trigger KB ingestion job (runs asynchronously in the background)
  if [ -n "$KB_ID" ] && [ "$KB_ID" != "None" ] && [ -n "$KB_DS_ID" ] && [ "$KB_DS_ID" != "None" ]; then
    echo "Triggering KB ingestion job..."
    aws bedrock-agent start-ingestion-job \
      --knowledge-base-id "$KB_ID" \
      --data-source-id "$KB_DS_ID" \
      --region "$REGION" \
      --output text > /dev/null 2>&1 || echo "Warning: KB ingestion trigger failed (non-fatal)."
    echo "KB ingestion job started (runs in background, ~1-3 minutes)."
  else
    echo "Warning: KB ID or Data Source ID not found. Skipping ingestion trigger."
  fi
fi

# ---------------------------------------------------------------------------
# Step 6: Upload scenario evidence logs to Athena S3 bucket
# ---------------------------------------------------------------------------
step "Step 6/8: Uploading scenario evidence logs to S3"

LOG_BUCKET=$(cfn_output_by_export "RcaAthenaLogSearchStack" "${AGENT_NAME}-log-bucket")

if [ -z "$LOG_BUCKET" ] || [ "$LOG_BUCKET" = "None" ]; then
  echo "Warning: Athena log bucket not found. Skipping log upload."
else
  echo "Log Bucket: $LOG_BUCKET"
  $PYTHON "$PROJECT_ROOT/scripts/upload_logs_to_s3.py" \
    --bucket "$LOG_BUCKET" --all
fi

# ---------------------------------------------------------------------------
# Step 7: Update Amplify environment variables
# ---------------------------------------------------------------------------
step "Step 7/8: Updating Amplify environment variables"

aws amplify update-app \
  --app-id "$AMPLIFY_APP_ID" \
  --environment-variables \
    "VITE_AGENTCORE_ENDPOINT=$AGENTCORE_ENDPOINT,VITE_COGNITO_USER_POOL_ID=$COGNITO_USER_POOL_ID,VITE_COGNITO_APP_CLIENT_ID=$COGNITO_APP_CLIENT_ID,VITE_COGNITO_DOMAIN=$COGNITO_DOMAIN,VITE_AWS_REGION=$REGION" \
  --region "$REGION" \
  --output text > /dev/null

echo "Amplify environment variables updated."

# ---------------------------------------------------------------------------
# Step 8: Rebuild frontend with real env vars and deploy to Amplify
# ---------------------------------------------------------------------------
step "Step 8/8: Rebuilding frontend and deploying to Amplify"

# Rebuild with the real environment variables baked in
cd "$PROJECT_ROOT/frontend"

VITE_AGENTCORE_ENDPOINT="$AGENTCORE_ENDPOINT" \
VITE_COGNITO_USER_POOL_ID="$COGNITO_USER_POOL_ID" \
VITE_COGNITO_APP_CLIENT_ID="$COGNITO_APP_CLIENT_ID" \
VITE_COGNITO_DOMAIN="$COGNITO_DOMAIN" \
VITE_AWS_REGION="$REGION" \
  bun run build

cd "$PROJECT_ROOT"

echo "Frontend rebuilt with production env vars."

# Upload to S3 staging bucket
echo "Uploading frontend/dist/ to s3://${STAGING_BUCKET}/ ..."
aws s3 sync "$PROJECT_ROOT/frontend/dist/" "s3://${STAGING_BUCKET}/" \
  --delete \
  --region "$REGION"

# Deploy to Amplify via zip upload (create-deployment + start-deployment).
# The --source-url method is not reliably supported, so we use zip upload directly.
echo "Creating Amplify deployment..."

DEPLOY_ZIP="/tmp/rca-frontend-deploy-$$.zip"
(cd "$PROJECT_ROOT/frontend/dist" && zip -qr "$DEPLOY_ZIP" .)

CREATE_RESULT=$(aws amplify create-deployment \
  --app-id "$AMPLIFY_APP_ID" \
  --branch-name "main" \
  --region "$REGION" \
  --output json)

UPLOAD_URL=$(echo "$CREATE_RESULT" | $PYTHON -c "import sys,json; print(json.load(sys.stdin)['zipUploadUrl'])")
JOB_ID=$(echo "$CREATE_RESULT" | $PYTHON -c "import sys,json; print(json.load(sys.stdin)['jobId'])")

echo "Uploading frontend build (job $JOB_ID)..."
curl -s --upload-file "$DEPLOY_ZIP" "$UPLOAD_URL"

aws amplify start-deployment \
  --app-id "$AMPLIFY_APP_ID" \
  --branch-name "main" \
  --job-id "$JOB_ID" \
  --region "$REGION" \
  --output text > /dev/null

rm -f "$DEPLOY_ZIP"

echo ""
echo "========================================================================"
echo "  Deployment complete!"
echo "========================================================================"
echo ""
echo "  Frontend URL:     $AMPLIFY_URL"
echo "  Cognito Domain:   https://${COGNITO_DOMAIN}"
echo "  AgentCore:        $AGENTCORE_ENDPOINT"
echo ""
if [ -n "$ADMIN_EMAIL" ]; then
  echo "  Admin user ($ADMIN_EMAIL) created — check email for temporary password."
  echo ""
fi
echo "  Note: Amplify deployment may take 1-2 minutes to propagate."
echo ""
