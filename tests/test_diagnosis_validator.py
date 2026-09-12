import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pytest
from app.services.diagnosis_validator import DiagnosisValidator

def test_diagnosis_validator_valid():
    validator = DiagnosisValidator()
    valid_payload = {
        "problem": "Website unreachable over HTTPS.",
        "probable_root_cause": "Security Group missing inbound TCP 443 rule.",
        "evidence": ["Security Group sg-01234 lacks port 443 rule."],
        "impact": "Clients connection times out.",
        "recommendation": "Add inbound rule for TCP 443.",
        "confidence": 0.88
    }

    is_valid, err = validator.validate_schema(valid_payload)
    assert is_valid is True
    assert err is None


def test_diagnosis_validator_invalid_schema():
    validator = DiagnosisValidator()

    # Missing evidence field
    invalid_payload = {
        "problem": "Website unreachable",
        "probable_root_cause": "SG issue",
        "impact": "High",
        "recommendation": "Fix SG",
        "confidence": 0.80
    }
    is_valid, err = validator.validate_schema(invalid_payload)
    assert is_valid is False
    assert "Missing required field: 'evidence'" in err

    # Out-of-bound confidence
    invalid_conf = dict(valid_payload := {
        "problem": "Website unreachable.",
        "probable_root_cause": "SG issue.",
        "evidence": ["SG rule missing."],
        "impact": "High",
        "recommendation": "Fix SG",
        "confidence": 1.5
    })
    is_valid, err = validator.validate_schema(invalid_conf)
    assert is_valid is False
    assert "confidence" in err


def test_diagnosis_validator_advisory_safety():
    validator = DiagnosisValidator()
    data = {
        "problem": "Unreachable website",
        "probable_root_cause": "SG blocked",
        "evidence": ["Port 443 missing"],
        "impact": "Outage",
        "recommendation": "I fixed the security group and automatically restarted the EC2 instance now.",
        "confidence": 0.90
    }

    sanitized = validator.enforce_advisory_safety(data)
    assert "Review the identified issue and consider taking corrective action" in sanitized["recommendation"]


test_diagnosis_validator_advisory_safety()


def test_insufficient_evidence_response():
    validator = DiagnosisValidator()
    resp = validator.build_insufficient_evidence_response("Why is EC2 offline?")

    assert resp["confidence"] == 0.20
    assert "Insufficient evidence" in resp["probable_root_cause"]
    assert isinstance(resp["evidence"], list)


def test_markdown_wrapped_json_extraction():
    validator = DiagnosisValidator()
    markdown_raw = """Here is the structured diagnosis based on the AWS telemetry context:
```json
{
  "problem": "Website port 80 unreachable.",
  "probable_root_cause": "Inbound TCP port 80 missing from Security Group.",
  "evidence": ["Security group lacks TCP 80 rule."],
  "impact": "HTTP connections fail.",
  "recommendation": "Authorize inbound TCP port 80.",
  "confidence": 0.88
}
```
Hope this helps!"""

    extracted = validator.safe_extract_json(markdown_raw)
    assert extracted is not None
    assert extracted["problem"] == "Website port 80 unreachable."
    is_valid, err = validator.validate_schema(extracted)
    assert is_valid is True
    assert err is None


def test_field_alias_normalization():
    validator = DiagnosisValidator()
    raw_alias_payload = {
        "issue": "Website is completely unreachable on port 80.",
        "root_cause": "Security group sg-0508c does not allow inbound TCP 80.",
        "evidence_list": ["Security group sg-0508c missing port 80 rule."],
        "operational_impact": "Users receive connection timeout error.",
        "remediation": "Add inbound rule for TCP port 80 in sg-0508c.",
        "confidence_score": 0.90
    }

    normalized = validator.normalize_diagnosis_payload(raw_alias_payload)
    assert normalized["problem"] == "Website is completely unreachable on port 80."
    assert normalized["probable_root_cause"] == "Security group sg-0508c does not allow inbound TCP 80."
    assert normalized["evidence"] == ["Security group sg-0508c missing port 80 rule."]
    assert normalized["impact"] == "Users receive connection timeout error."
    assert normalized["recommendation"] == "Add inbound rule for TCP port 80 in sg-0508c."
    assert normalized["confidence"] == 0.90

    is_valid, err = validator.validate_schema(normalized)
    assert is_valid is True
    assert err is None


