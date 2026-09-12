import json
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from model.config import PROCESSED_DATA_DIR, TEST_FILE, TRAIN_FILE, VALIDATION_FILE
from model.dataset import load_jsonl, validate_example


def validate_dataset_split(filepath: Path, split_name: str) -> Tuple[int, int, List[str], set]:
    """Validates a single dataset split file."""
    print(f"\nScanning split: {split_name} ({filepath.name})...")
    if not filepath.exists():
        print(f"  ❌ Error: File not found: {filepath}")
        return 0, 0, [f"File not found: {filepath}"], set()

    examples = load_jsonl(filepath)
    valid_count = 0
    invalid_count = 0
    all_errors = []
    seen_inputs = set()

    for idx, ex in enumerate(examples, start=1):
        is_valid, errors = validate_example(ex)
        inp_key = (ex.get("instruction", ""), ex.get("input", ""))

        if inp_key in seen_inputs:
            errors.append("Duplicate input found in same split")
            is_valid = False
        else:
            seen_inputs.add(inp_key)

        if is_valid:
            valid_count += 1
        else:
            invalid_count += 1
            all_errors.append(f"Example #{idx} in {split_name}: " + "; ".join(errors))

    return valid_count, invalid_count, all_errors, seen_inputs


def main():
    print("=" * 60)
    print("CloudOps LLM — Dataset Validation & Integrity Scanner")
    print("=" * 60)

    splits = [
        (TRAIN_FILE, "Train"),
        (VALIDATION_FILE, "Validation"),
        (TEST_FILE, "Test"),
    ]

    total_valid = 0
    total_invalid = 0
    all_issues = []
    seen_across_splits = {}
    leakage_errors = []

    for filepath, name in splits:
        v_count, inv_count, errors, inputs = validate_dataset_split(filepath, name)
        total_valid += v_count
        total_invalid += inv_count
        all_issues.extend(errors)

        # Data leakage check across splits
        for inp in inputs:
            if inp in seen_across_splits:
                leakage_errors.append(
                    f"Data leakage detected! Input in '{name}' split already exists in '{seen_across_splits[inp]}' split."
                )
            else:
                seen_across_splits[inp] = name

    all_issues.extend(leakage_errors)

    total_examples = total_valid + total_invalid

    print("\n" + "=" * 60)
    print("DATASET VALIDATION SUMMARY REPORT")
    print("=" * 60)
    print(f"  Total Processed Examples: {total_examples}")
    print(f"  Valid Examples          : {total_valid}")
    print(f"  Invalid Examples        : {total_invalid}")
    print(f"  Data Leakage Issues     : {len(leakage_errors)}")
    print(f"  Train Set Count         : {len(load_jsonl(TRAIN_FILE))}")
    print(f"  Validation Set Count    : {len(load_jsonl(VALIDATION_FILE))}")
    print(f"  Test Set Count          : {len(load_jsonl(TEST_FILE))}")

    if all_issues:
        print("\n[FAIL] Validation Failures Found:")
        for err in all_issues[:10]:
            print(f"  - {err}")
        if len(all_issues) > 10:
            print(f"  ... and {len(all_issues) - 10} more issues.")
        print("\nRESULT: FAILED")
        sys.exit(1)
    else:
        print("\n[PASS] RESULT: ALL DATASET SPLITS ARE 100% VALID AND PASSED AUDIT")
        sys.exit(0)



if __name__ == "__main__":
    main()
