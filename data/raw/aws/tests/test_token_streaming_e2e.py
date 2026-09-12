"""End-to-end test for token-level streaming through the SSE pipeline.

Tests the full backend path: mock graph → _stream_graph() → SSE events,
verifying that token events are emitted before complete message events.
No real LLM calls — uses a mock graph with fake AIMessageChunks.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, AIMessageChunk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_graph(tokens, node_name="general_qa"):
    """Create a mock graph that yields token-level streaming events.

    Simulates stream_mode=["updates", "messages"]:
      - ("messages", (AIMessageChunk, metadata)) for each token
      - ("updates", {node: {messages: [AIMessage]}}) for the final message
    """
    mock_graph = MagicMock()
    full_content = "".join(tokens)

    async def fake_astream(input_data, config, stream_mode=None, subgraphs=False):
        for tok in tokens:
            chunk = AIMessageChunk(content=tok)
            yield ((), "messages", (chunk, {"langgraph_node": node_name}))
        yield (
            (),
            "updates",
            {node_name: {"messages": [AIMessage(content=full_content)]}},
        )

    mock_graph.astream = fake_astream
    _state = MagicMock(next=None, values={"synthesized_report": full_content})
    mock_graph.get_state.return_value = _state
    mock_graph.aget_state = AsyncMock(return_value=_state)
    return mock_graph


async def _collect_events(async_gen):
    """Collect all events from an async generator."""
    events = []
    async for event in async_gen:
        events.append(event)
    return events


def _parse_sse_line(line: str) -> dict:
    """Parse an SSE wire-format line (data: {json}\\n\\n) into a dict."""
    stripped = line.strip()
    if stripped.startswith("data: "):
        stripped = stripped[6:]
    elif stripped.startswith("data:"):
        stripped = stripped[5:]
    return json.loads(stripped)


# ---------------------------------------------------------------------------
# Tests: _stream_graph produces token events
# ---------------------------------------------------------------------------


class TestStreamGraphTokenEvents:
    """Verify _stream_graph yields token SSE events from the mock graph."""

    def test_stream_graph_emits_token_events(self):
        """_stream_graph yields 'token' SSE events for each AIMessageChunk."""
        from api import InvestigationState, _stream_graph

        tokens = ["Hello", " world", "!"]
        mock_graph = _make_mock_graph(tokens, node_name="clarify_incident")

        inv = InvestigationState(
            id="test-1",
            scenario_name="test",
            incident="Test incident",
            thread_config={"configurable": {"thread_id": "test-thread"}},
        )

        with patch("api._graph", mock_graph):
            raw_lines = asyncio.run(_collect_events(_stream_graph(inv)))

        # Parse SSE lines and filter token events
        parsed = [_parse_sse_line(line) for line in raw_lines]
        token_events = [e for e in parsed if e["event"] == "token"]

        assert len(token_events) == len(tokens), (
            f"Expected {len(tokens)} token events, got {len(token_events)}. "
            f"All events: {[e['event'] for e in parsed]}"
        )

        received = [e["data"]["content"] for e in token_events]
        assert received == tokens

    def test_token_events_carry_node_name(self):
        """Each token event includes the originating node name."""
        from api import InvestigationState, _stream_graph

        mock_graph = _make_mock_graph(["tok"], node_name="synthesize_findings")

        inv = InvestigationState(
            id="test-2",
            scenario_name="test",
            incident="Test incident",
            thread_config={"configurable": {"thread_id": "test-thread-2"}},
        )

        with patch("api._graph", mock_graph):
            raw_lines = asyncio.run(_collect_events(_stream_graph(inv)))

        parsed = [_parse_sse_line(line) for line in raw_lines]
        token_events = [e for e in parsed if e["event"] == "token"]
        assert len(token_events) == 1
        assert token_events[0]["data"]["node"] == "synthesize_findings"

    def test_tokens_arrive_before_complete_message(self):
        """Token events precede the corresponding message event in the stream."""
        from api import InvestigationState, _stream_graph

        tokens = ["A", "B", "C"]
        mock_graph = _make_mock_graph(tokens, node_name="general_qa")

        inv = InvestigationState(
            id="test-3",
            scenario_name="test",
            incident="Test incident",
            thread_config={"configurable": {"thread_id": "test-thread-3"}},
        )

        with patch("api._graph", mock_graph):
            raw_lines = asyncio.run(_collect_events(_stream_graph(inv)))

        parsed = [_parse_sse_line(line) for line in raw_lines]
        event_types = [e["event"] for e in parsed]

        first_token = next((i for i, t in enumerate(event_types) if t == "token"), None)
        first_msg = next((i for i, t in enumerate(event_types) if t == "message"), None)

        assert first_token is not None, f"No token events. Events: {event_types}"
        assert first_msg is not None, f"No message events. Events: {event_types}"
        assert first_token < first_msg, (
            f"Token at index {first_token} should precede message at {first_msg}"
        )

    def test_complete_message_has_full_content(self):
        """The 'message' event contains the full concatenated text."""
        from api import InvestigationState, _stream_graph

        tokens = ["Root ", "cause: ", "timeout"]
        mock_graph = _make_mock_graph(tokens, node_name="general_qa")

        inv = InvestigationState(
            id="test-4",
            scenario_name="test",
            incident="Test incident",
            thread_config={"configurable": {"thread_id": "test-thread-4"}},
        )

        with patch("api._graph", mock_graph):
            raw_lines = asyncio.run(_collect_events(_stream_graph(inv)))

        parsed = [_parse_sse_line(line) for line in raw_lines]
        message_events = [e for e in parsed if e["event"] == "message"]
        assert len(message_events) >= 1
        assert message_events[0]["data"]["content"] == "Root cause: timeout"

    def test_stream_ends_with_complete_event(self):
        """The stream ends with a 'complete' event containing the report."""
        from api import InvestigationState, _stream_graph

        tokens = ["Done"]
        mock_graph = _make_mock_graph(tokens, node_name="general_qa")

        inv = InvestigationState(
            id="test-5",
            scenario_name="test",
            incident="Test incident",
            thread_config={"configurable": {"thread_id": "test-thread-5"}},
        )

        with patch("api._graph", mock_graph):
            raw_lines = asyncio.run(_collect_events(_stream_graph(inv)))

        last_parsed = _parse_sse_line(raw_lines[-1])
        assert last_parsed["event"] == "complete"
        assert last_parsed["data"]["report"] == "Done"
