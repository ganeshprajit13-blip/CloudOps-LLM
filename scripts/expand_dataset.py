import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from model.config import DATA_DIR, PROCESSED_DATA_DIR, TEST_FILE, TRAIN_FILE, VALIDATION_FILE
from model.data_expansion import CloudOpsScenarioGenerator, ExternalDatasetImporter
from model.dataset import (
    generate_dataset_statistics,
    generate_decoupled_dataset_statistics,
    group_and_split_dataset,
    load_jsonl,
    save_jsonl,
    validate_example,
)

RAW_EXPANDED_DIR = DATA_DIR / "raw" / "expanded"


def print_group_report(title: str, stats: dict):
    print(f"\n--- {title} ---")
    print(f"  Total Examples                : {stats['total_examples']}")
    print(f"  Exact Duplicate Count         : {stats['exact_duplicates']}")
    print(f"  Near-Duplicate Pairs (>=0.85) : {stats.get('near_duplicate_pairs_85', 0)}")
    print(f"  Near-Duplicate Pairs (>=0.75) : {stats.get('near_duplicate_pairs_75', 0)}")
    print(f"  Low Confidence (<= 0.50)      : {stats.get('low_confidence_examples', 0)}")
    print(f"  High Confidence (> 0.50)      : {stats.get('high_confidence_examples', 0)}")

    if "scenario_breakdown" in stats:
        print("  Scenario Types Breakdown:")
        for scen, cnt in sorted(stats['scenario_breakdown'].items(), key=lambda x: x[1], reverse=True):
            pct = (cnt / stats['total_examples']) * 100 if stats['total_examples'] > 0 else 0
            print(f"    * {scen:32s}: {cnt:3d} ({pct:5.1f}%)")

    print("  Top AWS Services:")
    top_services = list(sorted(stats['services_breakdown'].items(), key=lambda x: x[1], reverse=True))[:10]
    for svc, cnt in top_services:
        print(f"    * {svc:30s}: {cnt:3d}")


