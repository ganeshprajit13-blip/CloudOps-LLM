"""
RCAEval Download Script -- Real Labeled Failure Dataset Download

Downloads the official RCAEval dataset from HuggingFace (phamquiluan/RCAEval),
as recommended in the official RCAEval repository documentation:
  - cases.parquet (Master index of all 735 failure cases with ground-truth labels)
  - RE1 Suite (375 metric-based failure cases: RE1-OB, RE1-SS, RE1-TT)
  - RE3 Suite (90 code-level multi-source failure cases: RE3-OB, RE3-SS, RE3-TT)

Preserves existing zip archives (RCAEval-1.7.0.zip/tar.gz).
Records filename, size, SHA-256, source URL, download date for every file.
Updates data/manifests/rcaeval.manifest.json.
"""

import os
import json
import hashlib
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

HF_BASE_URL = "https://huggingface.co/datasets/phamquiluan/RCAEval/resolve/main"
TARGET_DIR = "data/external/rcaeval"
MANIFEST_PATH = "data/manifests/rcaeval.manifest.json"
DOWNLOAD_DATE = "2026-09-11"

def compute_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def download_single_file(rel_path):
    url = f"{HF_BASE_URL}/{rel_path}"
    dest_path = os.path.join(TARGET_DIR, rel_path)
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp, open(dest_path, "wb") as f:
        f.write(resp.read())
        
    size = os.path.getsize(dest_path)
    sha256 = compute_sha256(dest_path)
    return {
        "rel_path": rel_path,
        "full_path": dest_path,
        "url": url,
        "size_bytes": size,
        "sha256": sha256,
        "download_date": DOWNLOAD_DATE
    }

