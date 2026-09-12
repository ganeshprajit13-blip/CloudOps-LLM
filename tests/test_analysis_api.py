import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
BACKEND_DIR = BASE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.api.routes.analysis import get_analyzer_service
from app.schemas.analysis import AnalysisResponse, DiagnosisSchema, RetrievedKnowledgeItem

client = TestClient(app)

@pytest.fixture
def mock_analyzer_service():
    mock_analyzer = MagicMock()

    def mock_analyze(question, cloud_context=None, resource_id=None, collect_live_data=True):
        if not question or not question.strip():
            return AnalysisResponse(
                query=question or "",
                diagnosis=DiagnosisSchema(
                    problem="[Empty Query]",
                    probable_root_cause="Insufficient evidence due to empty query string.",
                    evidence=[],
                    impact="Uncertain",
                    recommendation="Provide a valid query.",
                    confidence=0.20
                ),
                error="EMPTY_QUERY"
            )

        return AnalysisResponse(
            query=question,
            diagnosis=DiagnosisSchema(
                problem="Website is unreachable over HTTPS.",
                probable_root_cause="Security Group sg-01234 lacks inbound TCP port 443 rule.",
                evidence=["Security Group sg-01234 lacks port 443 rule.", "EC2 instance state is running."],
                impact="External client connections time out.",
                recommendation="Review Security Group sg-01234 rules and authorize inbound TCP port 443.",
                confidence=0.91
            ),
            retrieved_knowledge=[
                RetrievedKnowledgeItem(
                    source="sg_guide.md",
                    title="SG Guide",
                    service="security_group",
                    score=0.85,
                    text="Verify inbound TCP 443 rule exists."
                )
            ]
        )

    mock_analyzer.analyze.side_effect = mock_analyze
    return mock_analyzer


def test_analyze_api_valid_request(mock_analyzer_service):
    app.dependency_overrides[get_analyzer_service] = lambda: mock_analyzer_service
    try:
        response = client.post(
            "/api/analyze",
            json={
                "question": "Why is my website unreachable?",
                "resource_id": "i-0123456789",
                "collect_live_data": False
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "problem" in data
        assert "probable_root_cause" in data
        assert "evidence" in data
        assert "impact" in data
        assert "recommendation" in data
        assert "confidence" in data
        assert data["confidence"] == 0.91
        assert "Security Group sg-01234" in data["probable_root_cause"]
    finally:
        app.dependency_overrides.clear()


def test_analyze_api_empty_question(mock_analyzer_service):
    app.dependency_overrides[get_analyzer_service] = lambda: mock_analyzer_service
    try:
        response = client.post(
            "/api/analyze",
            json={"question": "   ", "collect_live_data": False}
        )
        assert response.status_code == 400
        assert "INVALID_REQUEST" in response.text or "detail" in response.json()
    finally:
        app.dependency_overrides.clear()


def test_analyze_api_missing_question():
    response = client.post("/api/analyze", json={})
    assert response.status_code == 422


def test_analyze_api_model_unavailable():
    failing_analyzer = MagicMock()
    failing_analyzer.analyze.side_effect = RuntimeError("Model generation process crashed")

    app.dependency_overrides[get_analyzer_service] = lambda: failing_analyzer
    try:
        response = client.post(
            "/api/analyze",
            json={"question": "Why is CPU high?"}
        )
        assert response.status_code == 503
        data = response.json()
        assert "MODEL_UNAVAILABLE" in data["detail"]["error"]
    finally:
        app.dependency_overrides.clear()
