"""Tests for token-level streaming behavior.

Verifies that stream_mode="messages" produces AIMessageChunk events,
that process_dual_stream() correctly converts them to structured events,
and that structured output chunks (empty content) are filtered out.
"""

import asyncio
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, AIMessageChunk
from stream_formatter import (
    _namespace_send_id,
    process_dual_stream,
    process_update_event,
)


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
# Tests: process_dual_stream (stream_formatter.py)
# ---------------------------------------------------------------------------


class TestProcessDualStream:
    """Tests for the process_dual_stream() function in stream_formatter.py."""

    def test_token_events_from_messages_namespace(self):
        """Messages namespace with AIMessageChunk produces token events."""
        chunk = AIMessageChunk(content="Hello")
        metadata = {"langgraph_node": "general_qa"}

        events = [("messages", (chunk, metadata))]

        results = asyncio.run(_collect_async(process_dual_stream(_async_gen(events))))
        assert len(results) == 1
        assert results[0]["event"] == "token"
        assert results[0]["data"]["content"] == "Hello"
        assert results[0]["data"]["node"] == "general_qa"

    def test_empty_content_chunks_filtered_out(self):
        """AIMessageChunk with empty content (e.g., tool-call chunks) is skipped."""
        # Structured output tool-call chunk — has tool_call_chunks but empty content
        chunk = AIMessageChunk(content="")
        metadata = {"langgraph_node": "hypothesis_generation"}

        events = [("messages", (chunk, metadata))]

        results = asyncio.run(_collect_async(process_dual_stream(_async_gen(events))))
        assert len(results) == 0

    def test_update_events_produce_phase_and_message(self):
        """Updates namespace produces phase and message events."""
        update_data = {
            "general_qa": {
                "messages": [AIMessage(content="The answer is 42.")],
            }
        }

        events = [("updates", update_data)]

        results = asyncio.run(_collect_async(process_dual_stream(_async_gen(events))))

        # Should produce a phase event and a message event
        event_types = [r["event"] for r in results]
        assert "phase" in event_types
        assert "message" in event_types

        msg_event = next(r for r in results if r["event"] == "message")
        assert msg_event["data"]["content"] == "The answer is 42."
        assert msg_event["data"]["node"] == "general_qa"

    def test_mixed_updates_and_messages(self):
        """Both namespaces interleaved produce correct events."""
        chunk1 = AIMessageChunk(content="tok1")
        chunk2 = AIMessageChunk(content="tok2")
        update_data = {
            "synthesize_findings": {
                "messages": [AIMessage(content="Synthesis complete.")],
            }
        }

        events = [
            ("messages", (chunk1, {"langgraph_node": "general_qa"})),
            ("updates", update_data),
            ("messages", (chunk2, {"langgraph_node": "general_qa"})),
        ]

        results = asyncio.run(_collect_async(process_dual_stream(_async_gen(events))))

        event_types = [r["event"] for r in results]
        assert event_types.count("token") == 2
        assert "phase" in event_types
        assert "message" in event_types

    def test_non_dict_update_data_skipped(self):
        """Non-dict data in updates namespace is silently skipped."""
        events = [("updates", "not-a-dict")]

        results = asyncio.run(_collect_async(process_dual_stream(_async_gen(events))))
        assert len(results) == 0

    def test_non_aimessagechunk_in_messages_skipped(self):
        """Non-AIMessageChunk objects in messages namespace are skipped."""
        # Human messages shouldn't produce token events
        from langchain_core.messages import HumanMessageChunk

        chunk = HumanMessageChunk(content="user input")
        metadata = {"langgraph_node": "human_input"}

        events = [("messages", (chunk, metadata))]

        results = asyncio.run(_collect_async(process_dual_stream(_async_gen(events))))
        assert len(results) == 0


# ---------------------------------------------------------------------------
# Tests: _namespace_send_id
# ---------------------------------------------------------------------------


class TestNamespaceSendId:
    """Tests for the _namespace_send_id() helper."""

    def test_empty_tuple_returns_none(self):
        assert _namespace_send_id(()) is None

    def test_root_graph_returns_none(self):
        assert _namespace_send_id(("clarify_incident",)) is None

    def test_worker_namespace_extracts_send_id(self):
        ns = ("investigation_worker:investigator-1",)
        assert _namespace_send_id(ns) == "investigator-1"

    def test_uuid_namespace_extracts_send_id(self):
        ns = ("investigation_worker:854e8aa6-14cf-6d57-3afc-b1715a5afa3a",)
        assert _namespace_send_id(ns) == "854e8aa6-14cf-6d57-3afc-b1715a5afa3a"

    def test_nested_subgraph_extracts_from_first(self):
        ns = ("investigation_worker:investigator-2", "investigation_reasoning")
        assert _namespace_send_id(ns) == "investigator-2"


