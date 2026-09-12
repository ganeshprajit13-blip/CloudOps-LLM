# CloudOps LLM — Model Architecture, Fine-Tuning & Evaluation Specification

This directory contains the core model adaptation, inference engine, structured output validation, and evaluation framework for **CloudOps LLM — AI Cloud Infrastructure Troubleshooter**.

---

## 1. Architecture Overview & Core Concepts

### Transformer
The core deep learning architecture underpinning the language model. Uses self-attention mechanisms to process long contextual sequences, capturing complex relationships across cloud configuration files, log lines, CloudTrail audit trails, and metric time-series data.

### Qwen2.5-3B-Instruct
The base pretrained Large Language Model (`Qwen/Qwen2.5-3B-Instruct`). A state-of-the-art 3-billion parameter dense autoregressive Transformer optimized for instruction following, code reasoning, and structured output formatting.

### LoRA (Low-Rank Adaptation)
A Parameter-Efficient Fine-Tuning (PEFT) technique that freezes base model weights and injects low-rank trainable decomposition matrices (`r=16`, `alpha=32`, `dropout=0.05`) into key target modules (`q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`). This reduces trainable parameters from ~3.09B down to ~12.5M (~0.40% of total parameters).

### QLoRA (Quantized Low-Rank Adaptation)
Combines 4-bit NF4 (NormalFloat4) quantization with double quantization and paged optimizers to reduce GPU memory footprint during training from >16GB down to <6GB VRAM.

### PEFT (Parameter-Efficient Fine-Tuning)
The Hugging Face library used to initialize, manage, freeze, and serialize low-rank adapter matrices separately from base model weights.

### Hugging Face Transformers
The primary model orchestration library used for tokenization, model loading, quantization configuration, text generation pipelines, and model evaluation.

---

## 2. RAG Notice (Phase 6 Separation)

> [!IMPORTANT]
> **Retrieval-Augmented Generation (RAG) is NOT implemented in Phase 5.**
> Phase 5 focuses purely on base model adaptation via instruction-tuning on structured CloudOps incident datasets. RAG (vector database retrieval with ChromaDB, Sentence Transformers, and external documentation search) is explicitly isolated and scheduled for implementation in **Phase 6**.

---

## 3. Dataset & Preprocessing

- **Dataset Source**: `data/processed/train.jsonl`, `validation.jsonl`, `test.jsonl`.
- **Dataset Size**: 220 instruction examples split 80% train (176), 10% validation (22), 10% test (22).
- **Format**: Structured ChatML JSONL instruction format matching Qwen2.5 template.
- **Normalization**: Preprocessed via Phase 3 signals normalization engine.

---

## 4. Training Process & Parameters

- **Base Model**: `Qwen/Qwen2.5-3B-Instruct`
- **Adapter Type**: LoRA / QLoRA
- **Quantization**: 4-bit NF4 (`bitsandbytes`)
- **LoRA Rank ($r$)**: 16
- **LoRA Alpha ($\alpha$)**: 32
- **LoRA Dropout**: 0.05
- **Optimizer**: `paged_adamw_8bit` / `AdamW`
- **Learning Rate**: $2 \times 10^{-4}$ with cosine scheduler
- **Batch Size**: 4 (Gradient Accumulation: 4 $\rightarrow$ Effective Batch Size: 16)
- **Epochs**: 3
- **Checkpoint Artifacts**: Saved to `outputs/checkpoints/` and `outputs/adapter/`.

---

## 5. Adapter Serialization

Adapter weights are serialized independently of base model weights in `outputs/adapter/`:
- `adapter_config.json`: PEFT configuration schema.
- `adapter_model.safetensors` / `adapter_model.bin`: Low-rank weight matrices (~50MB total).

---

## 6. Inference Engine & Structured JSON Parsing

Located in [`model/inference.py`](file:///c:/Users/Prajit%20Radhakrishnan/OneDrive/Desktop/CloudOPS/model/inference.py).

### Workflow:
1. Formats input prompt with `CLOUDOPS_SYSTEM_PROMPT`.
2. Generates diagnosis tokens via model or fallback engine.
3. Safe JSON Extraction: Extracts JSON substrings using regex (`safe_extract_json`).
4. Schema Validation (`validate_diagnosis_schema`):
   - `problem`: String
   - `probable_root_cause`: String
   - `evidence`: Array of context strings
   - `impact`: String
   - `recommendation`: String
   - `confidence`: Float between `0.0` and `1.0`
5. Safe Error Recovery: If JSON parsing or validation fails, returns `MODEL_OUTPUT_PARSE_ERROR` schema instead of throwing unhandled exceptions.
6. Advisory Safety Enforcement: Verifies recommendations do NOT contain forbidden execution phrases ("I fixed", "automatically modify", "restarted EC2"). Sanitizes output to strictly advisory guidance.

---

## 7. Evaluation Framework

Located in [`model/evaluate.py`](file:///c:/Users/Prajit%20Radhakrishnan/OneDrive/Desktop/CloudOPS/model/evaluate.py) and executable via `scripts/evaluate_cloudops.py`.

Evaluates test examples in `data/processed/test.jsonl` across 8 dimensions:
1. Valid JSON Rate
2. Schema Validity Rate
3. Confidence Validity Rate
4. Evidence Grounding Rate
5. Probable Root-Cause Relevance
6. Advisory Safety Pass Rate
7. Output Consistency Rate
8. Uncertainty Handling Pass Rate

Results are exported to `outputs/evaluation/`:
- `evaluation_summary.json`
- `evaluation_results.json`

---

## 8. Hardware Requirements & Device Fallbacks

- **Optimal Execution**: NVIDIA GPU with $\ge$ 8GB VRAM (CUDA 11.8+ / 12.0+).
- **CPU / Lightweight Fallback**: Automatically falls back to 32-bit CPU float tensor mode or heuristic rule engine when CUDA or GPU memory is unavailable.

---

## 9. Limitations

1. **Static Pre-training Snapshot**: Base model knowledge cut-off limits awareness of AWS API changes introduced post-2024.
2. **Context Window Limitations**: Context token limits require prior normalization of raw Boto3 responses (Phase 3).
3. **No Execution Capability**: Model outputs are strictly advisory and cannot perform mutating actions against AWS environments.