def test_malformed_json_recovery_and_type_coercion():
    validator = DiagnosisValidator()
    # Missing fields and non-list evidence
    raw_payload = {
        "summary": "Port 80 HTTP blocked",
        "cause": "Security Group rule missing",
        "evidence": "Single string evidence item",
        "confidence": "0.85"
    }

    normalized = validator.normalize_diagnosis_payload(raw_payload)
    assert normalized["problem"] == "Port 80 HTTP blocked"
    assert normalized["probable_root_cause"] == "Security Group rule missing"
    assert normalized["evidence"] == ["Single string evidence item"]
    assert isinstance(normalized["impact"], str)
    assert isinstance(normalized["recommendation"], str)
    assert normalized["confidence"] == 0.85

    is_valid, err = validator.validate_schema(normalized)
    assert is_valid is True
    assert err is None


def test_evidence_contradiction_rejection_for_allowed_port():
    validator = DiagnosisValidator()
    context = {
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "security_groups": [
                {
                    "group_id": "sg-0508c38f4cfa83f82",
                    "name": "CloudOps-Test-SG",
                    "inbound_rules": [
                        {"protocol": "tcp", "from_port": 80, "to_port": 80},
                        {"protocol": "tcp", "from_port": 443, "to_port": 443}
                    ]
                }
            ],
            "host_telemetry": [
                {
                    "instance_id": "i-07243bdf548e18f5b",
                    "services": [{"name": "W3SVC", "status": "Stopped"}],
                    "listening_ports": [{"port": 3389, "state": "Listen"}]
                }
            ]
        },
        "signals": [
            {"type": "windows_service_stopped", "resource_id": "i-07243bdf548e18f5b", "value": "Stopped"}
        ]
    }

    # Evidence with contradictory claim about port 443
    raw_evidence = [
        "EC2 instance state is running but Windows service 'W3SVC' (IIS) is stopped.",
        "Security Group allows inbound TCP port 80 but IIS is likely not started.",
        "No evidence of HTTPS (port 443) protocol in Security Group."
    ]

    valid_ev, rejected = validator.validate_and_filter_evidence(raw_evidence, context)
    assert len(valid_ev) == 2
    assert "No evidence of HTTPS (port 443) protocol in Security Group." not in valid_ev
    assert any("port 443" in r for r in rejected)


def test_evidence_service_and_port_state():
    validator = DiagnosisValidator()
    context = {
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "security_groups": [{"group_id": "sg-1", "inbound_rules": [{"protocol": "tcp", "from_port": 80, "to_port": 80}]}],
            "host_telemetry": [
                {
                    "instance_id": "i-07243bdf548e18f5b",
                    "services": [{"name": "W3SVC", "status": "Stopped"}, {"name": "Spooler", "status": "Running"}],
                    "listening_ports": [{"port": 3389, "state": "Listen"}]
                }
            ]
        },
        "signals": []
    }

    # Contradictory service claim: Spooler is stopped (when it's Running)
    evidence = [
        "Windows service 'W3SVC' is stopped.",
        "Windows service 'Spooler' is stopped."
    ]
    valid_ev, rejected = validator.validate_and_filter_evidence(evidence, context)
    assert len(valid_ev) == 1
    assert valid_ev[0] == "Windows service 'W3SVC' is stopped."
    assert any("Spooler" in r for r in rejected)


