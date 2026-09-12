"""Tests for graph structure, Send() pattern, and worker node logic.

Verifies the orchestrator and worker graph topology, the dynamic
investigator spawning via Send(), and worker node behavior with mocked LLMs.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from rca_agent import (
    build_orchestrator_graph,
    build_worker_graph,
    spawn_investigators,
    context_enrichment,
    OrchestratorState,
    WorkerState,
    Hypothesis,
    Hypotheses,
    investigation_tool,
    render_hypotheses,
)


# ---------------------------------------------------------------------------
# Tests: Graph structure
# ---------------------------------------------------------------------------


class TestOrchestratorGraphStructure:
    """Verify the orchestrator graph has the expected topology."""

    @pytest.fixture
    def graph(self):
        return build_orchestrator_graph()

    def test_graph_compiles(self, graph):
        """Graph compiles without errors."""
        assert graph is not None

    def test_graph_has_expected_nodes(self, graph):
        """All orchestrator nodes are present in the compiled graph."""
        # Access the underlying graph's nodes
        node_names = set(graph.get_graph().nodes.keys())

        expected_nodes = {
            "clarify_incident",
            "human_input_clarify",
            "extract_details",
            "context_enrichment",
            "hypothesis_generation",
            "human_input",
            "general_qa",
            "initiate_agents",
            "investigation_worker",
            "synthesize_findings",
            "human_input_post",
            "__start__",
            "__end__",
        }

        for node in expected_nodes:
            assert node in node_names, f"Missing node: {node}"


class TestWorkerGraphStructure:
    """Verify the worker subgraph has the expected topology."""

    @pytest.fixture
    def graph(self):
        return build_worker_graph()

    def test_worker_graph_compiles(self, graph):
        """Worker graph compiles without errors."""
        assert graph is not None

    def test_worker_graph_has_expected_nodes(self, graph):
        node_names = set(graph.get_graph().nodes.keys())
        assert "investigation_reasoning" in node_names
        assert "investigation_tool" in node_names


# ---------------------------------------------------------------------------
# Tests: spawn_investigators (Send pattern)
# ---------------------------------------------------------------------------


class TestSpawnInvestigators:
    """Test the Send() pattern for dynamic agent spawning."""

    def _make_state(self, num_hypotheses=3, time_start=None, time_end=None):
        """Create an OrchestratorState-like dict with hypotheses."""
        hypotheses = {}
        for i in range(1, num_hypotheses + 1):
            hypotheses[i] = Hypothesis(
                service=f"service-{i}",
                description=f"Hypothesis {i} description",
                search_terms=[f"term-{i}a", f"term-{i}b"],
                rationale=f"Rationale {i}",
                time_window_start=None,
                time_window_end=None,
            )

        return {
            "current_hypotheses": Hypotheses(hypotheses=hypotheses),
            "scenario_name": "test-scenario",
            "time_window_start": time_start,
            "time_window_end": time_end,
        }

    def test_creates_correct_number_of_sends(self):
        """One Send per hypothesis."""
        state = self._make_state(num_hypotheses=3)
        sends = spawn_investigators(state)
        assert len(sends) == 3

    def test_sends_target_investigation_worker(self):
        """All Sends target the investigation_worker node."""
        state = self._make_state(num_hypotheses=2)
        sends = spawn_investigators(state)
        for send in sends:
            assert send.node == "investigation_worker"

    def test_sends_have_correct_worker_ids(self):
        """Worker IDs follow the investigator-{priority} pattern."""
        state = self._make_state(num_hypotheses=3)
        sends = spawn_investigators(state)
        worker_ids = [s.arg["worker_id"] for s in sends]
        assert "investigator-1" in worker_ids
        assert "investigator-2" in worker_ids
        assert "investigator-3" in worker_ids

    def test_sends_carry_hypothesis(self):
        """Each Send carries its corresponding hypothesis."""
        state = self._make_state(num_hypotheses=2)
        sends = spawn_investigators(state)
        for send in sends:
            hyp = send.arg["hypothesis"]
            assert isinstance(hyp, Hypothesis)
            assert hyp.service.startswith("service-")

    def test_state_time_window_propagated(self):
        """Time windows from state are passed to workers (start extended by 14-day lookback)."""
        state = self._make_state(
            num_hypotheses=1,
            time_start="2024-03-15T14:00:00",
            time_end="2024-03-15T14:30:00",
        )
        sends = spawn_investigators(state)
        # spawn_investigators extends start backward by 14 days for root-cause discovery
        assert sends[0].arg["time_window_start"] == "2024-03-01T14:00:00"
        assert sends[0].arg["time_window_end"] == "2024-03-15T14:30:00"

    def test_hypothesis_time_window_overrides_state(self):
        """Per-hypothesis time windows override the global state time window."""
        hypotheses = {
            1: Hypothesis(
                service="redis",
                description="Cache issue",
                search_terms=["redis"],
                rationale="test",
                time_window_start="2024-03-15T15:00:00",
                time_window_end="2024-03-15T15:30:00",
            )
        }

        state = {
            "current_hypotheses": Hypotheses(hypotheses=hypotheses),
            "scenario_name": "test",
            "time_window_start": "2024-03-15T14:00:00",
            "time_window_end": "2024-03-15T14:30:00",
        }

        sends = spawn_investigators(state)
        # Hypothesis time window should win over state time window
        assert sends[0].arg["time_window_start"] == "2024-03-15T15:00:00"
        assert sends[0].arg["time_window_end"] == "2024-03-15T15:30:00"

    def test_sends_have_correct_initial_state(self):
        """Send args have all required WorkerState fields."""
        state = self._make_state(num_hypotheses=1)
        sends = spawn_investigators(state)
        arg = sends[0].arg

        assert "worker_id" in arg
        assert "worker_messages" in arg
        assert arg["worker_messages"] == []
        assert "n_iterations" in arg
        assert arg["n_iterations"] == 0
        assert "max_iterations" in arg
        assert arg["max_iterations"] == 25
        assert "hypothesis" in arg
        assert "scenario_name" in arg
        assert arg["scenario_name"] == "test-scenario"

    def test_single_hypothesis(self):
        """Single hypothesis produces single Send."""
        state = self._make_state(num_hypotheses=1)
        sends = spawn_investigators(state)
        assert len(sends) == 1


# ---------------------------------------------------------------------------
# Tests: State schemas
# ---------------------------------------------------------------------------


class TestStateSchemas:
    """Verify state TypedDicts have expected fields."""

    def test_orchestrator_state_fields(self):
        """OrchestratorState inherits from MessagesState and adds RCA fields."""
        annotations = OrchestratorState.__annotations__
        expected_fields = [
            "incident",
            "incident_time",
            "context",
            "enriched_context",
            "current_hypotheses",
            "selected_hypotheses",
            "worker_messages",
            "synthesized_report",
            "scenario_name",
            "investigation_complete",
        ]
        for field in expected_fields:
            assert field in annotations, f"Missing field: {field}"

    def test_worker_state_fields(self):
        """WorkerState has worker-specific fields."""
        annotations = WorkerState.__annotations__
        expected_fields = [
            "worker_id",
            "worker_messages",
            "n_iterations",
            "max_iterations",
            "hypothesis",
            "scenario_name",
            "time_window_start",
            "time_window_end",
        ]
        for field in expected_fields:
            assert field in annotations, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# Tests: Helper functions
# ---------------------------------------------------------------------------


class TestHelperFunctions:
    def test_lookup_context_executor_uses_search(self):
        """lookup_context executor calls search() with the query."""
        from tool_registry import execute_lookup_context

        mock_source = MagicMock()
        mock_source.search.return_value = [
            "Check redis connection pool settings",
            "Redis timeout configuration",
        ]
        ctx = {"context_source": mock_source, "scenario_name": "test"}
        result = execute_lookup_context(
            {"query": "redis", "context_type": "runbooks"}, ctx
        )
        mock_source.search.assert_called_once_with(
            query="runbooks: redis", num_results=5, scenario_name="test"
        )
        assert "redis connection pool" in result

    def test_lookup_context_executor_returns_all(self):
        """lookup_context executor returns search results for default context_type."""
        from tool_registry import execute_lookup_context

        mock_source = MagicMock()
        mock_source.search.return_value = [
            "Check redis connection pool",
            "Similar outage in Q1",
        ]
        ctx = {"context_source": mock_source, "scenario_name": "test"}
        result = execute_lookup_context({"query": "redis"}, ctx)
        mock_source.search.assert_called_once_with(
            query="redis", num_results=5, scenario_name="test"
        )
        assert "redis connection pool" in result
        assert "Similar outage" in result

    def test_lookup_context_executor_no_source(self):
        """lookup_context executor handles missing context source."""
        from tool_registry import execute_lookup_context

        result = execute_lookup_context({"query": "redis"}, {})
        assert "ERROR" in result

    def test_lookup_context_executor_empty_query(self):
        """lookup_context executor requires a non-empty query."""
        from tool_registry import execute_lookup_context

        mock_source = MagicMock()
        ctx = {"context_source": mock_source, "scenario_name": "test"}
        result = execute_lookup_context({"query": ""}, ctx)
        assert "ERROR" in result
        mock_source.search.assert_not_called()

    def test_render_hypotheses(self):
        """Formats hypotheses for display."""
        hypotheses = Hypotheses(
            hypotheses={
                1: Hypothesis(
                    service="redis",
                    description="Cache thundering herd",
                    search_terms=["redis", "eviction"],
                    rationale="High cache miss rate",
                ),
            }
        )
        result = render_hypotheses(hypotheses)
        assert "redis" in result
        assert "Cache thundering herd" in result
        assert "eviction" in result

    def test_render_hypotheses_multiple(self):
        """Renders multiple hypotheses with priorities."""
        hypotheses = Hypotheses(
            hypotheses={
                1: Hypothesis(
                    service="redis",
                    description="H1",
                    search_terms=["t1"],
                    rationale="r1",
                ),
                2: Hypothesis(
                    service="nginx",
                    description="H2",
                    search_terms=["t2"],
                    rationale="r2",
                ),
            }
        )
        result = render_hypotheses(hypotheses)
        assert "Hypothesis 1" in result
        assert "Hypothesis 2" in result
        assert "redis" in result
        assert "nginx" in result


# ---------------------------------------------------------------------------
# Tests: investigation_tool with trajectory
# ---------------------------------------------------------------------------


class TestInvestigationToolTrajectory:
    """Test that investigation_tool records to trajectory when present."""

    def test_trajectory_recording_via_config(self):
        """Tool calls are recorded to trajectory passed via config."""
        from trajectory import TrajectoryCapture

        trajectory = TrajectoryCapture("session-1", "test-scenario")

        # Create a minimal state with a tool call
        state = {
            "worker_id": "investigator-1",
            "worker_messages": [
                {
                    "type": "ai",
                    "content": "Let me search",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "name": "search_logs",
                            "args": {
                                "query": "error",
                                "time_start": "2024-03-15T14:00:00",
                                "time_end": "2024-03-15T14:30:00",
                            },
                        }
                    ],
                }
            ],
            "hypothesis": Hypothesis(
                service="redis",
                description="Cache issue",
                search_terms=["redis"],
                rationale="test",
            ),
            "scenario_name": "test",
            "time_window_start": "2024-03-15T14:00:00",
            "time_window_end": "2024-03-15T14:30:00",
            "n_iterations": 1,
            "max_iterations": 5,
        }

        config = {"configurable": {"trajectory": trajectory}}

        # Mock the tool registry to return a simple executor
        mock_registry = MagicMock()
        mock_registry.get_executor.return_value = lambda args, ctx: (
            "Found 5 log entries"
        )

        mock_log_search = MagicMock()
        mock_ctx_source = MagicMock()
        with (
            patch("tool_registry.get_tool_registry", return_value=mock_registry),
            patch("rca_agent.create_log_search_source", return_value=mock_log_search),
            patch("rca_agent.create_context_source", return_value=mock_ctx_source),
        ):
            asyncio.run(investigation_tool(state, config=config))

        # Verify trajectory was populated
        record = trajectory.finalize()
        assert len(record.tool_calls) == 1
        assert record.tool_calls[0].tool_name == "search_logs"
        assert record.tool_calls[0].worker_id == "investigator-1"
        assert record.tool_calls[0].duration_ms >= 0

    def test_no_trajectory_no_error(self):
        """When no trajectory in config, tool executes without error."""
        state = {
            "worker_id": "investigator-1",
            "worker_messages": [
                {
                    "type": "ai",
                    "content": "searching",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "name": "search_logs",
                            "args": {
                                "query": "error",
                                "time_start": "2024-03-15T14:00:00",
                                "time_end": "2024-03-15T14:30:00",
                            },
                        }
                    ],
                }
            ],
            "hypothesis": Hypothesis(
                service="redis",
                description="Cache issue",
                search_terms=["redis"],
                rationale="test",
            ),
            "scenario_name": "test",
            "time_window_start": "2024-03-15T14:00:00",
            "time_window_end": "2024-03-15T14:30:00",
            "n_iterations": 1,
            "max_iterations": 5,
        }

        config = {"configurable": {}}

        mock_registry = MagicMock()
        mock_registry.get_executor.return_value = lambda args, ctx: "results"
        mock_log_search = MagicMock()
        mock_ctx_source = MagicMock()

        with (
            patch("tool_registry.get_tool_registry", return_value=mock_registry),
            patch("rca_agent.create_log_search_source", return_value=mock_log_search),
            patch("rca_agent.create_context_source", return_value=mock_ctx_source),
        ):
            result = asyncio.run(investigation_tool(state, config=config))

        # Should complete without error
        assert "worker_messages" in result


# ---------------------------------------------------------------------------
# Tests: context_enrichment node
# ---------------------------------------------------------------------------


class TestContextEnrichment:
    """Test the pre-hypothesis context enrichment node."""

    def test_enrichment_uses_targeted_search(self):
        """Context enrichment calls search() with targeted queries."""
        mock_ctx_source = MagicMock()
        mock_ctx_source.search.return_value = [
            "Check redis connection pool settings",
            "Similar outage in Q1 2024",
        ]

        state = {
            "scenario_name": "test-scenario",
            "enriched_context": "# Current Incident\n\nTest incident\n\n",
            "incident_details": None,
            "time_window_start": None,
            "time_window_end": None,
        }

        with patch("rca_agent.create_context_source", return_value=mock_ctx_source):
            result = asyncio.run(context_enrichment(state))

        enriched = result.update["enriched_context"]
        assert "redis connection pool" in enriched
        assert "Similar outage" in enriched
        assert mock_ctx_source.search.call_count >= 1
        assert result.goto == "hypothesis_generation"

    def test_enrichment_skips_log_search_without_time_window(self):
        """No log searches when time window is not available."""
        mock_ctx_source = MagicMock()
        mock_ctx_source.search.return_value = []

        state = {
            "scenario_name": "test-scenario",
            "enriched_context": "# Current Incident\n\nTest\n\n",
            "incident_details": None,
            "time_window_start": None,
            "time_window_end": None,
        }

        with (
            patch("rca_agent.create_context_source", return_value=mock_ctx_source),
            patch("rca_agent.create_log_search_source") as mock_log_factory,
        ):
            result = asyncio.run(context_enrichment(state))

        # Log search source should never be created
        mock_log_factory.assert_not_called()
        assert result.goto == "hypothesis_generation"

    def test_enrichment_probes_logs_with_time_window(self):
        """Log searches are executed when time window is available."""
        mock_ctx_source = MagicMock()
        mock_ctx_source.search.return_value = []

        mock_log_search = MagicMock()
        mock_log_search.search.return_value = "Found 3 logs matching 'deploy'"

        state = {
            "scenario_name": "test-scenario",
            "enriched_context": "# Current Incident\n\nTest\n\n",
            "incident_details": None,
            "time_window_start": "2024-03-15T14:00:00",
            "time_window_end": "2024-03-15T14:30:00",
        }

        with (
            patch("rca_agent.create_context_source", return_value=mock_ctx_source),
            patch(
                "rca_agent.create_log_search_source",
                return_value=mock_log_search,
            ),
        ):
            result = asyncio.run(context_enrichment(state))

        # Log search should have been called for probe terms
        assert mock_log_search.search.call_count > 0
        mock_log_search.set_scenario.assert_called_once_with("test-scenario")
        assert result.goto == "hypothesis_generation"

    def test_enrichment_routes_to_hypothesis_generation(self):
        """The node always routes to hypothesis_generation."""
        mock_ctx_source = MagicMock()
        mock_ctx_source.search.return_value = []

        state = {
            "scenario_name": "test",
            "enriched_context": "",
            "incident_details": None,
            "time_window_start": None,
            "time_window_end": None,
        }

        with patch("rca_agent.create_context_source", return_value=mock_ctx_source):
            result = asyncio.run(context_enrichment(state))

        assert result.goto == "hypothesis_generation"
        assert "context" in result.update
        assert "enriched_context" in result.update

    def test_build_context_queries_with_details(self):
        """_build_context_queries produces targeted queries from incident details."""
        from rca_agent import _build_context_queries, IncidentDetails

        details = IncidentDetails(
            incident_time="2024-03-15T10:00:00",
            time_window_start="2024-03-15T09:45:00",
            time_window_end="2024-03-15T10:15:00",
            affected_services=["redis", "api-gateway"],
            symptoms=["high latency", "connection timeouts"],
            summary="Redis causing latency spikes",
        )
        queries = _build_context_queries(details, "test-scenario")
        assert len(queries) >= 2
        # Should include service-focused and symptom-focused queries
        assert any("redis" in q for q in queries)
        assert any("latency" in q or "timeout" in q for q in queries)

    def test_build_context_queries_fallback(self):
        """_build_context_queries falls back to scenario name when details are empty."""
        from rca_agent import _build_context_queries

        queries = _build_context_queries(None, "volte-call-drop")
        assert len(queries) >= 1
        assert any("volte-call-drop" in q for q in queries)

    def test_infer_time_window_various_formats(self):
        """_infer_time_window parses freeform and ISO date strings."""
        from rca_agent import _infer_time_window

        # Freeform: "Around March 18, 2026"
        result = _infer_time_window("Around March 18, 2026")
        assert result is not None
        start, end = result
        assert "2026-03-17" in start
        assert "2026-03-19" in end

        # ISO format
        result = _infer_time_window("2026-03-18")
        assert result is not None

        # None returns None
        assert _infer_time_window(None) is None

        # Unparseable returns None
        assert _infer_time_window("no date here at all") is None

    def test_enrichment_infers_time_window_from_incident_time(self):
        """Log probes execute when time window is inferred from incident_time."""
        from rca_agent import IncidentDetails

        mock_ctx_source = MagicMock()
        mock_ctx_source.search.return_value = []

        mock_log_search = MagicMock()
        mock_log_search.search.return_value = "Found 2 logs matching 'deploy'"

        details = IncidentDetails(
            incident_time="Around March 18, 2026",
            time_window_start=None,
            time_window_end=None,
            affected_services=["defect-classifier"],
            symptoms=["complaint spike"],
            summary="Test",
        )

        state = {
            "scenario_name": "test-scenario",
            "enriched_context": "# Current Incident\n\nTest\n\n",
            "incident_details": details,
            "time_window_start": None,
            "time_window_end": None,
        }

        with (
            patch("rca_agent.create_context_source", return_value=mock_ctx_source),
            patch(
                "rca_agent.create_log_search_source",
                return_value=mock_log_search,
            ),
        ):
            result = asyncio.run(context_enrichment(state))

        # Log search SHOULD have been called (inferred window)
        assert mock_log_search.search.call_count > 0
        mock_log_search.set_scenario.assert_called_once_with("test-scenario")
        assert result.goto == "hypothesis_generation"
        # Inferred window must be propagated to state for downstream workers
        assert result.update.get("time_window_start") is not None
        assert result.update.get("time_window_end") is not None
        assert "2026-03-17" in result.update["time_window_start"]
        assert "2026-03-19" in result.update["time_window_end"]


# ---------------------------------------------------------------------------
# Tests: LocalContextSource
# ---------------------------------------------------------------------------


class TestLocalContextSource:
    """Test the file-based context source for local dev without Bedrock KB."""

    def test_search_returns_relevant_chunks(self, tmp_path):
        """LocalContextSource returns chunks matching query keywords."""
        from data_source_factory import LocalContextSource

        # Create a fake scenario with context files
        ctx_dir = tmp_path / "test-scenario" / "context"
        ctx_dir.mkdir(parents=True)
        (ctx_dir / "runbooks.md").write_text(
            "Check redis connection pool settings\n\n"
            "This runbook covers timeout diagnostics for the API gateway\n\n"
            "Unrelated topic about billing reports"
        )
        (ctx_dir / "past_incidents.md").write_text(
            "Past incident: redis latency spike caused by connection exhaustion"
        )

        source = LocalContextSource(tmp_path)
        results = source.search("redis timeout", scenario_name="test-scenario")

        assert len(results) >= 1
        assert any("redis" in r.lower() for r in results)

    def test_search_no_scenario_returns_empty(self, tmp_path):
        from data_source_factory import LocalContextSource

        source = LocalContextSource(tmp_path)
        assert source.search("redis", scenario_name=None) == []

    def test_search_missing_scenario_returns_empty(self, tmp_path):
        from data_source_factory import LocalContextSource

        source = LocalContextSource(tmp_path)
        assert source.search("redis", scenario_name="nonexistent") == []

    def test_search_no_match_returns_empty(self, tmp_path):
        from data_source_factory import LocalContextSource

        ctx_dir = tmp_path / "test-scenario" / "context"
        ctx_dir.mkdir(parents=True)
        (ctx_dir / "runbooks.md").write_text("Nothing relevant here")

        source = LocalContextSource(tmp_path)
        results = source.search("xyzzy_nonexistent_term", scenario_name="test-scenario")
        assert results == []

    def test_enrichment_uses_local_fallback_when_kb_unavailable(self):
        """Context enrichment uses LocalContextSource when KB is unavailable."""
        from data_source_factory import LocalContextSource

        mock_local = MagicMock(spec=LocalContextSource)
        mock_local.search.return_value = ["Runbook: check thermal management"]

        state = {
            "scenario_name": "care-transcript-supply-chain",
            "enriched_context": "# Current Incident\n\nTest\n\n",
            "incident_details": None,
            "time_window_start": None,
            "time_window_end": None,
        }

        with patch("rca_agent.create_context_source", return_value=mock_local):
            result = asyncio.run(context_enrichment(state))

        enriched = result.update["enriched_context"]
        assert "thermal management" in enriched
        assert mock_local.search.call_count >= 1


# ---------------------------------------------------------------------------
# Tests: selective hypothesis investigation
# ---------------------------------------------------------------------------


class TestSelectiveInvestigation:
    """Test that spawn_investigators respects selected_hypotheses."""

    def _make_state(self, num_hypotheses=3, selected=None):
        hypotheses = {}
        for i in range(1, num_hypotheses + 1):
            hypotheses[i] = Hypothesis(
                service=f"service-{i}",
                description=f"Hypothesis {i}",
                search_terms=[f"term-{i}"],
                rationale=f"Rationale {i}",
            )
        return {
            "current_hypotheses": Hypotheses(hypotheses=hypotheses),
            "scenario_name": "test-scenario",
            "time_window_start": None,
            "time_window_end": None,
            "selected_hypotheses": selected,
        }

    def test_all_hypotheses_when_none_selected(self):
        """When selected_hypotheses is None, all hypotheses are spawned."""
        state = self._make_state(num_hypotheses=3, selected=None)
        sends = spawn_investigators(state)
        assert len(sends) == 3

    def test_subset_when_selected(self):
        """Only selected hypotheses are spawned."""
        state = self._make_state(num_hypotheses=4, selected=[1, 3])
        sends = spawn_investigators(state)
        assert len(sends) == 2
        worker_ids = [s.arg["worker_id"] for s in sends]
        assert "investigator-1" in worker_ids
        assert "investigator-3" in worker_ids
        assert "investigator-2" not in worker_ids
        assert "investigator-4" not in worker_ids

    def test_single_selection(self):
        """Selecting a single hypothesis works."""
        state = self._make_state(num_hypotheses=3, selected=[2])
        sends = spawn_investigators(state)
        assert len(sends) == 1
        assert sends[0].arg["worker_id"] == "investigator-2"
        assert sends[0].arg["hypothesis"].service == "service-2"

    def test_empty_selection_spawns_nothing(self):
        """Empty selection list spawns no investigators."""
        state = self._make_state(num_hypotheses=3, selected=[])
        sends = spawn_investigators(state)
        assert len(sends) == 0
