#!/usr/bin/env python3
"""
Comprehensive Support Agent Dataset Expansion Pipeline (Phases 1-12)
Ingests, filters, cleans, normalizes, categorizes, deduplicates, and combines:
1. Existing combined dataset (10,281 records)
2. Skilln/devops-qa-dataset
3. Omarrran/StackPulse_778K_QnA_Code_dataset ("full")
4. thegovind/azure-architecture-vqa
"""

import os
import sys
import re
import json
import random
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple
from datasets import load_dataset

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "datasets" / "support_training"
EXISTING_DATASET_PATH = OUTPUT_DIR / "support_agent_combined_dataset.jsonl"

FILTERED_DEVOPS_PATH = OUTPUT_DIR / "filtered_devops_qa.jsonl"
FILTERED_STACKPULSE_PATH = OUTPUT_DIR / "filtered_stackpulse.jsonl"
FILTERED_AZURE_PATH = OUTPUT_DIR / "filtered_azure_vqa.jsonl"
EXPANDED_DATASET_PATH = OUTPUT_DIR / "support_agent_expanded_dataset.jsonl"
REPORT_PATH = OUTPUT_DIR / "support_dataset_expansion_report.json"

# Relevance keyword lists for aggressive domain filtering
RELEVANT_KEYWORDS = [
    r"\baws\b", r"\bamazon\b", r"\bec2\b", r"\bvpc\b", r"\bsubnet\b", r"\broute table\b",
    r"\binternet gateway\b", r"\bigw\b", r"\bnat gateway\b", r"\bnat\b", r"\bsecurity group\b",
    r"\bnacl\b", r"\biam\b", r"\bs3\b", r"\brds\b", r"\blambda\b", r"\bcloudwatch\b",
    r"\bcloudtrail\b", r"\bssm\b", r"\bsystems manager\b", r"\bload balancer\b", r"\balb\b", r"\belb\b",
    r"\bazure\b", r"\bvirtual machine\b", r"\bvm\b", r"\bvnet\b", r"\bvirtual network\b",
    r"\bnsg\b", r"\bnetwork security group\b", r"\bazure storage\b", r"\bazure monitor\b",
    r"\brbac\b", r"\bdocker\b", r"\bkubernetes\b", r"\bk8s\b", r"\bterraform\b", r"\bansible\b",
    r"\blinux\b", r"\bdevops\b", r"\bci/cd\b", r"\bjenkins\b", r"\bgithub actions\b",
    r"\binfrastructure\b", r"\bobservability\b", r"\bmonitoring\b", r"\btroubleshooting\b",
    r"\bdeployment\b", r"\bcloud security\b", r"\bai\b", r"\bllm\b", r"\brag\b", r"\bqlora\b"
]

RELEVANT_REGEX = re.compile("|".join(RELEVANT_KEYWORDS), re.IGNORECASE)

IRRELEVANT_KEYWORDS = [
    r"\bandroid\b", r"\bios\b", r"\bswift\b", r"\bxcode\b", r"\bflutter\b", r"\breact native\b",
    r"\bgame\b", r"\bunity\b", r"\bunreal\b", r"\bopengl\b", r"\bhtml\b", r"\bcss\b",
    r"\bjavascript\b", r"\bjquery\b", r"\bphp\b", r"\bwordpress\b", r"\blaravel\b",
    r"\bjava\.swing\b", r"\bjavafx\b", r"\bc++\b", r"\bdataframe\b", r"\bpandas\b",
    r"\bexcel\b", r"\bmatlab\b", r"\bphotoshop\b", r"\bgameplay\b"
]

IRRELEVANT_REGEX = re.compile("|".join(IRRELEVANT_KEYWORDS), re.IGNORECASE)


def normalize_question(q: str) -> str:
    """Normalizes question text for robust deduplication."""
    if not q:
        return ""
    q_norm = q.lower().strip()
    q_norm = re.sub(r"[^\w\s]", "", q_norm)
    q_norm = re.sub(r"\s+", " ", q_norm)
    return q_norm


