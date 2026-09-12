#!/bin/bash
# Run HITL scenarios using Athena (deployed infrastructure)

# Set environment for Athena mode
export RCA_AGENT_MODE=production
export LOG_SEARCH_BACKEND=athena
export ATHENA_DATABASE=rca_agent_logs
export ATHENA_TABLE=logs
export ATHENA_OUTPUT_LOCATION=s3://rca-agent-athena-results-ACCOUNT_ID-us-west-2/
export AWS_REGION=us-west-2

SCENARIO="${1:-volte-call-drop-handover}"

echo "=================================================="
echo "Running HITL Demo with Athena (Production Mode)"
echo "=================================================="
echo ""
echo "Scenario: $SCENARIO"
echo "Log Search: Athena ($ATHENA_DATABASE.$ATHENA_TABLE)"
echo "Region: $AWS_REGION"
echo ""
echo "Available scenarios:"
echo "  - volte-call-drop-handover"
echo "  - iot-fleet-disconnect-cascade"
echo "  - k8s-canary-silent-poisoning"
echo "  - ml-training-drift-schema-migration"
echo "  - care-transcript-supply-chain"
echo ""
echo "=================================================="
echo ""

cd "$(dirname "$0")/../src"
python run_demo.py "$SCENARIO"
