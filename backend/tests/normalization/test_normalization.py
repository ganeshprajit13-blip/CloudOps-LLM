import json
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.services.evidence import generate_evidence_statements
from app.services.normalizer import (
    normalize_aws_data,
    normalize_cloudtrail_data,
    normalize_cloudwatch_data,
    normalize_ec2_data,
    normalize_host_telemetry,
    normalize_load_balancer_data,
    normalize_security_group_data,
    normalize_vpc_data,
)


from app.services.preprocessing import extract_signals, preprocess_cloud_context

client = TestClient(app)

# Load synthetic raw sample data
SAMPLE_RAW_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "examples" / "raw_aws_data.json"


def load_sample_raw_data():
    with open(SAMPLE_RAW_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def test_ec2_normalization():
    raw_data = load_sample_raw_data()
    normalized = normalize_ec2_data(raw_data["ec2"])
    assert len(normalized) == 1
    assert normalized[0]["instance_id"] == "i-0a1b2c3d4e5f67890"
    assert normalized[0]["state"] == "running"
    assert normalized[0]["tags"]["Name"] == "Production-WebServer-1"


def test_cloudwatch_normalization():
    raw_data = load_sample_raw_data()
    normalized = normalize_cloudwatch_data(raw_data["cloudwatch"])
    assert len(normalized) == 2
    assert normalized[0]["metric_name"] == "CPUUtilization"
    assert normalized[0]["value"] == 31.5


def test_cloudtrail_normalization():
    raw_data = load_sample_raw_data()
    normalized = normalize_cloudtrail_data(raw_data["cloudtrail"])
    assert len(normalized) == 1
    assert normalized[0]["event_name"] == "AuthorizeSecurityGroupIngress"
    assert normalized[0]["principal"] == "admin-devops"


def test_vpc_normalization():
    raw_data = load_sample_raw_data()
    normalized = normalize_vpc_data(raw_data["vpc"])
    assert len(normalized["vpcs"]) == 1
    assert normalized["vpcs"][0]["vpc_id"] == "vpc-0fe0dcba987654321"
    assert len(normalized["subnets"]) == 1
    assert len(normalized["route_tables"]) == 1
    assert len(normalized["internet_gateways"]) == 1


def test_security_group_normalization():
    raw_data = load_sample_raw_data()
    normalized = normalize_security_group_data(raw_data["security_groups"])
    assert len(normalized) == 1
    assert normalized[0]["group_id"] == "sg-0987654321fedcba0"
    assert len(normalized[0]["inbound_rules"]) == 1
    assert normalized[0]["inbound_rules"][0]["from_port"] == 80


def test_alb_normalization():
    raw_data = load_sample_raw_data()
    normalized = normalize_load_balancer_data(raw_data["load_balancers"])
    assert len(normalized) == 1
    assert normalized[0]["name"] == "prod-alb"
    assert len(normalized[0]["target_groups"][0]["unhealthy_targets"]) == 1
    assert normalized[0]["target_groups"][0]["unhealthy_targets"][0]["target_id"] == "i-0a1b2c3d4e5f67890"


def test_signal_extraction():
    raw_data = load_sample_raw_data()
    normalized = normalize_aws_data(raw_data)
    signals = extract_signals(normalized)

    signal_types = [s["type"] for s in signals]
    assert "port_not_allowed" in signal_types
    assert "unhealthy_load_balancer_target" in signal_types
    assert "recent_infrastructure_change" in signal_types

    # Assert signal details
    sg_sig = next(s for s in signals if s["type"] == "port_not_allowed")
    assert sg_sig["severity"] == "high"
    assert sg_sig["value"] == 443

    alb_sig = next(s for s in signals if s["type"] == "unhealthy_load_balancer_target")
    assert alb_sig["severity"] == "high"
    assert alb_sig["resource_id"] == "i-0a1b2c3d4e5f67890"


def test_evidence_generation_no_causal_claims():
    raw_data = load_sample_raw_data()
    normalized = normalize_aws_data(raw_data)
    signals = extract_signals(normalized)
    evidence = generate_evidence_statements(signals, normalized)

    assert len(evidence) >= 3
    evidence_text = " ".join(evidence)

    # Assert evidence is factual
    assert "does not contain an inbound TCP 443 rule" in evidence_text
    assert "unhealthy" in evidence_text
    assert "AuthorizeSecurityGroupIngress" in evidence_text

    # CRITICAL AUDIT: Assert evidence NEVER claims root cause
    assert "root cause" not in evidence_text.lower()
    assert "caused the outage" not in evidence_text.lower()
    assert "definitely causing" not in evidence_text.lower()


def test_full_preprocessing_pipeline():
    raw_data = load_sample_raw_data()
    context = preprocess_cloud_context(raw_data)

    assert "timestamp" in context
    assert context["region"] == "ap-south-1"
    assert context["summary"]["total_instances"] == 1
    assert context["summary"]["running_instances"] == 1
    assert context["summary"]["unhealthy_targets"] == 1
    assert len(context["signals"]) >= 3
    assert len(context["evidence"]) >= 3


@patch("app.api.routes.cloud_context.collect_infrastructure_data")
def test_cloud_context_api_routes(mock_collect):
    raw_data = load_sample_raw_data()
    mock_collect.return_value = raw_data

    # Test GET /api/cloud/context
    res_ctx = client.get("/api/cloud/context")
    assert res_ctx.status_code == 200
    json_ctx = res_ctx.json()
    assert json_ctx["region"] == "ap-south-1"
    assert "summary" in json_ctx
    assert len(json_ctx["signals"]) >= 3

    # Test GET /api/cloud/signals
    res_sig = client.get("/api/cloud/signals")
    assert res_sig.status_code == 200
    json_sig = res_sig.json()
    assert isinstance(json_sig, list)
    assert len(json_sig) >= 3


def test_host_telemetry_normalization_and_signals():
    raw_host_data = [
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
                }
            ],
            "listening_ports": [
                {"port": 22, "local_address": "0.0.0.0", "state": "Listen", "owning_process": 4}
            ],
            "system_info": {"os_name": "Windows Server 2022"},
            "error": None,
        }
    ]

    normalized_hosts = normalize_host_telemetry(raw_host_data)
    assert len(normalized_hosts) == 1
    assert normalized_hosts[0]["instance_id"] == "i-07243bdf548e18f5b"
    assert normalized_hosts[0]["services"][0]["name"] == "W3SVC"
    assert normalized_hosts[0]["services"][0]["status"] == "Stopped"
    assert len(normalized_hosts[0]["win32_service"]) == 1

    full_context_raw = {
        "region": "eu-north-1",
        "timestamp": "2026-09-12T12:00:00+00:00",
        "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running", "security_group_ids": ["sg-1"]}],
        "host_telemetry": raw_host_data,
        "security_groups": [{"group_id": "sg-1", "name": "web-sg", "inbound_rules": [{"protocol": "tcp", "from_port": 80, "to_port": 80}]}],
        "vpc": {},
        "cloudwatch": [],
        "cloudtrail": [],
        "load_balancers": [],
    }

    preprocessed = preprocess_cloud_context(full_context_raw)
    signals = preprocessed["signals"]
    signal_types = [s["type"] for s in signals]
    assert "windows_service_stopped" in signal_types
    assert "port_not_listening" in signal_types

    svc_sig = next(s for s in signals if s["type"] == "windows_service_stopped")
    assert svc_sig["severity"] == "high"
    assert svc_sig["resource_id"] == "i-07243bdf548e18f5b"
    assert "W3SVC" in svc_sig["description"]
    assert "Stopped" in svc_sig["description"]

    evidence = preprocessed["evidence"]
    evidence_text = " ".join(evidence)
    assert "W3SVC" in evidence_text
    assert "Stopped" in evidence_text
    assert "World Wide Web Publishing Service" in evidence_text
    assert "not running" in evidence_text


