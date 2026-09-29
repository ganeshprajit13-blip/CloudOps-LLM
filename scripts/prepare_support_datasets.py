"""
Script to prepare, clean, filter, and combine HuggingFace datasets for CloudOps Support Agent QLoRA fine-tuning:
1. Debarun12/aws-enterprise-assistant-dataset
2. halencarjunior/cis_aws_foundation_benchmark_5_0
"""

import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple
from datasets import load_from_disk

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASETS_DIR = PROJECT_ROOT / "datasets"
OUTPUT_DIR = DATASETS_DIR / "support_training"

AWS_KEYWORDS = [
    "aws", "ec2", "vpc", "subnet", "security group", "route table", "internet gateway",
    "cloudwatch", "cloudtrail", "ssm", "iam", "load balancer", "target group", "s3",
    "rds", "kms", "policy", "mfa", "principal", "arn", "cloud", "instance", "network",
    "ingress", "egress", "port", "access key", "credential", "troubleshoot", "remediation",
    "compliance", "benchmark", "cis", "audit", "infrastructure", "telemetry", "metric",
    "log", "alarm", "parameter store", "secrets manager", "ebs", "efs", "elb"
]

def contains_aws_keywords(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in AWS_KEYWORDS)

def sanitize_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    return text.strip()

def process_aws_enterprise() -> Tuple[List[Dict[str, Any]], int, int]:
    ds_path = DATASETS_DIR / "aws_enterprise"
    print(f"\n--- Loading Dataset 1 from disk: {ds_path} ---")
    dataset = load_from_disk(str(ds_path))
    
    split_name = list(dataset.keys())[0] if hasattr(dataset, "keys") else "train"
    raw_data = dataset[split_name] if hasattr(dataset, "keys") else dataset
    
    total_original = len(raw_data)
    print(f"Original examples in aws-enterprise-assistant-dataset ({split_name}): {total_original}")
    print(f"Features: {raw_data.features}")
    
    cleaned = []
    seen = set()
    removed_count = 0

    for idx, row in enumerate(raw_data):
        instruction = sanitize_text(row.get("instruction", ""))
        input_text = sanitize_text(row.get("input", ""))
        output_text = sanitize_text(row.get("response", ""))
        
        # 1. Validation checks
        if not instruction or not output_text:
            removed_count += 1
            continue
            
        if len(instruction) < 5 or len(output_text) < 10:
            removed_count += 1
            continue

        # 2. Relevance check
        full_content = f"{instruction} {input_text} {output_text}"
        if not contains_aws_keywords(full_content):
            removed_count += 1
            continue

        # 3. Deduplication check
        dedup_key = f"{instruction.lower()}::{output_text.lower()[:100]}"
        if dedup_key in seen:
            removed_count += 1
            continue
        seen.add(dedup_key)

        record = {
            "instruction": instruction,
            "input": input_text,
            "output": output_text,
            "_metadata": {
                "source": "Debarun12/aws-enterprise-assistant-dataset",
                "category": "AWS Enterprise Support",
                "original_index": idx
            }
        }
        cleaned.append(record)

    print(f"Cleaned aws-enterprise-assistant: {len(cleaned)} usable, {removed_count} removed.")
    return cleaned, total_original, removed_count


def process_cis_aws() -> Tuple[List[Dict[str, Any]], int, int]:
    ds_path = DATASETS_DIR / "cis_aws"
    print(f"\n--- Loading Dataset 2 from disk: {ds_path} ---")
    dataset = load_from_disk(str(ds_path))
    
    split_name = list(dataset.keys())[0] if hasattr(dataset, "keys") else "train"
    raw_data = dataset[split_name] if hasattr(dataset, "keys") else dataset
    
    total_original = len(raw_data)
    print(f"Original examples in cis_aws_foundation_benchmark_5_0 ({split_name}): {total_original}")
    print(f"Features: {raw_data.features}")

    cleaned = []
    seen = set()
    removed_count = 0

    for idx, row in enumerate(raw_data):
        instruction = sanitize_text(row.get("instruction", ""))
        input_text = sanitize_text(row.get("input", ""))
        output_text = sanitize_text(row.get("output", ""))
        
        # 1. Validation checks
        if not instruction or not output_text:
            removed_count += 1
            continue
            
        if len(instruction) < 5 or len(output_text) < 10:
            removed_count += 1
            continue

        # 2. Relevance check
        full_content = f"{instruction} {input_text} {output_text}"
        if not contains_aws_keywords(full_content):
            removed_count += 1
            continue

        # 3. Deduplication check
        dedup_key = f"{instruction.lower()}::{output_text.lower()[:100]}"
        if dedup_key in seen:
            removed_count += 1
            continue
        seen.add(dedup_key)

        record = {
            "instruction": instruction,
            "input": input_text,
            "output": output_text,
            "_metadata": {
                "source": "halencarjunior/cis_aws_foundation_benchmark_5_0",
                "category": "CIS AWS Benchmark Security",
                "original_index": idx
            }
        }
        cleaned.append(record)

    print(f"Cleaned cis_aws_foundation_benchmark_5_0: {len(cleaned)} usable, {removed_count} removed.")
    return cleaned, total_original, removed_count