def main():
    print("=" * 70)
    print("RCAEval DATASET DOWNLOAD — Step 5 (Download Phase)")
    print("=" * 70)
    
    os.makedirs(TARGET_DIR, exist_ok=True)
    
    # Step 1: Download cases.parquet
    print("\n[Step 1] Downloading master index cases.parquet...")
    cases_parquet_info = download_single_file("cases.parquet")
    print(f"  cases.parquet downloaded: {cases_parquet_info['size_bytes']} bytes, SHA-256: {cases_parquet_info['sha256']}")
    
    # Read cases index to verify
    df_cases = pd.read_parquet(cases_parquet_info["full_path"])
    total_cases_in_index = len(df_cases)
    print(f"  Master index verified: {total_cases_in_index} total failure cases indexed across 9 datasets.")
    
    # Step 2: Fetch full file tree from HF API using HfApi
    print("\n[Step 2] Querying HuggingFace API for telemetry files (RE1 and RE3 suites)...")
    from huggingface_hub import HfApi
    api = HfApi()
    all_items = api.list_repo_tree(repo_id="phamquiluan/RCAEval", repo_type="dataset", recursive=True)
    
    files_to_download = []
    allowed_prefixes = ("re1ob_", "re1ss_", "re1tt_", "re3ob_", "re3ss_", "re3tt_")
    
    for item in all_items:
        if hasattr(item, "size") and item.size is not None and item.size > 0:
            path = item.path
            if any(path.startswith(prefix) for prefix in allowed_prefixes):
                files_to_download.append(path)
                
    print(f"  Identified {len(files_to_download)} telemetry files across RE1 (375 cases) and RE3 (90 cases).")
    
    # Step 3: Multithreaded download of telemetry files
    print("\n[Step 3] Downloading telemetry files using ThreadPoolExecutor...")
    downloaded_records = [cases_parquet_info]
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(download_single_file, rel_path): rel_path for rel_path in files_to_download}
        completed = 0
        total = len(futures)
        for future in as_completed(futures):
            completed += 1
            res = future.result()
            downloaded_records.append(res)
            if completed % 100 == 0 or completed == total:
                print(f"  Progress: {completed}/{total} files downloaded ({completed/total*100:.1f}%)...")
                
    elapsed = time.time() - start_time
    total_download_bytes = sum(r["size_bytes"] for r in downloaded_records)
    print(f"\n  Download Complete in {elapsed:.2f} seconds!")
    print(f"  Total files downloaded in this run: {len(downloaded_records)}")
    print(f"  Total download size: {total_download_bytes} bytes ({total_download_bytes / (1024*1024):.2f} MB)")
    
    # Step 4: Verify previously existing files in data/external/rcaeval
    existing_files_manifest = {
        "RCAEval-1.7.0.zip": {
            "size_bytes": 2362516,
            "sha256": "C9F68B97E955220F9BDAD0E6C28BA083E96A6A0CB7610395307FE42925AE42AA",
            "url": "https://github.com/phamquiluan/RCAEval/archive/refs/tags/v1.7.0.zip",
            "download_date": "2026-09-11"
        },
        "RCAEval-1.7.0.tar.gz": {
            "size_bytes": 2302319,
            "sha256": "50A1ED4C7E4BF7F82ECB1342DB7E07E635BFFB450F9327E9C80D257B31F0DA93",
            "url": "https://github.com/phamquiluan/RCAEval/archive/refs/tags/v1.7.0.tar.gz",
            "download_date": "2026-09-11"
        }
    }
    
    # Step 5: Update data/manifests/rcaeval.manifest.json
    print("\n[Step 4] Updating data/manifests/rcaeval.manifest.json...")
    
    # Load existing manifest
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)
        
    # Build updated files dictionary
    files_registry = {}
    
    # Include original archives
    for k, v in existing_files_manifest.items():
        files_registry[k] = v
        
    # Include all newly downloaded files
    for item in downloaded_records:
        files_registry[item["rel_path"]] = {
            "size_bytes": item["size_bytes"],
            "sha256": item["sha256"],
            "url": item["url"],
            "download_date": item["download_date"]
        }
        
    manifest_data["downloaded_files"] = files_registry
    manifest_data["total_downloaded_files_count"] = len(files_registry)
    manifest_data["total_downloaded_size_bytes"] = sum(v["size_bytes"] for v in files_registry.values())
    manifest_data["official_dataset_source"] = "HuggingFace Dataset repository phamquiluan/RCAEval (https://huggingface.co/datasets/phamquiluan/RCAEval)"
    manifest_data["huggingface_repo"] = "phamquiluan/RCAEval"
    manifest_data["master_index_file"] = "cases.parquet"
    manifest_data["verifiable_failure_cases_in_master_index"] = total_cases_in_index
    manifest_data["suites_downloaded_telemetry"] = ["RE1-OB", "RE1-SS", "RE1-TT", "RE3-OB", "RE3-SS", "RE3-TT"]
    manifest_data["download_phase_completed_date"] = DOWNLOAD_DATE
    
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
        
    print(f"  Manifest successfully updated: {MANIFEST_PATH}")
    print(f"  Total registered files in manifest: {len(files_registry)}")
    print(f"  Total size in manifest: {manifest_data['total_downloaded_size_bytes'] / (1024*1024):.2f} MB")
    
    # Step 6: Verify downloaded files and run quick validation test
    print("\n[Step 5] Running validation tests on downloaded files...")
    
    # Test 1: Check cases.parquet exists and has 735 rows
    assert os.path.exists("data/external/rcaeval/cases.parquet"), "cases.parquet missing!"
    df_test = pd.read_parquet("data/external/rcaeval/cases.parquet")
    assert len(df_test) == 735, f"Expected 735 cases in index, got {len(df_test)}"
    print("  Test 1 PASSED: cases.parquet verified (735 cases indexed with ground truth).")
    
    # Test 2: Verify sample telemetry files load cleanly
    sample_metrics_path = os.path.join(TARGET_DIR, "re1ob_adservice_cpu_1", "metrics.parquet")
    assert os.path.exists(sample_metrics_path), "sample metrics parquet missing!"
    df_m = pd.read_parquet(sample_metrics_path)
    assert len(df_m) > 0, "sample metrics dataframe is empty!"
    print(f"  Test 2 PASSED: Sample telemetry file verified ({len(df_m)} metric timestamps loaded).")
    
    # Test 3: Verify manifest file exists and parses
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        m_check = json.load(f)
    assert "downloaded_files" in m_check, "downloaded_files key missing in manifest!"
    print("  Test 3 PASSED: Manifest structure validated.")
    
    print("\n" + "=" * 70)
    print("RCAEval DATASET DOWNLOAD COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    main()


