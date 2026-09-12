#!/usr/bin/env python3
"""
Generate a static scenarios.json manifest for the frontend.

Reads scenario metadata from the scenarios/ directory and writes a JSON
file that the React frontend can fetch directly (no API call needed in
production). Used during the build stage for Amplify/S3 deployments.

Usage:
    python scripts/generate_scenario_manifest.py [--output frontend/public/scenarios.json]
"""

import argparse
import json
import sys
from pathlib import Path

SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"
DEFAULT_OUTPUT = Path(__file__).parent.parent / "frontend" / "public" / "scenarios.json"


def generate_manifest(scenarios_dir: Path) -> dict:
    """Generate the scenario manifest from the filesystem."""
    scenarios = []
    scenario_docs = {}

    if not scenarios_dir.exists():
        return {"scenarios": scenarios, "docs": scenario_docs}

    for d in sorted(scenarios_dir.iterdir()):
        if not d.is_dir() or not (d / "incident.md").exists():
            continue

        name = d.name

        # Build scenario list entry
        entry = {
            "name": name,
            "display_name": name.replace("-", " ").title(),
            "description": name.replace("-", " ").title(),
            "has_hitl": False,
        }

        gt = None
        gt_file = d / "ground_truth.yaml"
        if gt_file.exists():
            try:
                import yaml

                gt = yaml.safe_load(gt_file.read_text())
                if gt and gt.get("display_name"):
                    entry["display_name"] = gt["display_name"]
                if gt and gt.get("domain"):
                    entry["description"] = gt["domain"]
                if gt:
                    entry["has_hitl"] = gt.get("hitl_scenario", False)
            except Exception as e:
                print(
                    f"Warning: Failed to parse ground_truth.yaml for {name}: {e}",
                    file=sys.stderr,
                )

        scenarios.append(entry)

        # Build docs for this scenario
        docs = {
            "incident": None,
            "context": {},
            "evidence": {},
            "readme": None,
            "ground_truth": gt,
        }

        incident_file = d / "incident.md"
        if incident_file.exists():
            docs["incident"] = incident_file.read_text()

        readme_file = d / "README.md"
        if readme_file.exists():
            docs["readme"] = readme_file.read_text()

        context_dir = d / "context"
        if context_dir.is_dir():
            for f in sorted(context_dir.iterdir()):
                if f.is_file():
                    docs["context"][f.name] = f.read_text()

        # Evidence files are NOT included in the manifest — they are queried
        # at runtime by the agent's tools from the configured data source
        # (Athena, CloudWatch, OpenSearch). Only include filenames for reference.
        evidence_dir = d / "evidence"
        if evidence_dir.is_dir():
            for f in sorted(evidence_dir.iterdir()):
                if f.is_file():
                    docs["evidence"][f.name] = f.read_text()

        scenario_docs[name] = docs

    return {"scenarios": scenarios, "docs": scenario_docs}


def main():
    parser = argparse.ArgumentParser(description="Generate scenario manifest JSON")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--scenarios-dir",
        type=Path,
        default=SCENARIOS_DIR,
        help=f"Scenarios directory (default: {SCENARIOS_DIR})",
    )
    args = parser.parse_args()

    manifest = generate_manifest(args.scenarios_dir)

    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with open(args.output, "w") as f:
        json.dump(manifest, f, indent=2, default=str)

    print(
        f"Generated {args.output}: "
        f"{len(manifest['scenarios'])} scenarios, "
        f"{len(manifest['docs'])} docs entries"
    )


if __name__ == "__main__":
    main()