def test_unrelated_resource_evidence_rejected():
    validator = DiagnosisValidator()
    context = {
        "resources": {
            "ec2": [{"instance_id": "i-target", "state": "running"}],
            "security_groups": [{"group_id": "sg-target", "inbound_rules": []}],
            "host_telemetry": []
        }
    }
    evidence = [
        "Instance i-target is running.",
        "Security Group sg-unrelated999 has missing port 80 rule."
    ]
    valid_ev, rejected = validator.validate_and_filter_evidence(evidence, context)
    assert len(valid_ev) == 1
    assert valid_ev[0] == "Instance i-target is running."
    assert any("sg-unrelated999" in r for r in rejected)


def test_regression_target_sg_has_port_443_evidence_cannot_claim_missing_443():
    """
    Regression Test: If target SG allows port 443, evidence claiming port 443 is missing
    must be rejected by DiagnosisValidator.
    """
    validator = DiagnosisValidator()
    context = {
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "security_groups": [
                {
                    "group_id": "sg-0508c38f4cfa83f82",
                    "name": "web-sg",
                    "inbound_rules": [
                        {"protocol": "tcp", "from_port": 80, "to_port": 80},
                        {"protocol": "tcp", "from_port": 443, "to_port": 443}
                    ]
                }
            ],
            "host_telemetry": [
                {
                    "instance_id": "i-07243bdf548e18f5b",
                    "services": [{"name": "W3SVC", "status": "Stopped"}],
                    "listening_ports": [{"port": 3389, "state": "Listen"}]
                }
            ]
        },
        "signals": []
    }

    raw_evidence = [
        "EC2 instance state is running but Windows service 'W3SVC' (IIS) is stopped.",
        "Security Group allows inbound TCP port 80 but IIS is likely not started.",
        "No evidence of HTTPS (port 443) protocol in Security Group."
    ]

    valid_ev, rejected = validator.validate_and_filter_evidence(raw_evidence, context)
    assert len(valid_ev) == 2
    assert "No evidence of HTTPS (port 443) protocol in Security Group." not in valid_ev
    assert any("443" in r for r in rejected)


def test_regression_w3svc_stopped_evidence_allowed():
    """
    Regression Test: When W3SVC is stopped in host telemetry, evidence stating W3SVC is stopped is valid.
    """
    validator = DiagnosisValidator()
    context = {
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "security_groups": [{"group_id": "sg-0508c", "inbound_rules": [{"protocol": "tcp", "from_port": 80, "to_port": 80}]}],
            "host_telemetry": [
                {
                    "instance_id": "i-07243bdf548e18f5b",
                    "services": [{"name": "W3SVC", "status": "Stopped"}],
                    "listening_ports": []
                }
            ]
        }
    }

    evidence = [
        "EC2 instance state is running but Windows service 'W3SVC' (IIS) is stopped.",
        "Port 80 is not listening on the host."
    ]
    valid_ev, rejected = validator.validate_and_filter_evidence(evidence, context)
    assert len(valid_ev) == 2
    assert len(rejected) == 0


def test_regression_port_80_not_listening_evidence_allowed():
    """
    Regression Test: When port 80 is not in listening ports, evidence claiming port 80 is not listening is allowed,
    while claiming port 80 is listening is rejected as a contradiction.
    """
    validator = DiagnosisValidator()
    context = {
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "host_telemetry": [
                {
                    "instance_id": "i-07243bdf548e18f5b",
                    "services": [{"name": "W3SVC", "status": "Stopped"}],
                    "listening_ports": [{"port": 3389, "state": "Listen"}]
                }
            ]
        }
    }

    evidence_valid = ["Port 80 is not listening on the host."]
    valid_ev, rejected = validator.validate_and_filter_evidence(evidence_valid, context)
    assert len(valid_ev) == 1
    assert valid_ev[0] == "Port 80 is not listening on the host."

    evidence_invalid = ["Port 80 is actively listening on all interfaces."]
    valid_ev, rejected = validator.validate_and_filter_evidence(evidence_invalid, context)
    assert len(valid_ev) == 0
    assert any("port 80" in r.lower() for r in rejected)


