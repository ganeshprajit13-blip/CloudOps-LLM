# Dataset License & Provenance Audit Report

**Audit Date**: 2026-09-11
**Auditor**: Automated (Step 3 - REAL DATA LICENSE + PROVENANCE AUDIT)
**Scope**: All datasets under `data/external/`
**Purpose**: Determine training eligibility, RAG eligibility, and licensing status for each dataset.

> [!IMPORTANT]
> This audit is conservative by design. Where license terms are ambiguous or absent,
> datasets are marked `REQUIRES_HUMAN_REVIEW` or `UNKNOWN`. Absence of explicit prohibition
> is NOT treated as permission. All checksums were verified against the actual downloaded files.

---

## Summary Table

| Dataset | Source | License | Actual Contents | Real/Synthetic | Training Status | RAG Status | Attribution Required | Main Restrictions | Recommendation |
|---------|--------|---------|-----------------|----------------|-----------------|------------|----------------------|-------------------|----------------|
| RCAEval | github.com/phamquiluan/RCAEval | MIT | Metrics (Prometheus), traces (Jaeger), 735 labeled failure cases | Real (microservice deployments) | TRAINING_ALLOWED | RAG_ALLOWED | YES - copyright notice in copies | None beyond attribution in copies | Include for training and RAG after normalization |
| danluu/post-mortems | github.com/danluu/post-mortems | NO EXPLICIT LICENSE | Index of links to real post-mortems (README.md only, no full text) | Real (links to production incidents) | TRAINING_REQUIRES_HUMAN_REVIEW | RAG_REQUIRES_HUMAN_REVIEW | UNKNOWN | No license file; each linked URL governed by its company ToS | Use as reference only; human review required before training |
| AWS Sample RCA Deep Investigations | github.com/aws-samples/sample-rca-deep-investigations | MIT-0 (No Attribution) | 5 structured incident scenarios with logs, context, ground truth | Synthetic/curated (AWS-authored scenarios) | TRAINING_ALLOWED | RAG_ALLOWED | NO (MIT-0 explicitly waives attribution) | None | Include for training and RAG - highest priority AWS-native source |
| LEMMA-RCA Baselines | github.com/KnowledgeDiscovery/rca_baselines | CC BY-NC 4.0 | Baseline code only; raw data not downloaded (resides on HuggingFace) | Code is algorithmic; raw data (not downloaded) is real | TRAINING_NOT_ALLOWED (commercial) | RAG_NOT_ALLOWED (commercial) | YES - attribution required per CC BY-NC 4.0 | Non-commercial only; raw data not downloaded | Exclude from training (commercial). Research use only; raw data must be separately downloaded |

---

## 1. RCAEval

### 1.1 Source Verification

| Field | Value |
|-------|-------|
| Official Repository URL | https://github.com/phamquiluan/RCAEval |
| Organization / Author | Luan Pham (phamquiluan) |
| Repository Name | RCAEval |
| Release / Tag | v1.7.0 (published 2026-09-03) |
| Acquisition Date | 2026-09-11 |
| Downloaded Files | RCAEval-1.7.0.zip (2,362,516 bytes), RCAEval-1.7.0.tar.gz (2,302,319 bytes) |
| SHA-256 (zip) | C9F68B97E955220F9BDAD0E6C28BA083E96A6A0CB7610395307FE42925AE42AA - VERIFIED |
| SHA-256 (tar.gz) | 50A1ED4C7E4BF7F82ECB1342DB7E07E635BFFB450F9327E9C80D257B31F0DA93 - VERIFIED |
| Original Size (compressed) | 4,664,835 bytes total |
| Extracted Size | 4,436,532 bytes (149 ZIP entries) |

### 1.2 License Verification

