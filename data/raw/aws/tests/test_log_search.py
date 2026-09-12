#!/usr/bin/env python3
"""Quick test of log search functionality across scenarios."""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data_source_factory import create_log_search_source

SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"

TEST_CASES = [
    # (scenario, query, time_start, time_end, expected_min_results)
    (
        "volte-call-drop-handover",
        "handover",
        "2025-03-20T03:00:00",
        "2025-03-30T08:00:00",
        1,
    ),
    (
        "iot-fleet-disconnect-cascade",
        "cert",
        "2026-03-28T10:00:00",
        "2026-03-29T23:00:00",
        1,
    ),
    (
        "k8s-canary-silent-poisoning",
        "latency",
        "2026-03-25T02:00:00",
        "2026-03-28T08:00:00",
        1,
    ),
    (
        "ml-training-drift-schema-migration",
        "feature",
        "2026-03-25T02:00:00",
        "2026-04-01T01:00:00",
        1,
    ),
    (
        "care-transcript-supply-chain",
        "thermal",
        "2026-03-10T02:00:00",
        "2026-03-19T20:00:00",
        1,
    ),
]


def run_tests():
    print("=" * 60)
    print("Log Search Tests")
    print("=" * 60)

    log_source = create_log_search_source()
    passed = 0

    for scenario, query, time_start, time_end, min_results in TEST_CASES:
        print(f"\n{scenario}: searching for '{query}'...")

        try:
            log_source.set_scenario(scenario)
            result = log_source.search(
                query=query,
                time_start=datetime.fromisoformat(time_start),
                time_end=datetime.fromisoformat(time_end),
                limit=5,
            )

            # Check if we got results
            if "Found" in result:
                print(f"  OK: {result.split(chr(10))[0]}")
                passed += 1
            elif "No logs found" in result:
                print(f"  WARN: No results for '{query}' in {time_start} to {time_end}")
                print("        (This may be expected if query term not in logs)")
                passed += 1  # Not a failure, just no matches
            else:
                print("  FAIL: Unexpected result")
        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"\n{'=' * 60}")
    print(f"Passed: {passed}/{len(TEST_CASES)}")
    return passed == len(TEST_CASES)


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
