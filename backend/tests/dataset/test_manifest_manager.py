import json
import pytest
from pathlib import Path

from model.manifest_manager import (
    MANIFEST_SCHEMA_PATH,
    create_manifest,
    load_manifest,
    load_manifest_schema,
    save_manifest,
    update_manifest_status,
    validate_manifest,
)


def test_load_manifest_schema():
    """Verify that JSON schema exists and can be loaded."""
    schema = load_manifest_schema()
    assert schema["title"] == "CloudOpsDatasetManifest"
    assert "dataset_name" in schema["properties"]
    assert "license" in schema["properties"]
    assert "provenance" in schema["properties"]


def test_create_and_validate_manifest_valid():
    """Verify valid manifest creation and validation."""
    manifest = create_manifest(
        dataset_name="RCAEval_SockShop_Faults",
        license_name="Apache-2.0",
        provenance="Acquired from RCAEval GitHub repository releases",
        source_url="https://github.com/RCAEval/RCAEval",
        source_organization="RCAEval Research Group",
        data_types=["logs", "metrics", "traces"],
        cloud_provider="Kubernetes",
        services=["Microservices", "Docker"],
        processing_status="pending",
        sanitization_status="unverified"
    )

    is_valid, errors = validate_manifest(manifest)
    assert is_valid is True, f"Validation errors: {errors}"
    assert manifest["dataset_name"] == "RCAEval_SockShop_Faults"
    assert manifest["license"] == "Apache-2.0"


def test_manifest_validation_failures():
    """Verify schema validation catches missing required fields and invalid enum values."""
    # Missing required field
    incomplete = {
        "dataset_name": "Incomplete_Dataset",
        "processing_status": "pending",
        "sanitization_status": "unverified"
    }
    is_valid, errors = validate_manifest(incomplete)
    assert is_valid is False
    assert any("license" in err for err in errors)

    # Invalid status enum
    invalid_status = create_manifest(
        dataset_name="Test",
        license_name="MIT",
        provenance="Lineage",
        processing_status="super_ready"
    )
    is_valid, errors = validate_manifest(invalid_status)
    assert is_valid is False
    assert any("processing_status" in err for err in errors)


def test_readiness_validation_provenance_and_license_required():
    """
    CRITICAL BUSINESS RULE TEST:
    Verify that a dataset CANNOT be marked 'ready' unless provenance and license are present and non-empty.
    """
    # 1. Ready with empty license -> FAIL
    manifest_no_license = create_manifest(
        dataset_name="Missing_License_Dataset",
        license_name="",
        provenance="Valid provenance details provided",
        processing_status="ready",
        sanitization_status="clean"
    )
    is_valid, errors = validate_manifest(manifest_no_license)
    assert is_valid is False
    assert any("license" in err.lower() for err in errors)

    # 2. Ready with 'unknown' provenance -> FAIL
    manifest_unknown_prov = create_manifest(
        dataset_name="Unknown_Prov_Dataset",
        license_name="MIT",
        provenance="unknown",
        processing_status="ready",
        sanitization_status="clean"
    )
    is_valid, errors = validate_manifest(manifest_unknown_prov)
    assert is_valid is False
    assert any("provenance" in err.lower() for err in errors)

    # 3. Ready with valid explicit provenance and license -> PASS
    manifest_valid_ready = create_manifest(
        dataset_name="Valid_Ready_Dataset",
        license_name="MIT",
        provenance="Downloaded from public GitHub RCA repository commit sha a1b2c3d4",
        processing_status="ready",
        sanitization_status="clean"
    )
    is_valid, errors = validate_manifest(manifest_valid_ready)
    assert is_valid is True, f"Errors: {errors}"


def test_save_and_load_manifest(tmp_path):
    """Verify manifest file persistence and loading."""
    manifest = create_manifest(
        dataset_name="Test_Persist",
        license_name="CC-BY-4.0",
        provenance="Local test pipeline",
        processing_status="extracted"
    )

    manifest_file = tmp_path / "manifests" / "test_persist.manifest.json"
    ok, errors = save_manifest(manifest, manifest_file)
    assert ok is True, f"Save errors: {errors}"
    assert manifest_file.exists()

    loaded = load_manifest(manifest_file)
    assert loaded["dataset_name"] == "Test_Persist"
    assert loaded["license"] == "CC-BY-4.0"


def test_update_manifest_status():
    """Verify status update validation."""
    manifest = create_manifest(
        dataset_name="Status_Test",
        license_name="Apache-2.0",
        provenance="Explicit acquisition lineage details",
        processing_status="pending"
    )

    ok, errors = update_manifest_status(manifest, processing_status="sanitized", sanitization_status="scrubbed")
    assert ok is True, f"Errors: {errors}"

    # Try setting status to ready with empty provenance -> FAIL
    manifest["provenance"] = ""
    ok, errors = update_manifest_status(manifest, processing_status="ready")
    assert ok is False
    assert any("provenance" in err.lower() for err in errors)
