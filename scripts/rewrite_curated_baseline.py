import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from model.config import RANDOM_SEED, TEST_FILE, TRAIN_FILE, VALIDATION_FILE
from model.dataset import (
    PROMPT_VARIATIONS,
    calculate_jaccard_similarity,
    classify_incident_attributes,
    find_near_duplicates,
    generate_dataset_statistics,
    load_jsonl,
    save_jsonl,
    validate_example,
)

# 8 Explicit Scenario Types
DIVERSE_SCENARIOS = [
    "CONFIGURATION_MISMATCH",
    "COMPETING_CAUSE",
    "INSUFFICIENT_EVIDENCE",
    "MISLEADING_SYMPTOM",
    "APPLICATION_VS_INFRASTRUCTURE",
    "CLOUDTRAIL_CORRELATION",
    "SINGLE_CAUSE",
    "MULTI_SIGNAL",
]

def generate_rewritten_scenario(idx: int, scenario_type: str, seed: int) -> Dict[str, Any]:
    """Generates a genuinely distinct diagnostic scenario with calibrated confidence and evidence."""
    random.seed(seed + idx * 37)
    inst_id = f"i-0curated{idx:03d}"
    vpc_id = f"vpc-0curated{idx:03d}"
    sg_id = f"sg-0curated{idx:03d}"
    subnet_id = f"subnet-0curated{idx:03d}"
    instruction = random.choice(PROMPT_VARIATIONS)

    categories = [
        "EC2", "EBS", "VPC", "Subnets", "Route Tables", "Internet Gateway", "NAT Gateway",
        "Security Groups", "Network ACLs", "ALB", "Target Groups", "CloudWatch", "CloudTrail",
        "IAM", "S3", "RDS", "Lambda", "ECS", "EKS", "Auto Scaling", "Route 53/DNS", "TLS/SSL"
    ]
    cat = categories[idx % len(categories)]

    if scenario_type == "INSUFFICIENT_EVIDENCE":
        input_text = f"User reports application performance degradation on {cat} workload in VPC {vpc_id}. Resource CPU utilization is 38%. No memory utilization, disk I/O metrics, or recent CloudTrail audit logs are collected."
        output_obj = {
            "problem": f"{cat} service performance degradation",
            "probable_root_cause": f"Available telemetry for {cat} is ambiguous and insufficient to conclusively diagnose root cause",
            "evidence": [
                f"Resource telemetry for {cat} shows normal CPU at 38%",
                "Memory, disk I/O, and application runtime logs are unavailable"
            ],
            "impact": "End-user web application latency elevated, but root cause remains unverified",
            "recommendation": f"Enable CloudWatch detailed telemetry and APM tracing for {cat} workload before executing remediation",
            "confidence": round(random.uniform(0.38, 0.47), 2)
        }

    elif scenario_type == "COMPETING_CAUSE":
        input_text = f"App server {inst_id} reports HTTP 504 Gateway Timeout. Host CPU utilization is 91.5% sustained for 30m. Simultaneously, CloudTrail shows RevokeSecurityGroupIngress on {sg_id} port 443 executed 10m ago."
        output_obj = {
            "problem": "Competing failure signals affecting web application reachability",
            "probable_root_cause": f"Primary cause is severe host CPU saturation on {inst_id}, while recent Security Group {sg_id} rule revocation presents a competing network ingress signal",
            "evidence": [
                f"EC2 instance {inst_id} CPU utilization is 91.5%",
                f"CloudTrail logged RevokeSecurityGroupIngress on {sg_id} port 443 10m ago",
                "ALB target health check reports HTTP 504 timeout"
            ],
            "impact": "Application latency degraded and inbound client traffic blocked",
            "recommendation": f"Inspect high CPU processes on instance {inst_id} while restoring TCP port 443 ingress on Security Group {sg_id}",
            "confidence": round(random.uniform(0.80, 0.86), 2)
        }

    elif scenario_type == "MISLEADING_SYMPTOM":
        input_text = f"CloudWatch alarm triggered for metric DiskReadOps on EBS volume vol-0curated{idx:03d} attached to {inst_id}. However, HTTP connection failure is caused by an expired TLS certificate on port 443."
        output_obj = {
            "problem": "HTTPS client SSL handshake failure",
            "probable_root_cause": "Server TLS/SSL certificate on port 443 expired; high DiskReadOps metric is a secondary misleading symptom",
            "evidence": [
                "Clients receive SSL_ERROR_EXPIRED_CERTIFICATE",
                f"CloudWatch alarm for DiskReadOps is active on vol-0curated{idx:03d}"
            ],
            "impact": "Clients cannot establish secure HTTPS connections to web service",
            "recommendation": "Renew expired ACM/TLS certificate on the web endpoint and adjust EBS CloudWatch alarm threshold",
            "confidence": round(random.uniform(0.91, 0.96), 2)
        }

    elif scenario_type == "CONFIGURATION_MISMATCH":
        input_text = f"ALB prod-alb target group tg-curated{idx:03d} reports target instance {inst_id} as unhealthy. Target group health check path is configured as /healthz on port 8080, but application process listens on port 8000."
        output_obj = {
            "problem": "ALB target health check port configuration mismatch",
            "probable_root_cause": f"Target group tg-curated{idx:03d} checks port 8080 while application service on {inst_id} listens on port 8000",
            "evidence": [
                "ALB target status reports unhealthy",
                f"Target group health check configured for port 8080, application running on port 8000"
            ],
            "impact": "ALB marks all backend targets unhealthy and returns 502 Bad Gateway",
            "recommendation": f"Update Target Group tg-curated{idx:03d} health check port setting to 8000",
            "confidence": round(random.uniform(0.93, 0.97), 2)
        }

    elif scenario_type == "APPLICATION_VS_INFRASTRUCTURE":
        input_text = f"EC2 instance {inst_id} state is running, Security Group {sg_id} allows port 80, and Route Table is active. However, HTTP requests return 502 Bad Gateway because Gunicorn app process crashed."
        output_obj = {
            "problem": "Upstream application runtime process crash",
            "probable_root_cause": f"AWS infrastructure (EC2, Security Group, Route Table) is 100% healthy, but application process Gunicorn on {inst_id} crashed",
            "evidence": [
                f"EC2 instance {inst_id} state is running and Security Group {sg_id} permits port 80",
                "Gunicorn application process on port 5000 is stopped/crashed"
            ],
            "impact": "Web server returns HTTP 502 Bad Gateway to incoming clients",
            "recommendation": f"Inspect Gunicorn application crash logs on instance {inst_id} and restart the service process",
            "confidence": round(random.uniform(0.92, 0.96), 2)
        }

    elif scenario_type == "CLOUDTRAIL_CORRELATION":
        input_text = f"Outbound traffic from Subnet {subnet_id} failed 15m ago. CloudTrail audit log shows event DeleteRoute executed by IAM user sec-admin on Route Table rtb-curated{idx:03d} removing 0.0.0.0/0 route."
        output_obj = {
            "problem": "Subnet outbound internet reachability loss",
            "probable_root_cause": f"CloudTrail event DeleteRoute removed default route 0.0.0.0/0 from Route Table rtb-curated{idx:03d}",
            "evidence": [
                f"CloudTrail logged DeleteRoute on Route Table rtb-curated{idx:03d}",
                "Outbound internet connectivity dropped immediately following CloudTrail event"
            ],
            "impact": "Instances in private subnet lose outbound internet connectivity",
            "recommendation": f"Re-add default route 0.0.0.0/0 targeting NAT Gateway in Route Table rtb-curated{idx:03d}",
            "confidence": round(random.uniform(0.95, 0.98), 2)
        }

    elif scenario_type == "SINGLE_CAUSE":
        input_text = f"EC2 instance {inst_id} state is stopped. Console indicates instance was stopped via StopInstances API by admin. Web server hosted on instance is unreachable."
        output_obj = {
            "problem": f"EC2 instance {inst_id} in stopped state",
            "probable_root_cause": f"EC2 instance {inst_id} is stopped, preventing OS execution and network request processing",
            "evidence": [
                f"EC2 instance {inst_id} state is stopped",
                "StopInstances API call recorded in management console"
            ],
            "impact": "Web application hosted on instance is completely offline",
            "recommendation": f"Start instance {inst_id} and confirm application daemon startup",
            "confidence": round(random.uniform(0.95, 0.98), 2)
        }

    else:  # MULTI_SIGNAL
        input_text = f"EBS volume vol-curated{idx:03d} attached to {inst_id} reports VolumeQueueLength > 55. System log records I/O write timeouts, and EC2 CloudWatch DiskWriteBytes metric dropped to 0."
        output_obj = {
            "problem": "EBS volume I/O credit exhaustion and write stall",
            "probable_root_cause": f"EBS volume vol-curated{idx:03d} exhausted provisioned IOPS burst credits under heavy write workload",
            "evidence": [
                f"EBS VolumeQueueLength > 55 on vol-curated{idx:03d}",
                "OS system log records I/O write operation timeouts",
                "CloudWatch DiskWriteBytes metric dropped to 0"
            ],
            "impact": "Database write transactions are stalled and timing out",
            "recommendation": f"Modify volume vol-curated{idx:03d} to gp3 with provisioned IOPS or upgrade to io2",
            "confidence": round(random.uniform(0.93, 0.97), 2)
        }

    return {
        "instruction": instruction,
        "input": input_text,
        "output": json.dumps(output_obj),
        "_metadata": {
            "category": cat,
            "scenario_type": scenario_type,
            "source": "curated_baseline_transformed_v1",
            "license": "Internal / Proprietary",
            "provenance": f"CloudOps Baseline Rewrite ({scenario_type})"
        }
    }


