import json
import pytest
from app.services.cloudops_analyzer import CloudOpsAnalyzer
from app.services.context_builder import ContextBuilder
from app.services.diagnosis_validator import DiagnosisValidator
from app.services.preprocessing import preprocess_cloud_context


@pytest.fixture
def controlled_w3svc_failure_raw_data():
    """Controlled failure scenario: EC2 running, SG port 80 open, W3SVC service stopped."""
    return {
        "region": "eu-north-1",
        "timestamp": "2026-09-12T15:00:00+00:00",
        "ec2": [
            {
                "instance_id": "i-07243bdf548e18f5b",
                "state": "running",
                "instance_type": "t3.medium",
                "private_ip": "172.31.20.10",
                "public_ip": "13.51.100.50",
                "availability_zone": "eu-north-1b",
                "subnet_id": "subnet-0123456789abcdef0",
                "vpc_id": "vpc-0123456789abcdef0",
                "security_group_ids": ["sg-0b5463631438f138c"],
                "tags": {"Name": "CloudOps-Test-Server"},
            }
        ],
        "host_telemetry": [
            {
                "instance_id": "i-07243bdf548e18f5b",
                "platform": "windows",
                "collection_method": "ssm_run_command",
                "services": [
                    {
                        "name": "W3SVC",
                        "display_name": "World Wide Web Publishing Service",
                        "status": "Stopped",
                        "start_type": "Automatic",
                    },
                    {
                        "name": "WAS",
                        "display_name": "Windows Process Activation Service",
                        "status": "Running",
                        "start_type": "Automatic",
                    },
                ],
                "listening_ports": [
                    {"port": 22, "local_address": "0.0.0.0", "state": "Listen", "owning_process": 4},
                    {"port": 3389, "local_address": "0.0.0.0", "state": "Listen", "owning_process": 1200},
                ],
                "system_info": {
                    "os_name": "Microsoft Windows Server 2022 Datacenter",
                    "os_version": "10.0.20348",
                    "last_boot_time": "2026-09-12T08:00:00+00:00",
                    "total_memory_kb": 4193808,
                    "free_memory_kb": 2540000,
                },
                "error": None,
            }
        ],
        "security_groups": [
            {
                "group_id": "sg-0b5463631438f138c",
                "name": "cloudops-test-web-sg",
                "vpc_id": "vpc-0123456789abcdef0",
                "inbound_rules": [
                    {"protocol": "tcp", "from_port": 80, "to_port": 80, "sources": ["0.0.0.0/0"]},
                    {"protocol": "tcp", "from_port": 3389, "to_port": 3389, "sources": ["0.0.0.0/0"]},
                ],
            }
        ],
        "cloudwatch": [
            {"metric_name": "CPUUtilization", "resource_id": "i-07243bdf548e18f5b", "average": 4.5, "maximum": 8.0, "unit": "Percent"}
        ],
        "cloudtrail": [],
        "vpc": {},
        "load_balancers": [],
    }


def test_controlled_w3svc_failure_telemetry_and_evidence(controlled_w3svc_failure_raw_data):
    """Verifies that W3SVC=Stopped telemetry is collected, normalized, and yields factual evidence."""
    context = preprocess_cloud_context(controlled_w3svc_failure_raw_data)

    # 1. Verify Host Telemetry in Resources
    hosts = context["resources"]["host_telemetry"]
    assert len(hosts) == 1
    assert hosts[0]["instance_id"] == "i-07243bdf548e18f5b"
    assert hosts[0]["services"][0]["name"] == "W3SVC"
    assert hosts[0]["services"][0]["status"] == "Stopped"

    # 2. Verify win32_service and process_status exist for grounding checks
    assert "win32_service" in hosts[0]
    assert hosts[0]["win32_service"][0]["name"] == "W3SVC"
    assert hosts[0]["win32_service"][0]["status"] == "Stopped"

    # 3. Verify Detected Signals
    signals = context["signals"]
    svc_signals = [s for s in signals if s["type"] == "windows_service_stopped"]
    assert len(svc_signals) == 1
    assert svc_signals[0]["severity"] == "high"
    assert svc_signals[0]["resource_id"] == "i-07243bdf548e18f5b"
    assert "W3SVC" in svc_signals[0]["description"]
    assert "Stopped" in svc_signals[0]["description"]

    # 4. Verify Factual Evidence Statements
    evidence = context["evidence"]
    assert len(evidence) >= 2
    evidence_str = " ".join(evidence)
    assert "W3SVC" in evidence_str
    assert "Stopped" in evidence_str
    assert "World Wide Web Publishing Service (W3SVC / IIS) is not running" in evidence_str

    # 5. Verify Formatted Context Section
    context_builder = ContextBuilder()
    formatted_text = context_builder.build_context_text(context, resource_id="i-07243bdf548e18f5b")
    assert "=== HOST-LEVEL & OS SERVICE TELEMETRY ===" in formatted_text
    assert "W3SVC (World Wide Web Publishing Service): Status=Stopped" in formatted_text
    assert "i-07243bdf548e18f5b" in formatted_text


