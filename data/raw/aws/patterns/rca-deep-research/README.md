# RCA Deep Research Agent Pattern

This pattern deploys the Deep Research RCA Agent on Amazon Bedrock AgentCore with full HITL (Human-in-the-Loop) support.

## Features

- **Deep Research Pattern**: Parallel hypothesis investigation with dynamic agent spawning
- **HITL Support**: Clarification questions via `interrupt()` with stateful resumption
- **AgentCore Memory**: Conversation history persisted via `AgentCoreMemorySaver`
- **Token-Level Streaming**: True token-by-token streaming via `graph.astream()`
- **Secure Identity**: User identity extracted from validated JWT token

## Architecture

```
User Request (incident report)
    |
BedrockAgentCoreApp (src/agentcore_app.py)
    |
RCA Orchestrator (LangGraph StateGraph)
    |
    +-- Context Enrichment (KB + runbooks)
    |
    +-- HITL Clarification (interrupt())
    |
    +-- Hypothesis Generation (structured output)
    |
    +-- Dynamic Worker Spawning (Send() per hypothesis)
    |       |
    |       +-- Worker 1: Investigate hypothesis A
    |       +-- Worker 2: Investigate hypothesis B
    |       +-- Worker N: Investigate hypothesis N
    |
    +-- Synthesis (compare evidence, determine root cause)
    |
    +-- AgentCore Memory (conversation history)
```

## File Structure

```
patterns/rca-deep-research/
├── Dockerfile           # Container build (runs src/agentcore_app.py)
├── requirements.txt     # Pinned dependencies
└── README.md            # This file
```

## Payload Format

### Start Investigation

```json
{
  "message": "Product catalog is slow again",
  "scenario_name": "volte-call-drop-handover",
  "incident": "Optional full incident text"
}
```

Session ID is sent via the `X-Amzn-Bedrock-AgentCore-Runtime-Session-Id` header.

### Resume from HITL Interrupt

```json
{
  "message": "March 15, around 10am"
}
```

Same session ID header — the checkpointer resumes from the last interrupt.

## Streaming Events

| Event | Description |
|-------|-------------|
| `phase` | Investigation phase update (clarification, investigation, synthesis) |
| `token` | Streamed text token |
| `message` | Complete AI message from a node |
| `hypothesis` | Generated hypotheses |
| `tool_call` | Tool invocation (log search, KB query) |
| `tool_result` | Tool execution result |
| `worker_update` | Update from a parallel investigation worker |
| `interrupt` | Agent waiting for user input (HITL) |
| `complete` | Investigation finished with report |
| `error` | Error occurred |

## Environment Variables

The CDK stack auto-wires all required env vars into the AgentCore Runtime, including Athena config (`LOG_SEARCH_BACKEND`, `ATHENA_DATABASE`, `ATHENA_TABLE`, `ATHENA_OUTPUT_LOCATION`) and Knowledge Base ID (`BEDROCK_KB_ID`).

| Variable | Description | Auto-wired by CDK |
|----------|-------------|-------------------|
| `MEMORY_ID` | AgentCore Memory resource ID | Yes |
| `AWS_DEFAULT_REGION` | AWS region | Yes |
| `RCA_AGENT_MODE` | `local` or `production` | Yes (`production`) |
| `LOG_SEARCH_BACKEND` | `athena`, `cloudwatch`, or `opensearch` | Yes (`athena`) |
| `ATHENA_DATABASE` | Athena/Glue database name | Yes |
| `ATHENA_TABLE` | Athena table name | Yes |
| `ATHENA_OUTPUT_LOCATION` | S3 URI for query results | Yes |
| `BEDROCK_KB_ID` | Knowledge Base ID | Yes |

## Deployment

### Using CDK

```bash
cd deployment/agentcore
npm install

# Deploy everything (Amplify + Cognito + AgentCore + KB + Athena)
npx cdk deploy --all
```

### Using Docker Locally

```bash
# Build
docker build -f patterns/rca-deep-research/Dockerfile -t rca-agent .

# Run (LOCAL mode with file-based data)
docker run -p 8080:8080 \
  -e AWS_REGION=us-east-1 \
  -e RCA_AGENT_MODE=local \
  rca-agent
```

## Dependencies

```
bedrock-agentcore>=1.0.6
langgraph>=1.0.5
langchain-aws>=1.0.0
langgraph-checkpoint-aws>=1.0.1
boto3>=1.34.0
PyJWT[crypto]>=2.10.1
```

## Security

- User identity extracted from validated JWT token (not payload body)
- Scenario names validated for path traversal prevention
- No hardcoded credentials - uses IAM roles
