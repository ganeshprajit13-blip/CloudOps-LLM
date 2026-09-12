#!/usr/bin/env python3
"""
Phase 2: Systematic testing of all scenarios.

Tests that each scenario:
1. Has valid structure (incident.md, evidence/, context/)
2. Logs can be loaded and searched with time windowing
3. Context (runbooks, past incidents) loads correctly
4. Ground truth is defined
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import yaml

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data_source_factory import LocalLogSearchSource

SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"


def check_scenario_structure(scenario_path: Path) -> list[str]:
    """Verify scenario has required files."""
    errors = []

    required = ["incident.md", "evidence", "context", "ground_truth.yaml"]
    for item in required:
        path = scenario_path / item
        if not path.exists():
            errors.append(f"Missing: {item}")

    return errors


def check_context_files(scenario_name: str) -> dict:
    """Check that context files exist for a scenario (Bedrock KB ingests these)."""
    result = {"runbooks": False, "past_incidents": False, "errors": []}

    context_dir = SCENARIOS_DIR / scenario_name / "context"
    if not context_dir.exists():
        result["errors"].append("context/ directory missing")
        return result

    result["runbooks"] = (context_dir / "runbooks.md").exists()
    result["past_incidents"] = (context_dir / "past_incidents.md").exists()
    return result


def check_log_search(scenario_name: str, log_source: LocalLogSearchSource) -> dict:
    """Test log search for a scenario."""
    result = {"log_files": 0, "searchable": False, "sample_results": 0, "errors": []}

    try:
        log_source.set_scenario(scenario_name)

        # Count log files
        evidence_dir = SCENARIOS_DIR / scenario_name / "evidence"
        log_files = list(evidence_dir.glob("*.log")) + list(evidence_dir.glob("*.json"))
        result["log_files"] = len(log_files)

        if log_files:
            # Try to extract time range from first log file (skip comment lines)
            first_log = log_files[0]
            time_start = None
            import re

            patterns = [
                (r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", "%Y-%m-%dT%H:%M:%S"),
                (r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", "%Y-%m-%d %H:%M:%S"),
            ]

            with open(first_log) as f:
                for line in f:
                    # Skip comment lines and empty lines
                    if line.startswith("#") or not line.strip():
                        continue
                    # Try common time patterns
                    for pattern, fmt in patterns:
                        match = re.search(pattern, line)
                        if match:
                            time_start = datetime.strptime(match.group(1), fmt)
                            break
                    if time_start:
                        break

            if time_start:
                # Search with a 1-hour window
                time_end = time_start + timedelta(hours=1)

                # Generic search for "error" or any content
                search_result = log_source.search(
                    query="error", time_start=time_start, time_end=time_end, limit=5
                )
                result["searchable"] = True
                result["sample_results"] = search_result.count("Found") or 0
                result["time_window"] = f"{time_start} to {time_end}"
            else:
                result["errors"].append("Could not extract timestamp from logs")

    except Exception as e:
        result["errors"].append(str(e))

    return result


def load_ground_truth(scenario_path: Path) -> tuple[dict, str]:
    """Load ground truth from YAML. Returns (data, error)."""
    gt_path = scenario_path / "ground_truth.yaml"
    if gt_path.exists():
        try:
            with open(gt_path) as f:
                return yaml.safe_load(f), None
        except yaml.YAMLError as e:
            return {}, f"YAML error: {e}"
    return {}, "File not found"


def run_tests():
    """Run tests on all scenarios."""
    print("=" * 70)
    print("Phase 2: Scenario Testing")
    print("=" * 70)

    scenarios = sorted([d.name for d in SCENARIOS_DIR.iterdir() if d.is_dir()])
    print(f"\nFound {len(scenarios)} scenarios\n")

    log_source = LocalLogSearchSource(SCENARIOS_DIR)

    results = []

    for scenario in scenarios:
        scenario_path = SCENARIOS_DIR / scenario
        print(f"\n{'=' * 50}")
        print(f"Testing: {scenario}")
        print(f"{'=' * 50}")

        # Test structure
        struct_errors = check_scenario_structure(scenario_path)
        if struct_errors:
            print(f"  Structure: FAIL - {struct_errors}")
        else:
            print("  Structure: OK")

        # Test context files exist (actual retrieval is via Bedrock KB)
        ctx_result = check_context_files(scenario)
        ctx_status = []
        if ctx_result["runbooks"]:
            ctx_status.append("runbooks")
        if ctx_result["past_incidents"]:
            ctx_status.append("past_incidents")
        if ctx_result["errors"]:
            print(f"  Context: FAIL - {ctx_result['errors']}")
        else:
            print(f"  Context: {', '.join(ctx_status) if ctx_status else 'empty'}")

        # Test log search
        log_result = check_log_search(scenario, log_source)
        if log_result["errors"]:
            print(f"  Logs: FAIL - {log_result['errors']}")
        else:
            print(
                f"  Logs: {log_result['log_files']} files, searchable={log_result['searchable']}"
            )
            if log_result.get("time_window"):
                print(f"        Time window: {log_result['time_window']}")

        # Load ground truth
        gt, gt_error = load_ground_truth(scenario_path)
        if gt_error:
            print(f"  Ground Truth: FAIL - {gt_error}")
        elif gt:
            root_cause = gt.get("root_cause", {})
            print(
                f"  Ground Truth: {root_cause.get('category', 'N/A')} - {root_cause.get('service', 'N/A')}"
            )
        else:
            print("  Ground Truth: EMPTY")

        results.append(
            {
                "scenario": scenario,
                "structure_ok": len(struct_errors) == 0,
                "context_ok": len(ctx_result["errors"]) == 0,
                "logs_ok": len(log_result["errors"]) == 0 and log_result["searchable"],
                "has_ground_truth": bool(gt) and not gt_error,
            }
        )

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    passed = sum(
        1
        for r in results
        if all(
            [r["structure_ok"], r["context_ok"], r["logs_ok"], r["has_ground_truth"]]
        )
    )
    print(f"\nFully passing: {passed}/{len(results)}")

    # Show failures
    failures = [
        r
        for r in results
        if not all(
            [r["structure_ok"], r["context_ok"], r["logs_ok"], r["has_ground_truth"]]
        )
    ]
    if failures:
        print("\nIssues found:")
        for r in failures:
            issues = []
            if not r["structure_ok"]:
                issues.append("structure")
            if not r["context_ok"]:
                issues.append("context")
            if not r["logs_ok"]:
                issues.append("logs")
            if not r["has_ground_truth"]:
                issues.append("ground_truth")
            print(f"  - {r['scenario']}: {', '.join(issues)}")

    return results


if __name__ == "__main__":
    run_tests()
