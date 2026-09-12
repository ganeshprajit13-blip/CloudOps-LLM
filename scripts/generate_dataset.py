import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from model.config import TEST_FILE, TRAIN_FILE, VALIDATION_FILE
from model.dataset import generate_synthetic_dataset, save_jsonl, split_dataset


def main():
    print("Generating CloudOps instruction-tuning dataset...")
    raw_examples = generate_synthetic_dataset(count=220)
    print(f"Generated {len(raw_examples)} total synthetic examples.")

    train_set, val_set, test_set = split_dataset(raw_examples)
    print(f"Dataset split completed:")
    print(f"  - Train: {len(train_set)} examples")
    print(f"  - Validation: {len(val_set)} examples")
    print(f"  - Test: {len(test_set)} examples")

    save_jsonl(train_set, TRAIN_FILE)
    save_jsonl(val_set, VALIDATION_FILE)
    save_jsonl(test_set, TEST_FILE)

    print(f"\nSaved dataset files:")
    print(f"  - {TRAIN_FILE}")
    print(f"  - {VALIDATION_FILE}")
    print(f"  - {TEST_FILE}")


if __name__ == "__main__":
    main()