def test_regression_unrelated_sg_route_table_rejected():
    """
    Regression Test: Unrelated Security Groups and Route Tables not associated with the target context are rejected.
    """
    validator = DiagnosisValidator()
    context = {
        "resources": {
            "ec2": [{"instance_id": "i-target", "state": "running"}],
            "security_groups": [{"group_id": "sg-target1", "inbound_rules": []}],
            "route_tables": [{"route_table_id": "rtb-target1", "routes": []}]
        }
    }

    evidence = [
        "Target instance i-target is running.",
        "Security Group sg-unrelated456 lacks port 80 rule.",
        "Route table rtb-unrelated789 is missing default route."
    ]

    valid_ev, rejected = validator.validate_and_filter_evidence(evidence, context)
    assert len(valid_ev) == 1
    assert valid_ev[0] == "Target instance i-target is running."
    assert any("sg-unrelated456" in r for r in rejected)
    assert any("rtb-unrelated789" in r for r in rejected)


def test_regression_generic_readonly_cloudtrail_calls_rejected():
    """
    Regression Test: Generic read-only CloudTrail API calls (e.g. DescribeInstances, GetCommandInvocation)
    cannot be accepted as RCA evidence statements.
    """
    validator = DiagnosisValidator()
    context = {
        "resources": {
            "ec2": [{"instance_id": "i-target", "state": "running"}]
        }
    }

    evidence = [
        "Target instance i-target is running.",
        "CloudTrail event shows DescribeInstances API call was executed.",
        "CloudTrail event records GetCommandInvocation call."
    ]

    valid_ev, rejected = validator.validate_and_filter_evidence(evidence, context)
    assert len(valid_ev) == 1
    assert valid_ev[0] == "Target instance i-target is running."
    assert len(rejected) == 2
    assert any("CloudTrail" in r or "read-only" in r for r in rejected)


def test_regression_current_port_80_allowed_historical_remove_event_rejected():
    """
    Regression Test: Current port 80 allowed + historical remove event → must NOT diagnose port 80 blocked/removed.
    Evidence or root cause claiming port 80 was removed must be rejected because active SG has port 80.
    """
    validator = DiagnosisValidator()
    context = {
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "security_groups": [
                {
                    "group_id": "sg-0508c38f4cfa83f82",
                    "inbound_rules": [
                        {"protocol": "tcp", "from_port": 80, "to_port": 80}
                    ]
                }
            ],
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
                "resource": "sg-0508c38f4cfa83f82"
            }
        ]
    }

    # Evidence claiming port 80 was removed must be rejected
    evidence = [
        "EC2 instance state is running.",
        "Inbound TCP port 80 was removed in the security group."
    ]
    valid_ev, rejected = validator.validate_and_filter_evidence(evidence, context)
    assert len(valid_ev) == 1
    assert valid_ev[0] == "EC2 instance state is running."
    assert any("port 80" in r for r in rejected)

    # Grounding check must reject diagnosis claiming port 80 was removed
    hallucinated_diagnosis = {
        "problem": "Cannot access website on port 80.",
        "probable_root_cause": "Inbound TCP port 80 was removed in the security group.",
        "evidence": ["Inbound TCP port 80 was removed in the security group."],
        "impact": "Traffic dropped.",
        "recommendation": "Authorize port 80.",
        "confidence": 0.90
    }
    is_grounded, warnings = validator.check_evidence_grounding(hallucinated_diagnosis, context, [])
    assert is_grounded is False
    assert any("port 80" in w.lower() for w in warnings)


