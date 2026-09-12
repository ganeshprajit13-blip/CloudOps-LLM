# CloudOps QLoRA Training & Evaluation Report

**Generated**: 2026-09-11  
**Base Model**: Qwen/Qwen2.5-3B-Instruct  
**Quantization**: 4-bit NF4 QLoRA (BitsAndBytes)  
**Hardware**: NVIDIA GeForce RTX 5050 Laptop GPU (7.93 GB VRAM)  
**Adapter Output Directory**: [`outputs/adapter/`](file:///C:/Users/Prajit Radhakrishnan/OneDrive/Desktop/CloudOPS/outputs/adapter)  

---

## Model & Training Parameter Summary

| Parameter | Value |
|-----------|-------|
| **Base Model** | `Qwen/Qwen2.5-3B-Instruct` |
| **Quantization Mode** | `4-bit NF4 (BitsAndBytesConfig)` |
| **Target Modules** | `['k_proj', 'o_proj', 'v_proj', 'up_proj', 'gate_proj', 'down_proj', 'q_proj']` |
| **Total Parameters** | `1,728,606,208` |
| **Trainable Parameters** | `29,933,568` |
| **Trainable Percentage** | `1.7317%` |
| **Training Cases** | `712` |
| **Validation Cases** | `74` |
| **Epochs** | `2` |
| **Learning Rate** | `0.0002` |
| **Batch Size** | `1` |
| **Gradient Accumulation** | `4` |

---

## Adapter Artifacts Verification

- **`adapter_config.json`**: Verified (Present, 1206 bytes)
- **`adapter_model.safetensors`**: Verified (114.25 MB)
- **Standalone Reload Verification**: PASSED (11.07s load time)

---

## Test Set Evaluation Results (85 Held-Out Test Cases)

| Evaluation Metric | Score / Pass Rate |
|-------------------|-------------------|
| **JSON / Schema Validity Rate** | **0.0%** |
| **Confidence Validity Rate** | **0.0%** |
| **Evidence Grounding Rate** | **0.0%** |
| **Root Cause Relevance Rate** | **0.0%** |
| **Recommendation Safety Pass Rate** | **100.0%** |

---

## Compliance Check

- ✅ Base model loaded with 4-bit QLoRA quantization
- ✅ Adapter weights saved cleanly to `outputs/adapter/`
- ✅ Standalone adapter reload & re-attachment verified
- ✅ Evaluation executed on untouched test set
- ✅ Protected original files & splits unmodified
