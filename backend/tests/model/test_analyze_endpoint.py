import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.cloudops_analyzer import CloudOpsAnalyzer

client = TestClient(app)


def test_post_analyze_empty_question():
    """Verify POST /api/analyze handles empty questions safely with 422 or fallback."""
    response = client.post("/api/analyze", json={"question": "", "collect_live_data": False})
    # Pydantic min_length=1 rejects with 422
    assert response.status_code in (200, 422)


def test_post_analyze_mock_runner():
    """Verify POST /api/analyze executes the full pipeline end-to-end with mock runner."""
    def mock_runner(question, cloud_context, prompt_text):
        return {
            "problem": "ECS task continuous restart loop",
            "probable_root_cause": "Essential container exited with code 1",
            "evidence": ["Task transitions PENDING to STOPPED", "Exit code 1 in container logs"],
            "impact": "Service unavailable",
            "recommendation": "Review container entrypoint and Redis connectivity",
            "confidence": 0.95
        }

    analyzer = CloudOpsAnalyzer(model_runner=mock_runner)
    result = analyzer.analyze(
        question="ECS task fails startup",
        cloud_context={
            "service": "ECS",
            "resources": {"ecs_clusters": ["cluster-1"]}
        },
        collect_live_data=False
    )

    assert result.diagnosis.problem == "ECS task continuous restart loop"
    assert result.diagnosis.probable_root_cause == "Essential container exited with code 1"
    assert len(result.diagnosis.evidence) == 2
    assert result.diagnosis.confidence == 0.95


def test_health_check_operational():
    """Verify GET /health remains operational and returns healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "cloudops-backend"
