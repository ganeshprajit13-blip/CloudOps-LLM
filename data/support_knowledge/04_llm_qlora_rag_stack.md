# AI, LLM, QLoRA & RAG Architecture in CloudOps

## 1. Model Selection: Qwen2.5-3B-Instruct
- **Why Qwen2.5-3B-Instruct Was Chosen**:
  1. **Superior Reasoning**: Exceptional instruction following and structured JSON schema generation in the 3B parameter class.
  2. **Compact Footprint**: 3-billion parameters fit in ~3.5 GB VRAM using 4-bit quantization, enabling local desktop execution alongside FastAPI without multi-GPU cloud nodes.
  3. **Deterministic Output**: High adherence to system prompt constraints and post-inference validation rules.

---

## 2. Parameter-Efficient Fine-Tuning: LoRA & QLoRA
- **What is QLoRA?**: Quantized Low-Rank Adaptation (QLoRA) freezes the base LLM parameters in 4-bit NormalFloat (`nf4`) precision using `bitsandbytes` while attaching small trainable rank-decomposition adapter matrices ($r=16, \alpha=32$).
- **Target Modules**: `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`.
- **VRAM & Training Efficiency**: Reduces memory requirement from ~12 GB (16-bit) down to ~3.5 GB (4-bit), allowing fast fine-tuning on consumer GPUs (e.g. RTX 5050 8GB VRAM).
- **Separate Adapters in CloudOps**:
  - `outputs/adapter/`: Belongs strictly to the AI Troubleshooter model.
  - `outputs/support_agent_adapter/`: Belongs strictly to the CloudOps Support Agent model.

---

## 3. RAG Architecture: Embeddings & Vector Database
- **Sentence Transformers**: Uses `sentence-transformers/all-MiniLM-L6-v2` to map text documents into 384-dimensional dense vector embeddings.
- **ChromaDB Vector Database**: Persistent vector store configured with HNSW index and cosine distance metric (`hnsw:space: cosine`).
- **RAG Collections**:
  - `cloudops_knowledge`: Dedicated vector collection for AI Troubleshooter runbooks.
  - `cloudops_support`: Dedicated vector collection for CloudOps Support Agent knowledge base.

---

## 4. Evidence Grounding & Diagnosis Validation Engine
- **DiagnosisValidator**: Deterministic post-inference validation module that checks Qwen model output against live collected AWS context.
- **Evidence Verification**: Verifies every claim in model output against empirical AWS telemetry facts.
- **Contradiction Detection**: Filters out ungrounded or contradictory claims (e.g. model claiming port 80 is blocked when Security Group rules explicitly allow port 80).
- **Advisory Safety Enforcement**: Removes autonomous action language ('i restarted instance') and enforces strictly advisory remediation steps.