def main():
    parser = argparse.ArgumentParser(description="CloudOps LLM — Dataset Expansion & Quality Assurance Framework")
    parser.add_argument("--count-per-category", type=int, default=12, help="Number of synthetic examples to generate per category for sample run")
    parser.add_argument("--import-file", type=str, default=None, help="Path to external raw JSONL dataset to import")
    parser.add_argument("--source-name", type=str, default="External_RCA", help="Metadata source name for external import")
    parser.add_argument("--license-name", type=str, default="MIT", help="License identifier for external import")
    args = parser.parse_args()

    RAW_EXPANDED_DIR.mkdir(parents=True, exist_ok=True)
    print("=" * 70)
    print("CLOUDOPS LLM — DATASET EXPANSION & QUALITY CONTROL FRAMEWORK")
    print("=" * 70)

    # 1. Load existing curated dataset
    print(f"\n1. Loading existing curated dataset splits:")
    train_curated = load_jsonl(TRAIN_FILE)
    val_curated = load_jsonl(VALIDATION_FILE)
    test_curated = load_jsonl(TEST_FILE)
    original_curated_all = train_curated + val_curated + test_curated

    print(f"   - Curated Train      : {len(train_curated)} examples")
    print(f"   - Curated Validation : {len(val_curated)} examples")
    print(f"   - Curated Test (PRESERVED): {len(test_curated)} examples (PRESERVED - UNTOUCHED)")
    print(f"   - Total Original Curated: {len(original_curated_all)} examples")

    all_expanded_raw = []

    # 2. Generate sample synthetic batch across all 25 categories
    print(f"\n2. Generating synthetic scenario batch ({args.count_per_category} per category across 25 categories)...")
    generator = CloudOpsScenarioGenerator()
    synthetic_batch = generator.generate_scenarios(count_per_category=args.count_per_category)
    print(f"   - Synthetic batch generated: {len(synthetic_batch)} examples")

    raw_synth_path = RAW_EXPANDED_DIR / "sample_synthetic_expanded.jsonl"
    save_jsonl(synthetic_batch, raw_synth_path)
    print(f"   - Saved raw synthetic batch to: {raw_synth_path}")
    all_expanded_raw.extend(synthetic_batch)

    # 3. External dataset import (if provided)
    if args.import_file:
        import_path = Path(args.import_file)
        print(f"\n3. Importing external dataset from '{import_path}'...")
        importer = ExternalDatasetImporter()
        imported = importer.import_from_jsonl(import_path, args.source_name, args.license_name)
        print(f"   - Imported and normalized {len(imported)} external examples")
        all_expanded_raw.extend(imported)

    # 4. Merge with existing curated train + val (keeping test separate)
    combined_train_val = train_curated + val_curated + all_expanded_raw
    print(f"\n4. Combined raw candidates count: {len(combined_train_val)} (excluding test set)")

    # 5. Quality Control & Deduplication
    print("\n5. Running Quality Control & Deduplication...")
    valid_candidates = []
    invalid_count = 0

    for ex in combined_train_val:
        is_valid, errors = validate_example(ex)
        if is_valid:
            valid_candidates.append(ex)
        else:
            invalid_count += 1

    print(f"   - Valid examples: {len(valid_candidates)}")
    print(f"   - Rejected invalid examples: {invalid_count}")

    # 6. Grouped Splitting (Anti-leakage)
    print("\n6. Splitting expanded candidates using variant grouping (protecting test set)...")
    new_train, new_val, new_extra_test = group_and_split_dataset(
        valid_candidates,
        train_ratio=0.88,
        val_ratio=0.12,
        test_ratio=0.0
    )

    print(f"   - Expanded Train Set      : {len(new_train)} examples")
    print(f"   - Expanded Validation Set : {len(new_val)} examples")
    print(f"   - Preserved Original Test : {len(test_curated)} examples")
    print(f"   - Total Combined Dataset  : {len(new_train) + len(new_val) + len(test_curated)} examples")

    # 7. Generate Decoupled 3-Way Dataset Statistics Report
    decoupled_stats = generate_decoupled_dataset_statistics(
        curated_examples=original_curated_all,
        generated_examples=synthetic_batch,
        preserved_test_examples=test_curated
    )

    print("\n" + "=" * 70)
    print("DECOUPLED 3-WAY DATASET METRICS & STATISTICS REPORT")
    print("=" * 70)

    print_group_report("1. ORIGINAL CURATED DATASET (Baseline 220 Examples)", decoupled_stats["curated"])
    print_group_report("2. NEWLY GENERATED VALIDATION DATASET (~200 Examples)", decoupled_stats["generated"])
    print_group_report("3. COMBINED EXPANDED DATASET (~420 Examples)", decoupled_stats["combined"])

    print("\n--- DECOUPLED DEDUPLICATION & SIGNATURE UNIQUENESS METRICS ---")
    print(f"  Curated Internal Near-Duplicates (>=0.85) : {decoupled_stats['curated'].get('near_duplicate_pairs_85', 0)}")
    print(f"  Curated Internal Near-Duplicates (>=0.75) : {decoupled_stats['curated'].get('near_duplicate_pairs_75', 0)}")
    print(f"  Generated Internal Near-Duplicates (>=0.85): {decoupled_stats['generated'].get('near_duplicate_pairs_85', 0)}")
    print(f"  Generated Internal Near-Duplicates (>=0.75): {decoupled_stats['generated'].get('near_duplicate_pairs_75', 0)}")
    print(f"  Cross-Group Near-Duplicates (Curated vs Gen >=0.85): {decoupled_stats['cross_near_duplicates_85']}")
    print(f"  Cross-Group Near-Duplicates (Curated vs Gen >=0.75): {decoupled_stats['cross_near_duplicates_75']}")
    print(f"  Generated Semantic Signature Uniqueness Rate: {decoupled_stats['generated_signature_uniqueness_rate'] * 100:.1f}% ({decoupled_stats['generated_unique_signatures_count']}/{len(synthetic_batch)} unique)")

    print("=" * 70)
    print("\n[NOTE] Validation sample generation and 3-way decoupled reporting completed cleanly.")
    print("Full generation paused. Waiting for user approval before scaling to thousands of examples.")


if __name__ == "__main__":
    main()
