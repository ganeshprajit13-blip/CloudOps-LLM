# CloudOps LLM Platform Architecture & Features Overview

## 1. System Architecture
CloudOps LLM is an enterprise-grade AI technical advisory platform for AWS cloud infrastructure. It combines real-time read-only AWS telemetry, signal extraction, Retrieval-Augmented Generation (RAG), and parameter-efficient fine-tuned Large Language Models (LLM) to perform automated root-cause analysis and operational guidance.

### Stack Components:
- **Frontend Framework**: React 18 + Vite, single-page application (SPA) with modern UI components and real-time state management.
- **Backend API Server**: FastAPI running on Uvicorn web server, providing structured RESTful endpoints (`/api/analyze`, `/api/support-chat`, `/api/resources`, `/api/incidents`, `/api/logs`).
- **Base LLM Model**: Qwen2.5-3B-Instruct, fine-tuned using 4-bit NF4 QLoRA quantization (`bitsandbytes` + `peft`).
- **Vector Database**: Persistent ChromaDB vector store using HNSW index and cosine distance metric.
- **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2` generating 384-dimensional dense vector representations.
- **Post-Inference Safety Engine**: `DiagnosisValidator` for JSON schema enforcement, factual evidence grounding verification, and safety filtering.

---

## 2. Navigation & Main Features
CloudOps features 7 dedicated pages accessible from the main navigation sidebar:

1. **Dashboard (`/dashboard`)**:
   - High-level operational overview of system health, active telemetry signals, CPU usage trends, and incident severity counts.
2. **AI Troubleshooter (`/troubleshoot`)**:
   - Interactive diagnostic workspace for AWS infrastructure incidents. Takes incident prompts and optional target AWS Resource IDs (e.g. `i-07243bdf548e18f5`), collects read-only AWS telemetry, and produces 6-field structured root-cause diagnoses.
3. **Support Agent (`/support-agent`)**:
   - Dedicated full-page AI technical assistant grounded in the CloudOps Support Knowledge Base (`cloudops_support` ChromaDB collection). Provides grounded guidance on platform usage, AWS cloud concepts, and AI/RAG technology.
4. **Cloud Resources (`/resources`)**:
   - Live inventory browser for EC2 instances, VPCs, Security Groups, Load Balancers, and CloudWatch metrics.
5. **Incidents (`/incidents`)**:
   - Incident tracking board filtering active alerts by severity (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
6. **Logs (`/logs`)**:
   - Centralized log stream aggregator for CloudWatch logs across EC2, ALB, RDS, and Lambda.
7. **Analysis History (`/history`)**:
   - Historical record of past diagnostic runs, complete telemetry evidence, and recorded confidence scores.