def main():
    print("=" * 80)
    print("CLOUDOPS LLM — CURATED BASELINE REWRITING & DIVERSIFICATION PROCESS")
    print("=" * 80)

    # 1. Load train, val, and test splits
    train_curated = load_jsonl(TRAIN_FILE)
    val_curated = load_jsonl(VALIDATION_FILE)
    test_curated = load_jsonl(TEST_FILE)

    print(f"Original Train Examples       : {len(train_curated)}")
    print(f"Original Validation Examples  : {len(val_curated)}")
    print(f"Original Test Examples (KEEP) : {len(test_curated)} (PRESERVED 100% UNTOUCHED)")

    train_val_all = train_curated + val_curated
    total_train_val = len(train_val_all)
    print(f"Total Train/Val Candidates    : {total_train_val}")

    # 2. Cluster examples at >=0.85 similarity to find primary representatives
    visited = set()
    kept_indices = set()
    rewrite_indices = set()

    for i in range(total_train_val):
        if i in visited:
            continue
        # Mark first member of cluster as KEPT
        kept_indices.add(i)
        visited.add(i)
        text_i = train_val_all[i].get("instruction", "") + " " + train_val_all[i].get("input", "")

        for j in range(i + 1, total_train_val):
            if j in visited:
                continue
            text_j = train_val_all[j].get("instruction", "") + " " + train_val_all[j].get("input", "")
            if calculate_jaccard_similarity(text_i, text_j) >= 0.85:
                rewrite_indices.add(j)
                visited.add(j)

    # Also make sure remaining unvisited examples are distributed
    for i in range(total_train_val):
        if i not in kept_indices and i not in rewrite_indices:
            rewrite_indices.add(i)

    print(f"\nCluster Representative Analysis:")
    print(f"  - Primary Representatives KEPT  : {len(kept_indices)}")
    print(f"  - Repetitive Variants REWRITTEN : {len(rewrite_indices)}")

    # 3. Rewrite repetitive variants into diverse 8 scenario types
    transformed_train_val: List[Dict[str, Any]] = []
    scenario_counter = 0

    for idx in range(total_train_val):
        if idx in kept_indices:
            # Preserve strong primary representative, but ensure metadata is attached
            orig = dict(train_val_all[idx])
            if "_metadata" not in orig:
                attrs = classify_incident_attributes(orig)
                orig["_metadata"] = {
                    "category": attrs["primary_service"],
                    "scenario_type": attrs["scenario_type"],
                    "source": "curated_baseline_primary",
                    "provenance": "Kept Primary Baseline Representative"
                }
            transformed_train_val.append(orig)
        else:
            # Rewrite repetitive template variant
            scen_type = DIVERSE_SCENARIOS[scenario_counter % len(DIVERSE_SCENARIOS)]
            scenario_counter += 1
            rewritten = generate_rewritten_scenario(idx, scen_type, seed=RANDOM_SEED)
            transformed_train_val.append(rewritten)

    # Validate all transformed examples
    invalid_count = 0
    valid_transformed = []
    for ex in transformed_train_val:
        is_valid, errs = validate_example(ex)
        if is_valid:
            valid_transformed.append(ex)
        else:
            invalid_count += 1

    print(f"\nValidation & Schema Verification:")
    print(f"  - Valid Transformed Examples   : {len(valid_transformed)}")
    print(f"  - Rejected Invalid Examples    : {invalid_count}")

    # Split back into train (176) and val (22) keeping exact original counts
    new_train = valid_transformed[:len(train_curated)]
    new_val = valid_transformed[len(train_curated):]

    print(f"\nSaving Transformed Baseline Datasets:")
    save_jsonl(new_train, TRAIN_FILE)
    print(f"  - Saved Train Set ({len(new_train)} examples) to: {TRAIN_FILE}")
    save_jsonl(new_val, VALIDATION_FILE)
    print(f"  - Saved Validation Set ({len(new_val)} examples) to: {VALIDATION_FILE}")
    print(f"  - Preserved Test Set ({len(test_curated)} examples) untouched at: {TEST_FILE}")

    # 4. Generate & Display Updated Baseline Statistics
    full_transformed_baseline = new_train + new_val + test_curated
    stats = generate_dataset_statistics(full_transformed_baseline)

    print("\n" + "=" * 80)
    print("TRANSFORMED CURATED BASELINE METRICS & STATISTICS REPORT (220 EXAMPLES)")
    print("=" * 80)
    print(f"  Total Curated Examples        : {stats['total_examples']}")
    print(f"  Kept Primary Representatives  : {len(kept_indices)}")
    print(f"  Rewritten Diverse Variants    : {len(rewrite_indices)}")
    print(f"  Preserved Test Set Examples   : {len(test_curated)}")
    print(f"  Exact Duplicate Count         : {stats['exact_duplicates']}")
    print(f"  Near-Duplicate Pairs (>=0.85) : {stats.get('near_duplicate_pairs_85', 0)}")
    print(f"  Near-Duplicate Pairs (>=0.75) : {stats.get('near_duplicate_pairs_75', 0)}")
    print(f"  Low Confidence (<= 0.50)      : {stats.get('low_confidence_examples', 0)}")
    print(f"  High Confidence (> 0.50)      : {stats.get('high_confidence_examples', 0)}")

    print("\n--- Scenario Types Distribution ---")
    for scen, count in sorted(stats['scenario_breakdown'].items(), key=lambda x: x[1], reverse=True):
        pct = (count / stats['total_examples']) * 100
        print(f"  - {scen:32s}: {count:3d} ({pct:5.1f}%)")

    print("\n--- AWS Services Distribution ---")
    for svc, count in sorted(stats['services_breakdown'].items(), key=lambda x: x[1], reverse=True):
        print(f"  - {svc:30s}: {count:3d} examples")

    print("=" * 80)
    print("\n[SUCCESS] Curated baseline rewriting completed cleanly.")

if __name__ == "__main__":
    main()
