"""
Tests for Real CloudOps Data Acquisition Phase (Step 2).

Validates:
- Downloaded files exist and are the correct size
- SHA-256 checksums match expected values
- Files are valid ZIP archives (PK magic bytes)
- Manifests exist and are valid JSON
- Required manifest fields are present and non-empty
- Preserved baseline datasets (test.jsonl, train.jsonl, validation.jsonl) are untouched
- LEMMA-RCA license restriction is documented in manifest
"""
import hashlib
import json
import os
import zipfile
from pathlib import Path

import pytest

# ─────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"
EXTERNAL = DATA / "external"
MANIFESTS = DATA / "manifests"
PROCESSED = DATA / "processed"


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def load_manifest(name: str) -> dict:
    p = MANIFESTS / name
    assert p.exists(), f"Manifest not found: {p}"
    with open(p, encoding="utf-8") as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────
# RCAEval tests
# ─────────────────────────────────────────────────────────────

class TestRCAEval:
    ZIP_PATH = EXTERNAL / "rcaeval" / "RCAEval-1.7.0.zip"
    TAR_PATH = EXTERNAL / "rcaeval" / "RCAEval-1.7.0.tar.gz"
    EXPECTED_ZIP_SHA256 = "C9F68B97E955220F9BDAD0E6C28BA083E96A6A0CB7610395307FE42925AE42AA"
    EXPECTED_TAR_SHA256 = "50A1ED4C7E4BF7F82ECB1342DB7E07E635BFFB450F9327E9C80D257B31F0DA93"
    EXPECTED_ZIP_SIZE = 2_362_516
    EXPECTED_TAR_SIZE = 2_302_319

    def test_zip_exists(self):
        assert self.ZIP_PATH.exists(), f"Missing: {self.ZIP_PATH}"

    def test_tar_exists(self):
        assert self.TAR_PATH.exists(), f"Missing: {self.TAR_PATH}"

    def test_zip_size(self):
        assert self.ZIP_PATH.stat().st_size == self.EXPECTED_ZIP_SIZE

    def test_tar_size(self):
        assert self.TAR_PATH.stat().st_size == self.EXPECTED_TAR_SIZE

    def test_zip_sha256(self):
        assert sha256_of(self.ZIP_PATH) == self.EXPECTED_ZIP_SHA256

    def test_tar_sha256(self):
        assert sha256_of(self.TAR_PATH) == self.EXPECTED_TAR_SHA256

    def test_zip_is_valid_zip(self):
        assert zipfile.is_zipfile(self.ZIP_PATH), "RCAEval ZIP is not a valid zip archive"

    def test_zip_readme_exists(self):
        readme = EXTERNAL / "rcaeval" / "README.md"
        assert readme.exists(), "RCAEval README.md is missing"

    def test_manifest_exists(self):
        m = load_manifest("rcaeval.manifest.json")
        assert m["dataset_name"] == "RCAEval"

    def test_manifest_license_present(self):
        m = load_manifest("rcaeval.manifest.json")
        assert "MIT" in m["license"]

    def test_manifest_provenance_present(self):
        m = load_manifest("rcaeval.manifest.json")
        assert m["provenance"] and len(m["provenance"]) > 50

    def test_manifest_record_count(self):
        m = load_manifest("rcaeval.manifest.json")
        assert m["record_count"] == 735

    def test_manifest_checksums_present(self):
        m = load_manifest("rcaeval.manifest.json")
        assert "checksum" in m
        checksums = m["checksum"]
        assert "RCAEval-1.7.0.zip" in checksums
        assert "RCAEval-1.7.0.tar.gz" in checksums

    def test_manifest_data_types(self):
        m = load_manifest("rcaeval.manifest.json")
        valid_types = {"logs", "metrics", "traces", "incidents", "configuration"}
        for dt in m["data_types"]:
            assert dt in valid_types, f"Invalid data_type: {dt}"


# ─────────────────────────────────────────────────────────────
# Post-mortems (incidents) tests
# ─────────────────────────────────────────────────────────────