# ---------------------------------------------------------------------------
# Tests: process_dual_stream with subgraphs=True (3-tuple format)
# ---------------------------------------------------------------------------


class TestProcessDualStreamSubgraphs:
    """Tests for process_dual_stream() with the 3-tuple subgraph event format."""

    def test_subgraph_tokens_are_suppressed(self):
        """Token events from worker subgraphs should be suppressed (only tool dropdowns shown)."""
        chunk = AIMessageChunk(content="Searching logs...")
        metadata = {"langgraph_node": "investigation_reasoning"}
        ns = ("investigation_worker:investigator-1",)

        events = [(ns, "messages", (chunk, metadata))]

        results = asyncio.run(_collect_async(process_dual_stream(_async_gen(events))))
        token_events = [r for r in results if r["event"] == "token"]
        assert len(token_events) == 0

    def test_subgraph_updates_suppress_worker_text(self):
        """Worker reasoning text in subgraph updates should be suppressed.

        Only the initial worker_update announcement is emitted; the AI
        message content from worker_messages must not leak as a message event.
        """
        output = {
            "investigation_reasoning": {
                "worker_messages": [
                    {
                        "worker_id": "investigator-1",
                        "content": "Found timeout evidence",
                        "type": "ai",
                    }
                ],
                "messages": [],
            }
        }
        ns = ("investigation_worker:investigator-1",)

        events = [(ns, "updates", output)]

        results = asyncio.run(_collect_async(process_dual_stream(_async_gen(events))))
        message_events = [r for r in results if r["event"] == "message"]
        assert len(message_events) == 0
        # Initial worker_update announcement is expected (exactly one)
        wu = [r for r in results if r["event"] == "worker_update"]
        assert len(wu) == 1

    def test_subgraph_updates_suppress_all_text_events(self):
        """Subgraph update events must NOT emit 'message' events for worker text.

        The only worker-related event allowed is the one-time worker_update
        announcement emitted the first time a worker is seen.
        """
        output = {
            "investigation_reasoning": {
                "messages": [
                    AIMessage(content="Worker reasoning text that should be suppressed")
                ],
                "worker_messages": [
                    {
                        "worker_id": "investigator-1",
                        "content": "Found timeout evidence",
                        "type": "ai",
                    }
                ],
            }
        }
        ns = ("investigation_worker:investigator-1",)

        events = [(ns, "updates", output)]

        results = asyncio.run(_collect_async(process_dual_stream(_async_gen(events))))
        message_events = [r for r in results if r["event"] == "message"]
        # No AI message text events from workers
        assert len(message_events) == 0
        # Initial worker_update announcement is expected
        wu = [r for r in results if r["event"] == "worker_update"]
        assert len(wu) == 1

    def test_uuid_namespace_resolves_to_real_worker_id(self):
        """LangGraph uses UUIDs in namespace; worker_update must use the real investigator-N id."""
        output = {
            "investigation_reasoning": {
                "worker_messages": [
                    {
                        "worker_id": "investigator-2",
                        "content": "Reasoning about hypothesis",
                        "type": "ai",
                    }
                ],
                "messages": [],
            }
        }
        # Realistic namespace: UUID, not investigator-N
        ns = ("investigation_worker:854e8aa6-14cf-6d57-3afc-b1715a5afa3a",)

        events = [(ns, "updates", output)]

        results = asyncio.run(_collect_async(process_dual_stream(_async_gen(events))))
        wu = [r for r in results if r["event"] == "worker_update"]
        assert len(wu) == 1
        assert wu[0]["data"]["worker_id"] == "investigator-2"

    def test_uuid_namespace_second_event_reuses_mapping(self):
        """After resolving a UUID→worker_id, subsequent events for the same UUID reuse it."""
        output1 = {
            "investigation_reasoning": {
                "worker_messages": [
                    {
                        "worker_id": "investigator-1",
                        "content": "first",
                        "type": "ai",
                        "tool_calls": [
                            {"id": "tc1", "name": "search_logs", "args": {"query": "x"}}
                        ],
                    }
                ],
                "messages": [],
            }
        }
        output2 = {
            "investigation_tool": {
                "worker_messages": [
                    {
                        "worker_id": "investigator-1",
                        "content": "result",
                        "type": "tool",
                        "tool_call_id": "tc1",
                    }
                ],
                "messages": [],
            }
        }
        uuid_ns = ("investigation_worker:aaaa-bbbb-cccc",)

        events = [
            (uuid_ns, "updates", output1),
            (uuid_ns, "updates", output2),
        ]

        results = asyncio.run(_collect_async(process_dual_stream(_async_gen(events))))
        # Only one worker_update (not two)
        wu = [r for r in results if r["event"] == "worker_update"]
        assert len(wu) == 1
        # Tool call uses the resolved worker_id, not the UUID
        tc = [r for r in results if r["event"] == "tool_call"]
        assert len(tc) == 1
        assert tc[0]["data"]["node"] == "investigator-1"

    def test_conclusion_emitted_as_worker_update(self):
        """When a worker's final message contains CONCLUSION:, a worker_update with conclusion is emitted."""
        output1 = {
            "investigation_reasoning": {
                "worker_messages": [
                    {
                        "worker_id": "investigator-1",
                        "content": "Starting investigation",
                        "type": "ai",
                    }
                ],
                "messages": [],
            }
        }
        output2 = {
            "investigation_reasoning": {
                "worker_messages": [
                    {
                        "worker_id": "investigator-1",
                        "content": "HYPOTHESIS: thermal pads\nEVIDENCE: logs show swap\nCONCLUSION: SUPPORTED with evidence",
                        "type": "ai",
                    }
                ],
                "messages": [],
            }
        }
        uuid_ns = ("investigation_worker:some-uuid",)

        events = [
            (uuid_ns, "updates", output1),
            (uuid_ns, "updates", output2),
        ]

        results = asyncio.run(_collect_async(process_dual_stream(_async_gen(events))))
        wu = [r for r in results if r["event"] == "worker_update"]
        # First: announcement, second: conclusion
        assert len(wu) == 2
        assert wu[0]["data"]["worker_id"] == "investigator-1"
        assert "conclusion" not in wu[0]["data"]
        assert wu[1]["data"]["conclusion"] == "SUPPORTED"

    def test_partially_supported_conclusion(self):
        """PARTIALLY SUPPORTED conclusion is normalised correctly."""
        output = {
            "investigation_reasoning": {
                "worker_messages": [
                    {
                        "worker_id": "investigator-3",
                        "content": "CONCLUSION: PARTIALLY SUPPORTED due to partial evidence",
                        "type": "ai",
                    }
                ],
                "messages": [],
            }
        }
        ns = ("investigation_worker:uuid-123",)
        events = [(ns, "updates", output)]

        results = asyncio.run(_collect_async(process_dual_stream(_async_gen(events))))
        wu = [r for r in results if r["event"] == "worker_update"]
        conclusion_wu = [w for w in wu if "conclusion" in w["data"]]
        assert len(conclusion_wu) == 1
        assert conclusion_wu[0]["data"]["conclusion"] == "PARTIALLY SUPPORTED"

    def test_root_investigation_worker_update_is_skipped(self):
        """Root-graph investigation_worker updates are skipped to avoid duplicates."""
        output = {
            "investigation_worker": {
                "messages": [],
                "worker_messages": [
                    {
                        "worker_id": "investigator-1",
                        "content": "duplicated content",
                        "type": "ai",
                    }
                ],
            }
        }
        # Root graph: empty namespace tuple
        events = [
            ((), "updates", output),
        ]

        results = asyncio.run(_collect_async(process_dual_stream(_async_gen(events))))
        # Should be empty — root investigation_worker updates are suppressed
        assert len(results) == 0

    def test_root_graph_3tuple_still_works(self):
        """Root-graph events in 3-tuple format (empty namespace) still emit normally."""
        update_data = {
            "clarify_incident": {
                "messages": [AIMessage(content="Need more info.")],
            }
        }

        events = [((), "updates", update_data)]

        results = asyncio.run(_collect_async(process_dual_stream(_async_gen(events))))
        event_types = [r["event"] for r in results]
        assert "phase" in event_types
        assert "message" in event_types

    def test_legacy_2tuple_still_works(self):
        """Legacy 2-tuple format (no subgraphs) continues to work."""
        chunk = AIMessageChunk(content="Hello")
        metadata = {"langgraph_node": "general_qa"}

        events = [("messages", (chunk, metadata))]

        results = asyncio.run(_collect_async(process_dual_stream(_async_gen(events))))
        assert len(results) == 1
        assert results[0]["event"] == "token"
        assert results[0]["data"]["node"] == "general_qa"


