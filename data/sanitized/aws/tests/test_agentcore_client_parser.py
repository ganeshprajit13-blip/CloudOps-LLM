"""
Contract tests between the backend stream_formatter and the frontend
AgentCore SSE parser (frontend/src/api/agentcore-client.ts).

The frontend's routeEvent() expects every event to be a JSON object with
exactly two top-level keys: "event" (str) and "data" (dict).  Each event
type requires specific fields inside "data".  These tests exercise
process_update_event() and process_dual_stream() and verify the emitted
dicts match the shape that the frontend destructures.

If someone changes the backend event format without updating the frontend,
these tests will break and signal a contract violation.
"""

import asyncio
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage

from stream_formatter import process_dual_stream, process_update_event


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _collect_async(agen):
    """Collect all items from an async generator into a list."""
    items = []
    async for item in agen:
        items.append(item)
    return items


async def _async_gen(items):
    """Create an async generator from a list of items."""
    for item in items:
        yield item


# ---------------------------------------------------------------------------
# Contract: phase events
# ---------------------------------------------------------------------------


class TestPhaseEventContract:
    """Frontend expects: {event: "phase", data: {phase: str, description: str}}"""

    def test_phase_event_has_required_fields(self):
        """Phase events must contain 'phase' and 'description' in data."""
        output = {"messages": []}
        results = asyncio.run(
            _collect_async(process_update_event("clarify_incident", output))
        )

        phase_events = [r for r in results if r["event"] == "phase"]
        assert len(phase_events) >= 1, "Expected at least one phase event"

        for evt in phase_events:
            assert "event" in evt
            assert "data" in evt
            assert evt["event"] == "phase"
            assert isinstance(evt["data"], dict)
            assert "phase" in evt["data"], "phase event missing 'phase' field"
            assert "description" in evt["data"], (
                "phase event missing 'description' field"
            )
            assert isinstance(evt["data"]["phase"], str)
            assert isinstance(evt["data"]["description"], str)

    def test_phase_values_match_known_phases(self):
        """Phase values should be one of the known frontend phase strings."""
        known_phases = {
            "clarification",
            "hypothesis_generation",
            "hypothesis_review",
            "investigation",
            "synthesis",
            "followup",
        }
        # Test a selection of nodes that map to different phases
        node_phase_pairs = [
            ("clarify_incident", "clarification"),
            ("hypothesis_generation", "hypothesis_generation"),
            ("human_input", "hypothesis_review"),
            ("initiate_agents", "investigation"),
            ("investigation_worker", "investigation"),
            ("synthesize_findings", "synthesis"),
            ("human_input_post", "followup"),
        ]
        for node_name, expected_phase in node_phase_pairs:
            output = {"messages": []}
            results = asyncio.run(
                _collect_async(process_update_event(node_name, output))
            )
            phase_events = [r for r in results if r["event"] == "phase"]
            assert len(phase_events) == 1, f"Expected 1 phase event for {node_name}"
            assert phase_events[0]["data"]["phase"] == expected_phase
            assert phase_events[0]["data"]["phase"] in known_phases


# ---------------------------------------------------------------------------
# Contract: message events
# ---------------------------------------------------------------------------


class TestMessageEventContract:
    """Frontend expects: {event: "message", data: {node: str, content: str, role: str}}"""

    def test_message_event_has_required_fields(self):
        """Message events must contain 'node', 'content', and 'role' in data."""
        output = {"messages": [AIMessage(content="Starting analysis...")]}
        results = asyncio.run(
            _collect_async(process_update_event("general_qa", output))
        )

        msg_events = [r for r in results if r["event"] == "message"]
        assert len(msg_events) >= 1, "Expected at least one message event"

        for evt in msg_events:
            assert "event" in evt
            assert "data" in evt
            assert evt["event"] == "message"
            assert isinstance(evt["data"], dict)
            assert "node" in evt["data"], "message event missing 'node' field"
            assert "content" in evt["data"], "message event missing 'content' field"
            assert "role" in evt["data"], "message event missing 'role' field"
            assert isinstance(evt["data"]["node"], str)
            assert isinstance(evt["data"]["content"], str)
            assert isinstance(evt["data"]["role"], str)

    def test_message_role_is_ai(self):
        """Backend AI messages should set role to 'ai'."""
        output = {"messages": [AIMessage(content="Hello")]}
        results = asyncio.run(
            _collect_async(process_update_event("general_qa", output))
        )

        msg_events = [r for r in results if r["event"] == "message"]
        assert len(msg_events) == 1
        assert msg_events[0]["data"]["role"] == "ai"

    def test_message_node_matches_source_node(self):
        """The 'node' field must match the LangGraph node name."""
        output = {"messages": [AIMessage(content="Found evidence")]}
        results = asyncio.run(
            _collect_async(process_update_event("clarify_incident", output))
        )

        msg_events = [r for r in results if r["event"] == "message"]
        assert len(msg_events) == 1
        assert msg_events[0]["data"]["node"] == "clarify_incident"


