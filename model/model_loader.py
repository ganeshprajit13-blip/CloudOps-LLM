import os
import logging
import torch

from model.config import (
    BASE_MODEL_NAME,
    BNB_4BIT_QUANT_TYPE,
    BNB_4BIT_USE_DOUBLE_QUANT,
    LOAD_IN_4BIT,
    MODEL_MODE,
)

logger = logging.getLogger(__name__)



def get_torch_device() -> torch.device:
    """Detects available PyTorch device (CUDA GPU vs CPU) and configures CPU threads."""
    if torch.cuda.is_available():
        device = torch.device("cuda")
        logger.info(f"CUDA GPU detected: {torch.cuda.get_device_name(0)}")
    else:
        device = torch.device("cpu")
        cpu_threads = int(os.getenv("CPU_THREADS", str(os.cpu_count() or 8)))
        try:
            torch.set_num_threads(cpu_threads)
        except Exception as te:
            logger.debug(f"torch.set_num_threads setting skipped: {te}")
        logger.info(f"CUDA GPU unavailable. Operating in CPU mode with {cpu_threads} PyTorch threads.")
    return device


def load_base_model(
    model_name: str = BASE_MODEL_NAME,
    mode: str = MODEL_MODE,
):
    """Loads base model with LoRA or 4-bit QLoRA quantization configuration."""
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig

    device = get_torch_device()
    use_cuda = device.type == "cuda"

    logger.info(f"Loading base model '{model_name}' in mode='{mode}' (CUDA={use_cuda})")

    if os.getenv("OFFLINE_MODE", "0") == "1" or os.getenv("DRY_RUN", "0") == "1":
        logger.info("OFFLINE_MODE active: using lightweight DummyQwenModel.")
        return _create_dummy_qwen_model(), mode

    if mode.lower() == "qlora" and use_cuda and LOAD_IN_4BIT:
        compute_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type=BNB_4BIT_QUANT_TYPE,
            bnb_4bit_use_double_quant=BNB_4BIT_USE_DOUBLE_QUANT,
            bnb_4bit_compute_dtype=compute_dtype,
        )
        try:
            model = AutoModelForCausalLM.from_pretrained(
                model_name,
                quantization_config=quantization_config,
                device_map="auto",
                trust_remote_code=True,
            )
            logger.info("Base model successfully loaded with 4-bit QLoRA quantization.")
            return model, mode
        except Exception as e:
            logger.warning(f"4-bit quantization model load failed ({e}), falling back to standard precision.")

    # Standard / LoRA / CPU loading
    torch_dtype = torch.float16 if use_cuda else torch.float32
    device_map = "auto" if use_cuda else None

    try:
        # First attempt loading from local cache without blocking network calls
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch_dtype,
            device_map=device_map,
            trust_remote_code=True,
            local_files_only=True,
        )
        if not use_cuda:
            model = model.to(device)
        logger.info(f"Base model loaded from local cache on {device}.")
        return model, mode
    except Exception as local_err:
        logger.info(f"Local model cache not found for '{model_name}'. Attempting remote load or offline fallback.")

    if os.getenv("OFFLINE_MODE", "0") == "1" or os.getenv("DRY_RUN", "0") == "1":
        logger.info("OFFLINE_MODE active: using lightweight DummyQwenModel.")
        return _create_dummy_qwen_model(), mode

    try:
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch_dtype,
            device_map=device_map,
            trust_remote_code=True,
        )
        if not use_cuda:
            model = model.to(device)
        logger.info(f"Base model loaded successfully on {device}.")
        return model, mode
    except Exception as e:
        logger.warning(f"Could not load Hugging Face model '{model_name}' ({e}). Falling back to dummy architecture for testing/dry-run.")
        return _create_dummy_qwen_model(), mode



def _create_dummy_qwen_model():
    import torch.nn as nn

    class DummyQwenLayer(nn.Module):
        def __init__(self):
            super().__init__()
            self.q_proj = nn.Linear(10, 10)
            self.k_proj = nn.Linear(10, 10)
            self.v_proj = nn.Linear(10, 10)
            self.o_proj = nn.Linear(10, 10)
            self.gate_proj = nn.Linear(10, 10)
            self.up_proj = nn.Linear(10, 10)
            self.down_proj = nn.Linear(10, 10)

    class DummyQwenModel(nn.Module):
        def __init__(self):
            super().__init__()
            self.layers = nn.ModuleList([DummyQwenLayer()])
            self.config = type("Config", (), {"model_type": "qwen2", "hidden_size": 10})()

        def save_pretrained(self, save_directory):
            os.makedirs(save_directory, exist_ok=True)
            with open(os.path.join(save_directory, "config.json"), "w") as f:
                import json
                json.dump({"model_type": "qwen2"}, f)

    return DummyQwenModel()