# ---------------------------------------------------------------------------
# Tests: process_update_event (stream_formatter.py)
# ---------------------------------------------------------------------------


class TestProcessUpdateEvent:
    """Tests for process_update_event() in stream_formatter.py."""

    def test_emits_phase_for_known_node(self):
        """Known nodes emit a phase event."""
        output = {"messages": []}
        results = asyncio.run(
            _collect_async(process_update_event("clarify_incident", output))
        )
        phase_events = [r for r in results if r["event"] == "phase"]
        assert len(phase_events) == 1
        assert phase_events[0]["data"]["phase"] == "clarification"

    def test_emits_hypothesis_event(self):
        """When current_hypotheses is in output, emits hypothesis event."""
        # Create a mock hypotheses object
        mock_hyp = MagicMock()
        mock_hyp.hypotheses = {
            1: MagicMock(
                service="redis",
                description="Cache issue",
                search_terms=["redis", "cache"],
                rationale="Likely",
            ),
        }

        output = {"current_hypotheses": mock_hyp, "messages": []}
        results = asyncio.run(
            _collect_async(process_update_event("hypothesis_generation", output))
        )

        hyp_events = [r for r in results if r["event"] == "hypothesis"]
        assert len(hyp_events) == 1

    def test_worker_text_suppressed(self):
        """Worker AIMessage text should not produce worker_update events."""
        output = {
            "messages": [],
            "worker_messages": [AIMessage(content="Found evidence of timeout")],
        }
        results = asyncio.run(
            _collect_async(process_update_event("investigation_worker", output))
        )

        worker_events = [r for r in results if r["event"] == "worker_update"]
        assert len(worker_events) == 0

    def test_worker_dict_text_suppressed(self):
        """Dict-format worker AI messages should not produce worker_update events."""
        output = {
            "messages": [],
            "worker_messages": [
                {
                    "worker_id": "investigator-1",
                    "content": "Checking logs for timeout",
                    "type": "ai",
                },
                {
                    "worker_id": "investigator-1",
                    "content": "result data",
                    "type": "tool",
                    "tool_call_id": "tc1",
                },
            ],
        }
        results = asyncio.run(
            _collect_async(process_update_event("investigation_worker", output))
        )

        worker_events = [r for r in results if r["event"] == "worker_update"]
        assert len(worker_events) == 0

    def test_emits_worker_tool_calls_from_dict(self):
        """Dict-format worker messages with tool_calls emit paired tool_call + tool_result."""
        output = {
            "messages": [],
            "worker_messages": [
                {
                    "worker_id": "investigator-2",
                    "content": "",
                    "type": "ai",
                    "tool_calls": [
                        {"id": "tc1", "name": "search_logs", "args": {"query": "error"}}
                    ],
                },
                {
                    "worker_id": "investigator-2",
                    "content": "Found 3 errors",
                    "type": "tool",
                    "tool_call_id": "tc1",
                },
            ],
        }
        results = asyncio.run(
            _collect_async(process_update_event("investigation_worker", output))
        )

        tc_events = [r for r in results if r["event"] == "tool_call"]
        tr_events = [r for r in results if r["event"] == "tool_result"]
        assert len(tc_events) == 1
        assert len(tr_events) == 1
        assert tc_events[0]["data"]["name"] == "search_logs"
        assert tc_events[0]["data"]["node"] == "investigator-2"
        assert "3 errors" in tr_events[0]["data"]["content"]

    def test_emits_ai_message(self):
        """AI messages in output produce message events."""
        output = {"messages": [AIMessage(content="Starting investigation...")]}
        results = asyncio.run(
            _collect_async(process_update_event("initiate_agents", output))
        )

        msg_events = [r for r in results if r["event"] == "message"]
        assert len(msg_events) == 1
        assert msg_events[0]["data"]["role"] == "ai"
        assert msg_events[0]["data"]["node"] == "initiate_agents"


# ---------------------------------------------------------------------------
# Tests: streaming=True on ChatBedrockConverse
# ---------------------------------------------------------------------------


class TestLLMStreamingConfig:
    """Verify the LLM is configured with streaming=True."""

    def test_get_llm_has_streaming_enabled(self):
        """get_llm() returns a ChatBedrockConverse with disable_streaming=False."""
        import rca_agent

        # Mock the ChatBedrockConverse constructor to capture kwargs
        captured_kwargs = {}

        class FakeLLM:
            def __init__(self, **kwargs):
                captured_kwargs.update(kwargs)
                self.disable_streaming = kwargs.get("disable_streaming", True)

        rca_agent._llm = None
        with (
            patch.object(rca_agent, "ChatBedrockConverse", FakeLLM),
            patch("rca_agent.boto3") as mock_boto3,
        ):
            mock_boto3.client.return_value = MagicMock()
            llm = rca_agent.get_llm()
            assert llm.disable_streaming is False
            assert captured_kwargs.get("disable_streaming") is False

        # Cleanup
        rca_agent._llm = None