def test_cloudtrail_read_only_events_excluded_from_signals():
    raw_events = [
        {"event_name": "DescribeInstances", "username": "CloudOps-ReadOnly", "resources": [{"resource_name": "i-123"}]},
        {"event_name": "DescribeSecurityGroups", "username": "CloudOps-ReadOnly", "resources": [{"resource_name": "sg-123"}]},
        {"event_name": "GetCommandInvocation", "username": "CloudOps-ReadOnly", "resources": [{"resource_name": "cmd-123"}]},
        {"event_name": "LookupEvents", "username": "CloudOps-ReadOnly", "resources": [{"resource_name": "evt-123"}]},
        {"event_name": "ListInventoryEntries", "username": "CloudOps-ReadOnly", "resources": [{"resource_name": "inv-123"}]},
        {"event_name": "AuthorizeSecurityGroupIngress", "username": "admin-devops", "resources": [{"resource_name": "sg-target"}]},
    ]
    norm_events = normalize_cloudtrail_data(raw_events)
    norm_data = {
        "region": "eu-north-1",
        "timestamp": "2026-09-12T12:00:00+00:00",
        "resources": {},
        "metrics": [],
        "cloudtrail_events": norm_events
    }
    signals = extract_signals(norm_data)
    # Only AuthorizeSecurityGroupIngress should produce a recent_infrastructure_change signal
    change_signals = [s for s in signals if s["type"] == "recent_infrastructure_change"]
    assert len(change_signals) == 1
    assert change_signals[0]["value"] == "AuthorizeSecurityGroupIngress"
    assert change_signals[0]["resource_id"] == "sg-target"


def test_unattached_security_group_signal_association():
    norm_data = {
        "region": "eu-north-1",
        "timestamp": "2026-09-12T12:00:00+00:00",
        "resources": {
            "ec2": [{"instance_id": "i-target", "security_group_ids": ["sg-attached"]}],
            "security_groups": [
                {"group_id": "sg-attached", "name": "app-sg", "inbound_rules": [{"protocol": "tcp", "from_port": 80, "to_port": 80}]},
                {"group_id": "sg-unattached", "name": "unused-sg", "inbound_rules": [{"protocol": "tcp", "from_port": 80, "to_port": 80}]}
            ]
        },
        "metrics": [],
        "cloudtrail_events": []
    }
    signals = extract_signals(norm_data)
    port_signals = [s for s in signals if s["type"] == "port_not_allowed"]

    attached_sig = next(s for s in port_signals if s["metadata"]["group_id"] == "sg-attached")
    assert attached_sig["resource_id"] == "i-target"
    assert attached_sig["metadata"]["instance_id"] == "i-target"

    unattached_sig = next(s for s in port_signals if s["metadata"]["group_id"] == "sg-unattached")
    assert unattached_sig["resource_id"] == "sg-unattached"
    assert unattached_sig["metadata"]["instance_id"] is None


