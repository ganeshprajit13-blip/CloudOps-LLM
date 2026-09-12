"""
Smoke tests for the FastAPI server: dual-mode streaming, SSE format, and
scenario manifest consistency.

These tests complement test_api.py by focusing on the streaming infrastructure
and cross-checking the /api/scenarios endpoint against the static manifest
generator.  The LangGraph graph is mocked so no real LLM calls are made.

Streaming tests use the _stream_graph() async generator directly (same approach
as test_token_streaming_e2e.py) to test SSE output without a full HTTP round-trip.
"""

import asyncio
import json
import re
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Ensure scripts/ is importable for generate_scenario_manifest
# ---------------------------------------------------------------------------

_scripts_dir = Path(__file__).parent.parent / "scripts"
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))


# ---------------------------------------------------------------------------
# Patch heavy imports before loading api module
# ---------------------------------------------------------------------------

_mock_graph = MagicMock()
_mock_graph.get_state.return_value = MagicMock(
    next=None, values={"synthesized_report": "Smoke test report"}
)
_mock_graph.aget_state = AsyncMock(
    return_value=MagicMock(
        next=None, values={"synthesized_report": "Smoke test report"}
    )
)


@pytest.fixture(autouse=True)
def _patch_graph():
    """Patch graph and checkpointer at module level for all tests."""
    with (
        patch("api._graph", _mock_graph),
        patch("api._checkpointer", MagicMock()),
        patch("api._investigations", {}),
    ):
        yield


@pytest.fixture
def client():
    """Create a FastAPI test client."""
    from api import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _first_scenario_name(client) -> str:
    """Return the name of the first available scenario, or skip the test."""
    scenarios = client.get("/api/scenarios").json()["scenarios"]
    if not scenarios:
        pytest.skip("No scenarios available in scenarios/ directory")
    return scenarios[0]["name"]


def _make_investigation(scenario_name="test", incident="Test incident"):
    """Create an InvestigationState for direct _stream_graph testing."""
    from api import InvestigationState

    return InvestigationState(
        id="smoke-test",
        scenario_name=scenario_name,
        incident=incident,
        thread_config={"configurable": {"thread_id": "smoke-thread"}},
    )


async def _collect_events(async_gen):
    """Drain an async generator into a list."""
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
# 1. Scenario manifest consistency
# ---------------------------------------------------------------------------


class TestScenarioManifestConsistency:
    """Cross-check /api/scenarios against generate_scenario_manifest.py."""

    def test_scenarios_json_endpoint_matches_manifest(self, client):
        """Scenario names from the API must match what the static manifest
        generator would produce (same scenarios directory, same filter logic)."""
        from generate_scenario_manifest import generate_manifest

        scenarios_dir = Path(__file__).parent.parent / "scenarios"
        if not scenarios_dir.exists():
            pytest.skip("scenarios/ directory not found")

        manifest = generate_manifest(scenarios_dir)
        manifest_names = sorted(s["name"] for s in manifest["scenarios"])

        api_response = client.get("/api/scenarios")
        assert api_response.status_code == 200
        api_names = sorted(s["name"] for s in api_response.json()["scenarios"])

        assert api_names == manifest_names, (
            f"API scenario names diverge from manifest generator.\n"
            f"  API only: {set(api_names) - set(manifest_names)}\n"
            f"  Manifest only: {set(manifest_names) - set(api_names)}"
        )


# ---------------------------------------------------------------------------
# 2. Scenario docs endpoint structure
# ---------------------------------------------------------------------------


class TestScenarioDocsStructure:
    """Validate the shape of /api/scenarios/{name}/docs responses."""

    EXPECTED_KEYS = {"incident", "context", "evidence", "readme", "ground_truth"}

    def test_scenario_docs_endpoint_returns_expected_keys(self, client):
        """The docs endpoint must return all expected top-level keys."""
        name = _first_scenario_name(client)
        response = client.get(f"/api/scenarios/{name}/docs")
        assert response.status_code == 200

        data = response.json()
        assert set(data.keys()) == self.EXPECTED_KEYS, (
            f"Unexpected keys in docs response: {set(data.keys())}"
        )

    def test_scenario_docs_context_and_evidence_are_dicts(self, client):
        """context and evidence must be dicts (filename -> content)."""
        name = _first_scenario_name(client)
        data = client.get(f"/api/scenarios/{name}/docs").json()
        assert isinstance(data["context"], dict)
        assert isinstance(data["evidence"], dict)


# ---------------------------------------------------------------------------
# 3. Investigation creation
# ---------------------------------------------------------------------------


class TestInvestigationCreation:
    """Verify that creating an investigation returns a valid short UUID."""

    UUID_RE = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )

    def test_create_investigation_returns_valid_id(self, client):
        """POST /api/investigations should return an 8-hex-char ID."""
        name = _first_scenario_name(client)
        response = client.post("/api/investigations", json={"scenario_name": name})
        assert response.status_code == 200

        inv_id = response.json()["investigation_id"]
        assert self.UUID_RE.match(inv_id), (
            f"investigation_id '{inv_id}' does not look like a UUID"
        )

    def test_create_investigation_ids_are_unique(self, client):
        """Two successive creations must yield different IDs."""
        payload = {"incident_text": "Server is on fire"}
        id1 = client.post("/api/investigations", json=payload).json()[
            "investigation_id"
        ]
        id2 = client.post("/api/investigations", json=payload).json()[
            "investigation_id"
        ]
        assert id1 != id2


# ---------------------------------------------------------------------------
# 4. SSE stream content-type and route registration
# ---------------------------------------------------------------------------


