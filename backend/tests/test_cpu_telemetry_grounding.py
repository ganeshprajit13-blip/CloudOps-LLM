import pytest
from datetime import datetime, timezone, timedelta
from app.services.preprocessing import extract_signals, compute_summary, preprocess_cloud_context
from app.services.context_builder import ContextBuilder
from app.services.diagnosis_validator import DiagnosisValidator
from model.inference import _generate_synthetic_heuristic_response


def test_current_cpu_low_with_historical_peak():
    """Requirement 1: Current CPU low (5%) + historical high peak (99.5%) -> NO active high_cpu signal."""
    now = datetime.now(timezone.utc)
    raw_data = {
        "timestamp": now.isoformat(),
        "region": "us-east-1",
        "ec2": [
            {
                "instance_id": "i-0123456789abcdef0",
                "state": "running",
                "security_group_ids": ["sg-11111111"],
            }
        ],
        "security_groups": [
            {
                "group_id": "sg-11111111",
                "inbound_rules": [
                    {"protocol": "tcp", "from_port": 80, "to_port": 80},
                    {"protocol": "tcp", "from_port": 443, "to_port": 443},
                ],
            }
        ],
        "cloudwatch": [
            {
                "metric_name": "CPUUtilization",
                "resource_id": "i-0123456789abcdef0",
                "timestamp": (now - timedelta(minutes=25)).isoformat(),
                "value": 99.56,
                "maximum": 99.56,
            },
            {
                "metric_name": "CPUUtilization",
                "resource_id": "i-0123456789abcdef0",
                "timestamp": (now - timedelta(minutes=15)).isoformat(),
                "value": 15.0,
                "maximum": 15.0,
            },
            {
                "metric_name": "CPUUtilization",
                "resource_id": "i-0123456789abcdef0",
                "timestamp": (now - timedelta(minutes=10)).isoformat(),
                "value": 8.0,
                "maximum": 8.0,
            },
            {
                "metric_name": "CPUUtilization",
                "resource_id": "i-0123456789abcdef0",
                "timestamp": (now - timedelta(minutes=2)).isoformat(),
                "value": 5.85,
                "maximum": 5.85,
            },
        ],
    }

    ctx = preprocess_cloud_context(raw_data)
    signals = ctx.get("signals", [])

    high_cpu_signals = [s for s in signals if s.get("type") == "high_cpu"]
    normal_cpu_signals = [s for s in signals if s.get("type") == "normal_cpu"]

    assert len(high_cpu_signals) == 0, "Should NOT emit active high_cpu signal when current CPU is low."
    assert len(normal_cpu_signals) == 1, "Should emit normal_cpu signal for current low CPU."
    assert normal_cpu_signals[0]["metadata"]["recent_peak"] == 99.56
    assert ctx["summary"]["high_cpu_instances"] == 0


def test_current_cpu_high():
    """Requirement 2: Current CPU high (92%) -> active high_cpu signal."""
    now = datetime.now(timezone.utc)
    raw_data = {
        "timestamp": now.isoformat(),
        "region": "us-east-1",
        "ec2": [{"instance_id": "i-highcpu001", "state": "running"}],
        "cloudwatch": [
            {
                "metric_name": "CPUUtilization",
                "resource_id": "i-highcpu001",
                "timestamp": (now - timedelta(minutes=1)).isoformat(),
                "value": 92.5,
                "maximum": 95.0,
            }
        ],
    }

    ctx = preprocess_cloud_context(raw_data)
    signals = ctx.get("signals", [])

    high_cpu_signals = [s for s in signals if s.get("type") == "high_cpu"]
    assert len(high_cpu_signals) == 1
    assert high_cpu_signals[0]["value"] == 92.5
    assert ctx["summary"]["high_cpu_instances"] == 1


def test_sustained_high_cpu():
    """Requirement 3: Sustained high CPU -> high_cpu signal with high confidence heuristic response."""
    now = datetime.now(timezone.utc)
    raw_data = {
        "timestamp": now.isoformat(),
        "region": "us-east-1",
        "ec2": [{"instance_id": "i-sustainedcpu", "state": "running"}],
        "cloudwatch": [
            {
                "metric_name": "CPUUtilization",
                "resource_id": "i-sustainedcpu",
                "timestamp": (now - timedelta(minutes=i*2)).isoformat(),
                "value": 95.0 + i,
                "maximum": 99.0,
            }
            for i in range(5)
        ],
    }

    ctx = preprocess_cloud_context(raw_data)
    signals = ctx.get("signals", [])
    high_cpu_signals = [s for s in signals if s.get("type") == "high_cpu"]
    assert len(high_cpu_signals) == 1

    resp = _generate_synthetic_heuristic_response("Why is my CPU high?", ctx)
    assert "high CPU utilization" in resp["probable_root_cause"]
    assert resp["confidence"] >= 0.85


