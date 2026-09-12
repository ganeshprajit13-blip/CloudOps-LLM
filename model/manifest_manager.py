import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

MANIFEST_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "data" / "manifests" / "dataset_manifest.schema.json"

VALID_DATA_TYPES = {"logs", "metrics", "traces", "incidents", "configuration"}
VALID_PROCESSING_STATUSES = {"pending", "downloading", "extracted", "sanitized", "normalized", "processed", "ready", "failed"}
VALID_SANITIZATION_STATUSES = {"unverified", "clean", "scrubbed", "flagged"}


def load_manifest_schema() -> Dict[str, Any]:
    """Loads the JSON schema definition for dataset manifests."""
    if not MANIFEST_SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Manifest schema not found at: {MANIFEST_SCHEMA_PATH}")
    with open(MANIFEST_SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_manifest(manifest_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validates a dataset manifest against schema rules and business constraints.
    Business Constraint: Cannot be marked 'ready' unless provenance and license are present and non-empty.
    """
    errors = []

    # 1. Required top-level fields
    for field in ["dataset_name", "license", "provenance", "processing_status", "sanitization_status"]:
        if field not in manifest_data or manifest_data[field] is None:
            errors.append(f"Missing required manifest field: '{field}'")

    if errors:
        return False, errors

    # Check non-empty string types for dataset_name
    dataset_name = str(manifest_data.get("dataset_name", "")).strip()
    if not dataset_name:
        errors.append("Field 'dataset_name' cannot be empty or whitespace.")

    # 2. Check enum fields
    proc_status = str(manifest_data.get("processing_status", "")).strip().lower()
    if proc_status not in VALID_PROCESSING_STATUSES:
        errors.append(f"Invalid processing_status: '{proc_status}'. Must be one of {sorted(list(VALID_PROCESSING_STATUSES))}")

    san_status = str(manifest_data.get("sanitization_status", "")).strip().lower()
    if san_status not in VALID_SANITIZATION_STATUSES:
        errors.append(f"Invalid sanitization_status: '{san_status}'. Must be one of {sorted(list(VALID_SANITIZATION_STATUSES))}")

    # 3. Check data_types list
    data_types = manifest_data.get("data_types", [])
    if isinstance(data_types, list):
        for dt in data_types:
            if dt not in VALID_DATA_TYPES:
                errors.append(f"Invalid data_type: '{dt}'. Must be one of {sorted(list(VALID_DATA_TYPES))}")
    else:
        errors.append("Field 'data_types' must be a list of strings.")

    # 4. Strict Readiness Business Rule
    license_str = str(manifest_data.get("license", "")).strip()
    provenance_str = str(manifest_data.get("provenance", "")).strip()

    if proc_status == "ready":
        if not license_str or license_str.lower() in ["unknown", "unspecified", "none", "n/a"]:
            errors.append("Dataset cannot be marked 'ready' without valid, explicit license information.")
        if not provenance_str or provenance_str.lower() in ["unknown", "unspecified", "none", "n/a"]:
            errors.append("Dataset cannot be marked 'ready' without valid, detailed provenance information.")

    return len(errors) == 0, errors


def create_manifest(
    dataset_name: str,
    license_name: str,
    provenance: str,
    source_url: Optional[str] = None,
    source_organization: Optional[str] = None,
    download_date: Optional[str] = None,
    original_file_name: Optional[str] = None,
    original_size_bytes: Optional[int] = None,
    extracted_size_bytes: Optional[int] = None,
    checksum: Optional[str] = None,
    record_count: Optional[int] = None,
    data_types: Optional[List[str]] = None,
    cloud_provider: Optional[str] = "AWS",
    services: Optional[List[str]] = None,
    processing_status: str = "pending",
    sanitization_status: str = "unverified",
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Creates a new dataset manifest dictionary."""
    manifest = {
        "dataset_name": dataset_name.strip(),
        "source_url": source_url.strip() if source_url else None,
        "source_organization": source_organization.strip() if source_organization else None,
        "license": license_name.strip(),
        "download_date": download_date,
        "original_file_name": original_file_name,
        "original_size_bytes": original_size_bytes,
        "extracted_size_bytes": extracted_size_bytes,
        "checksum": checksum,
        "record_count": record_count,
        "data_types": data_types or ["incidents"],
        "cloud_provider": cloud_provider,
        "services": services or [],
        "provenance": provenance.strip(),
        "processing_status": processing_status,
        "sanitization_status": sanitization_status,
        "notes": notes,
    }

    return manifest


def save_manifest(manifest_data: Dict[str, Any], filepath: Path) -> Tuple[bool, List[str]]:
    """Validates and saves a manifest dictionary to a JSON file."""
    is_valid, errors = validate_manifest(manifest_data)
    if not is_valid:
        return False, errors

    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    return True, []


def load_manifest(filepath: Path) -> Dict[str, Any]:
    """Loads a dataset manifest dictionary from a JSON file."""
    if not filepath.exists():
        raise FileNotFoundError(f"Manifest file not found: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def update_manifest_status(
    manifest_data: Dict[str, Any],
    processing_status: str,
    sanitization_status: Optional[str] = None
) -> Tuple[bool, List[str]]:
    """Updates status fields of a manifest dictionary and validates the result."""
    updated = dict(manifest_data)
    updated["processing_status"] = processing_status
    if sanitization_status:
        updated["sanitization_status"] = sanitization_status

    return validate_manifest(updated)