class TestPostMortems:
    ZIP_PATH = EXTERNAL / "incidents" / "danluu-post-mortems-master.zip"
    EXPECTED_SHA256 = "8CF2D68BF6E15FFBBFE3B2A38F1C3D847BF07D13132B3B64D6BD60D1BC3E8D17"
    EXPECTED_SIZE = 39_456

    def test_zip_exists(self):
        assert self.ZIP_PATH.exists(), f"Missing: {self.ZIP_PATH}"

    def test_zip_size(self):
        assert self.ZIP_PATH.stat().st_size == self.EXPECTED_SIZE

    def test_zip_sha256(self):
        assert sha256_of(self.ZIP_PATH) == self.EXPECTED_SHA256

    def test_zip_is_valid_zip(self):
        assert zipfile.is_zipfile(self.ZIP_PATH), "post-mortems ZIP is not valid"

    def test_readme_exists(self):
        readme = EXTERNAL / "incidents" / "README.md"
        assert readme.exists()

    def test_manifest_exists(self):
        m = load_manifest("danluu-post-mortems.manifest.json")
        assert m["dataset_name"] == "danluu-post-mortems"

    def test_manifest_source_url(self):
        m = load_manifest("danluu-post-mortems.manifest.json")
        assert "danluu/post-mortems" in m["source_url"]

    def test_manifest_provenance_present(self):
        m = load_manifest("danluu-post-mortems.manifest.json")
        assert m["provenance"] and len(m["provenance"]) > 50

    def test_manifest_data_types(self):
        m = load_manifest("danluu-post-mortems.manifest.json")
        valid_types = {"logs", "metrics", "traces", "incidents", "configuration"}
        for dt in m["data_types"]:
            assert dt in valid_types


# ─────────────────────────────────────────────────────────────
# AWS RCA Deep Investigations tests
# ─────────────────────────────────────────────────────────────

class TestAWSRCADeepInvestigations:
    ZIP_PATH = EXTERNAL / "aws" / "aws-sample-rca-deep-investigations-main.zip"
    EXPECTED_SHA256 = "5D126D755185A5415BD6901414268175BB775CC85633295E656B603A12C5CD7D"
    EXPECTED_SIZE = 571_350

    def test_zip_exists(self):
        assert self.ZIP_PATH.exists(), f"Missing: {self.ZIP_PATH}"

    def test_zip_size(self):
        assert self.ZIP_PATH.stat().st_size == self.EXPECTED_SIZE

    def test_zip_sha256(self):
        assert sha256_of(self.ZIP_PATH) == self.EXPECTED_SHA256

    def test_zip_is_valid_zip(self):
        assert zipfile.is_zipfile(self.ZIP_PATH), "AWS RCA ZIP is not valid"

    def test_readme_exists(self):
        readme = EXTERNAL / "aws" / "README.md"
        assert readme.exists()

    def test_manifest_exists(self):
        m = load_manifest("aws-sample-rca-deep-investigations.manifest.json")
        assert m["dataset_name"] == "aws-sample-rca-deep-investigations"

    def test_manifest_license_is_permissive(self):
        m = load_manifest("aws-sample-rca-deep-investigations.manifest.json")
        # MIT-0 should be in license field
        assert "MIT" in m["license"]

    def test_manifest_cloud_provider_aws(self):
        m = load_manifest("aws-sample-rca-deep-investigations.manifest.json")
        assert "AWS" in m["cloud_provider"]

    def test_manifest_provenance_present(self):
        m = load_manifest("aws-sample-rca-deep-investigations.manifest.json")
        assert m["provenance"] and len(m["provenance"]) > 50


# ─────────────────────────────────────────────────────────────
# LEMMA-RCA Baselines tests
# ─────────────────────────────────────────────────────────────

class TestLEMMARCABaselines:
    ZIP_PATH = EXTERNAL / "microservices" / "lemma-rca-baselines-main.zip"
    EXPECTED_SHA256 = "781074D49DA7B04F4992AB2B9631AE63FC7ECAEE22D91376780A97232D7A8CD5"
    EXPECTED_SIZE = 1_792_968

    def test_zip_exists(self):
        assert self.ZIP_PATH.exists(), f"Missing: {self.ZIP_PATH}"

    def test_zip_size(self):
        assert self.ZIP_PATH.stat().st_size == self.EXPECTED_SIZE

    def test_zip_sha256(self):
        assert sha256_of(self.ZIP_PATH) == self.EXPECTED_SHA256

    def test_zip_is_valid_zip(self):
        assert zipfile.is_zipfile(self.ZIP_PATH), "LEMMA-RCA ZIP is not valid"

    def test_readme_exists(self):
        readme = EXTERNAL / "microservices" / "README.md"
        assert readme.exists()

    def test_manifest_exists(self):
        m = load_manifest("lemma-rca-baselines.manifest.json")
        assert m["dataset_name"] == "LEMMA-RCA-baselines"

    def test_manifest_license_documents_restriction(self):
        """CC BY-NC 4.0 restriction must be documented in manifest."""
        m = load_manifest("lemma-rca-baselines.manifest.json")
        license_str = m["license"].upper()
        assert "NON" in license_str or "NC" in license_str or "NON-COMMERCIAL" in license_str, (
            "LEMMA-RCA license restriction (CC BY-NC) must be documented in manifest"
        )

    def test_manifest_notes_warn_of_commercial_restriction(self):
        """Manifest notes must warn that commercial training is not permitted."""
        m = load_manifest("lemma-rca-baselines.manifest.json")
        notes = m.get("notes", "").lower()
        assert "commercial" in notes, "LEMMA-RCA notes must address commercial use restriction"

    def test_manifest_provenance_present(self):
        m = load_manifest("lemma-rca-baselines.manifest.json")
        assert m["provenance"] and len(m["provenance"]) > 50