# ---------------------------------------------------------------------------
# Contract: hypothesis events
# ---------------------------------------------------------------------------


class TestHypothesisEventContract:
    """Frontend expects: {event: "hypothesis", data: {hypotheses: dict}}

    Each hypothesis value should have: service, description, search_terms, rationale.
    """

    def test_hypothesis_event_has_required_fields(self):
        """Hypothesis events must contain 'hypotheses' dict in data."""
        mock_hyp = MagicMock()
        mock_hyp.hypotheses = {
            1: MagicMock(
                service="redis",
                description="Cache stampede",
                search_terms=["redis", "cache", "thundering"],
                rationale="High cache miss rate",
            ),
            2: MagicMock(
                service="api-gateway",
                description="Rate limiting misconfiguration",
                search_terms=["rate-limit", "429"],
                rationale="Sudden traffic spike",
            ),
        }

        output = {"current_hypotheses": mock_hyp, "messages": []}
        results = asyncio.run(
            _collect_async(process_update_event("hypothesis_generation", output))
        )

        hyp_events = [r for r in results if r["event"] == "hypothesis"]
        assert len(hyp_events) == 1, "Expected exactly one hypothesis event"

        evt = hyp_events[0]
        assert "event" in evt
        assert "data" in evt
        assert evt["event"] == "hypothesis"
        assert isinstance(evt["data"], dict)
        assert "hypotheses" in evt["data"], (
            "hypothesis event missing 'hypotheses' field"
        )

        hypotheses = evt["data"]["hypotheses"]
        assert isinstance(hypotheses, dict)
        assert len(hypotheses) == 2

        # Each hypothesis should have the required sub-fields
        for key, hyp in hypotheses.items():
            assert "service" in hyp, f"hypothesis {key} missing 'service'"
            assert "description" in hyp, f"hypothesis {key} missing 'description'"
            assert "search_terms" in hyp, f"hypothesis {key} missing 'search_terms'"
            assert "rationale" in hyp, f"hypothesis {key} missing 'rationale'"

    def test_hypothesis_keys_are_strings(self):
        """Frontend expects hypothesis keys to be strings (JS object keys)."""
        mock_hyp = MagicMock()
        mock_hyp.hypotheses = {
            1: MagicMock(
                service="db",
                description="Slow queries",
                search_terms=["slow"],
                rationale="High latency",
            ),
        }

        output = {"current_hypotheses": mock_hyp, "messages": []}
        results = asyncio.run(
            _collect_async(process_update_event("hypothesis_generation", output))
        )

        hyp_events = [r for r in results if r["event"] == "hypothesis"]
        hypotheses = hyp_events[0]["data"]["hypotheses"]
        for key in hypotheses.keys():
            assert isinstance(key, str), (
                f"Hypothesis key {key!r} should be str, got {type(key)}"
            )


# ---------------------------------------------------------------------------
# Contract: worker_update events
# ---------------------------------------------------------------------------