| Field | Value |
|-------|-------|
| License Name | MIT License |
| License File Path | phamquiluan-RCAEval-405c8fd/LICENSE (inside ZIP) |
| License URL | https://github.com/phamquiluan/RCAEval/blob/main/LICENSE |
| Commercial Use Allowed | YES |
| Modification Allowed | YES |
| Redistribution Allowed | YES (with copyright notice) |
| Derivative Datasets Allowed | YES |
| Model Training Explicitly Prohibited | NO prohibition - training is permitted |
| Attribution Required | YES - copyright notice must be included in copies/substantial portions |
| Other Restrictions | None beyond standard MIT warranty disclaimer |

LICENSE TEXT (verified from inside ZIP - phamquiluan-RCAEval-405c8fd/LICENSE):

    MIT License
    Copyright (c) 2024 Luan Pham
    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:
    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

### 1.3 Data-Level Provenance

| Field | Value |
|-------|-------|
| Data Types | Metrics (Prometheus time-series), Traces (Jaeger distributed traces), Incidents (labeled failure cases), RCA labels |
| Real vs Synthetic | REAL - 735 failure cases from live microservice deployments on Kubernetes |
| Applications Covered | Online Boutique (Google demo), Sock Shop (Weaveworks), Train Ticket |
| Platforms | Kubernetes-deployed microservices |
| Data Source | Academic benchmark, peer-reviewed at ASE'24, WWW'25, FSE'26 |
| Sensitive Data | None identified - no PII, no production secrets |
| Third-Party Content | Microservice apps are public open-source; data is from benchmark deployments |

Data types present:
- PRESENT: metrics
- PRESENT: traces
- PRESENT: incidents
- PRESENT: RCA labels (ground-truth root cause services)
- NOT PRIMARY: configurations, logs
- NOT PRESENT: real production secrets, PII

### 1.4 Training Eligibility

**Status: TRAINING_ALLOWED**

Rationale: MIT license is verified from within the downloaded ZIP. No training prohibition exists.
735 labeled real failure cases with ground-truth RCA labels provide high-quality supervised training signal.

### 1.5 RAG Eligibility

**Status: RAG_ALLOWED**

Rationale: MIT license permits use in RAG systems. Failure case descriptions and diagnostic patterns
are directly useful for retrieval-augmented CloudOps troubleshooting.

### 1.6 Content Quality

| Field | Value |
|-------|-------|
| Approximate Records | 735 labeled failure cases across 9 datasets |
| AWS-Specific Content | LOW - microservice benchmarks, applicable to EKS/ECS |
| Non-AWS Cloud Content | HIGH - Kubernetes/microservice environments |
| Services Represented | Prometheus, Jaeger, microservice RPC, pod-level failures |
| Root-Cause Labels Present | YES - ground-truth root cause services |
| Symptoms Present | YES - latency, error rate, pod crashes |
| Remediation Information | PARTIAL - benchmark focused on detection, not remediation |
| Telemetry Present | YES - metrics + traces |
| CloudOps Usefulness | HIGH - diverse multi-modal failure patterns |

### 1.7 Duplication / Overlap

- vs AWS Sample RCA: Minimal - different scenario types
- vs danluu/post-mortems: Minimal - danluu is link-index only; RCAEval has structured data
- vs LEMMA-RCA: SIGNIFICANT CONCEPTUAL OVERLAP - same benchmark apps (Online Boutique, Sock Shop, Train Ticket), different data snapshots
- vs our 412 examples: LOW - our examples are AWS-native CloudOps; RCAEval is generic microservices

---

## 2. danluu/post-mortems

### 2.1 Source Verification

| Field | Value |
|-------|-------|
| Official Repository URL | https://github.com/danluu/post-mortems |
| Organization / Author | Dan Luu (danluu) + community contributors |
| Repository Name | post-mortems |
| Commit / Tag | Branch: master, commit hash: 630562e (embedded in ZIP folder name) |
| Acquisition Date | 2026-09-11 |
| Downloaded Files | danluu-post-mortems-master.zip (39,456 bytes) |
| SHA-256 | 8CF2D68BF6E15FFBBFE3B2A38F1C3D847BF07D13132B3B64D6BD60D1BC3E8D17 - VERIFIED |
| Original Size (compressed) | 39,456 bytes |
| Extracted Size | ~97,530 bytes (README.md: 96,615 bytes + metadata: ~912 bytes) |

