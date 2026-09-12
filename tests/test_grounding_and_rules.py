import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"

if str(BACKEND_DIR) in sys.path:
    sys.path.remove(str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR))
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

import pytest
from app.services.cloudops_analyzer import CloudOpsAnalyzer
from app.services.diagnosis_validator import DiagnosisValidator
from model.inference import _generate_synthetic_heuristic_response


def test_grounding_a_port_80_blocked():
    """Test A: EC2 with port 80 blocked -> diagnose Security Group/network issue."""
    context = {
        "summary": {"total_instances": 1, "running_instances": 1},
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "security_groups": [{
                "group_id": "sg-0123",
                "name": "web-sg",
                "inbound_rules": [{"protocol": "tcp", "from_port": 3389, "to_port": 3389, "sources": ["0.0.0.0/0"]}]
            }],
            "load_balancers": []
        },
        "signals": [{"type": "port_not_allowed", "severity": "high", "resource_id": "sg-0123", "value": 80}]
    }

    res = _generate_synthetic_heuristic_response(
        question="Why can I not access my IIS website on HTTP port 80?",
        cloud_context=context
    )

    assert "port 80" in res["probable_root_cause"].lower() or "security group" in res["probable_root_cause"].lower()
    assert "alb" not in res["probable_root_cause"].lower()
    assert "target group" not in res["probable_root_cause"].lower()


def test_grounding_b_port_80_allowed():
    """Test B: EC2 with port 80 allowed -> do not claim port 80 is blocked."""
    context = {
        "summary": {"total_instances": 1, "running_instances": 1},
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "security_groups": [{
                "group_id": "sg-0123",
                "name": "web-sg",
                "inbound_rules": [{"protocol": "tcp", "from_port": 80, "to_port": 80, "sources": ["0.0.0.0/0"]}]
            }],
            "load_balancers": []
        },
        "signals": []
    }

    res = _generate_synthetic_heuristic_response(
        question="Why is my server slow?",
        cloud_context=context
    )

    assert "port 80 is not permitted" not in res["probable_root_cause"].lower()
    assert "alb" not in res["probable_root_cause"].lower()


def test_grounding_c_no_alb_present():
    """Test C: No ALB present -> model must not claim ALB target-group failure."""
    context = {
        "summary": {"total_instances": 1, "running_instances": 1, "unhealthy_targets": 0},
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "load_balancers": []
        },
        "signals": []
    }

    res = _generate_synthetic_heuristic_response(
        question="Why can I not access my website?",
        cloud_context=context
    )

    assert "application load balancer" not in res["probable_root_cause"].lower()
    assert "target group" not in res["probable_root_cause"].lower()

    # Also test validator grounding check
    validator = DiagnosisValidator()
    hallucinated_diagnosis = {
        "problem": "Website unreachable",
        "probable_root_cause": "Application Load Balancer target group reporting unhealthy targets.",
        "evidence": ["ALB target group is unhealthy"],
        "impact": "Traffic dropped",
        "recommendation": "Check ALB health path",
        "confidence": 0.90
    }
    is_grounded, warnings = validator.check_evidence_grounding(hallucinated_diagnosis, context, [])
    assert not is_grounded
    assert any("no alb resources exist" in w.lower() for w in warnings)


def test_grounding_d_alb_present_unhealthy_target():
    """Test D: ALB actually present with unhealthy target -> ALB diagnosis is allowed."""
    context = {
        "summary": {"total_instances": 1, "running_instances": 1, "unhealthy_targets": 1},
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "load_balancers": [{
                "name": "app-alb",
                "state": "active",
                "target_groups": [{
                    "name": "web-tg",
                    "port": 80,
                    "unhealthy_targets": [{"target_id": "i-07243bdf548e18f5b", "reason": "Target.FailedHealthChecks"}]
                }]
            }]
        },
        "signals": [{"type": "unhealthy_load_balancer_target", "severity": "high", "resource_id": "i-07243bdf548e18f5b"}]
    }

    res = _generate_synthetic_heuristic_response(
        question="Why is my ALB returning 502 Bad Gateway?",
        cloud_context=context
    )

    assert "load balancer" in res["probable_root_cause"].lower() or "target" in res["probable_root_cause"].lower()

    validator = DiagnosisValidator()
    diagnosis = {
        "problem": "ALB target unhealthy",
        "probable_root_cause": "Application Load Balancer target group reporting unhealthy targets.",
        "evidence": ["Target i-07243bdf548e18f5b failed health checks"],
        "impact": "502 Gateway errors",
        "recommendation": "Check target service health",
        "confidence": 0.85
    }
    is_grounded, warnings = validator.check_evidence_grounding(diagnosis, context, [])
    assert is_grounded