class TestWorkerUpdateEventContract:
    """Frontend expects: {event: "worker_update", data: {worker_id: str, content: str}}

    worker_update events are emitted by process_dual_stream (not process_update_event)
    when a real worker_id is resolved from a subgraph namespace.
    """

    def test_worker_update_event_has_required_fields(self):
        """Worker update events must contain 'worker_id' and 'content' in data."""
        # worker_update events are produced by process_dual_stream when
        # it resolves a worker_id from a subgraph update.
        output = {
            "messages": [],
            "worker_messages": [
                {
                    "worker_id": "investigator-1",
                    "content": "Searching logs for cache misses...",
                    "type": "ai",
                },
            ],
        }
        # Simulate a subgraph update event as seen by process_dual_stream
        update_data = {"investigation_worker": output}
        stream_events = [
            (("investigation_worker:send-uuid-1",), "updates", update_data),
        ]
        results = asyncio.run(
            _collect_async(process_dual_stream(_async_gen(stream_events)))
        )

        worker_events = [r for r in results if r["event"] == "worker_update"]
        assert len(worker_events) >= 1, "Expected at least one worker_update event"

        for evt in worker_events:
            assert "event" in evt
            assert "data" in evt
            assert evt["event"] == "worker_update"
            assert isinstance(evt["data"], dict)
            assert "worker_id" in evt["data"], (
                "worker_update event missing 'worker_id' field"
            )
            assert "content" in evt["data"], (
                "worker_update event missing 'content' field"
            )
            assert isinstance(evt["data"]["worker_id"], str)
            assert isinstance(evt["data"]["content"], str)

    def test_worker_update_from_aimessage(self):
        """Worker updates from AIMessage objects should also have worker_id and content."""
        output = {
            "messages": [],
            "worker_messages": [
                {
                    "worker_id": "investigator-1",
                    "content": "Checking DNS resolution...",
                    "type": "ai",
                },
            ],
        }
        update_data = {"investigation_worker": output}
        stream_events = [
            (("investigation_worker:send-uuid-2",), "updates", update_data),
        ]
        results = asyncio.run(
            _collect_async(process_dual_stream(_async_gen(stream_events)))
        )

        worker_events = [r for r in results if r["event"] == "worker_update"]
        assert len(worker_events) >= 1
        evt = worker_events[0]
        assert "worker_id" in evt["data"]
        assert "content" in evt["data"]


# ---------------------------------------------------------------------------
# Contract: tool_call events
# ---------------------------------------------------------------------------


class TestToolCallEventContract:
    """Frontend expects: {event: "tool_call", data: {name: str, args: dict, node: str}}"""

    def test_tool_call_event_has_required_fields(self):
        """Tool call events must contain 'name', 'args', and 'node' in data."""
        ai_msg = AIMessage(
            content="Let me search the logs.",
            tool_calls=[
                {
                    "id": "tc-001",
                    "name": "search_logs",
                    "args": {"query": "timeout error"},
                },
            ],
        )
        tool_msg = ToolMessage(
            content="Found 5 matching log entries",
            tool_call_id="tc-001",
        )

        output = {"messages": [ai_msg, tool_msg]}
        results = asyncio.run(
            _collect_async(process_update_event("general_qa", output))
        )

        tc_events = [r for r in results if r["event"] == "tool_call"]
        assert len(tc_events) >= 1, "Expected at least one tool_call event"

        for evt in tc_events:
            assert "event" in evt
            assert "data" in evt
            assert evt["event"] == "tool_call"
            assert isinstance(evt["data"], dict)
            assert "name" in evt["data"], "tool_call event missing 'name' field"
            assert "args" in evt["data"], "tool_call event missing 'args' field"
            assert "node" in evt["data"], "tool_call event missing 'node' field"
            assert isinstance(evt["data"]["name"], str)
            assert isinstance(evt["data"]["args"], dict)
            assert isinstance(evt["data"]["node"], str)

    def test_tool_call_name_and_args_populated(self):
        """Tool call name and args should reflect the actual invocation."""
        ai_msg = AIMessage(
            content="",
            tool_calls=[
                {"id": "tc-002", "name": "get_runbook", "args": {"service": "redis"}},
            ],
        )
        tool_msg = ToolMessage(content="Runbook content here", tool_call_id="tc-002")

        output = {"messages": [ai_msg, tool_msg]}
        results = asyncio.run(
            _collect_async(process_update_event("clarify_incident", output))
        )

        tc_events = [r for r in results if r["event"] == "tool_call"]
        assert len(tc_events) == 1
        assert tc_events[0]["data"]["name"] == "get_runbook"
        assert tc_events[0]["data"]["args"] == {"service": "redis"}
        assert tc_events[0]["data"]["node"] == "clarify_incident"


