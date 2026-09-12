import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pytest
from app.schemas.analysis import AnalysisResponse
from app.services.cloudops_analyzer import CloudOpsAnalyzer

def synthetic_rag_provider(query: str):
    class SyntheticRAGResult:
        results = [
            type("Chunk", (), {
                "text": "Security Groups control inbound traffic to EC2 instances. For HTTPS applications, verify that an inbound TCP 443 rule exists for the appropriate source CIDR.",
                "score": 0.88,
                "metadata": {
                    "source": "aws_security_group_troubleshooting.md",
                    "title": "Security Group Troubleshooting",
                    "service": "security_group",
                    "document_type": "documentation"
                }
            })()
        ]
    return SyntheticRAGResult()

def synthetic_llm_runner(question: str, cloud_context: dict, prompt_text: str):
    # Verify that the complete prompt received both cloud context AND RAG knowledge
    assert "=== CURRENT CLOUD STATE ===" in prompt_text
    assert "RETRIEVED KNOWLEDGE" in prompt_text
    assert "aws_security_group_troubleshooting.md" in prompt_text
    assert "TCP 443" in prompt_text

    return {
        "problem": "Website is unreachable over HTTPS.",
        "probable_root_cause": "Inbound TCP port 443 is blocked by active Security Group rules on the target EC2 instance.",
        "evidence": [
            "EC2 instance state is running.",
            "CPU utilization is normal (35%).",
            "Application process state is running.",
            "Security Group inbound rules do not allow TCP port 443 traffic.",
            "RAG operational knowledge confirms HTTPS requires inbound TCP 443 rule."
        ],
        "impact": "External client requests to port 443 time out, causing site unreachability.",
        "recommendation": "Review Security Group inbound rules for port 443 and authorize TCP 443 traffic from approved client sources.",
        "confidence": 0.92
    }

def test_phase7a_synthetic_end_to_end():
    # Synthetic cloud context matching prompt specification
    synthetic_cloud_context = {
        "summary": {
            "total_instances": 1,
            "running_instances": 1,
            "high_cpu_instances": 0,
            "unhealthy_targets": 0
        },
        "resources": {
            "ec2": [
                {
                    "instance_id": "i-0abc123456789def0",
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
                "resource_id": "i-0abc123456789def0",
                "value": 35.0,
                "unit": "Percent"
            }
        ],
        "signals": [
            {
                "type": "port_not_allowed",
                "severity": "high",
                "resource_id": "i-0abc123456789def0",
                "description": "TCP port 443 (HTTPS) inbound is not allowed by Security Group sg-web-01."
            }
        ]
    }

    analyzer = CloudOpsAnalyzer(
        model_runner=synthetic_llm_runner,
        rag_query_fn=synthetic_rag_provider
    )

    response = analyzer.analyze(
        question="Why is my website unreachable?",
        cloud_context=synthetic_cloud_context,
        resource_id="i-0abc123456789def0",
        collect_live_data=False
    )

    assert isinstance(response, AnalysisResponse)
    assert response.query == "Why is my website unreachable?"
    assert response.diagnosis.confidence == 0.92
    assert "Inbound TCP port 443" in response.diagnosis.probable_root_cause
    assert len(response.diagnosis.evidence) == 5
    assert len(response.retrieved_knowledge) == 1
    assert response.retrieved_knowledge[0].source == "aws_security_group_troubleshooting.md"
    assert response.execution_time_seconds is not None