def test_grounding_e_conflicting_rag_vs_live_data():
    """Test E: Conflicting RAG knowledge vs live AWS data -> live AWS data wins."""
    # Live data has NO ALB, only Security Group with missing port 80
    live_context = {
        "summary": {"total_instances": 1, "running_instances": 1},
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "security_groups": [{"group_id": "sg-0123", "name": "web", "inbound_rules": []}],
            "load_balancers": []
        },
        "signals": [{"type": "port_not_allowed", "severity": "high", "resource_id": "sg-0123", "value": 80}]
    }

    def rag_query_fn(q):
        class ConflictingRAG:
            results = [
                type("Item", (), {
                    "text": "ALB target groups may report 502 errors when targets are unhealthy.",
                    "score": 0.95,
                    "metadata": {"source": "alb_guide.md", "title": "ALB Guide", "service": "alb"}
                })()
            ]
        return ConflictingRAG()

    def model_runner_with_hallucinated_alb(q, ctx, prompt):
        # Modelrunner attempts to claim ALB failure despite no ALB in live context
        return {
            "problem": "IIS website unreachable",
            "probable_root_cause": "Application Load Balancer target group reporting unhealthy targets.",
            "evidence": ["ALB target group health check failed"],
            "impact": "Website connection timeout",
            "recommendation": "Fix ALB target group health check",
            "confidence": 0.90
        }

    analyzer = CloudOpsAnalyzer(
        model_runner=model_runner_with_hallucinated_alb,
        rag_query_fn=rag_query_fn
    )

    response = analyzer.analyze(
        question="Why can I not access my IIS website on HTTP port 80?",
        cloud_context=live_context,
        collect_live_data=False
    )

    # Validation should reject the hallucinated ALB claim because live AWS context has no ALB!
    assert "application load balancer" not in response.diagnosis.probable_root_cause.lower()
    assert response.diagnosis.confidence <= 0.50


def test_grounding_f_missing_insufficient_sg_data():
    """Test F: Missing/insufficient SG data -> diagnosis must explicitly state evidence is insufficient rather than guessing."""
    empty_context = {
        "summary": {"total_instances": 0, "running_instances": 0},
        "resources": {"ec2": [], "security_groups": [], "load_balancers": []},
        "signals": []
    }

    res = _generate_synthetic_heuristic_response(
        question="Why can I not access my IIS website on HTTP port 80?",
        cloud_context=empty_context
    )

    assert "insufficient" in res["probable_root_cause"].lower()
    assert "iis website is down" not in res["probable_root_cause"].lower()
    assert "configured to listen on a different port" not in res["probable_root_cause"].lower()
    assert res["confidence"] <= 0.50


def test_protocol_scenario_1_http_port_80_blocked():
    """Scenario 1: HTTP query + port 80 blocked -> diagnose TCP port 80."""
    context = {
        "summary": {"total_instances": 1, "running_instances": 1},
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "security_groups": [{"group_id": "sg-web", "inbound_rules": []}]
        },
        "signals": [
            {"type": "port_not_allowed", "severity": "high", "resource_id": "i-07243bdf548e18f5b", "value": 80},
            {"type": "port_not_allowed", "severity": "high", "resource_id": "i-07243bdf548e18f5b", "value": 443}
        ]
    }

    res = _generate_synthetic_heuristic_response("Why is my website unreachable?", context)
    assert "port 80" in res["probable_root_cause"].lower() or "80" in res["probable_root_cause"]
    assert "443" not in res["probable_root_cause"]
    assert res["confidence"] >= 0.80


def test_protocol_scenario_2_https_port_443_blocked():
    """Scenario 2: HTTPS query + port 443 blocked -> diagnose TCP port 443."""
    context = {
        "summary": {"total_instances": 1, "running_instances": 1},
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "security_groups": [{"group_id": "sg-web", "inbound_rules": []}]
        },
        "signals": [
            {"type": "port_not_allowed", "severity": "high", "resource_id": "i-07243bdf548e18f5b", "value": 80},
            {"type": "port_not_allowed", "severity": "high", "resource_id": "i-07243bdf548e18f5b", "value": 443}
        ]
    }

    res = _generate_synthetic_heuristic_response("Why is my website returning connection timeout over HTTPS?", context)
    assert "443" in res["probable_root_cause"] or "https" in res["probable_root_cause"].lower()
    assert res["confidence"] >= 0.80