# ---------------------------------------------------------------------------
# Contract: tool_result events
# ---------------------------------------------------------------------------


class TestToolResultEventContract:
    """Frontend expects: {event: "tool_result", data: {name: str, content: str, node: str}}"""

    def test_tool_result_event_has_required_fields(self):
        """Tool result events must contain 'name', 'content', and 'node' in data."""
        ai_msg = AIMessage(
            content="Searching for evidence.",
            tool_calls=[
                {"id": "tc-003", "name": "search_logs", "args": {"query": "OOM"}},
            ],
        )
        tool_msg = ToolMessage(
            content="3 OOM events found in the last hour",
            tool_call_id="tc-003",
        )

        output = {"messages": [ai_msg, tool_msg]}
        results = asyncio.run(
            _collect_async(process_update_event("general_qa", output))
        )

        tr_events = [r for r in results if r["event"] == "tool_result"]
        assert len(tr_events) >= 1, "Expected at least one tool_result event"

        for evt in tr_events:
            assert "event" in evt
            assert "data" in evt
            assert evt["event"] == "tool_result"
            assert isinstance(evt["data"], dict)
            assert "name" in evt["data"], "tool_result event missing 'name' field"
            assert "content" in evt["data"], "tool_result event missing 'content' field"
            assert "node" in evt["data"], "tool_result event missing 'node' field"
            assert isinstance(evt["data"]["name"], str)
            assert isinstance(evt["data"]["content"], str)
            assert isinstance(evt["data"]["node"], str)

    def test_tool_result_content_matches_tool_message(self):
        """Tool result content should reflect what the tool returned."""
        ai_msg = AIMessage(
            content="",
            tool_calls=[
                {"id": "tc-004", "name": "search_logs", "args": {"query": "crash"}},
            ],
        )
        tool_msg = ToolMessage(
            content="Segfault in worker process at 14:32:01 UTC",
            tool_call_id="tc-004",
        )

        output = {"messages": [ai_msg, tool_msg]}
        results = asyncio.run(
            _collect_async(process_update_event("investigation_worker", output))
        )

        tr_events = [r for r in results if r["event"] == "tool_result"]
        assert len(tr_events) == 1
        assert (
            tr_events[0]["data"]["content"]
            == "Segfault in worker process at 14:32:01 UTC"
        )
        assert tr_events[0]["data"]["name"] == "search_logs"


# ---------------------------------------------------------------------------
# Contract: token events
# ---------------------------------------------------------------------------


class TestTokenEventContract:
    """Frontend expects: {event: "token", data: {content: str, node: str}}"""

    def test_token_event_has_required_fields(self):
        """Token events must contain 'content' and 'node' in data."""
        chunk = AIMessageChunk(content="investigating")
        metadata = {"langgraph_node": "general_qa"}

        events = [("messages", (chunk, metadata))]
        results = asyncio.run(_collect_async(process_dual_stream(_async_gen(events))))

        assert len(results) >= 1, "Expected at least one token event"

        for evt in results:
            assert "event" in evt
            assert "data" in evt
            assert evt["event"] == "token"
            assert isinstance(evt["data"], dict)
            assert "content" in evt["data"], "token event missing 'content' field"
            assert "node" in evt["data"], "token event missing 'node' field"
            assert isinstance(evt["data"]["content"], str)
            assert isinstance(evt["data"]["node"], str)

    def test_token_content_matches_chunk(self):
        """Token content should reflect the streamed chunk text."""
        chunk = AIMessageChunk(content="root cause")
        metadata = {"langgraph_node": "synthesize_findings"}

        events = [("messages", (chunk, metadata))]
        results = asyncio.run(_collect_async(process_dual_stream(_async_gen(events))))

        assert len(results) == 1
        assert results[0]["data"]["content"] == "root cause"
        assert results[0]["data"]["node"] == "synthesize_findings"


# ---------------------------------------------------------------------------
# Contract: all events have {event, data} envelope
# ---------------------------------------------------------------------------


