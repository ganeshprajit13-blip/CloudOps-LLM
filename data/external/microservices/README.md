# LEMMA-RCA Baselines — Multi-modal Multi-domain RCA Research Repository

## ⚠️ LICENSE WARNING: CC BY-NC 4.0 — NON-COMMERCIAL ONLY

**This dataset/code is licensed under CC BY-NC 4.0 (Creative Commons
Attribution-NonCommercial). It CANNOT be used for commercial purposes or
for training models that will be used in commercial products without
explicit permission from the authors.**

If this CloudOps LLM project is non-commercial (academic/research), use
is permitted. If this project is commercial, DO NOT use this data for
training without contacting the authors for a commercial license.

---

## What It Contains

This repository contains **baseline implementations** for the LEMMA-RCA
benchmark — a large multi-modal, multi-domain dataset for Root Cause Analysis.

The downloaded ZIP (`lemma-rca-baselines-main.zip`) contains:
- Python baseline code for RCA algorithms
- Configuration files and experiment scripts
- References/pointers to the actual data on HuggingFace

**The actual raw data (metrics, logs, traces) is hosted separately on
HuggingFace at:** https://huggingface.co/datasets/LEMMA-RCA
(NOT downloaded in this batch — requires HuggingFace CLI + authentication)

Paper: "LEMMA-RCA: A Large Multi-modal Multi-domain Dataset for Root Cause Analysis"

## Source

- **Repository**: https://github.com/KnowledgeDiscovery/rca_baselines
- **Data (HuggingFace)**: https://huggingface.co/datasets/LEMMA-RCA
- **Organization**: KnowledgeDiscovery (academic research group)
- **Homepage**: https://lemma-rca.github.io/

## License

**CC BY-NC 4.0 (Creative Commons Attribution-NonCommercial 4.0)**

Permits:
- Non-commercial research use ✅ (with attribution)
- Modification ✅ (non-commercial)
- Distribution ✅ (non-commercial, with attribution)

Does NOT permit:
- Commercial use ❌
- Commercial model training ❌
- Use in commercial products without permission ❌

## Downloaded Files

| File | Size | SHA-256 |
|------|------|---------|
| `lemma-rca-baselines-main.zip` | 1,792,968 bytes | `781074D49DA7B04F4992AB2B9631AE63FC7ECAEE22D91376780A97232D7A8CD5` |

Downloaded: 2026-09-11

## Data Types

The full LEMMA-RCA dataset (on HuggingFace, NOT downloaded here) contains:
- **Metrics**: Time-series CPU, memory, network metrics
- **Logs**: System and application logs
- **Traces**: Distributed call traces
- **Incidents**: Labeled failure cases from microservice + industrial systems

## Cloud/Provider

Multi-platform / On-Premise:
- Microservice applications (Online Boutique, Sock Shop, Train Ticket)
- Industrial water treatment systems (SWaT, BATADAL)
- Not AWS-specific

## Services Covered

Microservice-level RCA, causal discovery, time-series fault detection,
online learning, multi-modal fusion.

## Why It Is Useful for CloudOps

1. **Multi-modal**: Combines metrics, logs, and traces — mimics real CloudOps observability
2. **Real faults**: Contains real system faults, not simulated
3. **Diverse domains**: Microservices + industrial systems = diverse failure patterns
4. **Research-grade**: Published in top-tier academic venues

## Known Limitations

- **Non-commercial license** — cannot be used for commercial training
- **Raw data not downloaded** — only baseline code acquired; full data on HuggingFace
- The actual multi-GB dataset requires separate HuggingFace download
- Focused on microservices and industrial systems, not AWS-native services

## Suitability for Training

⛔ **RESTRICTED** — CC BY-NC 4.0 license does NOT permit use for commercial
model training. Even for research use, the raw data must be downloaded
separately from HuggingFace (not included here).

## Suitability for RAG

⚠️ **CONDITIONAL (non-commercial research only)** — If used in a non-commercial
research context, the extracted failure case descriptions could be used for RAG.
Not available from the downloaded ZIP alone (code only, no raw data).

## Manifest

See: `data/manifests/lemma-rca-baselines.manifest.json`