def save_jsonl(records: List[Dict[str, Any]], filepath: Path):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Saved {len(records)} records to {filepath}")


def main():
    print("=" * 80)
    print("CLOUDOPS SUPPORT AGENT — DATASET PREPARATION & PREPROCESSING")
    print("=" * 80)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Process Dataset 1
    ds1_cleaned, ds1_orig, ds1_removed = process_aws_enterprise()
    ds1_file = OUTPUT_DIR / "cleaned_aws_enterprise.jsonl"
    save_jsonl(ds1_cleaned, ds1_file)

    # 2. Process Dataset 2
    ds2_cleaned, ds2_orig, ds2_removed = process_cis_aws()
    ds2_file = OUTPUT_DIR / "cleaned_cis_aws.jsonl"
    save_jsonl(ds2_cleaned, ds2_file)

    # 3. Combine and Deduplicate Datasets
    print("\n--- Combining & Deduplicating Cleaned Datasets ---")
    combined = []
    combined_seen = set()
    dup_across = 0

    for item in ds1_cleaned + ds2_cleaned:
        key = f"{item['instruction'].lower()}::{item['output'].lower()[:100]}"
        if key in combined_seen:
            dup_across += 1
            continue
        combined_seen.add(key)
        combined.append(item)

    combined_file = OUTPUT_DIR / "combined_support_dataset.jsonl"
    save_jsonl(combined, combined_file)

    # 4. Final Validation & Schema Verification against QLoRA Pipeline
    print("\n--- QLoRA Pipeline Compatibility Verification ---")
    valid_count = 0
    schema_errors = []
    for idx, ex in enumerate(combined):
        if "instruction" in ex and "input" in ex and "output" in ex:
            if isinstance(ex["instruction"], str) and isinstance(ex["output"], str):
                valid_count += 1
            else:
                schema_errors.append(f"Row {idx} has non-string instruction or output")
        else:
            schema_errors.append(f"Row {idx} missing instruction/input/output key")

    print(f"Schema Validation Result: {valid_count}/{len(combined)} examples match instruction/input/output format perfectly.")
    if schema_errors:
        print(f"Schema Errors Found: {len(schema_errors)}")
    else:
        print("Schema Validation: 100% SUCCESSFUL — Compatible with QLoRA instruction dataset format!")

    # 5. Output Final Statistics
    print("\n" + "=" * 80)
    print("FINAL SUPPORT DATASET PREPARATION SUMMARY REPORT")
    print("=" * 80)
    print(f"1. Debarun12/aws-enterprise-assistant-dataset:")
    print(f"   - Original Examples : {ds1_orig}")
    print(f"   - Usable Examples   : {len(ds1_cleaned)}")
    print(f"   - Removed Examples  : {ds1_removed}")
    print(f"   - Output File       : {ds1_file}")

    print(f"\n2. halencarjunior/cis_aws_foundation_benchmark_5_0:")
    print(f"   - Original Examples : {ds2_orig}")
    print(f"   - Usable Examples   : {len(ds2_cleaned)}")
    print(f"   - Removed Examples  : {ds2_removed}")
    print(f"   - Output File       : {ds2_file}")

    print(f"\n3. Combined Support Agent Dataset:")
    print(f"   - Combined Total    : {len(combined)}")
    print(f"   - Cross-duplicates  : {dup_across}")
    print(f"   - Combined File     : {combined_file}")
    print(f"   - Final Record Format: ['instruction', 'input', 'output', '_metadata']")
    print(f"   - QLoRA Readiness  : READY FOR QLoRA FINE-TUNING")

if __name__ == "__main__":
    main()
