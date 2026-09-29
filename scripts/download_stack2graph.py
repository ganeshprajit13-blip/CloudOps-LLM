"""
Script to download complete Hugging Face dataset: Mo7art/Stack2Graph_VD_r (~21.9 GB)
using huggingface_hub snapshot_download into datasets/stack2graph_r/
"""

import os
import sys
import time
from pathlib import Path
from huggingface_hub import snapshot_download

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOCAL_DIR = PROJECT_ROOT / "datasets" / "stack2graph_r"

def get_dir_size_and_files(path: Path):
    total_size = 0
    file_list = []
    if not path.exists():
        return 0, []
    for p in path.rglob("*"):
        if p.is_file():
            size = p.stat().st_size
            total_size += size
            rel_path = p.relative_to(path)
            file_list.append((str(rel_path), size))
    return total_size, file_list

def main():
    print("=" * 80)
    print("DOWNLOADING HUGGING FACE DATASET: Mo7art/Stack2Graph_VD_r")
    print("=" * 80)
    
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Target Directory : {LOCAL_DIR}")
    
    start_time = time.time()
    
    try:
        download_path = snapshot_download(
            repo_id="Mo7art/Stack2Graph_VD_r",
            repo_type="dataset",
            local_dir=str(LOCAL_DIR),
            max_workers=4
        )
        elapsed = time.time() - start_time
        print(f"\n[SUCCESS] snapshot_download completed in {elapsed:.2f} seconds.")
    except Exception as e:
        print(f"\n[ERROR] Download failed: {e}")
        sys.exit(1)

    print("\n" + "=" * 80)
    print("VERIFYING LOCAL DATASET FILES & DISK USAGE")
    print("=" * 80)

    total_bytes, file_list = get_dir_size_and_files(LOCAL_DIR)
    total_gb = total_bytes / (1024 ** 3)
    
    print(f"Total Files Downloaded : {len(file_list)}")
    print(f"Total Local Disk Size  : {total_gb:.2f} GB ({total_bytes:,} bytes)")
    
    print("\n--- Downloaded File Listing & File Sizes ---")
    for rel_path, fsize in sorted(file_list, key=lambda x: x[0]):
        mb_size = fsize / (1024 * 1024)
        gb_size = fsize / (1024 ** 3)
        if gb_size >= 0.1:
            size_str = f"{gb_size:.2f} GB"
        else:
            size_str = f"{mb_size:.2f} MB"
        print(f"  {rel_path:<70} | {size_str:>10}")

    print("\n--- Summary Verification ---")
    approx_match = 20.0 <= total_gb <= 25.0
    print(f"Approx 21.9 GB Match Confirmation : {'YES' if approx_match else 'NO'} ({total_gb:.2f} GB calculated)")
    
    if approx_match:
        print("\nAll files downloaded successfully. Dataset ready at datasets/stack2graph_r.")
    else:
        print(f"\nWarning: Expected ~21.9 GB, got {total_gb:.2f} GB. Please check for missing files.")

if __name__ == "__main__":
    main()