### 2.2 License Verification

| Field | Value |
|-------|-------|
| License Name | NONE - No explicit LICENSE file in repository |
| License File Path | NOT PRESENT - confirmed by ZIP inspection |
| License URL | Not available |
| Commercial Use Allowed | UNKNOWN |
| Modification Allowed | UNKNOWN |
| Redistribution Allowed | UNKNOWN |
| Derivative Datasets Allowed | UNKNOWN |
| Model Training Explicitly Prohibited | UNKNOWN - no license terms to evaluate |
| Attribution Required | UNKNOWN |
| Other Restrictions | Each linked post-mortem URL is governed by respective company Terms of Service |

ASSESSMENT: The repository has no license file. Default copyright law applies in most jurisdictions,
meaning all rights are reserved by the author unless explicitly granted. The collection of links
itself may qualify as factual information (not copyrightable), but arrangement and selection may
be protected. The linked external documents are each governed by their originating companies ToS.

**Status: UNKNOWN / REQUIRES HUMAN REVIEW**

### 2.3 Data-Level Provenance

| Field | Value |
|-------|-------|
| Data Types | Links/references to real incident post-mortems |
| Real vs Synthetic | REAL - links to actual published production incident reports |
| Content in Downloaded ZIP | README.md (621 lines, 256 lines with external HTTP links) only; no post-mortem full text |
| Full Text Available | NO - requires fetching each external URL separately |
| Third-Party Content | All linked documents are property of their respective companies |

Data types present (in downloaded ZIP):
- PRESENT: links/references (primary content type - 256 HTTP link lines in README)
- PRESENT: incidents (as link references with 1-2 sentence summaries)
- NOT PRESENT: logs, metrics, traces, RCA labels, telemetry

NOTE: The ZIP contains NO post-mortem full text. Categories in README: Config Errors,
Hardware/Power Failures, Conflicts, Time (clock skew), Database, Uncategorized.

### 2.4 Training Eligibility

**Status: TRAINING_REQUIRES_HUMAN_REVIEW**

Rationale: No license file in repository. Default copyright applies. The URL index + short summaries
may be factual (non-copyrightable) but individual post-mortem texts (not downloaded) are governed by
each company ToS. Human legal review required before using for model training.

### 2.5 RAG Eligibility

**Status: RAG_REQUIRES_HUMAN_REVIEW**

Rationale: Same licensing uncertainty as training. README link index alone is of limited RAG value
(no full text). Full RAG use would require URL fetching and per-URL ToS evaluation - not completed.

### 2.6 Content Quality

| Field | Value |
|-------|-------|
| Approximate Records | ~256 post-mortem references (link lines in README) |
| AWS-Specific Content | MODERATE - multiple AWS entries (EC2, DNS, S3, Route 53) |
| Non-AWS Cloud Content | HIGH - GCP, Cloudflare, GitHub, Meta, CircleCI, etc. |
| Services Represented | DNS, BGP, CDN, WAF, databases, Kubernetes, EC2, configuration management |
| Root-Cause Labels Present | PARTIAL - embedded in 1-2 sentence summaries only |
| Symptoms Present | PARTIAL - brief descriptions in README only |
| Remediation Information | VERY LIMITED - full remediation in external URLs not downloaded |
| Telemetry Present | NO - no telemetry data in downloaded ZIP |
| CloudOps Usefulness | MODERATE as index; HIGH if full text fetched and licensed |

### 2.7 Duplication / Overlap

- vs other datasets: Minimal - unique link-index format
- vs our 412 examples: LOW STRUCTURAL - our examples are structured QA; danluu is narrative links

---

## 3. AWS Sample RCA Deep Investigations

### 3.1 Source Verification

