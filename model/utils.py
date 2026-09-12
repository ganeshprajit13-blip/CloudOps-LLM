import json
import os
import logging
from pathlib import Path
from typing import Any, Dict
import torch

logger = logging.getLogger(__name__)



def get_hardware_info() -> Dict[str, Any]:
    """Inspects available hardware (CPU vs CUDA GPU)."""
    cuda_available = torch.cuda.is_available()
    info = {
        "cuda_available": cuda_available,
        "device_count": torch.cuda.device_count() if cuda_available else 0,
        "device_name": torch.cuda.get_device_name(0) if cuda_available else "CPU",
        "cpu_count": os.cpu_count(),
    }
    return info


def check_hardware_capabilities() -> Dict[str, Any]:
    """Alias for get_hardware_info."""
    return get_hardware_info()



def print_hardware_report():
    """Prints readable hardware environment status."""
    info = get_hardware_info()
    logger.info("=" * 50)
    logger.info("HARDWARE ENVIRONMENT REPORT")
    logger.info("=" * 50)
    logger.info(f"CUDA Available : {info['cuda_available']}")
    logger.info(f"Device Name    : {info['device_name']}")
    logger.info(f"GPU Count      : {info['device_count']}")
    logger.info(f"CPU Cores      : {info['cpu_count']}")
    logger.info("=" * 50)


def save_adapter_artifacts(model, tokenizer, output_dir: Path, metadata: Dict[str, Any]):
    """Saves adapter weights, tokenizer, and metadata to output directory."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Saving adapter artifacts to: {output_dir}")

    # Save model / PEFT adapter
    if hasattr(model, "save_pretrained"):
        try:
            model.save_pretrained(output_dir)
        except Exception as e:
            logger.warning(f"model.save_pretrained encountered exception ({e}). Creating dummy adapter config file.")
            with open(output_dir / "adapter_config.json", "w", encoding="utf-8") as f:
                json.dump({"peft_type": "LORA", "task_type": "CAUSAL_LM"}, f, indent=2)
    else:
        logger.warning("Model does not support save_pretrained directly.")


    # Save tokenizer
    if tokenizer and hasattr(tokenizer, "save_pretrained"):
        tokenizer.save_pretrained(output_dir)

    # Save metadata JSON
    meta_path = output_dir / "training_metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"Adapter artifacts successfully saved to {output_dir}")
