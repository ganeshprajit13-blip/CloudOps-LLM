from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_get_root():
    """Test GET / endpoint returns 200 OK and expected structure."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data
    assert data["message"] == "CloudOps LLM backend is running"
    assert data["version"] == "0.1.0"


def test_get_health():
    """Test GET /health endpoint returns 200 OK and expected health payload."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "service" in data
    assert "version" in data
    assert data["status"] == "healthy"
    assert data["service"] == "cloudops-backend"
    assert data["version"] == "0.1.0"