def test_regression_current_port_80_blocked_historical_remove_event_allowed():
    """
    Regression Test: Current port 80 blocked + historical remove event → MAY diagnose port 80 missing/blocked.
    """
    validator = DiagnosisValidator()
    context = {
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "security_groups": [
                {
                    "group_id": "sg-0508c38f4cfa83f82",
                    "inbound_rules": [
                        {"protocol": "tcp", "from_port": 22, "to_port": 22}
                    ]
                }
            ]
        },
        "signals": [
            {"type": "port_not_allowed", "resource_id": "sg-0508c38f4cfa83f82", "value": 80}
        ]
    }

    diagnosis = {
        "problem": "Cannot access website on port 80.",
        "probable_root_cause": "Inbound HTTP traffic on TCP port 80 is not permitted by the active Security Group configuration.",
        "evidence": ["Security Group inbound rules do not allow TCP port 80."],
        "impact": "Traffic dropped.",
        "recommendation": "Authorize port 80.",
        "confidence": 0.88
    }
    is_grounded, warnings = validator.check_evidence_grounding(diagnosis, context, [])
    assert is_grounded is True


def test_regression_current_w3svc_running_old_service_event_not_diagnosed_stopped():
    """
    Regression Test: Current W3SVC running + old service-related event → must NOT claim W3SVC is currently stopped.
    """
    validator = DiagnosisValidator()
    context = {
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "security_groups": [{"group_id": "sg-1", "inbound_rules": [{"protocol": "tcp", "from_port": 80, "to_port": 80}]}],
            "host_telemetry": [
                {
                    "instance_id": "i-07243bdf548e18f5b",
                    "services": [{"name": "W3SVC", "status": "Running"}],
                    "listening_ports": [{"port": 80, "state": "Listen"}]
                }
            ]
        },
        "cloudtrail_events": [
            {"event_name": "Stop-Service", "resource": "W3SVC"}
        ]
    }

    # Evidence claiming W3SVC is stopped must be rejected because telemetry confirms it is Running
    evidence = [
        "EC2 instance state is running.",
        "Windows service 'W3SVC' is stopped on the host."
    ]
    valid_ev, rejected = validator.validate_and_filter_evidence(evidence, context)
    assert len(valid_ev) == 1
    assert valid_ev[0] == "EC2 instance state is running."
    assert any("W3SVC" in r for r in rejected)

    # Root cause claiming W3SVC stopped must fail grounding check
    stopped_diagnosis = {
        "problem": "Website down.",
        "probable_root_cause": "Windows service W3SVC is stopped on instance i-07243bdf548e18f5b.",
        "evidence": ["Windows service W3SVC is stopped on instance i-07243bdf548e18f5b."],
        "impact": "Outage.",
        "recommendation": "Start service.",
        "confidence": 0.90
    }
    is_grounded, warnings = validator.check_evidence_grounding(stopped_diagnosis, context, [])
    assert is_grounded is False
    assert any("w3svc" in w.lower() for w in warnings)

def test_alb_grounding_benign_negation_not_flagged():
    """
    Regression: LLM evidence saying "No load balancer or target group configuration
    exists in the system." is a TRUE, benign observation and must NOT trigger the ALB
    grounding failure that previously dropped the entire diagnosis.
    """
    validator = DiagnosisValidator()
    context = {
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "load_balancers": []
        },
        "metrics": [{"metric_name": "CPUUtilization", "resource_id": "i-07243bdf548e18f5b", "maximum": 99.8}],
        "signals": [{"type": "high_cpu", "resource_id": "i-07243bdf548e18f5b", "value": 99.8}]
    }
    diagnosis = {
        "problem": "EC2 instance has high CPU utilization.",
        "probable_root_cause": "Web server process is running and consuming high CPU resources.",
        "evidence": [
            "EC2 instance id=i-07243bdf548e18f5b has high CPU utilization (99.8%).",
            "Services Spooler, W3SVC, and WAS are running on the EC2 instance.",
            "No load balancer or target group configuration exists in the system.",
        ],
        "impact": "EC2 instance performance is affected.",
        "recommendation": "Review running processes.",
        "confidence": 0.85
    }
    is_grounded, warnings = validator.check_evidence_grounding(diagnosis, context, [])
    # "No load balancer or target group configuration exists" is a negation — not an ALB failure claim
    alb_warnings = [w for w in warnings if "load balancer" in w.lower() or "alb" in w.lower()]
    assert not alb_warnings, f"Benign 'no target group' mention was incorrectly flagged: {alb_warnings}"
    # The overall diagnosis should remain grounded (CPU evidence is valid)
    assert is_grounded, f"Diagnosis was incorrectly marked ungrounded. Warnings: {warnings}"


