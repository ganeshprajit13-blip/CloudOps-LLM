import sys
from pathlib import Path
from unittest.mock import MagicMock

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pytest
from app.schemas.analysis import AnalysisResponse, RetrievedKnowledgeItem
from app.services.cloudops_analyzer import CloudOpsAnalyzer

@pytest.fixture
def mock_cloud_context():
    return {
        "summary": {"total_instances": 1, "running_instances": 1},
        "resources": {
            "ec2": [{"instance_id": "i-0123456789", "state": "running"}],
            "security_groups": [{"group_id": "sg-0001", "name": "web"}]
        },
        "signals": [{"type": "port_not_allowed", "severity": "high", "resource_id": "i-0123456789"}]
    }

def mock_rag_query(query: str):
    class MockRAGResponse:
        results = [
            type("Item", (), {
                "text": "Security Groups filter inbound traffic. Verify port 443 rule.",
                "score": 0.82,
                "metadata": {"source": "sg_guide.md", "title": "SG Guide", "service": "security_group"}
            })()
        ]
    return MockRAGResponse()

def mock_model_runner(question, cloud_context, prompt_text):
    return {
        "problem": "Website unreachable over HTTPS.",
        "probable_root_cause": "Inbound TCP port 443 rule missing from Security Group sg-0001.",
        "evidence": ["Security Group sg-0001 inbound rules lack port 443 permission."],
        "impact": "Clients connection times out.",
        "recommendation": "Add inbound rule for TCP port 443.",
        "confidence": 0.90
    }

def test_cloudops_analyzer_full_flow(mock_cloud_context):
    analyzer = CloudOpsAnalyzer(
        model_runner=mock_model_runner,
        rag_query_fn=mock_rag_query
    )

    response = analyzer.analyze(
        question="Why is my website unreachable?",
        cloud_context=mock_cloud_context,
        resource_id="i-0123456789",
        collect_live_data=False
    )

    assert isinstance(response, AnalysisResponse)
    assert response.query == "Why is my website unreachable?"
    assert response.diagnosis.confidence == 0.90
    assert "Inbound TCP port 443" in response.diagnosis.probable_root_cause
    assert len(response.retrieved_knowledge) == 1
    assert response.retrieved_knowledge[0].source == "sg_guide.md"


def test_cloudops_analyzer_rag_failure_fallback(mock_cloud_context):
    def failing_rag(query):
        raise RuntimeError("RAG DB connection error")

    analyzer = CloudOpsAnalyzer(
        model_runner=mock_model_runner,
        rag_query_fn=failing_rag
    )

    response = analyzer.analyze(
        question="Why is my website unreachable?",
        cloud_context=mock_cloud_context,
        collect_live_data=False
    )

    assert isinstance(response, AnalysisResponse)
    assert response.diagnosis.confidence > 0.0
    assert len(response.retrieved_knowledge) == 0


def test_cloudops_analyzer_empty_query():
    analyzer = CloudOpsAnalyzer()
    response = analyzer.analyze(question="   ", collect_live_data=False)

    assert response.error == "EMPTY_QUERY"
    assert response.diagnosis.confidence == 0.20