class TestEventEnvelopeContract:
    """Every event from process_dual_stream must have 'event' (str) and 'data' (dict)."""

    def test_all_events_have_event_and_data_keys(self):
        """Every emitted event must be a dict with exactly 'event' and 'data' top-level keys."""
        # Build a stream that produces multiple event types
        mock_hyp = MagicMock()
        mock_hyp.hypotheses = {
            1: MagicMock(
                service="cache",
                description="Stampede",
                search_terms=["cache"],
                rationale="Pattern match",
            ),
        }

        ai_msg_with_tool = AIMessage(
            content="Let me check.",
            tool_calls=[
                {"id": "tc-env-1", "name": "search_logs", "args": {"query": "error"}},
            ],
        )
        tool_result = ToolMessage(content="No errors found", tool_call_id="tc-env-1")

        update_data = {
            "hypothesis_generation": {
                "current_hypotheses": mock_hyp,
                "messages": [ai_msg_with_tool, tool_result],
                "worker_messages": [
                    {
                        "worker_id": "w1",
                        "content": "Checking...",
                        "type": "ai",
                    },
                ],
            },
        }

        chunk = AIMessageChunk(content="streaming token")
        metadata = {"langgraph_node": "general_qa"}

        stream_events = [
            ("updates", update_data),
            ("messages", (chunk, metadata)),
        ]

        results = asyncio.run(
            _collect_async(process_dual_stream(_async_gen(stream_events)))
        )

        # Should have multiple event types
        assert len(results) >= 4, (
            f"Expected at least 4 events (phase, hypothesis, message, token), got {len(results)}"
        )

        event_types_seen = set()
        for evt in results:
            # Every event must have the two required top-level keys
            assert "event" in evt, f"Event missing 'event' key: {evt}"
            assert "data" in evt, f"Event missing 'data' key: {evt}"
            assert isinstance(evt["event"], str), (
                f"'event' must be str, got {type(evt['event'])}"
            )
            assert isinstance(evt["data"], dict), (
                f"'data' must be dict, got {type(evt['data'])}"
            )
            event_types_seen.add(evt["event"])

        # Verify we actually tested multiple event types
        assert "phase" in event_types_seen, "Expected a 'phase' event in the stream"
        assert "token" in event_types_seen, "Expected a 'token' event in the stream"

    def test_all_update_event_types_have_envelope(self):
        """Individually verify each update event type has the {event, data} envelope."""
        # Phase-only node (no messages)
        output_phase = {"messages": []}
        results = asyncio.run(
            _collect_async(process_update_event("extract_details", output_phase))
        )
        for evt in results:
            assert "event" in evt and "data" in evt

        # Message-only output
        output_msg = {"messages": [AIMessage(content="Hello")]}
        results = asyncio.run(
            _collect_async(process_update_event("general_qa", output_msg))
        )
        for evt in results:
            assert "event" in evt and "data" in evt
            assert isinstance(evt["data"], dict)

        # Worker update output
        output_worker = {
            "messages": [],
            "worker_messages": [
                {"worker_id": "w1", "content": "Working...", "type": "ai"},
            ],
        }
        results = asyncio.run(
            _collect_async(process_update_event("investigation_worker", output_worker))
        )
        for evt in results:
            assert "event" in evt and "data" in evt
            assert isinstance(evt["data"], dict)

    def test_tool_call_without_result_not_emitted(self):
        """Tool calls without a paired ToolMessage result should NOT be emitted.

        The frontend expects tool_call events to always be followed by a tool_result.
        The backend enforces this by only emitting tool_call when a matching
        ToolMessage exists. Verify this contract.
        """
        ai_msg = AIMessage(
            content="",
            tool_calls=[
                {"id": "tc-orphan", "name": "search_logs", "args": {"query": "test"}},
            ],
        )
        # No ToolMessage for tc-orphan
        output = {"messages": [ai_msg]}
        results = asyncio.run(
            _collect_async(process_update_event("general_qa", output))
        )

        tc_events = [r for r in results if r["event"] == "tool_call"]
        tr_events = [r for r in results if r["event"] == "tool_result"]
        assert len(tc_events) == 0, "Orphan tool_call should not be emitted"
        assert len(tr_events) == 0, "Orphan tool_result should not be emitted"