import threading
import time
from model.config import ADAPTER_OUTPUT_DIR

class ModelSingletonManager:
    """
    Thread-safe global singleton for managing loaded PyTorch model, tokenizer,
    and adapter status across process lifetime.
    """
    _lock = threading.Lock()
    _model = None
    _tokenizer = None
    _adapter_status = "UNINITIALIZED"
    _model_load_time_seconds = 0.0
    _tokenizer_init_time_seconds = 0.0
    _base_model_init_time_seconds = 0.0
    _adapter_init_time_seconds = 0.0

    @classmethod
    def get_instance(
        cls,
        base_model_name: str = BASE_MODEL_NAME,
        adapter_path: str = ADAPTER_OUTPUT_DIR,
    ):
        """Returns loaded (model, tokenizer, adapter_status, model_load_time_seconds)."""
        if cls._model is not None and cls._tokenizer is not None:
            return cls._model, cls._tokenizer, cls._adapter_status, cls._model_load_time_seconds

        with cls._lock:
            if cls._model is not None and cls._tokenizer is not None:
                return cls._model, cls._tokenizer, cls._adapter_status, cls._model_load_time_seconds

            total_start_t = time.time()
            logger.info(f"Initializing global ModelSingletonManager for '{base_model_name}'...")

            # 1. Tokenizer initialization
            tok_start_t = time.time()
            from model.tokenizer import load_tokenizer
            tokenizer = load_tokenizer(base_model_name)
            cls._tokenizer_init_time_seconds = round(time.time() - tok_start_t, 4)
            logger.info(f"Tokenizer initialization completed in {cls._tokenizer_init_time_seconds}s")

            # 2. Base model initialization
            bm_start_t = time.time()
            model, mode = load_base_model(base_model_name)
            cls._base_model_init_time_seconds = round(time.time() - bm_start_t, 4)
            logger.info(f"Base model initialization completed in {cls._base_model_init_time_seconds}s")

            # 3. Adapter loading check
            adapter_start_t = time.time()
            adapter_config_file = os.path.join(adapter_path, "adapter_config.json")
            require_adapter = os.getenv("REQUIRE_ADAPTER", "0") == "1"

            if os.path.exists(adapter_config_file):
                try:
                    from peft import PeftModel
                    logger.info(f"[Adapter Status: FOUND] Loading LoRA adapter weights from '{adapter_path}'...")
                    model = PeftModel.from_pretrained(model, adapter_path)
                    adapter_status = "LOADED"
                    logger.info("[Adapter Status: LOADED] Successfully attached LoRA adapter to base model.")
                except Exception as e:
                    adapter_status = "FAILED"
                    logger.error(f"[Adapter Status: FAILED] Could not load LoRA adapter from '{adapter_path}': {e}")
                    if require_adapter:
                        raise RuntimeError(f"REQUIRE_ADAPTER=1 configured but adapter loading failed: {e}") from e
            else:
                adapter_status = "NOT_FOUND (Operating in Base Model Mode)"
                logger.warning(
                    f"[Adapter Status: NOT_FOUND] No adapter config file found at '{adapter_config_file}'. "
                    f"Operating in base model mode."
                )
                if require_adapter:
                    raise RuntimeError(
                        f"REQUIRE_ADAPTER=1 configured but adapter_config.json missing at '{adapter_config_file}'."
                    )

            cls._adapter_init_time_seconds = round(time.time() - adapter_start_t, 4)
            cls._model = model
            cls._tokenizer = tokenizer
            cls._adapter_status = adapter_status
            cls._model_load_time_seconds = round(time.time() - total_start_t, 4)

            logger.info(
                f"ModelSingletonManager initialization complete in {cls._model_load_time_seconds}s "
                f"(Tokenizer: {cls._tokenizer_init_time_seconds}s, Base Model: {cls._base_model_init_time_seconds}s, "
                f"Adapter: {cls._adapter_init_time_seconds}s). Adapter Status: {cls._adapter_status}"
            )
            return cls._model, cls._tokenizer, cls._adapter_status, cls._model_load_time_seconds

    @classmethod
    def reset(cls):
        with cls._lock:
            cls._model = None
            cls._tokenizer = None
            cls._adapter_status = "UNINITIALIZED"
            cls._model_load_time_seconds = 0.0
            cls._tokenizer_init_time_seconds = 0.0
            cls._base_model_init_time_seconds = 0.0
            cls._adapter_init_time_seconds = 0.0