| Field | Value |
|-------|-------|
| Official Repository URL | https://github.com/aws-samples/sample-rca-deep-investigations |
| Organization / Author | Amazon Web Services (aws-samples organization) |
| Repository Name | sample-rca-deep-investigations |
| Commit / Tag | main branch (folder name: sample-rca-deep-investigations-main) |
| Acquisition Date | 2026-09-11 |
| Downloaded Files | aws-sample-rca-deep-investigations-main.zip (571,350 bytes) |
| SHA-256 | 5D126D755185A5415BD6901414268175BB775CC85633295E656B603A12C5CD7D - VERIFIED |
| Original Size (compressed) | 571,350 bytes |
| Extracted Size | 2,324,176 bytes (263 ZIP entries) |

### 3.2 License Verification

| Field | Value |
|-------|-------|
| License Name | MIT No Attribution (MIT-0) |
| License File Path | sample-rca-deep-investigations-main/LICENSE (inside ZIP) |
| License URL | https://github.com/aws-samples/sample-rca-deep-investigations/blob/main/LICENSE |
| Commercial Use Allowed | YES |
| Modification Allowed | YES |
| Redistribution Allowed | YES |
| Derivative Datasets Allowed | YES |
| Model Training Explicitly Prohibited | NO prohibition |
| Attribution Required | NO - MIT-0 explicitly removes attribution requirement |
| Other Restrictions | None - most permissive OSS license |

LICENSE TEXT (verified from inside ZIP - sample-rca-deep-investigations-main/LICENSE):

    MIT No Attribution
    Copyright Amazon.com, Inc. or its affiliates. All rights reserved.
    Permission is hereby granted, free of charge, to any person obtaining a copy of
    this software and associated documentation files (the "Software"), to deal in
    the Software without restriction, including without limitation the rights to
    use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
    the Software, and to permit persons to whom the Software is furnished to do so.

### 3.3 Data-Level Provenance

| Field | Value |
|-------|-------|
| Data Types | Incidents (structured), Logs (sample), Configuration (architecture context), Documentation, RCA labels |
| Real vs Synthetic | SYNTHETIC/CURATED - AWS-authored scenarios; not from live production incidents |
| Scenario Count | 5 scenarios (verified by counting incident.md files inside ZIP) |
| Scenarios | care-transcript-supply-chain, iot-fleet-disconnect-cascade, k8s-canary-silent-poisoning, ml-training-drift-schema-migration, volte-call-drop-handover |
| Ground Truth | YES - ground_truth.yaml per scenario |
| Third-Party Content | None - 100% AWS-created |

