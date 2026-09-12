import os
from pathlib import Path

# Base Model Selection
BASE_MODEL_NAME = os.getenv("BASE_MODEL_NAME", "Qwen/Qwen2.5-3B-Instruct")
MODEL_NAME = BASE_MODEL_NAME

# Project Directory Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
EXAMPLES_DIR = DATA_DIR / "examples"
SCHEMAS_DIR = DATA_DIR / "schemas"

# Processed Dataset Files
COMBINED_DATA_DIR = PROCESSED_DATA_DIR / "combined"
if (COMBINED_DATA_DIR / "train.jsonl").exists():
    TRAIN_FILE = COMBINED_DATA_DIR / "train.jsonl"
    VALIDATION_FILE = COMBINED_DATA_DIR / "validation.jsonl"
    TEST_FILE = COMBINED_DATA_DIR / "test.jsonl"
else:
    TRAIN_FILE = PROCESSED_DATA_DIR / "train.jsonl"
    VALIDATION_FILE = PROCESSED_DATA_DIR / "validation.jsonl"
    TEST_FILE = PROCESSED_DATA_DIR / "test.jsonl"

# Dataset Splitting Settings
TRAIN_RATIO = 0.8
VAL_RATIO = 0.1
TEST_RATIO = 0.1
RANDOM_SEED = 42

# Model & Adaptation Mode
MODEL_MODE = os.getenv("MODEL_MODE", "qlora")

# Quantization Config
LOAD_IN_4BIT = True
BNB_4BIT_QUANT_TYPE = "nf4"
BNB_4BIT_USE_DOUBLE_QUANT = True

# LoRA / QLoRA Hyperparameters
LORA_R = int(os.getenv("LORA_R", "16"))
LORA_ALPHA = int(os.getenv("LORA_ALPHA", "32"))
LORA_DROPOUT = float(os.getenv("LORA_DROPOUT", "0.05"))
LORA_TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]

# Output Directory Paths
OUTPUT_DIR = str(PROJECT_ROOT / "outputs")
MODEL_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "adapter"
CHECKPOINT_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "checkpoints")
ADAPTER_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "adapter")
EVALUATION_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "evaluation")

# Training & Inference Generation Limits
MAX_SEQ_LENGTH = int(os.getenv("MAX_SEQUENCE_LENGTH", os.getenv("MAX_SEQ_LENGTH", "1024")))
MAX_SEQUENCE_LENGTH = MAX_SEQ_LENGTH
MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", "512"))
DEFAULT_CPU_THREADS = int(os.getenv("CPU_THREADS", "8"))
REQUIRE_ADAPTER = os.getenv("REQUIRE_ADAPTER", "0") == "1"
LEARNING_RATE = float(os.getenv("LEARNING_RATE", "2e-4"))
NUM_TRAIN_EPOCHS = int(os.getenv("NUM_EPOCHS", os.getenv("NUM_TRAIN_EPOCHS", "3")))
NUM_EPOCHS = NUM_TRAIN_EPOCHS

# RTX 5050 8GB GPU defaults: BATCH_SIZE=1, GRADIENT_ACCUMULATION_STEPS=16
BATCH_SIZE = int(os.getenv("PER_DEVICE_TRAIN_BATCH_SIZE", os.getenv("BATCH_SIZE", "1")))
PER_DEVICE_TRAIN_BATCH_SIZE = BATCH_SIZE
GRADIENT_ACCUMULATION_STEPS = int(os.getenv("GRADIENT_ACCUMULATION_STEPS", "16"))