def test_alb_grounding_actual_failure_claim_still_rejected():
    """
    Regression: A diagnosis that actively claims 'ALB target group is unhealthy' when no
    ALB resources exist must still be flagged and rejected.
    """
    validator = DiagnosisValidator()
    context = {
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "load_balancers": []
        },
        "signals": []
    }
    diagnosis = {
        "problem": "Website unreachable.",
        "probable_root_cause": "Application Load Balancer target group reporting unhealthy targets.",
        "evidence": ["ALB target group is failing health checks."],
        "impact": "502 errors.",
        "recommendation": "Investigate target health.",
        "confidence": 0.90
    }
    is_grounded, warnings = validator.check_evidence_grounding(diagnosis, context, [])
    assert not is_grounded
    assert any("alb" in w.lower() or "load balancer" in w.lower() for w in warnings)


# ---------------------------------------------------------------------------
# Spooler (Print Spooler) Failure Regression Tests
# ---------------------------------------------------------------------------

def _spooler_stopped_context():
    """Shared context: EC2 running, Spooler stopped, no ALB."""
    return {
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "security_groups": [
                {
                    "group_id": "sg-0508c38f4cfa83f82",
                    "inbound_rules": [
                        {"protocol": "tcp", "from_port": 80, "to_port": 80},
                        {"protocol": "tcp", "from_port": 443, "to_port": 443},
                        {"protocol": "tcp", "from_port": 3389, "to_port": 3389},
                    ],
                }
            ],
            "host_telemetry": [
                {
                    "instance_id": "i-07243bdf548e18f5b",
                    "services": [
                        {"name": "Spooler", "display_name": "Print Spooler", "status": "Stopped"},
                        {"name": "W3SVC", "display_name": "World Wide Web Publishing Service", "status": "Running"},
                    ],
                    "listening_ports": [{"port": 80, "state": "Listen"}],
                }
            ],
            "load_balancers": [],
        },
        "signals": [
            {
                "type": "windows_service_stopped",
                "severity": "high",
                "resource_id": "i-07243bdf548e18f5b",
                "description": "Windows service 'Spooler' (Print Spooler) is Stopped on instance i-07243bdf548e18f5b.",
                "value": "Stopped",
                "metadata": {
                    "service_name": "Spooler",
                    "display_name": "Print Spooler",
                    "status": "Stopped",
                    "instance_id": "i-07243bdf548e18f5b",
                },
            }
        ],
    }


def test_spooler_stopped_valid_evidence_accepted():
    """
    Regression: Spooler stopped → evidence about the stopped service and running EC2
    must be accepted as valid.
    """
    validator = DiagnosisValidator()
    ctx = _spooler_stopped_context()
    evidence = [
        "Host telemetry confirms Windows service 'Spooler' (Print Spooler) is Stopped on instance i-07243bdf548e18f5b.",
        "EC2 instance state is running.",
    ]
    valid_ev, rejected = validator.validate_and_filter_evidence(evidence, ctx)
    assert len(valid_ev) == 2, f"Expected 2 valid evidence items, got {len(valid_ev)}. Rejected: {rejected}"
    assert any("spooler" in e.lower() for e in valid_ev)
    assert any("running" in e.lower() for e in valid_ev)
    assert not rejected, f"Unexpected rejections: {rejected}"