def classify_category(text: str) -> str:
    """Assigns domain category based on text content."""
    t_lower = text.lower()
    
    if "qlora" in t_lower:
        return "qlora"
    if "rag" in t_lower or "vector" in t_lower or "chromadb" in t_lower:
        return "rag"
    if "llm" in t_lower or "ai" in t_lower or "model" in t_lower:
        return "ai_llm"
    if "troubleshoot" in t_lower or "error" in t_lower or "unreachable" in t_lower:
        return "troubleshooting"
    
    # AWS sub-domains
    if "ec2" in t_lower:
        return "aws_ec2"
    if "vpc" in t_lower or "subnet" in t_lower or "route table" in t_lower or "igw" in t_lower or "nat" in t_lower:
        return "aws_vpc"
    if "nacl" in t_lower or "security group" in t_lower or "iam" in t_lower:
        return "aws_security"
    if "s3" in t_lower:
        return "aws_storage"
    if "rds" in t_lower or "dynamodb" in t_lower:
        return "aws_database"
    if "cloudwatch" in t_lower or "cloudtrail" in t_lower or "ssm" in t_lower:
        return "aws_monitoring"
    if "aws" in t_lower or "amazon" in t_lower:
        return "aws"
    
    # Azure sub-domains
    if "vnet" in t_lower or "virtual network" in t_lower or "nsg" in t_lower:
        return "azure_vnet"
    if "virtual machine" in t_lower or "azure vm" in t_lower:
        return "azure_vm"
    if "azure" in t_lower:
        return "azure"
    
    # DevOps & Infrastructure
    if "kubernetes" in t_lower or "k8s" in t_lower:
        return "kubernetes"
    if "docker" in t_lower or "container" in t_lower:
        return "docker"
    if "terraform" in t_lower or "ansible" in t_lower:
        return "terraform"
    if "linux" in t_lower or "ubuntu" in t_lower or "bash" in t_lower:
        return "linux"
    if "ci/cd" in t_lower or "jenkins" in t_lower or "pipeline" in t_lower:
        return "ci_cd"
    if "devops" in t_lower:
        return "devops"
    
    return "cloud_fundamentals"


def build_instruction(input_text: str, category: str) -> str:
    """Builds technical support instruction based on category."""
    cat_to_inst = {
        "aws_ec2": "Provide technical assistance for AWS EC2 instance configuration and management.",
        "aws_vpc": "Answer the user's AWS VPC and networking inquiry accurately.",
        "aws_security": "Provide AWS security, NACL, and Security Group guidance.",
        "aws_storage": "Answer the user's AWS S3 and storage inquiry.",
        "aws_database": "Provide technical support for AWS RDS and database services.",
        "aws_monitoring": "Explain AWS CloudWatch, CloudTrail, and SSM monitoring operations.",
        "aws": "Answer the user's AWS cloud infrastructure question accurately.",
        "azure_vnet": "Provide Azure VNet and networking technical guidance.",
        "azure_vm": "Answer the user's Azure Virtual Machine support question.",
        "azure": "Answer the user's Azure cloud architecture question accurately.",
        "docker": "Provide technical support for Docker containerization.",
        "kubernetes": "Provide Kubernetes cluster management and orchestration guidance.",
        "terraform": "Answer the user's Terraform infrastructure-as-code question.",
        "linux": "Provide Linux system administration and command-line support.",
        "ci_cd": "Explain CI/CD pipeline and DevOps automation practices.",
        "devops": "Provide technical guidance on DevOps tools and cloud practices.",
        "troubleshooting": "Assist the user in diagnosing and troubleshooting cloud infrastructure issues.",
        "ai_llm": "Explain AI, LLM, and machine learning architecture concepts.",
        "rag": "Provide technical explanations of RAG vector architecture.",
        "qlora": "Explain QLoRA parameter-efficient fine-tuning methodology.",
        "cloud_fundamentals": "Provide clear technical guidance on cloud computing fundamentals."
    }
    return cat_to_inst.get(category, "Answer the user's technical cloud infrastructure question accurately.")