def test_protocol_scenario_3_both_ports_blocked():
    """Scenario 3: Both ports 80 and 443 blocked -> HTTP query selects 80; unspecified query notes both."""
    context = {
        "summary": {"total_instances": 1, "running_instances": 1},
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "security_groups": [{"group_id": "sg-web", "inbound_rules": []}]
        },
        "signals": [
            {"type": "port_not_allowed", "severity": "high", "resource_id": "i-07243bdf548e18f5b", "value": 80},
            {"type": "port_not_allowed", "severity": "high", "resource_id": "i-07243bdf548e18f5b", "value": 443}
        ]
    }

    # HTTP query
    res_http = _generate_synthetic_heuristic_response("Why is my website unreachable on HTTP?", context)
    assert "80" in res_http["probable_root_cause"]

    # Protocol unspecified query
    res_unspec = _generate_synthetic_heuristic_response("Why is network connection failing?", context)
    assert "80" in res_unspec["probable_root_cause"] or "443" in res_unspec["probable_root_cause"]


def test_protocol_scenario_4_both_ports_allowed():
    """Scenario 4: Both ports 80 and 443 allowed -> do NOT blame Security Group; confidence <= 0.50."""
    context = {
        "summary": {"total_instances": 1, "running_instances": 1},
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "security_groups": [{
                "group_id": "sg-web",
                "inbound_rules": [
                    {"protocol": "tcp", "from_port": 80, "to_port": 80, "sources": ["0.0.0.0/0"]},
                    {"protocol": "tcp", "from_port": 443, "to_port": 443, "sources": ["0.0.0.0/0"]}
                ]
            }]
        },
        "signals": []
    }

    res = _generate_synthetic_heuristic_response("Why is my website unreachable?", context)
    assert "port 80 is not permitted" not in res["probable_root_cause"].lower()
    assert "port 443 is not permitted" not in res["probable_root_cause"].lower()
    assert res["confidence"] <= 0.50


def test_protocol_scenario_5_protocol_unspecified():
    """Scenario 5: Protocol unspecified -> avoid defaulting to port 443 over 80."""
    context = {
        "summary": {"total_instances": 1, "running_instances": 1},
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "security_groups": [{"group_id": "sg-web", "inbound_rules": []}]
        },
        "signals": [
            {"type": "port_not_allowed", "severity": "high", "resource_id": "i-07243bdf548e18f5b", "value": 80},
            {"type": "port_not_allowed", "severity": "high", "resource_id": "i-07243bdf548e18f5b", "value": 443}
        ]
    }

    res = _generate_synthetic_heuristic_response("Why is server traffic failing?", context)
    assert res["confidence"] > 0.0
    # Must not claim only 443 is broken without mentioning 80 or general web ports
    prc = res["probable_root_cause"].lower()
    assert "80" in prc or "web ports" in prc or "both" in prc


def test_protocol_scenario_6_competing_causes():
    """Scenario 6: Competing causes (EC2 instance stopped vs SG port 80 blocked) -> EC2 stopped takes precedence."""
    context = {
        "summary": {"total_instances": 1, "running_instances": 0},
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "stopped"}],
            "security_groups": [{"group_id": "sg-web", "inbound_rules": []}]
        },
        "signals": [
            {"type": "port_not_allowed", "severity": "high", "resource_id": "i-07243bdf548e18f5b", "value": 80}
        ]
    }

    res = _generate_synthetic_heuristic_response("Why is my website unreachable?", context)
    assert "stopped" in res["probable_root_cause"].lower()
    assert res["confidence"] >= 0.90


def test_active_port_80_allowed_with_historical_revoke_event():
    """
    Current port 80 allowed + historical RevokeSecurityGroupIngress event in CloudTrail:
    Active configuration takes strict precedence over historical event.
    Model/Analyzer must NOT diagnose that port 80 was removed or is blocked.
    """
    context = {
        "summary": {"total_instances": 1, "running_instances": 1},
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "security_groups": [{
                "group_id": "sg-0508c38f4cfa83f82",
                "name": "CloudOps-SG",
                "inbound_rules": [
                    {"protocol": "tcp", "from_port": 80, "to_port": 80, "sources": ["0.0.0.0/0"]},
                    {"protocol": "tcp", "from_port": 443, "to_port": 443, "sources": ["0.0.0.0/0"]}
                ]
            }],
            "host_telemetry": [
                {
                    "instance_id": "i-07243bdf548e18f5b",
                    "services": [{"name": "W3SVC", "status": "Running"}],
                    "listening_ports": [{"port": 80, "state": "Listen"}]
                }
            ]
        },
        "cloudtrail_events": [
            {
                "event_name": "RevokeSecurityGroupIngress",
                "principal": "admin",
                "resource": "sg-0508c38f4cfa83f82",
                "event_time": "2026-09-12T10:00:00Z"
            }
        ],
        "signals": []
    }

    res = _generate_synthetic_heuristic_response(
        question="Why can I not access my IIS website on HTTP port 80?",
        cloud_context=context
    )

    assert "removed" not in res["probable_root_cause"].lower()
    assert "port 80 is not permitted" not in res["probable_root_cause"].lower()
    assert "missing" not in res["probable_root_cause"].lower()