def test_spooler_stopped_no_start_ec2_recommendation():
    """
    Regression: When EC2 is running and Spooler is stopped, enforce_advisory_safety must
    correct any 'Start the EC2 instance' recommendation to target the Spooler service.
    """
    validator = DiagnosisValidator()
    ctx = _spooler_stopped_context()
    bad_diagnosis = {
        "problem": "Print Spooler is unavailable.",
        "probable_root_cause": "Spooler service is stopped.",
        "evidence": ["Spooler is stopped."],
        "impact": "Printing unavailable.",
        "recommendation": "Start the EC2 instance and verify application process startup.",
        "confidence": 0.85,
    }
    sanitized = validator.enforce_advisory_safety(bad_diagnosis, cloud_context=ctx)
    rec = sanitized["recommendation"].lower()
    assert "start the ec2 instance" not in rec, (
        f"'Start the EC2 instance' must not appear when EC2 is running. Got: {sanitized['recommendation']}"
    )
    assert "spooler" in rec or "print spooler" in rec, (
        f"Recommendation should target the Spooler service. Got: {sanitized['recommendation']}"
    )


def test_spooler_stopped_no_start_ec2_when_ec2_actually_stopped():
    """
    Control: When EC2 itself IS stopped, 'Start the EC2 instance' is legitimate
    and must NOT be rewritten.
    """
    validator = DiagnosisValidator()
    ctx = {
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "stopped"}],
            "security_groups": [],
            "host_telemetry": [],
        },
        "signals": [],
    }
    diagnosis = {
        "problem": "EC2 is stopped.",
        "probable_root_cause": "EC2 instance is in stopped state.",
        "evidence": ["EC2 instance state is stopped."],
        "impact": "All services offline.",
        "recommendation": "Start the EC2 instance and verify application process startup.",
        "confidence": 0.95,
    }
    sanitized = validator.enforce_advisory_safety(diagnosis, cloud_context=ctx)
    assert "start the ec2 instance" in sanitized["recommendation"].lower(), (
        f"'Start the EC2 instance' must be preserved when EC2 is genuinely stopped. Got: {sanitized['recommendation']}"
    )


def test_tcp_445_sg_absence_not_evidence_for_spooler_failure():
    """
    Regression: 'No Security Group rule for TCP port 445' is NOT causal evidence for a
    locally stopped Spooler service. It must be rejected by validate_and_filter_evidence
    when host telemetry is present and a Windows service is stopped.
    """
    validator = DiagnosisValidator()
    ctx = _spooler_stopped_context()
    evidence = [
        "Host telemetry confirms Windows service 'Spooler' (Print Spooler) is Stopped on instance i-07243bdf548e18f5b.",
        "No Security Group rule exists for TCP port 445 (SMB), blocking remote printer access.",
        "EC2 instance state is running.",
    ]
    valid_ev, rejected = validator.validate_and_filter_evidence(evidence, ctx)
    assert not any("445" in e for e in valid_ev), (
        f"TCP 445 SG absence must not appear in valid evidence for a local Spooler failure. Valid: {valid_ev}"
    )
    assert any("445" in r for r in rejected), (
        f"TCP 445 SG absence must appear in rejection reasons. Rejected: {rejected}"
    )
    assert any("spooler" in e.lower() for e in valid_ev)
    assert any("running" in e.lower() for e in valid_ev)


def test_tcp_80_sg_absence_still_valid_for_web_context_with_spooler_stopped():
    """
    Control: TCP port 80 SG absence is still valid evidence even when Spooler is also
    stopped (ports 80/443 are exempt from the local-service-failure filter).
    """
    validator = DiagnosisValidator()
    ctx = {
        "resources": {
            "ec2": [{"instance_id": "i-07243bdf548e18f5b", "state": "running"}],
            "security_groups": [{"group_id": "sg-abc", "inbound_rules": []}],
            "host_telemetry": [
                {
                    "instance_id": "i-07243bdf548e18f5b",
                    "services": [{"name": "Spooler", "display_name": "Print Spooler", "status": "Stopped"}],
                    "listening_ports": [],
                }
            ],
        },
        "signals": [
            {
                "type": "windows_service_stopped",
                "resource_id": "i-07243bdf548e18f5b",
                "metadata": {"service_name": "Spooler", "display_name": "Print Spooler", "instance_id": "i-07243bdf548e18f5b"},
            },
            {"type": "port_not_allowed", "value": 80, "resource_id": "sg-abc"},
        ],
    }
    evidence = ["Security Group does not allow inbound TCP port 80."]
    valid_ev, rejected = validator.validate_and_filter_evidence(evidence, ctx)
    assert any("80" in e for e in valid_ev), (
        f"TCP port 80 SG absence must remain valid even when Spooler is stopped. Valid: {valid_ev}, Rejected: {rejected}"
    )
