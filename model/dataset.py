import json
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple
from model.config import (
    RANDOM_SEED,
    TEST_FILE,
    TEST_RATIO,
    TRAIN_FILE,
    TRAIN_RATIO,
    VALIDATION_FILE,
    VAL_RATIO,
)

# Secret scanning regexes
SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS Access Key ID
    re.compile(r"(?i)aws_secret_access_key\s*=\s*['\"][A-Za-z0-9/+=]{40}['\"]"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9\-\._~\+\/]+=*"),
    re.compile(r"(?i)password\s*[:=]\s*['\"][^'\"]+['\"]"),
]

PROMPT_VARIATIONS = [
    "Analyze this AWS infrastructure incident and determine the probable root cause.",
    "Why is the application or website unreachable based on this cloud telemetry?",
    "Identify the likely root cause and recommend an advisory remediation.",
    "Review this cloud incident telemetry and extract factual evidence and probable root cause.",
    "What is causing this infrastructure failure?",
    "Analyze the provided cloud signals and provide a safe advisory diagnosis.",
]


def scan_for_secrets(text: str) -> List[str]:
    """Scans input text for accidental secrets (AWS keys, passwords, tokens)."""
    found = []
    for pattern in SECRET_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            found.extend(matches)
    return found


def validate_example(example: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validates a single instruction-tuning training example against quality, schema, and security rules."""
    errors = []

    # 1. Top-level keys
    for req_key in ["instruction", "input", "output"]:
        if req_key not in example or not example[req_key]:
            errors.append(f"Missing or empty required top-level key: '{req_key}'")

    if errors:
        return False, errors

    # Secret scanning on instruction and input
    secrets_in_input = scan_for_secrets(example["instruction"] + " " + example["input"])
    if secrets_in_input:
        errors.append(f"Potential secret detected in input: {secrets_in_input}")

    # 2. Parse output payload
    output_raw = example["output"]
    if isinstance(output_raw, str):
        try:
            output_obj = json.loads(output_raw)
        except Exception as e:
            errors.append(f"Output string is not valid JSON: {e}")
            return False, errors
    elif isinstance(output_raw, dict):
        output_obj = output_raw
    else:
        errors.append("Output must be a JSON string or dict")
        return False, errors

    # Secret scanning on output string
    secrets_in_output = scan_for_secrets(json.dumps(output_obj))
    if secrets_in_output:
        errors.append(f"Potential secret detected in output: {secrets_in_output}")

    # 3. Check diagnosis JSON required fields
    diag_fields = ["problem", "probable_root_cause", "evidence", "impact", "recommendation", "confidence"]
    for f in diag_fields:
        if f not in output_obj or output_obj[f] is None:
            errors.append(f"Missing required field in output JSON: '{f}'")

    if errors:
        return False, errors

    # 4. Check confidence numeric bounds
    conf = output_obj.get("confidence")
    if not isinstance(conf, (int, float)) or not (0.0 <= conf <= 1.0):
        errors.append(f"Confidence must be a float between 0.0 and 1.0, got: {conf}")

    # 5. Check evidence list
    evidence = output_obj.get("evidence")
    if not isinstance(evidence, list) or len(evidence) == 0:
        errors.append("Evidence must be a non-empty list of strings")

    # 6. Check for non-causal claims in evidence
    if isinstance(evidence, list):
        for ev in evidence:
            if "root cause" in str(ev).lower() or "caused the outage" in str(ev).lower():
                errors.append(f"Evidence contains causal claim: '{ev}'")

    # 7. Check for unsafe remediation commands
    rec = str(output_obj.get("recommendation", "")).lower()
    unsafe_keywords = ["automatically terminate", "automatically delete", "auto-remediate", "restart instance automatically"]
    for kw in unsafe_keywords:
        if kw in rec:
            errors.append(f"Recommendation contains unsafe autonomous instruction: '{kw}'")

    return len(errors) == 0, errors


def generate_synthetic_dataset(count: int = 220) -> List[Dict[str, Any]]:
    """Generates synthetic instruction-tuning dataset covering 8 categories."""
    random.seed(RANDOM_SEED)

    categories = [
        "EC2", "Security Groups", "Networking", "Load Balancer",
        "CloudWatch", "CloudTrail", "IAM", "Multi-Signal & Uncertainty"
    ]

    examples: List[Dict[str, Any]] = []

    for i in range(count):
        cat = categories[i % len(categories)]
        inst_id = f"i-0example{i:03d}"
        vpc_id = f"vpc-0example{i:03d}"
        sg_id = f"sg-0example{i:03d}"
        subnet_id = f"subnet-0example{i:03d}"
        instruction = random.choice(PROMPT_VARIATIONS)

        if cat == "Security Groups":
            port = random.choice([443, 80, 22, 8080, 3306])
            service_name = {443: "HTTPS", 80: "HTTP", 22: "SSH", 8080: "App", 3306: "MySQL"}[port]
            input_text = f"EC2 instance {inst_id} state is running. CPU utilization is {random.randint(15, 45)}%. Security Group {sg_id} inbound rules do not allow TCP port {port}. Users report connection failure."
            output_obj = {
                "problem": f"{service_name} connection failure on port {port}",
                "probable_root_cause": f"Security Group {sg_id} is likely blocking inbound {service_name} traffic on TCP port {port}",
                "evidence": [
                    f"EC2 instance {inst_id} state is running",
                    f"Inbound TCP port {port} is missing from Security Group {sg_id}"
                ],
                "impact": f"Clients cannot establish {service_name} connections to the application",
                "recommendation": f"Review Security Group {sg_id} inbound rules and allow TCP {port} from expected source IPs if access is required",
                "confidence": round(random.uniform(0.90, 0.96), 2)
            }

        elif cat == "EC2":
            cpu = random.randint(85, 99)
            input_text = f"EC2 instance {inst_id} CPU utilization is {cpu}% sustained for {random.randint(15, 45)} minutes. Memory usage is {random.randint(60, 75)}%. CloudWatch CPUAlarm triggered."
            output_obj = {
                "problem": f"Severe instance CPU saturation on {inst_id}",
                "probable_root_cause": f"High computational workload or resource leak on instance {inst_id} causing CPU saturation at {cpu}%",
                "evidence": [
                    f"EC2 instance {inst_id} CPU utilization is {cpu}%",
                    "CloudWatch CPUAlarm is in ALARM state"
                ],
                "impact": "Application latency is severely degraded and HTTP requests are timing out",
                "recommendation": "Inspect active process utilization on the instance, scale out additional instances behind an ALB, or upgrade to a higher capacity instance type",
                "confidence": round(random.uniform(0.88, 0.95), 2)
            }

        elif cat == "Load Balancer":
            reason = random.choice(["Target.FailedHealthChecks", "Target.ResponseCodeMismatch", "Target.Timeout"])
            input_text = f"ALB prod-alb target group web-tg reports target instance {inst_id} as unhealthy. Reason: {reason}. EC2 instance state is running."
            output_obj = {
                "problem": "Load Balancer target reported as unhealthy",
                "probable_root_cause": f"The application service on {inst_id} is failing ALB health checks due to {reason}",
                "evidence": [
                    f"EC2 instance {inst_id} state is running",
                    f"ALB target {inst_id} health state is unhealthy with reason {reason}"
                ],
                "impact": "The load balancer stops routing traffic to {inst_id}, reducing overall application capacity",
                "recommendation": f"Inspect web service health logs on instance {inst_id} and verify target health check path and port configuration",
                "confidence": round(random.uniform(0.89, 0.94), 2)
            }

        elif cat == "Networking":
            input_text = f"Subnet {subnet_id} in VPC {vpc_id} cannot reach external endpoints. Route Table rtb-0ex{i:03d} contains local route 10.0.0.0/16 but lacks default route 0.0.0.0/0 to Internet Gateway."
            output_obj = {
                "problem": "Outbound internet connectivity failure in subnet",
                "probable_root_cause": f"Route Table rtb-0ex{i:03d} lacks a default route (0.0.0.0/0) pointing to an Internet Gateway or NAT Gateway",
                "evidence": [
                    f"Subnet {subnet_id} is associated with Route Table rtb-0ex{i:03d}",
                    "Route Table rtb-0ex{i:03d} lacks a default route to 0.0.0.0/0"
                ],
                "impact": "Instances in subnet {subnet_id} cannot communicate with external internet services or APIs",
                "recommendation": f"Review Route Table rtb-0ex{i:03d} and add a route for 0.0.0.0/0 targeting an Internet Gateway or NAT Gateway as appropriate",
                "confidence": round(random.uniform(0.92, 0.97), 2)
            }

        elif cat == "CloudTrail":
            event = random.choice(["AuthorizeSecurityGroupIngress", "RevokeSecurityGroupIngress", "ModifyInstanceAttribute", "DeleteRoute"])
            input_text = f"Recent CloudTrail event {event} executed by principal admin-user affecting resource {sg_id} {random.randint(5, 30)} minutes ago. Users report unexpected connectivity failure."
            output_obj = {
                "problem": f"Infrastructure anomaly following recent {event} event",
                "probable_root_cause": f"Recent CloudTrail change {event} on resource {sg_id} modified network access permissions shortly before the incident",
                "evidence": [
                    f"CloudTrail event {event} performed on {sg_id} by principal admin-user",
                    "Connectivity failure occurred immediately after the change"
                ],
                "impact": "System configuration state changed, impacting application network reachability",
                "recommendation": f"Audit recent CloudTrail event {event} parameters and revert unauthorized or incorrect rule modifications on {sg_id}",
                "confidence": round(random.uniform(0.87, 0.93), 2)
            }

        elif cat == "CloudWatch":
            metric = random.choice(["NetworkIn", "DiskReadOps", "CPUUtilization"])
            input_text = f"CloudWatch alarm triggered for metric {metric} on instance {inst_id}. Observed value is unusually high compared to historical baseline. Instance state is running."
            output_obj = {
                "problem": f"CloudWatch metric anomaly for {metric}",
                "probable_root_cause": f"Unexpected spike in {metric} on instance {inst_id} exceeding baseline threshold",
                "evidence": [
                    f"EC2 instance {inst_id} is running",
                    f"CloudWatch metric {metric} exceeded threshold limit"
                ],
                "impact": "Resource utilization imbalance may cause application degradation or I/O bottleneck",
                "recommendation": f"Investigate process activity and network traffic logs on instance {inst_id} during the alarm window",
                "confidence": round(random.uniform(0.85, 0.91), 2)
            }

        elif cat == "IAM":
            action = random.choice(["s3:GetObject", "cloudwatch:PutMetricData", "dynamodb:Query"])
            input_text = f"Application on instance {inst_id} logged error AccessDenied when performing action {action}. IAM instance profile role does not grant permission for {action}."
            output_obj = {
                "problem": f"IAM permission denied for {action}",
                "probable_root_cause": f"The IAM instance profile role attached to {inst_id} lacks policy permission for action {action}",
                "evidence": [
                    f"Application error log records AccessDenied on {action}",
                    f"Attached IAM role policy omits permission for {action}"
                ],
                "impact": "Application feature dependent on {action} fails execution",
                "recommendation": f"Review and update the IAM policy attached to the instance role to include required permission for {action}",
                "confidence": round(random.uniform(0.92, 0.96), 2)
            }

        else:  # Multi-Signal & Uncertainty
            if i % 2 == 0:
                input_text = f"Application latency is high. EC2 instance {inst_id} CPU is 40%. No memory metrics or disk I/O logs available. No recent CloudTrail events."
                output_obj = {
                    "problem": "Application performance degradation",
                    "probable_root_cause": "Available telemetry is insufficient to determine a definitive root cause",
                    "evidence": [
                        f"EC2 instance {inst_id} CPU is normal at 40%",
                        "Memory and disk I/O metrics are unavailable"
                    ],
                    "impact": "End users experience latency, but specific bottleneck remains unverified",
                    "recommendation": "Enable memory and disk telemetry collectors and review application runtime logs before selecting remediation",
                    "confidence": 0.40
                }
            else:
                input_text = f"EC2 instance {inst_id} state is running. CPU utilization is 28%. ALB target {inst_id} is healthy. Inbound TCP port 443 is missing from Security Group {sg_id}. User HTTPS requests fail."
                output_obj = {
                    "problem": "HTTPS website access failure",
                    "probable_root_cause": f"Security Group {sg_id} is blocking HTTPS port 443 despite healthy ALB target state",
                    "evidence": [
                        f"EC2 instance {inst_id} is running with 28% CPU",
                        f"ALB target status for {inst_id} is healthy",
                        f"Security Group {sg_id} lacks inbound TCP 443 rule"
                    ],
                    "impact": "External HTTPS connections cannot reach the load balancer or backend instance",
                    "recommendation": f"Review Security Group {sg_id} inbound rules and grant access to TCP 443 from client CIDRs",
                    "confidence": 0.94
                }

        examples.append({
            "instruction": instruction,
            "input": input_text,
            "output": json.dumps(output_obj),
        })

    return examples


def calculate_jaccard_similarity(text1: str, text2: str) -> float:
    """Calculates word-token Jaccard similarity between two text strings."""
    words1 = set(re.findall(r"\w+", text1.lower()))
    words2 = set(re.findall(r"\w+", text2.lower()))
    if not words1 or not words2:
        return 0.0
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    return intersection / union if union > 0 else 0.0


def find_near_duplicates(examples: List[Dict[str, Any]], threshold: float = 0.85) -> List[Tuple[int, int, float]]:
    """Finds pairs of examples with Jaccard similarity >= threshold."""
    near_dups = []
    n = len(examples)
    for i in range(n):
        text_i = examples[i].get("instruction", "") + " " + examples[i].get("input", "")
        for j in range(i + 1, n):
            text_j = examples[j].get("instruction", "") + " " + examples[j].get("input", "")
            sim = calculate_jaccard_similarity(text_i, text_j)
            if sim >= threshold:
                near_dups.append((i, j, sim))
    return near_dups


def classify_incident_attributes(example: Dict[str, Any]) -> Dict[str, Any]:
    """Classifies an incident example by AWS service, failure category, scenario type, and signal attributes."""
    inp = (example.get("input", "") + " " + example.get("instruction", "")).lower()
    meta = example.get("_metadata", {})

    output_raw = example.get("output", "")
    if isinstance(output_raw, str):
        try:
            output_obj = json.loads(output_raw)
        except Exception:
            output_obj = {}
    elif isinstance(output_raw, dict):
        output_obj = output_raw
    else:
        output_obj = {}

    cause = str(output_obj.get("probable_root_cause", "")).lower()
    evidence = output_obj.get("evidence", [])
    conf = float(output_obj.get("confidence", 0.8))

    services = []
    if "category" in meta and meta["category"]:
        services.append(meta["category"])

    service_keywords = {
        "EC2": ["ec2", "instance", "cpu utilization", "running state"],
        "EBS": ["ebs", "volume", "iops", "volumequeuelength"],
        "VPC": ["vpc", "enablednshostnames", "cidr"],
        "Subnets": ["subnet", "availableipaddresscount", "eni"],
        "Route Tables": ["route table", "rtb-", "0.0.0.0/0", "default route"],
        "Internet Gateway": ["internet gateway", "igw-", "elastic ip"],
        "NAT Gateway": ["nat gateway", "nat-", "blackhole"],
        "Security Groups": ["security group", "sg-", "inbound rule", "port 80", "port 443"],
        "Network ACLs": ["network acl", "nacl-", "deny tcp"],
        "ALB": ["alb", "load balancer", "target group", "502 bad gateway"],
        "CloudWatch": ["cloudwatch", "alarm", "metric", "threshold"],
        "CloudTrail": ["cloudtrail", "authorizesecuritygroupingress", "revokesecuritygroupingress"],
        "IAM": ["iam", "accessdenied", "policy", "s3:getobject", "s3:putobject"],
        "S3": ["s3", "bucket", "object", "getobject", "putobject"],
        "RDS": ["rds", "database", "freestoragespace", "mysql", "postgresql"],
        "Lambda": ["lambda", "function timeout", "task timed out"],
        "ECS": ["ecs", "cluster", "container", "task stopped"],
        "EKS": ["eks", "pod", "oomkilled", "memory limit"],
        "Auto Scaling": ["auto scaling", "asg-", "launch template"],
        "Route 53/DNS": ["route 53", "dns", "servfail", "alias"],
        "TLS/SSL": ["tls", "ssl", "certificate", "err_cert"],
    }
    for svc, kws in service_keywords.items():
        if any(kw in inp for kw in kws) and svc not in services:
            services.append(svc)
    if not services:
        services = ["General/Other"]

    if "timeout" in inp or "unreachable" in inp or "cannot connect" in inp:
        cat = "Connectivity / Network Failure"
    elif "cpu" in inp or "memory" in inp or "oom" in inp or "capacity" in inp:
        cat = "Resource Exhaustion / Performance"
    elif "accessdenied" in inp or "denied" in inp or "403" in inp:
        cat = "Permissions / Security Failure"
    elif "cloudtrail" in inp or "modified" in inp or "revoked" in inp:
        cat = "Recent Configuration Change"
    else:
        cat = "Service / Application Error"

    scenario_type = meta.get("scenario_type")
    is_multi_signal = (
        scenario_type in [
            "MULTI_SIGNAL", "COMPETING_CAUSE", "INSUFFICIENT_EVIDENCE",
            "MISLEADING_SYMPTOM", "CLOUDTRAIL_CORRELATION", "CONFIGURATION_MISMATCH",
            "APPLICATION_VS_INFRASTRUCTURE"
        ]
        or (isinstance(evidence, list) and (len(evidence) > 1 or "and" in inp))
    )
    is_competing = scenario_type == "COMPETING_CAUSE" or "despite" in cause or "competing" in cause or "however" in inp
    is_uncertainty = scenario_type == "INSUFFICIENT_EVIDENCE" or conf <= 0.50 or "insufficient" in cause

    return {
        "services": services,
        "primary_service": services[0],
        "category": cat,
        "scenario_type": scenario_type or ("INSUFFICIENT_EVIDENCE" if is_uncertainty else ("MULTI_SIGNAL" if is_multi_signal else "SINGLE_CAUSE")),
        "confidence": conf,
        "is_multi_signal": is_multi_signal,
        "is_competing": is_competing,
        "is_uncertainty": is_uncertainty,
    }


def generate_dataset_statistics(examples: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generates detailed metadata, scenario coverage, and balance statistics for a dataset."""
    total = len(examples)
    service_counts: Dict[str, int] = {}
    category_counts: Dict[str, int] = {}
    scenario_counts: Dict[str, int] = {}
    multi_signal_count = 0
    competing_count = 0
    uncertainty_count = 0
    low_confidence_count = 0
    high_confidence_count = 0

    seen_keys = set()
    exact_duplicates = 0

    for ex in examples:
        key = (ex.get("instruction", ""), ex.get("input", ""))
        if key in seen_keys:
            exact_duplicates += 1
        else:
            seen_keys.add(key)

        attrs = classify_incident_attributes(ex)
        for s in attrs["services"]:
            service_counts[s] = service_counts.get(s, 0) + 1

        cat = attrs["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

        scen = attrs["scenario_type"]
        scenario_counts[scen] = scenario_counts.get(scen, 0) + 1

        if attrs["confidence"] <= 0.50:
            low_confidence_count += 1
        else:
            high_confidence_count += 1

        if attrs["is_multi_signal"]:
            multi_signal_count += 1
        if attrs["is_competing"]:
            competing_count += 1
        if attrs["is_uncertainty"]:
            uncertainty_count += 1

    near_dups_85 = find_near_duplicates(examples, threshold=0.85)
    near_dups_75 = find_near_duplicates(examples, threshold=0.75)

    return {
        "total_examples": total,
        "exact_duplicates": exact_duplicates,
        "near_duplicate_pairs": len(near_dups_85),
        "near_duplicate_pairs_85": len(near_dups_85),
        "near_duplicate_pairs_75": len(near_dups_75),
        "multi_signal_examples": multi_signal_count,
        "competing_cause_examples": competing_count,
        "uncertainty_examples": uncertainty_count,
        "low_confidence_examples": low_confidence_count,
        "high_confidence_examples": high_confidence_count,
        "scenario_breakdown": scenario_counts,
        "services_breakdown": service_counts,
        "categories_breakdown": category_counts,
    }


def find_cross_near_duplicates(
    list1: List[Dict[str, Any]], list2: List[Dict[str, Any]], threshold: float = 0.85
) -> List[Tuple[int, int, float]]:
    """Finds near-duplicate pairs across two separate dataset lists."""
    cross_dups = []
    for i, ex1 in enumerate(list1):
        text1 = ex1.get("instruction", "") + " " + ex1.get("input", "")
        for j, ex2 in enumerate(list2):
            text2 = ex2.get("instruction", "") + " " + ex2.get("input", "")
            sim = calculate_jaccard_similarity(text1, text2)
            if sim >= threshold:
                cross_dups.append((i, j, sim))
    return cross_dups


def generate_decoupled_dataset_statistics(
    curated_examples: List[Dict[str, Any]],
    generated_examples: List[Dict[str, Any]],
    preserved_test_examples: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Generates decoupled statistics separately for Curated, Generated, and Combined datasets."""
    stats_curated = generate_dataset_statistics(curated_examples)
    stats_generated = generate_dataset_statistics(generated_examples)

    # Avoid duplicate inclusion of preserved_test_examples if already in curated_examples
    combined_seen = set()
    combined_unique = []
    for ex in curated_examples + generated_examples:
        key = (ex.get("instruction", ""), ex.get("input", ""))
        if key not in combined_seen:
            combined_seen.add(key)
            combined_unique.append(ex)

    stats_combined = generate_dataset_statistics(combined_unique)

    cross_dups_85 = find_cross_near_duplicates(curated_examples, generated_examples, threshold=0.85)
    cross_dups_75 = find_cross_near_duplicates(curated_examples, generated_examples, threshold=0.75)

    signatures = set()
    for ex in generated_examples:
        meta = ex.get("_metadata", {})
        cat = meta.get("category", "General")
        scen = meta.get("scenario_type", "SINGLE_CAUSE")
        inp_prefix = ex.get("input", "")[:40]
        signatures.add((cat, scen, inp_prefix))

    sig_uniqueness_rate = (len(signatures) / len(generated_examples)) if generated_examples else 1.0

    return {
        "curated": stats_curated,
        "generated": stats_generated,
        "combined": stats_combined,
        "cross_near_duplicates_85": len(cross_dups_85),
        "cross_near_duplicates_75": len(cross_dups_75),
        "generated_signature_uniqueness_rate": sig_uniqueness_rate,
        "generated_unique_signatures_count": len(signatures),
    }


def group_and_split_dataset(
    examples: List[Dict[str, Any]],
    train_ratio: float = TRAIN_RATIO,
    val_ratio: float = VAL_RATIO,
    test_ratio: float = TEST_RATIO,
    seed: int = RANDOM_SEED,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Groups related incident variants together before splitting to prevent
    near-duplicate data leakage across train, val, and test splits.
    """
    random.seed(seed)

    seen = set()
    unique_examples = []
    for ex in examples:
        key = (ex.get("instruction", ""), ex.get("input", ""))
        if key not in seen:
            seen.add(key)
            unique_examples.append(ex)

    groups: List[List[Dict[str, Any]]] = []
    for ex in unique_examples:
        text_ex = ex.get("instruction", "") + " " + ex.get("input", "")
        placed = False
        for group in groups:
            text_rep = group[0].get("instruction", "") + " " + group[0].get("input", "")
            if calculate_jaccard_similarity(text_ex, text_rep) >= 0.70:
                group.append(ex)
                placed = True
                break
        if not placed:
            groups.append([ex])

    random.shuffle(groups)

    n_total = len(unique_examples)
    n_train_target = int(n_total * train_ratio)
    n_val_target = int(n_total * val_ratio)

    train_set, val_set, test_set = [], [], []
    curr_train = 0
    curr_val = 0

    for group in groups:
        if curr_train < n_train_target:
            train_set.extend(group)
            curr_train += len(group)
        elif curr_val < n_val_target:
            val_set.extend(group)
            curr_val += len(group)
        else:
            test_set.extend(group)

    return train_set, val_set, test_set


def split_dataset(
    examples: List[Dict[str, Any]],
    train_ratio: float = TRAIN_RATIO,
    val_ratio: float = VAL_RATIO,
    test_ratio: float = TEST_RATIO,
    seed: int = RANDOM_SEED,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Splits dataset deterministically into train, validation, and test sets without data leakage."""
    return group_and_split_dataset(examples, train_ratio, val_ratio, test_ratio, seed)


def save_jsonl(examples: List[Dict[str, Any]], filepath: Path):
    """Saves dataset examples into JSONL format."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")


def load_jsonl(filepath: Path) -> List[Dict[str, Any]]:
    """Loads JSONL dataset examples from file."""
    examples = []
    if not filepath.exists():
        return examples
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                examples.append(json.loads(line))
    return examples