def test_active_port_80_blocked_with_historical_revoke_event():
    """
    Current port 80 blocked + historical RevokeSecurityGroupIngress event in CloudTrail:
    May diagnose that port 80 is missing/blocked because active configuration confirms it.
    """
    context = {
        "summary": {"total_instances": 1, "running_instances": 1},
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "security_groups": [{
                "group_id": "sg-0508c38f4cfa83f82",
                "name": "CloudOps-SG",
                "inbound_rules": []
            }]
        },
        "cloudtrail_events": [
            {
                "event_name": "RevokeSecurityGroupIngress",
                "principal": "admin",
                "resource": "sg-0508c38f4cfa83f82",
                "event_time": "2026-09-12T10:00:00Z"
            }
        ],
        "signals": [
            {"type": "port_not_allowed", "severity": "high", "resource_id": "sg-0508c38f4cfa83f82", "value": 80}
        ]
    }

    res = _generate_synthetic_heuristic_response(
        question="Why can I not access my IIS website on HTTP port 80?",
        cloud_context=context
    )

    assert "port 80" in res["probable_root_cause"].lower() or "missing" in res["probable_root_cause"].lower()


def test_high_cpu_utilization_diagnosis():
    """High CPU telemetry present -> diagnoses high CPU utilization on target EC2."""
    context = {
        "summary": {"total_instances": 1, "running_instances": 1, "high_cpu_instances": 1},
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "security_groups": [{"group_id": "sg-0508c38f4cfa83f82", "inbound_rules": []}],
            "load_balancers": []
        },
        "metrics": [
            {
                "metric_name": "CPUUtilization",
                "resource_id": "i-07243bdf548e18f5b",
                "value": 99.8,
                "maximum": 99.8,
                "average": 64.3,
                "unit": "Percent",
                "timestamp": "2026-09-13T00:20:00Z"
            }
        ],
        "signals": [
            {
                "type": "high_cpu",
                "severity": "high",
                "resource_id": "i-07243bdf548e18f5b",
                "value": 99.8,
                "description": "High CPU utilization of 99.8% observed on instance i-07243bdf548e18f5b."
            }
        ]
    }

    res = _generate_synthetic_heuristic_response(
        question="Why is my EC2 instance experiencing high CPU usage?",
        cloud_context=context
    )

    assert "high cpu" in res["probable_root_cause"].lower()
    assert "i-07243bdf548e18f5b" in res["probable_root_cause"]
    assert res["confidence"] >= 0.85
    assert any("99.8%" in ev or "high cpu" in ev.lower() for ev in res["evidence"])
    assert "alb" not in res["probable_root_cause"].lower()


def test_normal_cpu_utilization_diagnosis():
    """Normal CPU telemetry present when user asks about CPU -> indicates normal CPU."""
    context = {
        "summary": {"total_instances": 1, "running_instances": 1, "high_cpu_instances": 0},
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "security_groups": [{"group_id": "sg-0508c38f4cfa83f82", "inbound_rules": []}],
            "load_balancers": []
        },
        "metrics": [
            {
                "metric_name": "CPUUtilization",
                "resource_id": "i-07243bdf548e18f5b",
                "value": 15.2,
                "maximum": 15.2,
                "average": 12.0,
                "unit": "Percent"
            }
        ],
        "signals": [
            {
                "type": "normal_cpu",
                "severity": "info",
                "resource_id": "i-07243bdf548e18f5b",
                "value": 15.2,
                "description": "Normal CPU utilization of 15.2% observed on instance i-07243bdf548e18f5b."
            }
        ]
    }

    res = _generate_synthetic_heuristic_response(
        question="Why is my EC2 instance experiencing high CPU usage?",
        cloud_context=context
    )

    assert "normal" in res["probable_root_cause"].lower()
    assert "i-07243bdf548e18f5b" in res["probable_root_cause"]
    assert res["confidence"] >= 0.80
    assert any("normal cpu" in ev.lower() for ev in res["evidence"])