# ─────────────────────────────────────────────────────────────
# Baseline dataset preservation tests
# ─────────────────────────────────────────────────────────────

class TestBaselineDatasetPreservation:
    """Ensure the original 412-example curated datasets were NOT modified."""

    TRAIN = PROCESSED / "train.jsonl"
    VALIDATION = PROCESSED / "validation.jsonl"
    TEST = PROCESSED / "test.jsonl"

    def test_train_exists(self):
        assert self.TRAIN.exists(), "train.jsonl must exist and be untouched"

    def test_validation_exists(self):
        assert self.VALIDATION.exists(), "validation.jsonl must exist and be untouched"

    def test_test_exists(self):
        assert self.TEST.exists(), "test.jsonl must exist and be untouched"

    def test_train_has_expected_count(self):
        with open(self.TRAIN, encoding="utf-8") as f:
            lines = [l for l in f if l.strip()]
        assert len(lines) == 176, f"Expected 176 train examples, got {len(lines)}"

    def test_validation_has_expected_count(self):
        with open(self.VALIDATION, encoding="utf-8") as f:
            lines = [l for l in f if l.strip()]
        assert len(lines) == 22, f"Expected 22 validation examples, got {len(lines)}"

    def test_test_has_expected_count(self):
        with open(self.TEST, encoding="utf-8") as f:
            lines = [l for l in f if l.strip()]
        assert len(lines) == 22, f"Expected 22 test examples, got {len(lines)}"

    def test_all_test_examples_valid_json(self):
        with open(self.TEST, encoding="utf-8") as f:
            for i, line in enumerate(f):
                if line.strip():
                    record = json.loads(line)
                    assert "instruction" in record, f"Test example {i} missing 'instruction'"
                    assert "output" in record, f"Test example {i} missing 'output'"

    def test_external_datasets_not_in_processed(self):
        """External datasets must remain isolated in data/external/."""
        external_markers = ["rcaeval", "post-mortem", "danluu", "lemma"]
        processed_files = list(PROCESSED.glob("*.jsonl"))
        for f in processed_files:
            fname = f.name.lower()
            for marker in external_markers:
                assert marker not in fname, (
                    f"External dataset marker '{marker}' found in processed/: {fname}"
                )


# ─────────────────────────────────────────────────────────────
# Directory isolation tests
# ─────────────────────────────────────────────────────────────

class TestDirectoryIsolation:
    """Each external dataset must be in its own isolated directory."""

    def test_rcaeval_isolated(self):
        assert (EXTERNAL / "rcaeval").is_dir()
        assert (EXTERNAL / "rcaeval" / "RCAEval-1.7.0.zip").exists()

    def test_incidents_isolated(self):
        assert (EXTERNAL / "incidents").is_dir()
        assert (EXTERNAL / "incidents" / "danluu-post-mortems-master.zip").exists()

    def test_aws_isolated(self):
        assert (EXTERNAL / "aws").is_dir()
        assert (EXTERNAL / "aws" / "aws-sample-rca-deep-investigations-main.zip").exists()

    def test_microservices_isolated(self):
        assert (EXTERNAL / "microservices").is_dir()
        assert (EXTERNAL / "microservices" / "lemma-rca-baselines-main.zip").exists()

    def test_manifests_in_correct_location(self):
        assert MANIFESTS.is_dir()
        for name in [
            "rcaeval.manifest.json",
            "danluu-post-mortems.manifest.json",
            "aws-sample-rca-deep-investigations.manifest.json",
            "lemma-rca-baselines.manifest.json",
        ]:
            assert (MANIFESTS / name).exists(), f"Missing manifest: {name}"

    def test_no_external_data_in_raw(self):
        """Raw data from external downloads must not be in data/raw/ yet."""
        raw_dir = DATA / "raw"
        if raw_dir.exists():
            raw_zips = list(raw_dir.glob("*.zip"))
            assert len(raw_zips) == 0, f"External ZIPs found in data/raw/: {raw_zips}"
