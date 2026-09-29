#!/usr/bin/env python3
"""
Comprehensive Final Quality Audit Suite for CloudOps Support Agent Expanded Dataset.
Audits 25,475 records in datasets/support_training/support_agent_expanded_dataset.jsonl.
"""

import os
import sys
import re
import json
import random
from collections import defaultdict, Counter
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPANDED_DATASET_PATH = PROJECT_ROOT / "datasets" / "support_training" / "support_agent_expanded_dataset.jsonl"
ORIGINAL_DATASET_PATH = PROJECT_ROOT / "datasets" / "support_training" / "support_agent_combined_dataset.jsonl"
AUDIT_REPORT_PATH = PROJECT_ROOT / "datasets" / "support_training" / "support_agent_quality_audit_report.json"

def normalize_text(text: str) -> str:
    if not text:
        return ""
    t = text.lower().strip()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t

def get_shingles(text: str, k: int = 3) -> Set[str]:
    words = text.split()
    if len(words) < k:
        return set(words)
    return set(" ".join(words[i:i+k]) for i in range(len(words) - k + 1))

def jaccard_similarity(set1: Set[str], set2: Set[str]) -> float:
    if not set1 or not set2:
        return 0.0
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / union if union > 0 else 0.0

def main():
    print("=" * 90)
    print("CLOUDOPS SUPPORT AGENT EXPANDED DATASET QUALITY AUDIT")
    print("=" * 90)

    # 1. Load Dataset
    print(f"\n[1] Loading dataset from '{EXPANDED_DATASET_PATH}'...")
    if not EXPANDED_DATASET_PATH.exists():
        print(f"ERROR: File not found at {EXPANDED_DATASET_PATH}")
        return

    records = []
    line_errors = 0
    missing_fields_count = 0

    with open(EXPANDED_DATASET_PATH, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                for req_field in ["instruction", "input", "output", "_metadata"]:
                    if req_field not in data:
                        missing_fields_count += 1
                records.append(data)
            except Exception as e:
                line_errors += 1

    total_records = len(records)
    print(f"Loaded {total_records} records. Line Errors: {line_errors}, Missing Required Field Records: {missing_fields_count}")

    # 2. Exact Duplicate Audit
    print("\n[2] Analyzing Exact Duplicates...")
    q_map = defaultdict(list)
    qa_map = defaultdict(list)
    exact_rec_map = defaultdict(list)

    for idx, r in enumerate(records):
        q = r.get("input") or r.get("instruction") or ""
        a = r.get("output", "")
        q_norm = normalize_text(q)
        qa_norm = (q_norm, normalize_text(a[:200]))
        rec_json = json.dumps(r, sort_keys=True)

        q_map[q_norm].append(idx)
        qa_map[qa_norm].append(idx)
        exact_rec_map[rec_json].append(idx)

    dup_q_groups = {k: v for k, v in q_map.items() if len(v) > 1 and k}
    dup_qa_groups = {k: v for k, v in qa_map.items() if len(v) > 1 and k[0]}
    dup_rec_groups = {k: v for k, v in exact_rec_map.items() if len(v) > 1}

    dup_q_count = sum(len(v) - 1 for v in dup_q_groups.values())
    dup_qa_count = sum(len(v) - 1 for v in dup_qa_groups.values())
    dup_rec_count = sum(len(v) - 1 for v in dup_rec_groups.values())

    print(f"  - Duplicate Question entries (beyond first instance) : {dup_q_count} across {len(dup_q_groups)} groups")
    print(f"  - Duplicate Q&A pairs (beyond first instance)       : {dup_qa_count} across {len(dup_qa_groups)} groups")
    print(f"  - Duplicate Complete records                        : {dup_rec_count}")

    # 3. Near-Duplicate Audit (Semantic / Shingle Jaccard overlap)
    print("\n[3] Analyzing Near-Duplicates & Semantic Clustering...")
    # Sample subset or cluster by first 3 words prefix for efficiency
    prefix_map = defaultdict(list)
    for idx, r in enumerate(records):
        q = r.get("input") or r.get("instruction") or ""
        q_norm = normalize_text(q)
        words = q_norm.split()
        prefix = " ".join(words[:2]) if len(words) >= 2 else q_norm
        prefix_map[prefix].append((idx, q_norm, get_shingles(q_norm, k=2)))

    near_dup_groups = []
    seen_near_dup_indices = set()

    for prefix, items in prefix_map.items():
        if len(items) < 2 or len(items) > 100:  # Skip generic singletons or overly broad
            continue
        for i in range(len(items)):
            idx1, q1, sh1 = items[i]
            if idx1 in seen_near_dup_indices:
                continue
            group = [q1]
            for j in range(i + 1, len(items)):
                idx2, q2, sh2 = items[j]
                if q1 != q2 and jaccard_similarity(sh1, sh2) >= 0.65:
                    group.append(q2)
                    seen_near_dup_indices.add(idx2)
            if len(group) > 1:
                seen_near_dup_indices.add(idx1)
                near_dup_groups.append(group)

    print(f"  - Identified {len(near_dup_groups)} near-duplicate semantic clusters.")
    print("  - 20 Near-Duplicate Examples:")
    for g_idx, g in enumerate(near_dup_groups[:20], start=1):
        print(f"    Group #{g_idx} ({len(g)} variants):")
        for q_var in g[:3]:
            print(f"      * {q_var[:100]}")

    # 4. Question -> Answer Quality Assessment & Classification
    print("\n[4] Comprehensive Question -> Answer Quality Assessment...")
    good_records = 0
    questionable_records = 0
    bad_records = 0

    # Specific inspection counters
    broken_auth_notice_count = 0
    visual_reference_count = 0
    unanswered_q_count = 0
    code_only_low_expl_count = 0
    question_echo_count = 0

    source_quality = defaultdict(lambda: {"good": 0, "questionable": 0, "bad": 0, "total": 0})
    questionable_examples_by_source = defaultdict(list)

    for idx, r in enumerate(records):
        q = (r.get("input") or r.get("instruction") or "").strip()
        a = (r.get("output") or "").strip()
        meta = r.get("_metadata", {})
        src = meta.get("source", "unknown")
        cat = meta.get("category", "general")

        source_quality[src]["total"] += 1

        q_lower = q.lower()
        a_lower = a.lower()

        # Failure detection rules:
        is_bad = False
        is_questionable = False
        reason = ""

        # 1. Broken authorization / scraper error (seen in some raw scrapers)
        if "access to this page requires authorization" in a_lower or "trysigning inorchanging directories" in a_lower:
            is_bad = True
            broken_auth_notice_count += 1
            reason = "Scraper authentication error in answer text"

        # 2. Visual diagram dependency without description
        elif any(v in a_lower for v in ["shown in the diagram below", "red box indicates", "look at the image above", "blue arrow in the diagram"]):
            is_questionable = True
            visual_reference_count += 1
            reason = "Direct visual dependency in text answer"

        # 3. Short / uninformative answer
        elif len(a.split()) < 8:
            is_bad = True
            reason = "Extremely short / truncated answer (<8 words)"

        # 4. Question echoed as answer
        elif q_lower == a_lower or a_lower.startswith(q_lower + " ?"):
            is_bad = True
            question_echo_count += 1
            reason = "Question simply echoed as answer"

        # 5. StackOverflow specific checks (for StackPulse source)
        elif "StackPulse" in src:
            # Check if it is purely a raw user bug report rather than an instructional response
            if a.startswith("I have ") and ("my code" in a_lower or "getting error" in a_lower) and len(a.split()) < 30 and not any(k in a_lower for k in ["solution", "to fix", "you should", "resolve", "configure", "use"]):
                is_questionable = True
                unanswered_q_count += 1
                reason = "StackOverflow problem statement without resolved explanation"
            elif any(off_topic in q_lower for off_topic in ["angular", "react-native", "ios", "swift", "jquery", "wordpress", "matlab", "excel vba"]):
                is_bad = True
                reason = "Out-of-domain front-end/mobile topic in StackPulse"
            else:
                pass

        if is_bad:
            bad_records += 1
            source_quality[src]["bad"] += 1
            if len(questionable_examples_by_source[src]) < 25:
                questionable_examples_by_source[src].append({"type": "BAD", "reason": reason, "q": q, "a": a[:200], "cat": cat})
        elif is_questionable:
            questionable_records += 1
            source_quality[src]["questionable"] += 1
            if len(questionable_examples_by_source[src]) < 25:
                questionable_examples_by_source[src].append({"type": "QUESTIONABLE", "reason": reason, "q": q, "a": a[:200], "cat": cat})
        else:
            good_records += 1
            source_quality[src]["good"] += 1

    good_pct = round((good_records / total_records) * 100, 2)
    quest_pct = round((questionable_records / total_records) * 100, 2)
    bad_pct = round((bad_records / total_records) * 100, 2)

    print(f"  - GOOD Records         : {good_records} ({good_pct}%)")
    print(f"  - QUESTIONABLE Records : {questionable_records} ({quest_pct}%)")
    print(f"  - BAD Records          : {bad_records} ({bad_pct}%)")
    print(f"    * Scraper Auth Notice Issues: {broken_auth_notice_count}")
    print(f"    * Visual Diagram Dep Issues : {visual_reference_count}")
    print(f"    * StackOverflow Raw Problem Issues: {unanswered_q_count}")

    # 5. StackPulse Deep Audit
    print("\n[5] StackPulse Quality Audit (Omarrran/StackPulse_778K_QnA_Code_dataset)...")
    sp_stats = source_quality["Omarrran/StackPulse_778K_QnA_Code_dataset"]
    sp_total = sp_stats["total"]
    print(f"  Total StackPulse Records   : {sp_total}")
    print(f"  - GOOD                     : {sp_stats['good']} ({round((sp_stats['good']/sp_total)*100, 2) if sp_total else 0}%)")
    print(f"  - QUESTIONABLE             : {sp_stats['questionable']} ({round((sp_stats['questionable']/sp_total)*100, 2) if sp_total else 0}%)")
    print(f"  - BAD                      : {sp_stats['bad']} ({round((sp_stats['bad']/sp_total)*100, 2) if sp_total else 0}%)")

    print("\n  20 Questionable / Flagged StackPulse Examples:")
    for idx, ex in enumerate(questionable_examples_by_source["Omarrran/StackPulse_778K_QnA_Code_dataset"][:20], start=1):
        q_clean = ex['q'][:100].encode('ascii', 'ignore').decode('ascii')
        a_clean = ex['a'][:140].replace('\n', ' ').encode('ascii', 'ignore').decode('ascii')
        print(f"  [{idx}] [{ex['type']} - {ex['reason']}]")
        print(f"      Q: {q_clean}")
        print(f"      A: {a_clean}...")

    # 6. Azure VQA Audit
    print("\n[6] Azure VQA Quality Audit (thegovind/azure-architecture-vqa)...")
    az_stats = source_quality["thegovind/azure-architecture-vqa"]
    az_total = az_stats["total"]
    print(f"  Total Azure VQA Records    : {az_total}")
    print(f"  - GOOD                     : {az_stats['good']} ({round((az_stats['good']/az_total)*100, 2) if az_total else 0}%)")
    print(f"  - QUESTIONABLE             : {az_stats['questionable']} ({round((az_stats['questionable']/az_total)*100, 2) if az_total else 0}%)")
    print(f"  - BAD                      : {az_stats['bad']} ({round((az_stats['bad']/az_total)*100, 2) if az_total else 0}%)")

    # 7. DevOps QA Audit
    print("\n[7] DevOps QA Quality Audit (Skilln/devops-qa-dataset)...")
    dev_stats = source_quality["Skilln/devops-qa-dataset"]
    dev_total = dev_stats["total"]
    print(f"  Total DevOps QA Records    : {dev_total}")
    print(f"  - GOOD                     : {dev_stats['good']} ({round((dev_stats['good']/dev_total)*100, 2) if dev_total else 0}%)")
    print(f"  - QUESTIONABLE             : {dev_stats['questionable']} ({round((dev_stats['questionable']/dev_total)*100, 2) if dev_total else 0}%)")
    print(f"  - BAD                      : {dev_stats['bad']} ({round((dev_stats['bad']/dev_total)*100, 2) if dev_total else 0}%)")

    # 8. Cloud Domain Balance Calculations
    print("\n[8] Cloud Domain Balance & Category Distribution...")
    cat_counter = Counter()
    for r in records:
        cat = r.get("_metadata", {}).get("category", "general")
        cat_counter[cat] += 1

    aws_macro = sum(count for cat, count in cat_counter.items() if "aws" in cat)
    azure_macro = sum(count for cat, count in cat_counter.items() if "azure" in cat)
    devops_macro = sum(count for cat, count in cat_counter.items() if cat in ["devops", "docker", "kubernetes", "terraform", "ansible", "linux", "ci_cd"])
    troubleshooting_macro = sum(count for cat, count in cat_counter.items() if "troubleshoot" in cat)
    ai_llm_macro = sum(count for cat, count in cat_counter.items() if cat in ["ai_llm", "rag", "qlora", "AI & LLM Architecture"])
    cloud_fundamentals_macro = sum(count for cat, count in cat_counter.items() if cat in ["cloud_fundamentals", "general", "Cloud & DevOps", "Cloud Fundamentals"])

    print(f"  Macro Domains:")
    print(f"  - AWS Total                : {aws_macro} ({round((aws_macro/total_records)*100, 1)}%)")
    print(f"  - Azure Total              : {azure_macro} ({round((azure_macro/total_records)*100, 1)}%)")
    print(f"  - DevOps Total             : {devops_macro} ({round((devops_macro/total_records)*100, 1)}%)")
    print(f"  - Troubleshooting Total    : {troubleshooting_macro} ({round((troubleshooting_macro/total_records)*100, 1)}%)")
    print(f"  - AI / LLM / RAG Total     : {ai_llm_macro} ({round((ai_llm_macro/total_records)*100, 1)}%)")
    print(f"  - Cloud Fundamentals Total : {cloud_fundamentals_macro} ({round((cloud_fundamentals_macro/total_records)*100, 1)}%)")

    # 9. Source Balance
    print("\n[9] Source Distribution Breakdown...")
    source_counter = Counter()
    for r in records:
        src = r.get("_metadata", {}).get("source", "unknown")
        source_counter[src] += 1

    for src, count in source_counter.most_common():
        pct = round((count / total_records) * 100, 2)
        print(f"  - {src[:50]:<52}: {count:>6} ({pct}%)")

    # 10. Sample Review across 12 key categories
    print("\n[10] Representative Sample Review across 12 Key Categories...")
    sample_categories = [
        "aws", "aws_ec2", "aws_vpc", "azure", "azure_vm", "troubleshooting",
        "devops", "docker", "kubernetes", "terraform", "linux", "ai_llm"
    ]

    samples_by_cat = defaultdict(list)
    for r in records:
        c = r.get("_metadata", {}).get("category", "")
        samples_by_cat[c].append(r)

    for c in sample_categories:
        recs = samples_by_cat.get(c, [])
        if not recs:
            # Fallback to fuzzy match
            recs = [r for r in records if c in r.get("_metadata", {}).get("category", "").lower()]
        print(f"\n--- CATEGORY: {c.upper()} (Total in Category: {len(recs)}) ---")
        if recs:
            chosen = random.sample(recs, min(3, len(recs)))
            for i, samp in enumerate(chosen, start=1):
                src = samp['_metadata'].get('source', '')
                cat = samp['_metadata'].get('category', '')
                q_text = (samp.get('input') or samp.get('instruction') or '')[:120].encode('ascii', 'ignore').decode('ascii')
                a_text = samp.get('output', '')[:160].replace('\n', ' ').encode('ascii', 'ignore').decode('ascii')
                print(f"  [Sample #{i}] Source: {src} | Category: {cat}")
                print(f"    Q: {q_text}")
                print(f"    A: {a_text}...")

    # 11. Final Quality Assessment
    overall_quality = "Good"
    training_ready = True

    if bad_pct > 15.0 or good_pct < 75.0:
        overall_quality = "Needs Cleaning"
        training_ready = False
    elif good_pct >= 90.0 and bad_pct < 3.0:
        overall_quality = "Excellent"
        training_ready = True
    elif good_pct >= 80.0:
        overall_quality = "Good"
        training_ready = True
    else:
        overall_quality = "Needs Cleaning"
        training_ready = False

    print("\n" + "=" * 90)
    print("FINAL QUALITY AUDIT SUMMARY")
    print("=" * 90)
    print(f"Total Records Audited     : {total_records}")
    print(f"Overall Quality Rating    : {overall_quality}")
    print(f"Training Ready Status     : {training_ready}")
    print(f"Good Records Percentage   : {good_pct}%")
    print(f"Questionable Percentage   : {quest_pct}%")
    print(f"Bad Records Percentage    : {bad_pct}%")
    print("=" * 90)

    # 12. Save JSON Report
    report_dict = {
        "total_records": total_records,
        "exact_duplicates": {
            "duplicate_questions": dup_q_count,
            "duplicate_qa_pairs": dup_qa_count,
            "duplicate_complete_records": dup_rec_count
        },
        "near_duplicate_groups": len(near_dup_groups),
        "good_records": good_records,
        "good_percentage": good_pct,
        "questionable_records": questionable_records,
        "questionable_percentage": quest_pct,
        "bad_records": bad_records,
        "bad_percentage": bad_pct,
        "source_distribution": dict(source_counter),
        "category_distribution": dict(cat_counter),
        "macro_distribution": {
            "aws_total": aws_macro,
            "azure_total": azure_macro,
            "devops_total": devops_macro,
            "troubleshooting_total": troubleshooting_macro,
            "ai_llm_total": ai_llm_macro,
            "cloud_fundamentals_total": cloud_fundamentals_macro
        },
        "stackpulse_audit": {
            "total": sp_stats["total"],
            "good": sp_stats["good"],
            "questionable": sp_stats["questionable"],
            "bad": sp_stats["bad"],
            "good_percentage": round((sp_stats["good"]/sp_total)*100, 2) if sp_total else 0
        },
        "azure_audit": {
            "total": az_stats["total"],
            "good": az_stats["good"],
            "questionable": az_stats["questionable"],
            "bad": az_stats["bad"],
            "good_percentage": round((az_stats["good"]/az_total)*100, 2) if az_total else 0
        },
        "devops_audit": {
            "total": dev_stats["total"],
            "good": dev_stats["good"],
            "questionable": dev_stats["questionable"],
            "bad": dev_stats["bad"],
            "good_percentage": round((dev_stats["good"]/dev_total)*100, 2) if dev_total else 0
        },
        "overall_quality": overall_quality,
        "training_ready": training_ready,
        "issues_identified": {
            "scraper_auth_error_notices": broken_auth_notice_count,
            "visual_diagram_dependencies": visual_reference_count,
            "stackpulse_unresolved_problem_statements": unanswered_q_count,
            "question_echoes": question_echo_count
        }
    }

    with open(AUDIT_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=2)

    print(f"\nFull audit report saved to '{AUDIT_REPORT_PATH}'.")

if __name__ == "__main__":
    main()
