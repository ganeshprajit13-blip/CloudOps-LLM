import pytest
from app.services.cloudops_analyzer import CloudOpsAnalyzer
from app.services.prompt_builder import PromptBuilder
from app.services.diagnosis_validator import DiagnosisValidator

def test_evidence_correlation_test1_website_port80_missing():
    """TEST 1: Website unreachable + port 80 missing → missing inbound TCP 80"""
    builder = PromptBuilder()
    cloud_context = {
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "security_groups": [{"group_id": "sg-0508c38f4cfa83f82", "inbound_rules": []}],
            "host_telemetry": [],
            "vpcs": [],
            "load_balancers": []
        },
        "signals": [
            {
                "type": "port_not_allowed",
                "resource_id": "sg-0508c38f4cfa83f82",
                "severity": "critical",
                "description": "Port 80 (HTTP) is not allowed",
                "metadata": {"port": 80, "group_id": "sg-0508c38f4cfa83f82", "instance_id": "i-07243bdf548e18f5b"}
            },
            {
                "type": "normal_cpu",
                "resource_id": "i-07243bdf548e18f5b",
                "severity": "info",
                "value": 7.67,
                "description": "Normal CPU utilization (7.67%)"
            }
        ],
        "metrics": [{"metric_name": "CPUUtilization", "resource_id": "i-07243bdf548e18f5b", "maximum": 7.67, "average": 7.67}]
    }

    block = builder.format_structured_evidence_block(
        question="Why is my website unreachable ?",
        resource_id="i-07243bdf548e18f5b",
        cloud_context=cloud_context
    )

    assert "Port 80 is NOT allowed in Security Group sg-0508c38f4cfa83f82" in block
    assert "Normal CPU Utilization: 7.67%" in block
    assert "CONTRADICTIONS / NORMAL STATE:" in block

def test_evidence_correlation_test2_website_port80_allowed():
    """TEST 2: Website unreachable + port 80 allowed → MUST NOT claim port 80 is blocked"""
    validator = DiagnosisValidator()
    cloud_context = {
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "security_groups": [{
                "group_id": "sg-0508c38f4cfa83f82",
                "inbound_rules": [{"protocol": "tcp", "from_port": 80, "to_port": 80, "sources": ["0.0.0.0/0"]}]
            }],
        },
        "signals": []
    }

    evidence = ["Security Group sg-0508c38f4cfa83f82 does not allow inbound TCP 80"]
    valid_ev, rejection_reasons = validator.validate_and_filter_evidence(evidence, cloud_context)

    # Rejection reasons MUST reject the false claim that port 80 is blocked when it is allowed
    assert len(valid_ev) == 0
    assert any("Contradiction" in r for r in rejection_reasons)

def test_evidence_correlation_test3_https_port443_missing():
    """TEST 3: HTTPS failure + port 443 missing → missing inbound TCP 443"""
    builder = PromptBuilder()
    cloud_context = {
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "security_groups": [{"group_id": "sg-0508c38f4cfa83f82", "inbound_rules": []}],
        },
        "signals": [
            {
                "type": "port_not_allowed",
                "resource_id": "sg-0508c38f4cfa83f82",
                "severity": "critical",
                "description": "Port 443 (HTTPS) is not allowed",
                "metadata": {"port": 443, "group_id": "sg-0508c38f4cfa83f82", "instance_id": "i-07243bdf548e18f5b"}
            }
        ]
    }

    block = builder.format_structured_evidence_block(
        question="Why is HTTPS (SSL) unreachable?",
        resource_id="i-07243bdf548e18f5b",
        cloud_context=cloud_context
    )

    assert "Port 443 is NOT allowed in Security Group sg-0508c38f4cfa83f82" in block

def test_evidence_correlation_test4_iis_stopped_sg_allows_port():
    """TEST 4: IIS/W3SVC stopped + SG allows required port → distinguish service failure from SG failure"""
    builder = PromptBuilder()
    cloud_context = {
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "security_groups": [{
                "group_id": "sg-0508c38f4cfa83f82",
                "inbound_rules": [{"protocol": "tcp", "from_port": 80, "to_port": 80, "sources": ["0.0.0.0/0"]}]
            }],
            "host_telemetry": [{
                "instance_id": "i-07243bdf548e18f5b",
                "platform": "windows",
                "services": [{"name": "W3SVC", "display_name": "World Wide Web Publishing Service", "status": "Stopped", "start_type": "Auto"}],
                "listening_ports": []
            }]
        },
        "signals": [
            {
                "type": "windows_service_stopped",
                "resource_id": "i-07243bdf548e18f5b",
                "severity": "critical",
                "description": "Windows service W3SVC is Stopped",
                "metadata": {"service_name": "W3SVC", "display_name": "World Wide Web Publishing Service", "status": "Stopped"}
            }
        ]
    }

    block = builder.format_structured_evidence_block(
        question="Why is my web server down?",
        resource_id="i-07243bdf548e18f5b",
        cloud_context=cloud_context
    )

    assert "Allowed Inbound = [TCP 80]" in block
    assert "Service 'W3SVC' (World Wide Web Publishing Service): Status=Stopped" in block

