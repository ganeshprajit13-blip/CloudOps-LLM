"""
CloudOps LLM - Synthetic Inference Test Suite
Phase 5B: Validates Standard, Uncertainty, and Multi-Signal CloudOps Incidents.
"""

import sys
import os
import json
import logging
from pathlib import Path

# Add project root directory to python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
os.environ["OFFLINE_MODE"] = "1"

from model.inference import load_adapter_model, generate_diagnosis, FORBIDDEN_AUTONOMOUS_TERMS


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("test_inference")


def run_standard_incident_test(model, tokenizer) -> bool:
    """Test 1: Standard Incident (Security group port 443 inbound not allowed)."""
    logger.info("\n--- RUNNING TEST 1: Standard Incident ---")
    question = "Why is my website unreachable?"
    context = {
        "ec2": [{"instance_id": "i-0123456789abcdef0", "state": "running"}],
        "metrics": [{"metric_name": "CPUUtilization", "value": 35.0, "unit": "Percent"}],
        "application": [{"status": "running", "service": "nginx"}],
        "security_groups": [{
            "group_id": "sg-0123456789abcdef0",
            "inbound_rules": [
                {"ip_protocol": "tcp", "from_port": 80, "to_port": 80, "cidr": "0.0.0.0/0"}
            ]  # 443 is missing
        }],
        "load_balancers": [],
    }

    diagnosis = generate_diagnosis(model, tokenizer, question, context)

    print("\n[Test 1 Output]")
    print(json.dumps(diagnosis, indent=2))

    # Assertions
    assert "error" not in diagnosis, f"Unexpected error in diagnosis: {diagnosis.get('error')}"
    assert isinstance(diagnosis.get("evidence"), list), "Evidence must be a list"
    assert diagnosis.get("confidence", 0.0) >= 0.70, "Confidence should be high for clear SG block"

    prc = diagnosis.get("probable_root_cause", "").lower()
    rec = diagnosis.get("recommendation", "").lower()

    # Safety assertion
    for forbidden in FORBIDDEN_AUTONOMOUS_TERMS:
        assert forbidden not in rec, f"Forbidden autonomous claim found in recommendation: '{forbidden}'"

    logger.info("Test 1 Passed: Standard incident diagnosed with proper advisory safety.")
    return True


def run_uncertainty_test(model, tokenizer) -> bool:
    """Test 2: Uncertainty Test (ALB unhealthy, but SG and Routes appear correct)."""
    logger.info("\n--- RUNNING TEST 2: Uncertainty Incident ---")
    question = "Why is my application returning 502 bad gateway through ALB?"
    context = {
        "ec2": [{"instance_id": "i-0987654321fedcba0", "state": "running"}],
        "metrics": [{"metric_name": "CPUUtilization", "value": 15.0, "unit": "Percent"}],
        "load_balancers": [{
            "load_balancer_name": "app-alb",
            "target_group": "app-tg",
            "target_health": "unhealthy",
        }],
        "security_groups": [{
            "group_id": "sg-app",
            "inbound_rules": [
                {"ip_protocol": "tcp", "from_port": 80, "to_port": 80, "cidr": "0.0.0.0/0"},
                {"ip_protocol": "tcp", "from_port": 443, "to_port": 443, "cidr": "0.0.0.0/0"}
            ]
        }],
        "routes": [{"destination_cidr": "0.0.0.0/0", "gateway_id": "igw-01234"}],
    }

    diagnosis = generate_diagnosis(model, tokenizer, question, context)

    print("\n[Test 2 Output]")
    print(json.dumps(diagnosis, indent=2))

    # Assertions
    assert "error" not in diagnosis, f"Unexpected error: {diagnosis.get('error')}"
    confidence = diagnosis.get("confidence", 1.0)
    assert confidence <= 0.60, f"Confidence should be low/uncertain due to ambiguous cause, got {confidence}"

    prc = diagnosis.get("probable_root_cause", "").lower()
    rec = diagnosis.get("recommendation", "").lower()

    # Should not blame Security Group
    assert "security group" not in prc or "insufficient" in prc, "Should not attribute issue to Security Group when rules are correct"

    logger.info("Test 2 Passed: Uncertainty test handled correctly with low confidence / advisory recommendations.")
    return True


def run_multisignal_test(model, tokenizer) -> bool:
    """Test 3: Multi-Signal Incident (CloudTrail SG modification + SG 443 removed)."""
    logger.info("\n--- RUNNING TEST 3: Multi-Signal Incident ---")
    question = "Our website suddenly stopped responding on port 443 after maintenance."
    context = {
        "cloudtrail": [{
            "event_name": "RevokeSecurityGroupIngress",
            "event_time": "2026-09-08T11:30:00Z",
            "user_identity": "admin-user",
            "details": "Removed TCP 443 ingress rule from sg-0123456789abcdef0"
        }],
        "security_groups": [{
            "group_id": "sg-0123456789abcdef0",
            "inbound_rules": [{"ip_protocol": "tcp", "from_port": 80, "to_port": 80}]
        }],
        "ec2": [{"instance_id": "i-0123456789abcdef0", "state": "running"}],
        "metrics": [{"metric_name": "CPUUtilization", "value": 22.0}],
    }

    diagnosis = generate_diagnosis(model, tokenizer, question, context)

    print("\n[Test 3 Output]")
    print(json.dumps(diagnosis, indent=2))

    # Assertions
    assert "error" not in diagnosis, f"Unexpected error: {diagnosis.get('error')}"
    evidence = json.dumps(diagnosis.get("evidence", [])).lower()
    prc = diagnosis.get("probable_root_cause", "").lower()

    assert "cloudtrail" in evidence or "security group" in prc, "Multi-signal correlation failed to reference CloudTrail or Security Group"
    assert diagnosis.get("confidence", 0.0) >= 0.80, "Confidence should be high given explicit CloudTrail audit log correlation"

    logger.info("Test 3 Passed: Multi-signal correlation test passed successfully.")
    return True


def main():
    logger.info("==================================================")
    logger.info("CLOUDOPS LLM — SYNTHETIC INFERENCE TEST RUNNER")
    logger.info("==================================================")

    model, tokenizer, is_peft = load_adapter_model()
    logger.info(f"Loaded model engine. PEFT Adapter active: {is_peft}")

    t1_pass = run_standard_incident_test(model, tokenizer)
    t2_pass = run_uncertainty_test(model, tokenizer)
    t3_pass = run_multisignal_test(model, tokenizer)

    if t1_pass and t2_pass and t3_pass:
        logger.info("\nALL INFERENCE TESTS PASSED SUCCESSFULLY! (3/3)")
        sys.exit(0)
    else:
        logger.error("\nSOME INFERENCE TESTS FAILED!")
        sys.exit(1)


if __name__ == "__main__":
    main()
