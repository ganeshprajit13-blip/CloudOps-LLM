#!/usr/bin/env python3
"""
Phase 1: Inspection Script for 3 Hugging Face Datasets:
1. Skilln/devops-qa-dataset
2. Omarrran/StackPulse_778K_QnA_Code_dataset (full)
3. thegovind/azure-architecture-vqa
"""

import sys
import json
from pathlib import Path
from datasets import load_dataset

def inspect_ds(ds_name, ds_obj):
    print("=" * 80)
    print(f"DATASET: {ds_name}")
    print("=" * 80)
    print(f"Splits: {list(ds_obj.keys())}")
    for split_name in ds_obj.keys():
        split = ds_obj[split_name]
        print(f"\n--- Split: {split_name} ---")
        print(f"Number of records: {len(split)}")
        print(f"Column names: {split.column_names}")
        print(f"Features: {split.features}")

        # Missing value check & 3 representative examples
        sample_count = min(3, len(split))
        print(f"\n3 Representative Examples from '{split_name}':")
        for i in range(sample_count):
            ex = split[i]
            print(f"\n  [Example #{i+1}]:")
            for col in split.column_names:
                val = ex[col]
                val_type = type(val).__name__
                if isinstance(val, str):
                    val_preview = val[:150].replace('\n', ' ') + ('...' if len(val) > 150 else '')
                else:
                    val_preview = str(val)[:150]
                print(f"    - {col} ({val_type}): {val_preview}")

def main():
    print("Loading datasets for inspection...")
    
    # 1. Skilln/devops-qa-dataset
    print("\n1. Loading Skilln/devops-qa-dataset...")
    try:
        devops_ds = load_dataset("Skilln/devops-qa-dataset")
        inspect_ds("Skilln/devops-qa-dataset", devops_ds)
    except Exception as e:
        print(f"Error loading devops-qa-dataset: {e}")

    # 2. Omarrran/StackPulse_778K_QnA_Code_dataset ("full")
    print("\n2. Loading Omarrran/StackPulse_778K_QnA_Code_dataset ('full')...")
    try:
        stack_ds = load_dataset("Omarrran/StackPulse_778K_QnA_Code_dataset", "full")
        inspect_ds("Omarrran/StackPulse_778K_QnA_Code_dataset ('full')", stack_ds)
    except Exception as e:
        print(f"Error loading StackPulse: {e}")

    # 3. thegovind/azure-architecture-vqa
    print("\n3. Loading thegovind/azure-architecture-vqa...")
    try:
        azure_ds = load_dataset("thegovind/azure-architecture-vqa")
        inspect_ds("thegovind/azure-architecture-vqa", azure_ds)
    except Exception as e:
        print(f"Error loading azure-architecture-vqa: {e}")

if __name__ == "__main__":
    main()