def test_stale_high_cpu_datapoint():
    """Requirement 4: Stale high CPU datapoint (> 20 min old) -> NOT active high_cpu."""
    now = datetime.now(timezone.utc)
    raw_data = {
        "timestamp": now.isoformat(),
        "region": "us-east-1",
        "ec2": [{"instance_id": "i-stalecpu", "state": "running"}],
        "cloudwatch": [
            {
                "metric_name": "CPUUtilization",
                "resource_id": "i-stalecpu",
                "timestamp": (now - timedelta(minutes=45)).isoformat(),
                "value": 98.0,
                "maximum": 99.0,
            }
        ],
    }

    ctx = preprocess_cloud_context(raw_data)
    signals = ctx.get("signals", [])
    high_cpu_signals = [s for s in signals if s.get("type") == "high_cpu"]
    stale_cpu_signals = [s for s in signals if s.get("type") == "stale_cpu_telemetry"]

    assert len(high_cpu_signals) == 0
    assert len(stale_cpu_signals) == 1


def test_missing_cpu_telemetry():
    """Requirement 5: Missing CPU telemetry -> do not claim CPU critical."""
    now = datetime.now(timezone.utc)
    raw_data = {
        "timestamp": now.isoformat(),
        "region": "us-east-1",
        "ec2": [{"instance_id": "i-nocpu", "state": "running"}],
        "cloudwatch": [],
    }

    ctx = preprocess_cloud_context(raw_data)
    resp = _generate_synthetic_heuristic_response("Check CPU utilization", ctx)

    assert "unavailable" in resp["probable_root_cause"].lower()
    assert "high cpu utilization" not in resp["probable_root_cause"].lower()


def test_llm_hallucination_rejected_by_validator():
    """Requirement 6: LLM hallucination: current CPU normal + model says CPU critical -> validator rejects CPU claim."""
    now = datetime.now(timezone.utc)
    raw_data = {
        "timestamp": now.isoformat(),
        "region": "us-east-1",
        "ec2": [{"instance_id": "i-healthy001", "state": "running"}],
        "security_groups": [
            {
                "group_id": "sg-healthy",
                "inbound_rules": [{"protocol": "tcp", "from_port": 80, "to_port": 80}],
            }
        ],
        "host_telemetry": [
            {
                "instance_id": "i-healthy001",
                "services": [{"name": "W3SVC", "display_name": "World Wide Web Publishing Service", "status": "Running"}],
                "listening_ports": [{"port": 80, "state": "LISTENING"}],
            }
        ],
        "cloudwatch": [
            {
                "metric_name": "CPUUtilization",
                "resource_id": "i-healthy001",
                "timestamp": now.isoformat(),
                "value": 5.0,
                "maximum": 5.0,
            }
        ],
    }

    ctx = preprocess_cloud_context(raw_data)
    validator = DiagnosisValidator()

    hallucinated_diagnosis = {
        "problem": "Server experiencing high CPU saturation",
        "probable_root_cause": "EC2 instance i-healthy001 is suffering from high CPU utilization spike.",
        "evidence": ["High CPU utilization detected."],
        "impact": "Degraded performance.",
        "recommendation": "Restart server.",
        "confidence": 0.90,
    }

    is_grounded, warnings = validator.check_evidence_grounding(hallucinated_diagnosis, ctx, [])
    assert is_grounded is False, "Validator must flag hallucinated high CPU diagnosis when CPU is normal."
    assert any("high CPU" in w or "CPU critical" in w for w in warnings)


def test_healthy_analysis_does_not_contain_cpu_critical():
    """Requirement 7 & 8: Healthy instance analysis contains NO false CPU Critical diagnosis."""
    now = datetime.now(timezone.utc)
    raw_data = {
        "timestamp": now.isoformat(),
        "region": "eu-north-1",
        "ec2": [
            {
                "instance_id": "i-07243bdf548e18f5b",
                "state": "running",
                "security_group_ids": ["sg-0508c38f4cfa83f82"],
            }
        ],
        "security_groups": [
            {
                "group_id": "sg-0508c38f4cfa83f82",
                "inbound_rules": [
                    {"protocol": "tcp", "from_port": 80, "to_port": 80},
                    {"protocol": "tcp", "from_port": 443, "to_port": 443},
                ],
            }
        ],
        "cloudwatch": [
            {
                "metric_name": "CPUUtilization",
                "resource_id": "i-07243bdf548e18f5b",
                "timestamp": now.isoformat(),
                "value": 5.85,
                "maximum": 99.56,
            }
        ],
    }

    ctx = preprocess_cloud_context(raw_data)
    resp = _generate_synthetic_heuristic_response("Why is my CPU high?", ctx)

    assert "normal" in resp["probable_root_cause"].lower()
    assert "99.56%" in resp["probable_root_cause"] or "5.85%" in resp["probable_root_cause"]
    assert "high cpu utilization of" not in resp["probable_root_cause"].lower()