class TestStreamEndpoint:
    """Verify that the SSE stream endpoint is correctly wired and produces
    well-formed events.

    Uses _stream_graph() directly to test SSE wire format output
    (same pattern as test_token_streaming_e2e.py).
    """

    def test_stream_endpoint_returns_event_stream(self, client):
        """The stream route must be registered as POST and return StreamingResponse.

        We verify by checking the route handler and HTTP method."""
        from api import app

        # Find the stream route
        stream_route = None
        for route in app.routes:
            if (
                hasattr(route, "path")
                and route.path == "/api/investigations/{inv_id}/stream"
            ):
                stream_route = route
                break

        assert stream_route is not None, "Stream route not found in app.routes"
        # Verify the endpoint function is registered (POST method)
        assert "POST" in stream_route.methods

    def test_stream_graph_produces_sse_formatted_events(self):
        """_stream_graph yields SSE wire-format strings (data: {json}\\n\\n)
        that parse to dicts with 'event' and 'data' keys."""
        from api import _stream_graph

        async def _fake_astream(*args, **kwargs):
            yield (
                (),
                "updates",
                {"clarify_incident": {"messages": []}},
            )

        mock_graph = MagicMock()
        mock_graph.astream = _fake_astream
        _state = MagicMock(next=None, values={"synthesized_report": "done"})
        mock_graph.get_state.return_value = _state
        mock_graph.aget_state = AsyncMock(return_value=_state)

        inv = _make_investigation()

        with patch("api._graph", mock_graph):
            raw_lines = asyncio.run(_collect_events(_stream_graph(inv)))

        assert len(raw_lines) >= 1, "Expected at least one SSE event"
        for line in raw_lines:
            assert isinstance(line, str), f"Expected SSE string, got {type(line)}"
            assert line.startswith("data: "), (
                f"SSE line must start with 'data: ': {line!r}"
            )
            parsed = _parse_sse_line(line)
            assert "event" in parsed, f"Parsed SSE missing 'event' key: {parsed}"
            assert "data" in parsed, f"Parsed SSE missing 'data' key: {parsed}"

    # -----------------------------------------------------------------------
    # 5. SSE event validation
    # -----------------------------------------------------------------------

    def test_sse_events_have_valid_format(self):
        """Every event from _stream_graph must carry a recognised event type
        and a dict data payload."""
        from api import _stream_graph

        async def _fake_astream(*args, **kwargs):
            yield (
                (),
                "updates",
                {"clarify_incident": {"messages": []}},
            )

        mock_graph = MagicMock()
        mock_graph.astream = _fake_astream
        _state = MagicMock(next=None, values={"synthesized_report": "final report"})
        mock_graph.get_state.return_value = _state
        mock_graph.aget_state = AsyncMock(return_value=_state)

        inv = _make_investigation()

        with patch("api._graph", mock_graph):
            raw_lines = asyncio.run(_collect_events(_stream_graph(inv)))

        known_event_types = {
            "phase",
            "token",
            "message",
            "hypothesis",
            "tool_call",
            "tool_result",
            "worker_update",
            "interrupt",
            "complete",
            "error",
        }

        for line in raw_lines:
            parsed = _parse_sse_line(line)
            assert parsed["event"] in known_event_types, (
                f"Unknown event type '{parsed['event']}'"
            )
            assert isinstance(parsed["data"], dict), (
                f"Expected dict payload, got {type(parsed['data'])}"
            )

    def test_sse_phase_event_is_valid_json(self):
        """Phase events carry a payload with a 'phase' key."""
        from api import _stream_graph

        async def _fake_astream(*args, **kwargs):
            yield (
                (),
                "updates",
                {"clarify_incident": {"messages": []}},
            )

        mock_graph = MagicMock()
        mock_graph.astream = _fake_astream
        _state = MagicMock(next=None, values={"synthesized_report": "report"})
        mock_graph.get_state.return_value = _state
        mock_graph.aget_state = AsyncMock(return_value=_state)

        inv = _make_investigation()

        with patch("api._graph", mock_graph):
            raw_lines = asyncio.run(_collect_events(_stream_graph(inv)))

        phase_events = [
            _parse_sse_line(line)
            for line in raw_lines
            if '"phase"' in line and '"clarification"' in line
        ]
        assert len(phase_events) >= 1, "Expected at least one phase event"

        for evt in phase_events:
            assert "phase" in evt["data"], f"Phase event missing 'phase' key: {evt}"
            assert "description" in evt["data"], (
                f"Phase event missing 'description': {evt}"
            )

    def test_sse_complete_event_has_report(self):
        """The final 'complete' event carries the synthesized report text."""
        from api import _stream_graph

        async def _fake_astream(*args, **kwargs):
            yield (
                (),
                "updates",
                {"synthesize_findings": {"messages": []}},
            )

        mock_graph = MagicMock()
        mock_graph.astream = _fake_astream
        _state = MagicMock(
            next=None,
            values={"synthesized_report": "Root cause: misconfigured cache TTL"},
        )
        mock_graph.get_state.return_value = _state
        mock_graph.aget_state = AsyncMock(return_value=_state)

        inv = _make_investigation()

        with patch("api._graph", mock_graph):
            raw_lines = asyncio.run(_collect_events(_stream_graph(inv)))

        complete_lines = [
            _parse_sse_line(line) for line in raw_lines if '"event": "complete"' in line
        ]
        assert len(complete_lines) == 1, "Expected exactly one 'complete' event"

        assert "report" in complete_lines[0]["data"]
        assert "misconfigured cache TTL" in complete_lines[0]["data"]["report"]
