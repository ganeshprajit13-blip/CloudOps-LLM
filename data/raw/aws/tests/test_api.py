"""Tests for FastAPI API endpoints.

Tests all REST endpoints and SSE streaming, using mocked LangGraph graph
so no real LLM calls are made.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Patch heavy imports before loading api module
# ---------------------------------------------------------------------------

# We need to mock the graph construction that happens at module level in api.py.
# Patch build_orchestrator_graph and create_checkpointer before importing api.
_mock_graph = MagicMock()
_mock_graph.get_state.return_value = MagicMock(
    next=None, values={"synthesized_report": "Test report"}
)
_mock_graph.aget_state = AsyncMock(return_value=MagicMock(next=None, values={}))


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
# Tests: Health endpoint
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Tests: Scenarios endpoints
# ---------------------------------------------------------------------------


class TestScenariosEndpoints:
    def test_list_scenarios(self, client):
        """GET /api/scenarios returns a list of scenarios."""
        response = client.get("/api/scenarios")
        assert response.status_code == 200
        data = response.json()
        assert "scenarios" in data
        assert isinstance(data["scenarios"], list)
        # At least one scenario should exist
        assert len(data["scenarios"]) > 0

    def test_list_scenarios_have_required_fields(self, client):
        """Each scenario has name, description, has_hitl fields."""
        response = client.get("/api/scenarios")
        for s in response.json()["scenarios"]:
            assert "name" in s
            assert "description" in s
            assert "has_hitl" in s

    def test_get_scenario(self, client):
        """GET /api/scenarios/{name} returns incident text."""
        # Use a scenario we know exists
        scenarios = client.get("/api/scenarios").json()["scenarios"]
        if not scenarios:
            pytest.skip("No scenarios available")

        name = scenarios[0]["name"]
        response = client.get(f"/api/scenarios/{name}")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "incident" in data
        assert len(data["incident"]) > 0

    def test_get_scenario_not_found(self, client):
        """GET /api/scenarios/{name} returns 404 for unknown scenario."""
        response = client.get("/api/scenarios/nonexistent-scenario-xyz")
        assert response.status_code == 404

    def test_get_scenario_docs(self, client):
        """GET /api/scenarios/{name}/docs returns all documentation files."""
        scenarios = client.get("/api/scenarios").json()["scenarios"]
        if not scenarios:
            pytest.skip("No scenarios available")

        name = scenarios[0]["name"]
        response = client.get(f"/api/scenarios/{name}/docs")
        assert response.status_code == 200
        data = response.json()
        assert "incident" in data
        assert "context" in data
        assert "evidence" in data

    def test_get_scenario_docs_not_found(self, client):
        """GET /api/scenarios/{name}/docs returns 404 for unknown scenario."""
        response = client.get("/api/scenarios/nonexistent-scenario-xyz/docs")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests: Investigations endpoints
# ---------------------------------------------------------------------------


class TestInvestigationsEndpoints:
    def test_create_investigation_with_scenario(self, client):
        """POST /api/investigations with scenario_name returns investigation_id."""
        scenarios = client.get("/api/scenarios").json()["scenarios"]
        if not scenarios:
            pytest.skip("No scenarios available")

        name = scenarios[0]["name"]
        response = client.post("/api/investigations", json={"scenario_name": name})
        assert response.status_code == 200
        data = response.json()
        assert "investigation_id" in data
        assert len(data["investigation_id"]) > 0

    def test_create_investigation_with_text(self, client):
        """POST /api/investigations with incident_text returns investigation_id."""
        response = client.post(
            "/api/investigations",
            json={"incident_text": "Server is returning 500 errors"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "investigation_id" in data

    def test_create_investigation_scenario_with_text_uses_only_text(self, client):
        """When both scenario_name and incident_text are provided, only incident_text is used.

        This ensures the HITL clarification flow works: incident.md contains
        dates that would bypass clarification, so the user's vague text must
        be used exclusively as the incident.
        """
        scenarios = client.get("/api/scenarios").json()["scenarios"]
        if not scenarios:
            pytest.skip("No scenarios available")

        name = scenarios[0]["name"]
        user_text = "Things are broken but I don't know when it started"
        response = client.post(
            "/api/investigations",
            json={"scenario_name": name, "incident_text": user_text},
        )
        assert response.status_code == 200
        inv_id = response.json()["investigation_id"]

        from api import _investigations

        inv = _investigations[inv_id]
        # incident should be ONLY the user text, not concatenated with incident.md
        assert inv.incident == user_text
        # scenario_name must still be preserved for evidence/context file lookups
        assert inv.scenario_name == name

    def test_create_investigation_no_input(self, client):
        """POST /api/investigations with neither scenario nor text returns 400."""
        response = client.post("/api/investigations", json={})
        assert response.status_code == 400

    def test_create_investigation_with_trajectory(self, client):
        """POST /api/investigations with include_trajectory creates TrajectoryCapture."""
        response = client.post(
            "/api/investigations",
            json={
                "incident_text": "Test incident",
                "include_trajectory": True,
            },
        )
        assert response.status_code == 200
        inv_id = response.json()["investigation_id"]

        # Verify trajectory was created by checking the internal state
        from api import _investigations

        assert inv_id in _investigations
        assert _investigations[inv_id].trajectory is not None

    def test_stream_not_found(self, client):
        """POST /api/investigations/{id}/stream returns 404 for unknown ID."""
        response = client.post("/api/investigations/nonexistent/stream", json={})
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests: Investigation state model
# ---------------------------------------------------------------------------


class TestInvestigationState:
    def test_defaults(self):
        """InvestigationState has correct defaults."""
        from api import InvestigationState

        inv = InvestigationState(
            id="test-1",
            scenario_name="test",
            incident="Test incident",
            thread_config={"configurable": {"thread_id": "t1"}},
        )
        assert inv.started is False
        assert inv.trajectory is None


# ---------------------------------------------------------------------------
# Tests: Request models
# ---------------------------------------------------------------------------


class TestRequestModels:
    def test_create_investigation_request_defaults(self):
        from api import CreateInvestigationRequest

        req = CreateInvestigationRequest()
        assert req.scenario_name is None
        assert req.incident_text is None
        assert req.include_trajectory is False

    def test_stream_request(self):
        from api import StreamRequest

        req = StreamRequest(message="Around 10am yesterday")
        assert req.message == "Around 10am yesterday"

    def test_stream_request_defaults(self):
        from api import StreamRequest

        req = StreamRequest()
        assert req.message is None
