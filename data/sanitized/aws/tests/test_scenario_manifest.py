"""Tests for the scenario manifest generation script.

Validates that scripts/generate_scenario_manifest.py produces correct JSON
with the expected structure, matching the scenarios on the filesystem.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "generate_scenario_manifest.py"
SCENARIOS_DIR = PROJECT_ROOT / "scenarios"


@pytest.fixture()
def manifest_output(tmp_path):
    """Run the manifest generation script and return the parsed JSON."""
    output_file = tmp_path / "scenarios.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--output",
            str(output_file),
            "--scenarios-dir",
            str(SCENARIOS_DIR),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Script failed: {result.stderr}"
    return output_file


def test_manifest_generates_valid_json(manifest_output):
    """Run the script and verify the output is valid JSON."""
    raw = manifest_output.read_text()
    assert raw, "Output file is empty"
    # Should not raise
    data = json.loads(raw)
    assert isinstance(data, dict)


def test_manifest_has_expected_structure(manifest_output):
    """Verify the top-level keys are 'scenarios' and 'docs'."""
    data = json.loads(manifest_output.read_text())
    assert "scenarios" in data, "Missing top-level 'scenarios' key"
    assert "docs" in data, "Missing top-level 'docs' key"
    assert isinstance(data["scenarios"], list)
    assert isinstance(data["docs"], dict)


def test_manifest_scenarios_have_required_fields(manifest_output):
    """Each scenario entry should have: name, title (description), description, incident."""
    data = json.loads(manifest_output.read_text())
    scenarios = data["scenarios"]
    assert len(scenarios) > 0, "No scenarios found in manifest"

    required_fields = {"name", "description"}
    for entry in scenarios:
        for field in required_fields:
            assert field in entry, (
                f"Scenario '{entry.get('name', '<unknown>')}' missing field '{field}'"
            )
        # The incident content lives in docs; verify it is accessible
        name = entry["name"]
        assert name in data["docs"], f"Scenario '{name}' missing from docs"
        assert "incident" in data["docs"][name], (
            f"Scenario '{name}' docs missing 'incident' key"
        )


def test_manifest_docs_match_scenarios(manifest_output):
    """Every scenario in 'scenarios' should have a corresponding entry in 'docs'."""
    data = json.loads(manifest_output.read_text())
    scenario_names = {s["name"] for s in data["scenarios"]}
    doc_names = set(data["docs"].keys())

    missing_docs = scenario_names - doc_names
    assert not missing_docs, f"Scenarios without docs entries: {missing_docs}"

    extra_docs = doc_names - scenario_names
    assert not extra_docs, f"Docs entries without matching scenario: {extra_docs}"


def test_manifest_incident_content_not_empty(manifest_output):
    """Each scenario's incident text should be non-empty."""
    data = json.loads(manifest_output.read_text())
    for name, docs in data["docs"].items():
        incident = docs.get("incident")
        assert incident is not None, f"Scenario '{name}' has None incident"
        assert incident.strip(), f"Scenario '{name}' has empty incident text"


def test_manifest_scenario_count_matches_filesystem(manifest_output):
    """Number of scenarios in manifest should match directories with incident.md."""
    # Count scenario directories on the filesystem
    fs_scenarios = sorted(
        d.name
        for d in SCENARIOS_DIR.iterdir()
        if d.is_dir() and (d / "incident.md").exists()
    )

    data = json.loads(manifest_output.read_text())
    manifest_names = sorted(s["name"] for s in data["scenarios"])

    assert len(manifest_names) == len(fs_scenarios), (
        f"Manifest has {len(manifest_names)} scenarios but filesystem has {len(fs_scenarios)}"
    )
    assert manifest_names == fs_scenarios, (
        f"Mismatch between manifest and filesystem scenarios.\n"
        f"  Only in manifest: {set(manifest_names) - set(fs_scenarios)}\n"
        f"  Only on filesystem: {set(fs_scenarios) - set(manifest_names)}"
    )