def test_alb_grounding_unavailable_claim_still_rejected():
    """
    Regression: 'Target group is unavailable' without ALBs in context must still be rejected.
    """
    validator = DiagnosisValidator()
    context = {"resources": {"ec2": [{"instance_id": "i-aaa", "state": "running"}], "load_balancers": []}, "signals": []}
    diagnosis = {
        "problem": "Website down.",
        "probable_root_cause": "Target group is unavailable due to failed health checks.",
        "evidence": ["Target group health check failure detected."],
        "impact": "Service down.",
        "recommendation": "Inspect health.",
        "confidence": 0.85
    }
    is_grounded, warnings = validator.check_evidence_grounding(diagnosis, context, [])
    assert not is_grounded
    assert any("alb" in w.lower() or "load balancer" in w.lower() for w in warnings)


def test_irrelevant_negative_alb_observation_rejected():
    """
    Requirement 2 & 11: Generic negative resource observations like 'No Load Balancer exists'
    must be rejected from evidence when non-causal to the diagnosis.
    """
    validator = DiagnosisValidator()
    ctx = _spooler_stopped_context()
    evidence = [
        "Host telemetry confirms Windows service 'Spooler' (Print Spooler) is Stopped on instance i-07243bdf548e18f5b.",
        "No Application Load Balancer (ALB) or Target Group is configured in the VPC.",
    ]
    valid_ev, rejected = validator.validate_and_filter_evidence(evidence, ctx)
    assert not any("load balancer" in e.lower() or "alb" in e.lower() for e in valid_ev), (
        f"Negative ALB observation must be rejected from evidence. Valid: {valid_ev}"
    )
    assert any("negative resource observation" in r.lower() or "irrelevant" in r.lower() for r in rejected)


def test_multilingual_chinese_output_sanitized():
    """
    Requirement 4, 6 & 11: Unexpected Chinese/CJK multilingual output in impact, recommendation,
    or evidence must be sanitized to clean English.
    """
    validator = DiagnosisValidator()
    ctx = _spooler_stopped_context()
    diagnosis = {
        "problem": "The Print Spooler service is failing.",
        "probable_root_cause": "The Windows service 'Spooler' is stopped on the EC2 instance.",
        "evidence": ["Host telemetry confirms Windows service 'Spooler' is Stopped."],
        "impact": "可能导致打印服务不可用。",
        "recommendation": "建议启动Print Spooler服务。",
        "confidence": 0.85,
    }
    sanitized = validator.enforce_advisory_safety(diagnosis, cloud_context=ctx)
    assert "可能导致" not in sanitized["impact"]
    assert "建议" not in sanitized["recommendation"]
    assert sanitized["recommendation"] == "Start the Print Spooler (Spooler) service on the EC2 instance."
    assert "Print Spooler" in sanitized["impact"]


def test_spooler_stopped_ec2_running_exact_recommendation():
    """
    Requirement 5: For Spooler stopped + EC2 running, recommendation MUST be:
    'Start the Print Spooler (Spooler) service on the EC2 instance.'
    """
    validator = DiagnosisValidator()
    ctx = _spooler_stopped_context()
    diagnosis = {
        "problem": "Print Spooler failure.",
        "probable_root_cause": "Print Spooler service stopped.",
        "evidence": ["Spooler service is stopped."],
        "impact": "Print jobs failing.",
        "recommendation": "Start the EC2 instance or check services.",
        "confidence": 0.85,
    }
    sanitized = validator.enforce_advisory_safety(diagnosis, cloud_context=ctx)
    assert sanitized["recommendation"] == "Start the Print Spooler (Spooler) service on the EC2 instance."


