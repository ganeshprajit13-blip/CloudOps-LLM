import sys
from pathlib import Path

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
from app.services.cloudops_analyzer import CloudOpsAnalyzer

def mock_end_to_end_rag(query: str):
    class RAGResult:
        results = [
            type("Chunk", (), {
                "text": "Security groups control inbound traffic to EC2 instances. HTTPS applications require TCP port 443 inbound permission.",
                "score": 0.89,
                "metadata": {
                    "source": "aws_security_group_troubleshooting.md",
                    "title": "Security Group Guide",
                    "service": "security_group"
                }
            })()
        ]
    return RAGResult()

def mock_end_to_end_llm(question: str, cloud_context: dict, prompt_text: str):
    return {
        "problem": "Website is unreachable over HTTPS.",
        "probable_root_cause": "Security Group sg-web-01 does not permit inbound TCP port 443 traffic.",
        "evidence": [
            "EC2 instance i-0abc12345 is running.",
            "CPU utilization is normal (35%).",
            "Security Group sg-web-01 inbound rules allow port 80 but lack port 443.",
            "Retrieved operational knowledge confirms port 443 requirement for HTTPS."
        ],
        "impact": "External HTTPS requests time out before reaching the web server.",
        "recommendation": "Review Security Group sg-web-01 inbound rules and add permission for TCP port 443.",
        "confidence": 0.93
    }

def test_phase7b_full_end_to_end_integration():
    # Instantiate analyzer with mocked RAG and LLM components
    end_to_end_analyzer = CloudOpsAnalyzer(
        model_runner=mock_end_to_end_llm,
        rag_query_fn=mock_end_to_end_rag
    )

    # Synthetic cloud context matching real Phase 3 schema
    synthetic_context = {
        "summary": {
            "total_instances": 1,
            "running_instances": 1,
            "high_cpu_instances": 0,
            "unhealthy_targets": 0
        },
        "resources": {
            "ec2": [
                {
                    "instance_id": "i-0abc12345",
                    "state": "running",
                    "instance_type": "t3.medium",
                    "public_ip": "54.100.20.5",
                    "private_ip": "10.0.1.15",
                    "subnet_id": "subnet-public-1a",
                    "security_group_ids": ["sg-web-01"]
                }
            ],
            "security_groups": [
                {
                    "group_id": "sg-web-01",
                    "name": "web-sg",
                    "inbound_rules": [
                        {"protocol": "tcp", "from_port": 80, "to_port": 80, "sources": ["0.0.0.0/0"]}
                    ]
                }
            ]
        },
        "metrics": [
            {
                "metric_name": "CPUUtilization",
                "resource_id": "i-0abc12345",
                "value": 35.0,
                "unit": "Percent"
            }
        ],
        "signals": [
            {
                "type": "port_not_allowed",
                "severity": "high",
                "resource_id": "i-0abc12345",
                "description": "TCP port 443 (HTTPS) inbound is not allowed by Security Group sg-web-01."
            }
        ]
    }

    # Override dependency in FastAPI app
    app.dependency_overrides[get_analyzer_service] = lambda: end_to_end_analyzer

    try:
        test_client = TestClient(app)

        # 1. Test GET / root endpoint
        root_res = test_client.get("/")
        assert root_res.status_code == 200
        assert "CloudOps LLM backend is running" in root_res.json()["message"]

        # 2. Test GET /health endpoint
        health_res = test_client.get("/health")
        assert health_res.status_code == 200
        assert health_res.json()["status"] == "healthy"

        # 3. Test POST /api/analyze endpoint with full payload
        res = test_client.post(
            "/api/analyze",
            json={
                "question": "Why is my website unreachable?",
                "resource_id": "i-0abc12345",
                "cloud_context": synthetic_context,
                "collect_live_data": False
            }
        )

        assert res.status_code == 200
        diagnosis = res.json()

        # Validate schema compliance
        assert "problem" in diagnosis
        assert "probable_root_cause" in diagnosis
        assert "evidence" in diagnosis
        assert "impact" in diagnosis
        assert "recommendation" in diagnosis
        assert "confidence" in diagnosis

        # Validate values
        assert diagnosis["confidence"] == 0.93
        assert "Security Group sg-web-01" in diagnosis["probable_root_cause"]
        assert len(diagnosis["evidence"]) == 4

    finally:
        app.dependency_overrides.clear()
