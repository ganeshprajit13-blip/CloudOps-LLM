"""Tests for the trajectory capture module."""

import time

from trajectory import TrajectoryCapture, ToolCallRecord, NodeTransition


class TestToolCallRecord:
    def test_to_dict(self):
        record = ToolCallRecord(
            tool_name="search_logs",
            tool_args={"query": "error"},
            result_preview="Found 5 results",
            duration_ms=1234.5678,
            worker_id="worker-1",
            timestamp=1700000000.0,
        )
        d = record.to_dict()
        assert d["tool_name"] == "search_logs"
        assert d["duration_ms"] == 1234.6  # rounded


class TestNodeTransition:
    def test_to_dict(self):
        t = NodeTransition(
            from_node="hypothesis_generation",
            to_node="investigation",
            timestamp=1700000000.0,
            duration_ms=350.123,
        )
        d = t.to_dict()
        assert d["from_node"] == "hypothesis_generation"
        assert d["duration_ms"] == 350.1


class TestTrajectoryCapture:
    def test_record_tool_call(self):
        tc = TrajectoryCapture("session-1", "volte-call-drop-handover")
        tc.record_tool_call("search_logs", {"query": "error"}, "results", 100.0, "w1")
        record = tc.finalize()
        assert len(record.tool_calls) == 1
        assert record.tool_calls[0].tool_name == "search_logs"

    def test_record_node_transition(self):
        tc = TrajectoryCapture("session-1")
        tc.record_node_transition("enrichment", "hypothesis", 200.0)
        record = tc.finalize()
        assert len(record.node_transitions) == 1
        assert record.node_transitions[0].from_node == "enrichment"

    def test_record_llm_usage_accumulates(self):
        tc = TrajectoryCapture("session-1")
        tc.record_llm_usage(100, 50)
        tc.record_llm_usage(200, 80)
        record = tc.finalize()
        assert record.llm_input_tokens == 300
        assert record.llm_output_tokens == 130

    def test_set_hypothesis_and_worker_count(self):
        tc = TrajectoryCapture("session-1")
        tc.set_hypothesis_count(3)
        tc.set_worker_count(3)
        record = tc.finalize()
        assert record.num_hypotheses == 3
        assert record.num_workers == 3

    def test_finalize_computes_duration(self):
        tc = TrajectoryCapture("session-1")
        time.sleep(0.01)  # 10ms
        record = tc.finalize()
        assert record.total_duration_ms >= 10.0

    def test_to_dict_shorthand(self):
        tc = TrajectoryCapture("session-1", "test-scenario")
        tc.record_tool_call("think", {"reflection": "hmm"}, "thought", 50.0, "w1")
        d = tc.to_dict()
        assert d["session_id"] == "session-1"
        assert d["scenario_name"] == "test-scenario"
        assert d["num_tool_calls"] == 1
        assert isinstance(d["tool_calls"], list)

    def test_result_preview_truncated(self):
        tc = TrajectoryCapture("session-1")
        long_result = "x" * 500
        tc.record_tool_call("search_logs", {}, long_result, 100.0, "w1")
        record = tc.finalize()
        assert len(record.tool_calls[0].result_preview) == 200

    def test_empty_trajectory(self):
        tc = TrajectoryCapture("session-1")
        record = tc.finalize()
        assert len(record.tool_calls) == 0
        assert len(record.node_transitions) == 0
        assert record.llm_input_tokens == 0

    def test_finalize_twice_returns_independent_records(self):
        """Each finalize() returns a snapshot; adding data after first finalize is captured in second."""
        tc = TrajectoryCapture("session-1")
        tc.record_tool_call("search_logs", {}, "r1", 100.0, "w1")
        r1 = tc.finalize()
        tc.record_tool_call("think", {}, "r2", 50.0, "w1")
        r2 = tc.finalize()
        assert len(r1.tool_calls) == 1
        assert len(r2.tool_calls) == 2
        # Duration increases between finalizations
        assert r2.total_duration_ms >= r1.total_duration_ms

    def test_result_preview_exactly_200_chars(self):
        tc = TrajectoryCapture("session-1")
        result = "x" * 200
        tc.record_tool_call("search_logs", {}, result, 100.0, "w1")
        record = tc.finalize()
        assert len(record.tool_calls[0].result_preview) == 200

    def test_result_preview_short_string_unchanged(self):
        tc = TrajectoryCapture("session-1")
        tc.record_tool_call("search_logs", {}, "short", 100.0, "w1")
        record = tc.finalize()
        assert record.tool_calls[0].result_preview == "short"

    def test_result_preview_empty_string(self):
        tc = TrajectoryCapture("session-1")
        tc.record_tool_call("search_logs", {}, "", 100.0, "w1")
        record = tc.finalize()
        assert record.tool_calls[0].result_preview == ""

    def test_default_scenario_name_empty_string(self):
        tc = TrajectoryCapture("session-1")
        record = tc.finalize()
        assert record.scenario_name == ""

    def test_multiple_tool_calls_and_transitions(self):
        tc = TrajectoryCapture("session-1", "test")
        tc.record_tool_call("search_logs", {"q": "a"}, "r1", 100.0, "w1")
        tc.record_tool_call("search_logs", {"q": "b"}, "r2", 200.0, "w1")
        tc.record_tool_call("think", {}, "r3", 50.0, "w2")
        tc.record_node_transition("enrichment", "hypothesis", 300.0)
        tc.record_node_transition("hypothesis", "investigation", 100.0)
        d = tc.to_dict()
        assert d["num_tool_calls"] == 3
        assert len(d["node_transitions"]) == 2
        assert len(d["tool_calls"]) == 3