def clean_text(text: str) -> str:
    """Strips HTML tags and excessive spaces from text."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def main():
    print("=" * 90)
    print("CLOUDOPS SUPPORT AGENT DATASET EXPANSION PIPELINE (PHASES 1-12)")
    print("=" * 90)

    # Step 1: Load Existing Combined Dataset
    print(f"\n[Step 1]: Loading existing dataset from '{EXISTING_DATASET_PATH}'...")
    existing_records = []
    existing_q_set: Set[str] = set()

    if EXISTING_DATASET_PATH.exists():
        with open(EXISTING_DATASET_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    existing_records.append(item)
                    q_raw = item.get("input") or item.get("instruction") or ""
                    q_norm = normalize_question(q_raw)
                    if q_norm:
                        existing_q_set.add(q_norm)
        print(f"Loaded {len(existing_records)} existing records. Unique questions indexed: {len(existing_q_set)}")
    else:
        print(f"[ERROR]: Existing dataset file not found at '{EXISTING_DATASET_PATH}'!")
        return

    seen_questions = set(existing_q_set)
    duplicates_removed = 0
    quality_rejections = 0

    # -------------------------------------------------------------------------
    # Step 2: Process Skilln/devops-qa-dataset (Phase 3)
    # -------------------------------------------------------------------------
    print("\n[Step 2]: Processing 'Skilln/devops-qa-dataset'...")
    devops_original = 0
    devops_accepted = 0
    filtered_devops = []

    try:
        from huggingface_hub import hf_hub_download
        devops_file_path = hf_hub_download(repo_id="Skilln/devops-qa-dataset", filename="devops_dataset.jsonl", repo_type="dataset")
        devops_ds = load_dataset("json", data_files=devops_file_path)
        split_data = devops_ds.get("train") or list(devops_ds.values())[0]
        devops_original = len(split_data)

        for idx, row in enumerate(split_data):
            question = clean_text(row.get("question") or row.get("question_body") or "")
            answer = clean_text(row.get("answer") or "")

            if not question or not answer or len(answer) < 30:
                quality_rejections += 1
                continue

            q_norm = normalize_question(question)
            if not q_norm or q_norm in seen_questions:
                duplicates_removed += 1
                continue

            # Check relevance
            if not RELEVANT_REGEX.search(question + " " + answer):
                quality_rejections += 1
                continue

            category = classify_category(question + " " + answer)
            instruction = build_instruction(question, category)

            record = {
                "instruction": instruction,
                "input": question,
                "output": answer,
                "_metadata": {
                    "source": "Skilln/devops-qa-dataset",
                    "category": category,
                    "original_index": str(idx),
                    "dataset": "devops-qa-dataset"
                }
            }

            seen_questions.add(q_norm)
            filtered_devops.append(record)
            devops_accepted += 1

    except Exception as e:
        print(f"[WARNING]: Error processing devops-qa-dataset: {e}")

    print(f"DevOps QA: Original={devops_original}, Accepted={devops_accepted}")

    # Write filtered_devops_qa.jsonl
    with open(FILTERED_DEVOPS_PATH, "w", encoding="utf-8") as f:
        for r in filtered_devops:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # -------------------------------------------------------------------------
    # Step 3: Process thegovind/azure-architecture-vqa (Phase 4)
    # -------------------------------------------------------------------------
    print("\n[Step 3]: Processing 'thegovind/azure-architecture-vqa'...")
    azure_original = 0
    azure_accepted = 0
    filtered_azure = []

    try:
        azure_ds = load_dataset("thegovind/azure-architecture-vqa")
        # Process train and test splits
        all_azure_rows = []
        for s_name in azure_ds.keys():
            all_azure_rows.extend(list(azure_ds[s_name]))
        azure_original = len(all_azure_rows)

        for idx, row in enumerate(all_azure_rows):
            question = clean_text(row.get("question") or row.get("query") or "")
            answer = clean_text(row.get("answer") or row.get("explanation") or row.get("description") or "")
            
            # Exclude visual image dependency (e.g., "in this image", "red box", "diagram below")
            visual_triggers = ["in this image", "shown in the image", "red box", "blue arrow", "diagram above", "diagram below", "in the diagram", "what color"]
            if any(v in question.lower() or v in answer.lower() for v in visual_triggers):
                quality_rejections += 1
                continue

            if not question or not answer or len(answer) < 25:
                quality_rejections += 1
                continue

            q_norm = normalize_question(question)
            if not q_norm or q_norm in seen_questions:
                duplicates_removed += 1
                continue

            category = classify_category("azure " + question + " " + answer)
            instruction = build_instruction(question, category)

            record = {
                "instruction": instruction,
                "input": question,
                "output": answer,
                "_metadata": {
                    "source": "thegovind/azure-architecture-vqa",
                    "category": category,
                    "original_index": str(idx),
                    "dataset": "azure-architecture-vqa"
                }
            }

            seen_questions.add(q_norm)
            filtered_azure.append(record)
            azure_accepted += 1

    except Exception as e:
        print(f"[WARNING]: Error processing azure-architecture-vqa: {e}")

    print(f"Azure VQA: Original={azure_original}, Accepted={azure_accepted}")

    # Write filtered_azure_vqa.jsonl
    with open(FILTERED_AZURE_PATH, "w", encoding="utf-8") as f:
        for r in filtered_azure:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # -------------------------------------------------------------------------
    # Step 4: Process Omarrran/StackPulse_778K_QnA_Code_dataset (Phase 2 & 9)
    # -------------------------------------------------------------------------
    print("\n[Step 4]: Processing 'Omarrran/StackPulse_778K_QnA_Code_dataset' ('full')...")
    stack_original = 0
    stack_accepted = 0
    filtered_stackpulse = []
    # Cap StackPulse to ~10,000 top quality unique records to prevent dataset imbalance
    STACKPULSE_CAP = 10000

    try:
        stack_ds = load_dataset("Omarrran/StackPulse_778K_QnA_Code_dataset", "full")
        split_data = stack_ds.get("train") or list(stack_ds.values())[0]
        stack_original = len(split_data)

        for idx, row in enumerate(split_data):
            if len(filtered_stackpulse) >= STACKPULSE_CAP:
                break

            question = clean_text(row.get("title") or "")
            body = clean_text(row.get("body_text") or row.get("question_body") or "")
            tags = str(row.get("tags") or "").lower()

            if not question or not body or len(body) < 40 or len(question) < 15:
                quality_rejections += 1
                continue

            full_text = (question + " " + body + " " + tags).lower()

            # Check tag / keyword relevance
            relevant_tags = ["aws", "amazon", "ec2", "vpc", "docker", "kubernetes", "k8s", "terraform", "azure", "linux", "devops", "ansible", "nginx", "sysadmin", "networking", "cloud"]
            is_relevant = any(t in tags for t in relevant_tags) or RELEVANT_REGEX.search(full_text)

            if not is_relevant:
                quality_rejections += 1
                continue

            # Reject irrelevant topics (Android, Swift, iOS, Game dev, etc.)
            if IRRELEVANT_REGEX.search(question):
                quality_rejections += 1
                continue

            q_norm = normalize_question(question)
            if not q_norm or q_norm in seen_questions:
                duplicates_removed += 1
                continue

            category = classify_category(full_text)
            instruction = build_instruction(question, category)

            record = {
                "instruction": instruction,
                "input": question,
                "output": body,
                "_metadata": {
                    "source": "Omarrran/StackPulse_778K_QnA_Code_dataset",
                    "category": category,
                    "original_index": str(idx),
                    "dataset": "StackPulse_778K"
                }
            }

            seen_questions.add(q_norm)
            filtered_stackpulse.append(record)
            stack_accepted += 1

    except Exception as e:
        print(f"[WARNING]: Error processing StackPulse: {e}")

    print(f"StackPulse: Original={stack_original}, Accepted={stack_accepted} (Capped at {STACKPULSE_CAP})")

    # Write filtered_stackpulse.jsonl
    with open(FILTERED_STACKPULSE_PATH, "w", encoding="utf-8") as f:
        for r in filtered_stackpulse:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # -------------------------------------------------------------------------
    # Step 5: Merge into support_agent_expanded_dataset.jsonl (Phase 10)
    # -------------------------------------------------------------------------
    print("\n[Step 5]: Combining existing records with new unique records...")
    
    all_expanded_records = []
    # 1. Existing 10,281 records
    all_expanded_records.extend(existing_records)
    # 2. Filtered new records
    all_expanded_records.extend(filtered_devops)
    all_expanded_records.extend(filtered_azure)
    all_expanded_records.extend(filtered_stackpulse)

    total_final_records = len(all_expanded_records)
    new_records_added = len(filtered_devops) + len(filtered_azure) + len(filtered_stackpulse)

    # Save support_agent_expanded_dataset.jsonl
    with open(EXPANDED_DATASET_PATH, "w", encoding="utf-8") as f:
        for r in all_expanded_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"Expanded Dataset Saved to '{EXPANDED_DATASET_PATH}'. Total Records: {total_final_records}")

    # Category distribution calculation
    category_counts: Dict[str, int] = {}
    source_counts: Dict[str, int] = {}

    for r in all_expanded_records:
        meta = r.get("_metadata", {})
        cat = meta.get("category", "general")
        src = meta.get("source", "existing_support_dataset")
        category_counts[cat] = category_counts.get(cat, 0) + 1
        source_counts[src] = source_counts.get(src, 0) + 1

    # -------------------------------------------------------------------------
    # Step 6: Generate JSON Report (Phase 11)
    # -------------------------------------------------------------------------
    report_data = {
        "existing_records": len(existing_records),
        "devops_original": devops_original,
        "devops_accepted": devops_accepted,
        "stackpulse_original": stack_original,
        "stackpulse_accepted": stack_accepted,
        "azure_original": azure_original,
        "azure_accepted": azure_accepted,
        "duplicates_removed": duplicates_removed,
        "quality_rejections": quality_rejections,
        "new_records_added": new_records_added,
        "final_records": total_final_records,
        "categories": category_counts,
        "records_by_source": source_counts,
        "output_files": {
            "filtered_devops_qa": str(FILTERED_DEVOPS_PATH),
            "filtered_stackpulse": str(FILTERED_STACKPULSE_PATH),
            "filtered_azure_vqa": str(FILTERED_AZURE_PATH),
            "support_agent_expanded_dataset": str(EXPANDED_DATASET_PATH),
            "support_dataset_expansion_report": str(REPORT_PATH)
        }
    }

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    # Print Terminal Summary
    print("\n" + "=" * 90)
    print("DATASET EXPANSION COMPLETE SUMMARY")
    print("=" * 90)
    print(f"Existing Records          : {len(existing_records)}")
    print(f"DevOps QA (Original/Acc)  : {devops_original} / {devops_accepted}")
    print(f"StackPulse (Original/Acc) : {stack_original} / {stack_accepted}")
    print(f"Azure VQA (Original/Acc)  : {azure_original} / {azure_accepted}")
    print(f"Duplicates Removed        : {duplicates_removed}")
    print(f"Quality Rejections        : {quality_rejections}")
    print(f"NEW Records Added         : {new_records_added}")
    print(f"FINAL TOTAL RECORDS       : {total_final_records}")
    print("=" * 90)

    # -------------------------------------------------------------------------
    # Step 7: Validation (Phase 12)
    # -------------------------------------------------------------------------
    print("\n[Step 7]: Running Validation Suite on expanded dataset...")
    val_passed = True
    validated_lines = 0

    with open(EXPANDED_DATASET_PATH, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            if not line.strip():
                val_passed = False
                print(f"  [VAL ERROR]: Line {idx} is empty.")
                break
            record = json.loads(line)
            for req_key in ["instruction", "input", "output", "_metadata"]:
                if req_key not in record:
                    val_passed = False
                    print(f"  [VAL ERROR]: Line {idx} missing required key '{req_key}'.")
                    break
            if not record.get("output") or (not record.get("input") and not record.get("instruction")):
                val_passed = False
                print(f"  [VAL ERROR]: Line {idx} has empty input and instruction, or empty output.")
                break
            validated_lines += 1

    print(f"  - Verified JSONL lines: {validated_lines} / {total_final_records}")
    assert validated_lines == total_final_records, "Validated line count mismatch!"
    assert len(existing_records) == 10281, "Original 10,281 records count violated!"

    # Verify loading via Hugging Face load_dataset("json")
    print("  - Verifying loading via Hugging Face load_dataset('json')...")
    hf_ds = load_dataset("json", data_files=str(EXPANDED_DATASET_PATH))
    print(f"  - HF Load Dataset Result: {hf_ds}")

    # Print 20 random final examples
    print("\n" + "=" * 90)
    print("20 RANDOM REPRESENTATIVE FINAL EXAMPLES")
    print("=" * 90)
    samples = random.sample(all_expanded_records, 20)
    for i, s in enumerate(samples, start=1):
        src_str = str(s['_metadata']['source']).encode('ascii', 'ignore').decode('ascii')
        cat_str = str(s['_metadata']['category']).encode('ascii', 'ignore').decode('ascii')
        inst_str = str(s['instruction']).encode('ascii', 'ignore').decode('ascii')
        inp_str = str(s.get('input') or s.get('instruction'))[:120].encode('ascii', 'ignore').decode('ascii')
        out_str = str(s['output'])[:160].replace('\n', ' ').encode('ascii', 'ignore').decode('ascii')
        print(f"\n[Sample #{i}]: Source: '{src_str}' | Category: '{cat_str}'")
        print(f"  Instruction : {inst_str}")
        print(f"  Input       : {inp_str}")
        print(f"  Output      : {out_str}...")

    print("\n" + "=" * 90)
    if val_passed:
        print("ALL DATASET EXPANSION & VALIDATION CHECKS PASSED PERFECTLY!")
    print("=" * 90)


if __name__ == "__main__":
    main()
