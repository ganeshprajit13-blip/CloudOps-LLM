"""
Shared SSE event formatting for the RCA Deep Research Agent.

Used by both api.py (FastAPI SSE) and agentcore_app.py (AgentCore streaming)
to produce consistent structured events for the React frontend.
"""

import re
from typing import AsyncGenerator

from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage

# ---------------------------------------------------------------------------
# Node → phase / interrupt type mappings
# ---------------------------------------------------------------------------

INTERRUPT_NODE_MAP = {
    "human_input_clarify": "clarification",
    "human_input": "hypothesis_review",
    "human_input_post": "followup",
}

PHASE_NODE_MAP = {
    "clarify_incident": "clarification",
    "human_input_clarify": "clarification",
    "extract_details": "clarification",
    "context_enrichment": "context_enrichment",
    "hypothesis_generation": "hypothesis_generation",
    "human_input": "hypothesis_review",
    "general_qa": "hypothesis_review",
    "initiate_agents": "investigation",
    "investigation_worker": "investigation",
    "synthesize_findings": "synthesis",
    "human_input_post": "followup",
}

# Nodes whose AI messages are internal status — suppress from chat stream.
SUPPRESS_MESSAGE_NODES: set[str] = set()

# Tool names used internally by .with_structured_output() — these are Pydantic
# models, not real investigative tools.  Suppress from real-time tool_call events.
STRUCTURED_OUTPUT_TOOLS: set[str] = {
    "IncidentClarification",
    "IncidentDetails",
    "Hypotheses",
    "RouteFromQuery",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def extract_text_content(content) -> str:
    """Extract plain text from message content.

    LangChain message content can be a plain string or a list of content blocks
    like [{"type": "text", "text": "..."}].  This normalises both forms to str.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)


_CONCLUSION_RE = re.compile(
    r"CONCLUSION:\s*(SUPPORTED|REFUTED|INCONCLUSIVE|PARTIALLY\s+SUPPORTED)",
    re.IGNORECASE,
)


def _extract_conclusion(output: dict) -> str | None:
    """Return a normalised conclusion label from a worker update, or None."""
    for wm in output.get("worker_messages", []):
        text = ""
        if isinstance(wm, AIMessage):
            text = extract_text_content(wm.content)
        elif isinstance(wm, dict):
            text = wm.get("content", "")
        m = _CONCLUSION_RE.search(text)
        if m:
            return m.group(1).upper().replace("  ", " ")
    return None


# ---------------------------------------------------------------------------
# Update-stream event processing
# ---------------------------------------------------------------------------


async def process_update_event(
    node_name: str,
    output: dict,
    tc_names: dict[str, str] | None = None,
    suppress_messages: bool = False,
) -> AsyncGenerator[dict, None]:
    """Process a single node update event, yielding {event, data} dicts.

    The caller chooses the serialisation format (SSE text vs JSON dict).
    ``tc_names`` maps tool-call IDs to tool names, populated as tool_call
    events are emitted.  Used to look up names for standalone tool_results.

    When *suppress_messages* is True, regular ``message`` events are not
    emitted.  This is used for subgraph worker nodes whose text is already
    streamed via ``token`` events from the "messages" stream.
    """
    # Emit phase updates
    phase = PHASE_NODE_MAP.get(node_name)
    if phase:
        yield {
            "event": "phase",
            "data": {"phase": phase, "description": f"Running {node_name}..."},
        }

    # Emit context details if available (from context_enrichment node)
    context = output.get("context")
    if isinstance(context, dict) and (
        context.get("kb_results")
        or context.get("change_signals")
        or context.get("error_signals")
    ):
        details: dict = {}
        if context.get("kb_results"):
            # Send first ~300 chars of each chunk as a preview
            details["kb_chunks"] = [c[:300] for c in context["kb_results"]]
        if context.get("change_signals"):
            details["change_signals"] = context["change_signals"]
        if context.get("error_signals"):
            details["error_signals"] = context["error_signals"]
        yield {"event": "context_details", "data": details}

    # Emit hypotheses if available
    hyp_obj = output.get("current_hypotheses")
    if hyp_obj and hasattr(hyp_obj, "hypotheses"):
        hyp_dict = {
            str(k): {
                "service": h.service,
                "description": h.description,
                "search_terms": h.search_terms,
                "rationale": h.rationale,
            }
            for k, h in hyp_obj.hypotheses.items()
        }
        yield {"event": "hypothesis", "data": {"hypotheses": hyp_dict}}

    messages = output.get("messages", [])

    # Index ToolMessages by tool_call_id so we can pair them with tool_calls.
    tool_results_by_id: dict[str, ToolMessage] = {}
    for msg in messages:
        if isinstance(msg, ToolMessage):
            tcid = getattr(msg, "tool_call_id", "")
            if tcid:
                tool_results_by_id[tcid] = msg

    # Emit AI messages + paired tool calls
    for msg in messages:
        if not isinstance(msg, AIMessage):
            continue

        # Suppress internal status messages and worker duplicate messages
        if not suppress_messages and node_name not in SUPPRESS_MESSAGE_NODES:
            text = extract_text_content(msg.content)
            if text:
                yield {
                    "event": "message",
                    "data": {"node": node_name, "content": text, "role": "ai"},
                }

        # Emit real tool calls — only those with a matching ToolMessage result.
        for tc in getattr(msg, "tool_calls", []):
            tc_id = tc.get("id", "")
            result_msg = tool_results_by_id.get(tc_id)
            if result_msg is None:
                continue  # structured-output / no result → skip
            yield {
                "event": "tool_call",
                "data": {
                    "name": tc.get("name", "unknown"),
                    "args": tc.get("args", {}),
                    "node": node_name,
                },
            }
            if tc_names is not None and tc_id:
                tc_names[tc_id] = tc.get("name", "unknown")
            yield {
                "event": "tool_result",
                "data": {
                    "content": extract_text_content(result_msg.content),
                    "name": tc.get("name", ""),
                    "node": node_name,
                },
            }

    # Process worker_messages — emit tool calls only (text is suppressed)
    worker_tool_results: dict[str, dict] = {}
    worker_msgs = output.get("worker_messages", [])
    for wm in worker_msgs:
        if isinstance(wm, dict) and wm.get("type") == "tool":
            tcid = wm.get("tool_call_id", "")
            if tcid:
                worker_tool_results[tcid] = wm

    paired_result_ids: set[str] = set()

    for wm in worker_msgs:
        if isinstance(wm, AIMessage):
            worker_id = node_name
        elif isinstance(wm, dict) and wm.get("type") == "ai":
            worker_id = wm.get("worker_id", node_name)
        else:
            continue

        # Worker reasoning text is suppressed — only tool call dropdowns
        # are streamed to the frontend.

        # Emit tool calls from this AI entry (even without paired results yet —
        # results arrive in a separate investigation_tool update).
        tool_calls = []
        if isinstance(wm, AIMessage):
            tool_calls = getattr(wm, "tool_calls", [])
        elif isinstance(wm, dict):
            tool_calls = wm.get("tool_calls", [])

        for tc in tool_calls:
            tc_id = tc.get("id", "")
            tc_name = tc.get("name", "unknown")
            if tc_name in STRUCTURED_OUTPUT_TOOLS:
                continue
            yield {
                "event": "tool_call",
                "data": {
                    "name": tc_name,
                    "args": tc.get("args", {}),
                    "node": worker_id,
                },
            }
            if tc_names is not None and tc_id:
                tc_names[tc_id] = tc_name
            # Emit paired result if available in this same update
            result_entry = worker_tool_results.get(tc_id)
            if result_entry is not None:
                paired_result_ids.add(tc_id)
                yield {
                    "event": "tool_result",
                    "data": {
                        "content": extract_text_content(
                            result_entry.get("content", "")
                        ),
                        "name": tc_name,
                        "node": worker_id,
                    },
                }

    # Emit standalone tool results (arrived without a paired AI message in
    # this update — e.g. investigation_tool node completing).
    for wm in worker_msgs:
        if isinstance(wm, dict) and wm.get("type") == "tool":
            tc_id = wm.get("tool_call_id", "")
            if tc_id and tc_id not in paired_result_ids:
                tc_name = (tc_names or {}).get(tc_id, "tool")
                yield {
                    "event": "tool_result",
                    "data": {
                        "content": extract_text_content(wm.get("content", "")),
                        "name": tc_name,
                        "node": wm.get("worker_id", node_name),
                    },
                }


def _namespace_send_id(ns_tuple: tuple) -> str | None:
    """Extract the raw send_id from a LangGraph subgraph namespace tuple.

    With ``subgraphs=True``, subgraph events arrive with a namespace tuple like
    ``("investigation_worker:<send_id>",)`` or
    ``("investigation_worker:<send_id>", "investigation_reasoning")``.
    The ``<send_id>`` is an internal LangGraph UUID, **not** the
    ``worker_id`` we assigned in ``spawn_investigators``.  Use
    ``_resolve_worker_id()`` to map it to the real ``investigator-N`` id.
    """
    if not ns_tuple:
        return None
    first = ns_tuple[0]
    if ":" in first:
        return first.split(":", 1)[1]
    return None


def _resolve_worker_id(output: dict) -> str | None:
    """Extract the real worker_id (e.g. 'investigator-1') from a subgraph update.

    The worker_id is stored inside ``worker_messages`` entries or as a
    top-level ``worker_id`` key in the update output.
    """
    # Direct top-level field (present in full state snapshots)
    wid = output.get("worker_id")
    if isinstance(wid, str) and wid.startswith("investigator-"):
        return wid
    # Extract from worker_messages entries
    for wm in output.get("worker_messages", []):
        if isinstance(wm, dict):
            wid = wm.get("worker_id")
            if isinstance(wid, str) and wid.startswith("investigator-"):
                return wid
    return None


async def process_dual_stream(stream) -> AsyncGenerator[dict, None]:
    """Process events from graph.astream() with stream_mode=["updates", "messages"].

    Supports both formats:
    - **Without** ``subgraphs=True``: 2-tuple ``(stream_mode, data)``
    - **With** ``subgraphs=True``: 3-tuple ``(namespace_tuple, stream_mode, data)``

    "updates"  → structural events (phases, hypotheses, tool calls with full args + results)
    "messages" → token-level text streaming

    Yields {event, data} dicts. The caller serialises as needed.
    """
    # Maps tool-call ID → tool name.  Populated when tool_call events are
    # emitted from "updates"; used to look up names for standalone tool_results.
    tc_names: dict[str, str] = {}

    # LangGraph Send() uses internal UUIDs in the namespace, not our
    # "investigator-N" ids.  Build a mapping as we discover real worker_ids
    # from update payloads.
    send_id_to_worker: dict[str, str] = {}

    # Track workers we've already announced so we emit exactly one
    # worker_update "investigating…" event per worker.
    announced_workers: set[str] = set()

    async for event_tuple in stream:
        # Normalise the two possible tuple shapes into (ns_tuple, mode, data).
        if len(event_tuple) == 3:
            ns_tuple, mode, data = event_tuple
        else:
            # Legacy 2-tuple (no subgraphs)
            mode, data = event_tuple
            ns_tuple = ()

        send_id = _namespace_send_id(ns_tuple)
        is_subgraph = send_id is not None

        # Resolve the real worker_id from previously seen updates, or
        # try to learn it from the current update payload.
        worker_id: str | None = None
        if send_id:
            worker_id = send_id_to_worker.get(send_id)

        if mode == "updates":
            if not isinstance(data, dict):
                continue
            for node_name, output in data.items():
                if not isinstance(output, dict):
                    continue

                # Try to learn the real worker_id from the update payload.
                if send_id and not worker_id:
                    resolved = _resolve_worker_id(output)
                    if resolved:
                        send_id_to_worker[send_id] = resolved
                        worker_id = resolved

                # For subgraph nodes, override the node name with the
                # worker_id so the frontend can route to the right card.
                effective_node = worker_id if worker_id else node_name

                # Skip the root-graph investigation_worker update — it
                # only contains the final accumulated worker_messages
                # which we already streamed incrementally from the subgraph.
                if node_name == "investigation_worker" and not is_subgraph:
                    continue

                # Emit a worker_update the first time we resolve a real
                # worker_id so the frontend shows the card immediately.
                if worker_id and worker_id not in announced_workers:
                    announced_workers.add(worker_id)
                    yield {
                        "event": "worker_update",
                        "data": {
                            "worker_id": worker_id,
                            "content": "Investigating…",
                        },
                    }

                # Emit a conclusion worker_update when a worker finishes.
                if worker_id:
                    conclusion = _extract_conclusion(output)
                    if conclusion:
                        yield {
                            "event": "worker_update",
                            "data": {
                                "worker_id": worker_id,
                                "content": conclusion,
                                "conclusion": conclusion,
                            },
                        }

                async for evt in process_update_event(
                    effective_node,
                    output,
                    tc_names,
                    suppress_messages=bool(is_subgraph),
                ):
                    yield evt

        elif mode == "messages":
            message_chunk, metadata = data
            if isinstance(message_chunk, AIMessageChunk):
                # Stream text tokens — suppress worker reasoning tokens;
                # worker progress is shown via tool_call / tool_result
                # dropdowns only.
                if not is_subgraph:
                    text = extract_text_content(message_chunk.content)
                    if text:
                        node = metadata.get("langgraph_node", "")
                        yield {
                            "event": "token",
                            "data": {"content": text, "node": node},
                        }
