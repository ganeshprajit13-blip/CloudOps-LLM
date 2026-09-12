import argparse
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from model.train import CloudOpsTrainer


def main():
    parser = argparse.ArgumentParser(description="CloudOps LLM — Phase 5A Qwen2.5-3B-Instruct LoRA/QLoRA Fine-Tuning")
    parser.add_argument("--dry-run", action="store_true", help="Validate pipeline setup without full model training")
    parser.add_argument("--output-dir", type=str, default=None, help="Custom output directory for adapter weights")
    args = parser.parse_args()

    out_path = Path(args.output_dir) if args.output_dir else None
    trainer = CloudOpsTrainer(output_dir=out_path, dry_run=args.dry_run)
    metadata = trainer.run_training()

    print("\n" + "=" * 60)
    print("PHASE 5A MODEL TRAINING PIPELINE SUMMARY")
    print("=" * 60)
    print(f"Base Model             : {metadata['model_name']}")
    print(f"Mode                   : {metadata['mode']}")
    print(f"Target Modules         : {metadata['target_modules']}")
    print(f"Total Parameters       : {metadata['total_parameters']:,}")
    print(f"Trainable Parameters   : {metadata['trainable_parameters']:,}")
    print(f"Trainable Percentage   : {metadata['trainable_percentage']}%")
    print(f"Train Examples Count   : {metadata['train_examples_count']}")
    print(f"Validation Examples    : {metadata['val_examples_count']}")
    print(f"Output Adapter Directory: {metadata.get('output_dir', 'outputs/adapters/cloudops-qwen2.5-3b-lora')}")
    print("=" * 60)
    print("\n[PASS] Phase 5A execution complete.")


if __name__ == "__main__":
    main()
