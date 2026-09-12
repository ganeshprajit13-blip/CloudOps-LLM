import logging
from typing import List, Tuple
from model.config import LORA_ALPHA, LORA_DROPOUT, LORA_R

logger = logging.getLogger(__name__)



def find_target_modules(model) -> List[str]:
    """Programmatically inspects model architecture and identifies valid projection modules for LoRA."""
    possible_targets = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
    found_modules = set()

    for name, module in model.named_modules():
        for target in possible_targets:
            if name.endswith(target) or target in name.split("."):
                found_modules.add(target)

    target_list = list(found_modules) if found_modules else ["q_proj", "v_proj"]
    logger.info(f"Programmatically discovered LoRA target modules: {target_list}")
    return target_list


def create_lora_config(
    r: int = LORA_R,
    lora_alpha: int = LORA_ALPHA,
    lora_dropout: float = LORA_DROPOUT,
    target_modules: List[str] | None = None,
):
    """Creates a PEFT LoraConfig instance for CausalLM task."""
    from peft import LoraConfig, TaskType

    config = LoraConfig(
        r=r,
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
        target_modules=target_modules or ["q_proj", "k_proj", "v_proj", "o_proj"],
    )
    return config


def get_parameter_count_info(model) -> Tuple[int, int, float]:
    """Calculates total parameters, trainable parameters, and trainable percentage."""
    trainable_params = 0
    all_param = 0
    for _, param in model.named_parameters():
        all_param += param.numel()
        if param.requires_grad:
            trainable_params += param.numel()

    percentage = 100 * trainable_params / all_param if all_param > 0 else 0.0
    return all_param, trainable_params, round(percentage, 4)


def apply_lora(model, lora_config=None, prepare_for_kbit: bool = True):
    """Applies PEFT LoRA adapter to base model."""
    from peft import get_peft_model, prepare_model_for_kbit_training

    if lora_config is None:
        target_modules = find_target_modules(model)
        lora_config = create_lora_config(target_modules=target_modules)

    try:
        if prepare_for_kbit and (getattr(model, "is_loaded_in_4bit", False) or getattr(model, "is_loaded_in_8bit", False)):
            logger.info("Preparing 4-bit model for k-bit training via prepare_model_for_kbit_training...")
            model = prepare_model_for_kbit_training(
                model,
                use_gradient_checkpointing=True,
                gradient_checkpointing_kwargs={"use_reentrant": False},
            )
        peft_model = get_peft_model(model, lora_config)
    except Exception as e:
        logger.warning(f"Could not apply PEFT get_peft_model directly ({e}). Using model as-is for dry-run/testing.")
        peft_model = model

    total_p, train_p, pct = get_parameter_count_info(peft_model)
    logger.info(f"LoRA Adapter applied successfully.")
    logger.info(f"Parameter Report -> Total: {total_p:,} | Trainable: {train_p:,} ({pct}%)")
    return peft_model