def test_controlled_w3svc_failure_grounding_validation(controlled_w3svc_failure_raw_data):
    """Verifies that DiagnosisValidator accepts IIS / W3SVC diagnosis when host telemetry is present."""
    context = preprocess_cloud_context(controlled_w3svc_failure_raw_data)
    validator = DiagnosisValidator()

    candidate_diagnosis = {
        "problem": "Cannot access IIS website on port 80 of instance i-07243bdf548e18f5b.",
        "probable_root_cause": "The World Wide Web Publishing Service (W3SVC) / IIS is stopped on host i-07243bdf548e18f5b.",
        "evidence": [
            "Host telemetry confirms Windows service 'W3SVC' is Stopped on EC2 instance i-07243bdf548e18f5b.",
            "Security Group sg-0b5463631438f138c permits inbound TCP port 80, but web service is not running."
        ],
        "impact": "HTTP web traffic on port 80 cannot be served by the stopped IIS web server.",
        "recommendation": "Start the W3SVC service on instance i-07243bdf548e18f5b via SSM Run Command or Windows Service Manager.",
        "confidence": 0.95
    }

    is_grounded, warnings = validator.check_evidence_grounding(
        diagnosis_data=candidate_diagnosis,
        cloud_context=context,
        rag_texts=["W3SVC manages the World Wide Web Publishing Service in IIS."]
    )

    assert is_grounded is True
    assert len(warnings) == 0


def test_cloudops_analyzer_controlled_failure_diagnosis(controlled_w3svc_failure_raw_data):
    """Verifies end-to-end analyzer with a mock model runner returning grounded W3SVC diagnosis."""
    context = preprocess_cloud_context(controlled_w3svc_failure_raw_data)

    def mock_runner(question, cloud_ctx, prompt):
        return {
            "problem": "IIS web server is unreachable on HTTP port 80.",
            "probable_root_cause": "The World Wide Web Publishing Service (W3SVC) is in Stopped state on EC2 instance i-07243bdf548e18f5b.",
            "evidence": [
                "Host telemetry confirms Windows service 'W3SVC' (World Wide Web Publishing Service) status is Stopped on EC2 instance i-07243bdf548e18f5b.",
                "Security Group sg-0b5463631438f138c allows inbound TCP 80."
            ],
            "impact": "HTTP requests to port 80 fail to connect because IIS web service is down.",
            "recommendation": "Start the W3SVC service on the Windows EC2 host.",
            "confidence": 0.95
        }

    analyzer = CloudOpsAnalyzer(model_runner=mock_runner)
    resp = analyzer.analyze(
        question="Why can I not access my IIS website on HTTP port 80?",
        cloud_context=context,
        resource_id="i-07243bdf548e18f5b",
        collect_live_data=False
    )

    assert resp.error is None
    assert resp.diagnosis.confidence == 0.95
    assert "W3SVC" in resp.diagnosis.probable_root_cause
    assert len(resp.diagnosis.evidence) >= 2
    assert "W3SVC" in resp.diagnosis.evidence[0]
    assert resp.diagnosis.evidence[0] != "Insufficient evidence"