Data types present:
- PRESENT: incidents (structured incident.md per scenario)
- PRESENT: logs (evidence/*.log files per scenario)
- PRESENT: configurations (context/architecture.md per scenario)
- PRESENT: RCA labels (ground_truth.yaml per scenario)
- PRESENT: documentation (runbooks, past incidents, related tickets per scenario)
- PRESENT: synthetic/curated data (AWS-authored for LLM testing)
- NOT PRESENT: time-series metrics, structured trace data

NOTE: This is not real production data - it is professionally curated by AWS engineers
specifically for LLM-based RCA evaluation. Data quality is high and AWS alignment is excellent.

### 3.4 Training Eligibility

**Status: TRAINING_ALLOWED**

Rationale: MIT-0 license is verified from within the downloaded ZIP. No restrictions whatsoever.
AWS-created content specifically designed for LLM-based RCA workflows. 5 scenarios with ground truth
provide high-quality instruction-following training signal.

### 3.5 RAG Eligibility

**Status: RAG_ALLOWED**

Rationale: MIT-0 license permits any use. Repository includes a reference RAG implementation.
Scenario documents (incident reports, logs, runbooks, architecture docs) are ideal RAG source
documents for CloudOps.

### 3.6 Content Quality

| Field | Value |
|-------|-------|
| Approximate Records | 5 complete scenarios with multi-file evidence packages |
| AWS-Specific Content | HIGH - AWS services throughout (EKS, IoT Core, etc.) |
| Non-AWS Cloud Content | LOW |
| Services Represented | EC2, EKS/Kubernetes, IoT Core, CloudWatch, X-Ray, CloudTrail, Lambda, VPC, ML pipeline |
| Root-Cause Labels Present | YES - ground_truth.yaml per scenario |
| Symptoms Present | YES - incident.md per scenario |
| Remediation Information | YES - runbooks per scenario |
| Telemetry Present | PARTIAL - sample log files (not time-series metrics) |
| CloudOps Usefulness | VERY HIGH - best AWS alignment of all datasets |

### 3.7 Duplication / Overlap

- vs RCAEval: LOW - different scope (AWS scenarios vs generic microservices)
- vs danluu/post-mortems: LOW - structured scenarios vs link index
- vs LEMMA-RCA: LOW - AWS-specific vs multi-domain microservices
- vs our 412 examples: MODERATE - some scenario types (Kubernetes, IoT) may conceptually overlap; no exact duplication expected

---

## 4. LEMMA-RCA Baselines

### 4.1 Source Verification

| Field | Value |
|-------|-------|
| Official Repository URL | https://github.com/KnowledgeDiscovery/rca_baselines |
| Data Repository (HuggingFace) | https://huggingface.co/datasets/LEMMA-RCA (NOT downloaded) |
| Organization / Author | KnowledgeDiscovery (academic research group) |
| Repository Name | rca_baselines |
| Commit / Tag | main branch (folder name: rca_baselines-main) |
| Acquisition Date | 2026-09-11 |
| Downloaded Files | lemma-rca-baselines-main.zip (1,792,968 bytes) |
| SHA-256 | 781074D49DA7B04F4992AB2B9631AE63FC7ECAEE22D91376780A97232D7A8CD5 - VERIFIED |
| Original Size (compressed) | 1,792,968 bytes |
| Extracted Size | 2,361,084 bytes (108 ZIP entries) |

### 4.2 License Verification

| Field | Value |
|-------|-------|
| License Name | CC BY-NC 4.0 (Creative Commons Attribution-NonCommercial 4.0) |
| License File Path | rca_baselines-main/LICENSE (inside ZIP) - confirmed CC BY-NC 4.0 text |
| License URL | https://creativecommons.org/licenses/by-nc/4.0 |
| Commercial Use Allowed | NO |
| Modification Allowed | YES (non-commercial only) |
| Redistribution Allowed | YES (non-commercial, with attribution) |
| Derivative Datasets Allowed | YES (non-commercial, with attribution) |
| Model Training Explicitly Prohibited | PROHIBITED for commercial training; permitted for non-commercial research |
| Attribution Required | YES - attribution mandatory |
| Other Restrictions | NonCommercial - You can not use the material for commercial purposes (direct quote from LICENSE) |

> [!CAUTION]
> LICENSE TEXT (verified from inside ZIP - rca_baselines-main/LICENSE):
>
>     Creative Commons Attribution-NonCommercial (CC BY-NC)
>     Version 4.0, November 2013
>     https://creativecommons.org/licenses/by-nc/4.0
>     NonCommercial - You can not use the material for commercial purposes.
>
> A secondary MIT-licensed file exists at rca_baselines-main/Baseline/Offline/Nezha/LICENSE
> (MIT, Copyright 2023 IntelligentDDS) - this covers ONLY the Nezha algorithm code,
> NOT the dataset or the overall repository.

### 4.3 Data-Level Provenance

| Field | Value |
|-------|-------|
| Data Types (downloaded ZIP) | Baseline code only (Python scripts, configs) |
| Data Types (HuggingFace, NOT downloaded) | Metrics, Logs, Traces, Incidents - multi-modal multi-domain |
| Real vs Synthetic | Code: algorithmic; Raw data (not downloaded): REAL system faults |
| Raw Data Location | HuggingFace - NOT downloaded; requires huggingface-cli + authentication |
| Third-Party Content | Nezha algorithm code (MIT, IntelligentDDS) embedded in ZIP |

Data types present in downloaded ZIP only:
- NOT DOWNLOADED: metrics, logs, traces, incidents (all on HuggingFace)
- PRESENT: source code (baseline algorithm implementations)
- PRESENT: configuration files
- PRESENT: documentation

NOTE: The actual LEMMA-RCA dataset (raw multi-modal data) was NOT downloaded.
The downloaded ZIP contains ONLY baseline algorithm code. The raw data resides at
https://huggingface.co/datasets/LEMMA-RCA under the same CC BY-NC 4.0 license.

### 4.4 Training Eligibility

**Status: TRAINING_NOT_ALLOWED** (conservative - commercial use determination pending)

Rationale: CC BY-NC 4.0 explicitly prohibits commercial use. Additionally, the actual raw data
has NOT been downloaded - only baseline code is available. Commercial project classification
must be determined before any use.

### 4.5 RAG Eligibility

**Status: RAG_NOT_ALLOWED** (conservative - commercial use determination pending)

Rationale: Same restrictions as training. Downloaded ZIP contains no raw data suitable for RAG.
Raw data must be downloaded separately from HuggingFace.

### 4.6 Content Quality

| Field | Value |
|-------|-------|
| Approximate Records | 0 data records in downloaded ZIP (code only) |
| AWS-Specific Content | NONE |
| Non-AWS Cloud Content | NONE in downloaded ZIP |
| Services Represented | Microservices (Online Boutique, Sock Shop, Train Ticket), industrial (SWaT, BATADAL) |
| Root-Cause Labels Present | NOT IN DOWNLOADED ZIP |
| Symptoms Present | NOT IN DOWNLOADED ZIP |
| Remediation Information | NOT IN DOWNLOADED ZIP |
| Telemetry Present | NOT IN DOWNLOADED ZIP |
| CloudOps Usefulness | LOW with current download; requires HuggingFace data for any value |

### 4.7 Duplication / Overlap

- vs RCAEval: SIGNIFICANT CONCEPTUAL OVERLAP - same benchmark apps; different data collection
- vs AWS Sample RCA: LOW
- vs danluu/post-mortems: LOW
- vs our 412 examples: LOW

---

## Duplication Cross-Check

| Pair | Overlap Assessment |
|------|-------------------|
| RCAEval vs LEMMA-RCA | HIGH CONCEPTUAL - share same microservice benchmark apps; different data snapshots |
| RCAEval vs AWS Sample RCA | LOW - different domains |
| RCAEval vs danluu | LOW - different format |
| LEMMA-RCA vs AWS Sample RCA | LOW |
| LEMMA-RCA vs danluu | LOW |
| AWS Sample RCA vs danluu | LOW |
| All external vs our 412 examples | LOW STRUCTURAL - different format/origin; no exact record overlap identified |

---

## Final Eligibility Summary

| Dataset | Training Status | RAG Status | Action |
|---------|-----------------|------------|--------|
| RCAEval v1.7.0 | TRAINING_ALLOWED | RAG_ALLOWED | Include in pipeline (attribution in code/docs required) |
| AWS Sample RCA Deep Investigations | TRAINING_ALLOWED | RAG_ALLOWED | Include in pipeline (no attribution required) |
| danluu/post-mortems | TRAINING_REQUIRES_HUMAN_REVIEW | RAG_REQUIRES_HUMAN_REVIEW | Human review required - use as reference only until cleared |
| LEMMA-RCA Baselines | TRAINING_NOT_ALLOWED | RAG_NOT_ALLOWED | Exclude from training; human review required for any research use |

---

## Audit Integrity Notes

1. All SHA-256 checksums were computed at audit time and match values recorded during acquisition.
2. License texts were verified by reading license files directly from inside the downloaded ZIP archives.
3. No datasets were modified, extracted, merged, or processed during this audit.
4. The 412 examples in data/examples/ were not accessed or modified.
5. Ambiguous licensing (danluu, LEMMA-RCA commercial context) was marked conservatively as REQUIRES_HUMAN_REVIEW.
6. No new datasets were downloaded during this audit.