def test_evidence_correlation_test5_cpu_high():
    """TEST 5: CPU incident + CPU 95-100% → CPU saturation"""
    builder = PromptBuilder()
    cloud_context = {
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
        },
        "signals": [
            {
                "type": "high_cpu",
                "resource_id": "i-07243bdf548e18f5b",
                "severity": "critical",
                "value": 98.5,
                "description": "High CPU utilization (98.5%)"
            }
        ],
        "metrics": [{"metric_name": "CPUUtilization", "resource_id": "i-07243bdf548e18f5b", "maximum": 98.5, "average": 95.0}]
    }

    block = builder.format_structured_evidence_block(
        question="High CPU alert on EC2 instance",
        resource_id="i-07243bdf548e18f5b",
        cloud_context=cloud_context
    )

    assert "High CPU Utilization: 98.5% on i-07243bdf548e18f5b (exceeds 80% threshold)" in block

def test_evidence_correlation_test6_cpu_normal():
    """TEST 6: CPU incident + CPU 7% → must NOT blame CPU"""
    builder = PromptBuilder()
    cloud_context = {
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
        },
        "signals": [
            {
                "type": "normal_cpu",
                "resource_id": "i-07243bdf548e18f5b",
                "severity": "info",
                "value": 7.67,
                "description": "Normal CPU utilization (7.67%)"
            }
        ],
        "metrics": [{"metric_name": "CPUUtilization", "resource_id": "i-07243bdf548e18f5b", "maximum": 7.67, "average": 7.67}]
    }

    block = builder.format_structured_evidence_block(
        question="Why is my website slow?",
        resource_id="i-07243bdf548e18f5b",
        cloud_context=cloud_context
    )

    assert "Normal CPU Utilization: 7.67% on i-07243bdf548e18f5b" in block
    assert "CONTRADICTIONS / NORMAL STATE:" in block

def test_test_a_w3svc_stopped_overrides_missing_sg_port():
    """TEST A: Stop W3SVC + SG port 80 missing → W3SVC stopped is DIRECT_CAUSE and takes precedence"""
    from model.inference import _generate_synthetic_heuristic_response
    cloud_context = {
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "security_groups": [{"group_id": "sg-0508c38f4cfa83f82", "inbound_rules": []}],
            "host_telemetry": [{
                "instance_id": "i-07243bdf548e18f5b",
                "platform": "windows",
                "services": [{"name": "W3SVC", "display_name": "World Wide Web Publishing Service", "status": "Stopped"}]
            }]
        },
        "signals": [
            {
                "type": "windows_service_stopped",
                "resource_id": "i-07243bdf548e18f5b",
                "severity": "critical",
                "description": "Windows service 'W3SVC' (World Wide Web Publishing Service) is Stopped on instance i-07243bdf548e18f5b.",
                "metadata": {"service_name": "W3SVC", "display_name": "World Wide Web Publishing Service", "status": "Stopped", "instance_id": "i-07243bdf548e18f5b"}
            },
            {
                "type": "port_not_allowed",
                "resource_id": "sg-0508c38f4cfa83f82",
                "severity": "critical",
                "value": 80,
                "metadata": {"port": 80, "group_id": "sg-0508c38f4cfa83f82", "instance_id": "i-07243bdf548e18f5b"}
            }
        ]
    }

    res = _generate_synthetic_heuristic_response("Why is my website unreachable?", cloud_context)
    assert "W3SVC" in res["probable_root_cause"]
    assert "stopped" in res["probable_root_cause"].lower()

def test_test_b_w3svc_running_sg_port_missing():
    """TEST B: W3SVC running + SG port 80 missing → Security Group is identified as root cause"""
    from model.inference import _generate_synthetic_heuristic_response
    cloud_context = {
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "security_groups": [{"group_id": "sg-0508c38f4cfa83f82", "inbound_rules": []}],
            "host_telemetry": [{
                "instance_id": "i-07243bdf548e18f5b",
                "platform": "windows",
                "services": [{"name": "W3SVC", "display_name": "World Wide Web Publishing Service", "status": "Running"}],
                "listening_ports": [{"port": 80, "state": "Listen"}]
            }]
        },
        "signals": [
            {
                "type": "port_not_allowed",
                "resource_id": "sg-0508c38f4cfa83f82",
                "severity": "critical",
                "value": 80,
                "metadata": {"port": 80, "group_id": "sg-0508c38f4cfa83f82", "instance_id": "i-07243bdf548e18f5b"}
            }
        ]
    }

    res = _generate_synthetic_heuristic_response("Why is my website unreachable over HTTP?", cloud_context)
    assert "Security Group" in res["probable_root_cause"]
    assert "port 80" in res["probable_root_cause"].lower()

def test_test_e_uncollected_host_telemetry_explicit_note():
    """TEST E: Host telemetry uncollected + SG port 80 missing → identify missing port 80 & explicitly state W3SVC unobserved"""
    builder = PromptBuilder()
    from model.inference import _generate_synthetic_heuristic_response

    cloud_context = {
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "security_groups": [{"group_id": "sg-0508c38f4cfa83f82", "inbound_rules": []}],
            "host_telemetry": []
        },
        "signals": [
            {
                "type": "port_not_allowed",
                "resource_id": "sg-0508c38f4cfa83f82",
                "severity": "critical",
                "value": 80,
                "metadata": {"port": 80, "group_id": "sg-0508c38f4cfa83f82", "instance_id": "i-07243bdf548e18f5b"}
            }
        ]
    }

    block = builder.format_structured_evidence_block("Why is my website unreachable?", "i-07243bdf548e18f5b", cloud_context)
    assert "Host Service Telemetry: UNCOLLECTED / UNAVAILABLE" in block

    res = _generate_synthetic_heuristic_response("Why is my website unreachable over HTTP?", cloud_context)
    assert any("uncollected" in ev.lower() or "unobserved" in ev.lower() for ev in res["evidence"])

