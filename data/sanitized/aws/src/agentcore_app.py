"""
Bedrock AgentCore runtime entrypoint for the RCA Deep Research Agent.

Wraps the same LangGraph graph as api.py but serves via BedrockAgentCoreApp
for managed container deployment on Amazon Bedrock AgentCore.

Provides:
- Token-level streaming via graph.astream() with stream_mode="messages"
- AgentCore Memory for state persistence (via AgentCoreMemorySaver)
- HITL support via interrupt() and Command(resume=...)
- Secure user identity extraction from JWT tokens

Each invocation from AgentCore is a single request-response cycle.
HITL interrupts are persisted in the durable checkpointer and resumed
on the next invocation for the same session.

Usage (standalone):
    python -m src.agentcore_app

Environment variables:
    MEMORY_ID=<agentcore-memory-id>     (auto-selects AgentCoreMemorySaver)
    CHECKPOINT_BACKEND=dynamodb          (fallback if MEMORY_ID not set)
    CHECKPOINT_TABLE_NAME=rca-checkpoints
    RCA_AGENT_MODE=production
    See src/config.py for full list.
"""

import logging
import sys
import traceback
from pathlib import Path

# Ensure src is importable
_src_dir = Path(__file__).parent
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from config import get_config, configure_logging  # noqa: E402
from checkpoint import create_checkpointer  # noqa: E402
from rca_agent import build_orchestrator_graph, SCENARIOS_DIR  # noqa: E402
from stream_formatter import (  # noqa: E402
    INTERRUPT_NODE_MAP,
    process_dual_stream,
)

from langgraph.types import Command  # noqa: E402

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Graph setup (module-level singleton, shared across invocations)
# ---------------------------------------------------------------------------

_config = get_config()
configure_logging(_config.log_level)

_errors = _config.validate()
if _errors:
    for _e in _errors:
        logger.error("Config error: %s", _e)
    raise RuntimeError(f"Agent configuration invalid: {'; '.join(_errors)}")

_checkpointer = create_checkpointer()
_graph = build_orchestrator_graph(checkpointer=_checkpointer)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_user_id(context) -> str:
    """Extract user ID from JWT claims in RequestContext.

    More secure than trusting a user_id field in the payload body,
    as the JWT has been validated by AgentCore's authorizer.
    """
    try:
        if hasattr(context, "claims") and context.claims:
            return context.claims.get("sub", "anonymous")
    except Exception:
        logger.debug("Could not extract user ID from request context")
    return "anonymous"


from rca_agent import build_initial_state as _build_initial_state  # noqa: E402


# ---------------------------------------------------------------------------
# AgentCore entrypoints
# ---------------------------------------------------------------------------


def _create_app():
    """Create and configure the BedrockAgentCoreApp."""
    try:
        from bedrock_agentcore.runtime import BedrockAgentCoreApp, RequestContext
    except ImportError:
        logger.error(
            "bedrock-agentcore package not installed. "
            "Install with: pip install bedrock-agentcore"
        )
        raise

    app = BedrockAgentCoreApp()

    @app.entrypoint
    async def agent_stream(payload: dict, context: RequestContext):
        """Streaming entrypoint — structured events via dual stream mode.

        Emits the same event types as the FastAPI SSE endpoint so the React
        frontend can use a single parser regardless of transport:
          phase, hypothesis, message, worker_update, tool_call, tool_result,
          token, interrupt, complete, error

        Payload format:
            {
                "message": "user message or incident text",
                "scenario_name": "optional scenario name",
                "incident": "optional full incident text (for first message)",
                "isHeartbeat": true/false
            }

        The session_id from context determines the checkpoint thread.
        On first invocation: starts a new investigation.
        On subsequent invocations: resumes from the last interrupt.
        """
        # Heartbeat handling — AgentCore sends periodic heartbeats
        if payload.get("isHeartbeat"):
            yield {"event": "heartbeat", "data": {"status": "ok"}}
            return

        session_id = context.session_id or "default"
        user_message = payload.get("message", "")
        user_id = _extract_user_id(context)

        config = {
            "configurable": {
                "thread_id": f"investigation-{session_id}",
                "actor_id": user_id,
            }
        }

        logger.info(
            "AgentCore invocation: session=%s, user=%s, message_length=%d",
            session_id,
            user_id,
            len(user_message),
        )

        try:
            # Check if there's an existing interrupted session
            state = await _graph.aget_state(config)
            is_resume = state.next if state else False

            if is_resume:
                # Resume from HITL interrupt
                logger.info(
                    "Resuming interrupted session %s at node: %s",
                    session_id,
                    list(state.next),
                )
                graph_stream = _graph.astream(
                    Command(resume=user_message),
                    config,
                    stream_mode=["updates", "messages"],
                    subgraphs=True,
                )
            else:
                # New investigation or completed previous one
                incident = payload.get("incident") or user_message
                scenario_name = payload.get("scenario_name", "")

                # Try to load incident from scenario if specified
                if scenario_name and not payload.get("incident") and not user_message:
                    incident_file = SCENARIOS_DIR / scenario_name / "incident.md"
                    if incident_file.exists():
                        incident = incident_file.read_text()

                initial_state = _build_initial_state(incident, scenario_name)

                yield {
                    "event": "phase",
                    "data": {
                        "phase": "clarification",
                        "description": "Analyzing incident...",
                    },
                }

                graph_stream = _graph.astream(
                    initial_state,
                    config,
                    stream_mode=["updates", "messages"],
                    subgraphs=True,
                )

            # Stream structured events to the caller
            async for evt in process_dual_stream(graph_stream):
                yield evt

            # Check final state — emit interrupt or completion
            final_state = await _graph.aget_state(config)
            if final_state.next:
                next_node = list(final_state.next)[0]
                interrupt_type = INTERRUPT_NODE_MAP.get(next_node, "clarification")
                yield {
                    "event": "interrupt",
                    "data": {
                        "type": interrupt_type,
                        "next_node": next_node,
                        "prompt": f"Awaiting input at {next_node}",
                        "status": "awaiting_input",
                    },
                }
            else:
                report = final_state.values.get("synthesized_report", "")
                yield {
                    "event": "complete",
                    "data": {"report": report, "status": "complete"},
                }

            logger.info("Streaming completed for session %s", session_id)

        except Exception as e:
            error_msg = str(e) if str(e) else f"{type(e).__name__}: {repr(e)}"
            logger.error("Error in agent_stream: %s", error_msg)
            traceback.print_exc()
            yield {"event": "error", "data": {"message": error_msg, "status": "error"}}

    async def agent_invoke(payload: dict, context: RequestContext):
        """Non-streaming helper — collects all chunks, returns single response.

        Not registered as entrypoint (agent_stream is the registered one).
        Available for testing via direct function call.
        """
        chunks = []
        async for chunk in agent_stream(payload, context):
            chunks.append(chunk)

        # Combine text content from chunks
        text_parts = []
        for chunk in chunks:
            if isinstance(chunk, dict):
                content = chunk.get("content", "")
                if isinstance(content, str) and content:
                    text_parts.append(content)
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            text_parts.append(item.get("text", ""))

        return {
            "response": "".join(text_parts),
            "chunks": chunks,
        }

    return app


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

try:
    app = _create_app()
except ImportError:
    app = None  # bedrock-agentcore not installed (local dev / test)

if __name__ == "__main__":
    if app is None:
        logger.error("Cannot run: bedrock-agentcore package not installed")
        sys.exit(1)
    app.run()
