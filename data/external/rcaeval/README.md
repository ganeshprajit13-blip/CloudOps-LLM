# RCAEval — Benchmark for Root Cause Analysis in Microservice Systems

## What It Contains

RCAEval is an open-source academic benchmark for Root Cause Analysis (RCA)
in microservice environments. It provides:

- **9 datasets** with **735 real failure cases** from live microservice deployments
- **15 reproducible baselines** covering metric-based, trace-based, and multi-source methods
- Ground-truth labeled root cause services for each failure
- Benchmark evaluation framework with standardized metrics

Data types: **Prometheus metrics**, **Jaeger distributed traces**, structured fault labels.

Microservice applications covered:
- Online Boutique (Google's demo e-commerce app)
- Sock Shop (Weaveworks reference app)
- Train Ticket (complex ticketing system)

## Source

- **Repository**: https://github.com/phamquiluan/RCAEval
- **Author/Maintainer**: Luan Pham (phamquiluan)
- **Published At**: ASE'24, WWW'25, FSE'26 (top academic conferences)
- **Latest Release**: v1.7.0 (published 2026-09-03)

## License

**MIT License** (Copyright 2024 Luan Pham)

Permits:
- Commercial use ✅
- Modification ✅
- Distribution ✅
- Sublicensing ✅
- Training use ✅

No restrictions on use for training AI/ML models.

## Downloaded Files

| File | Size | SHA-256 |
|------|------|---------|
| `RCAEval-1.7.0.zip` | 2,362,516 bytes | `C9F68B97E955220F9BDAD0E6C28BA083E96A6A0CB7610395307FE42925AE42AA` |
| `RCAEval-1.7.0.tar.gz` | 2,302,319 bytes | `50A1ED4C7E4BF7F82ECB1342DB7E07E635BFFB450F9327E9C80D257B31F0DA93` |

Downloaded: 2026-09-11

## Data Types

- **Metrics**: Time-series CPU, memory, network, latency metrics from Prometheus
- **Traces**: Distributed request traces from Jaeger
- **Incidents**: 735 labeled failure cases with ground-truth root causes

## Cloud/Provider

Multi-platform — microservice benchmarks deployable on Kubernetes. Not
AWS-specific, but representative of cloud-native microservice failure patterns
applicable to AWS EKS/ECS deployments.

## Services Covered

Microservice-level RCA covering: API gateway timeouts, cascading failures,
memory leaks, CPU throttling, network latency, pod crashes, service degradation.

## Why It Is Useful for CloudOps

1. **Real labeled failure cases** with ground truth — ideal for supervised training
2. **Multi-modal data** (metrics + traces) mirrors real CloudOps observability stacks
3. **Academic benchmark** — well-validated, peer-reviewed data quality
4. **735 failure cases** provide diverse RCA reasoning patterns
5. **Microservice patterns** are applicable to AWS ECS/EKS environments
6. **Standardized baselines** allow comparison with state-of-the-art methods

## Known Limitations

- Focused on microservice architectures, not AWS-specific managed services
- Does not include CloudTrail, VPC Flow Logs, or AWS-native log formats
- Some datasets have limited coverage of infrastructure-level failures
- Data reflects research benchmark conditions, not production-scale deployments

## Suitability for Training

✅ **YES** — MIT license permits training use. 735 labeled failure cases with
ground truth provide high-quality supervised training signal for RCA tasks.
After normalization, suitable for inclusion in CloudOps LLM training set.

## Suitability for RAG

✅ **YES** — Failure case descriptions and diagnostic reasoning patterns are
valuable for retrieval-augmented generation in CloudOps troubleshooting context.

## Manifest

See: `data/manifests/rcaeval.manifest.json`
