#!/usr/bin/env python3
"""
End-to-end test: Config → Factory → OpenSearchDataSource → Serverless collection.

Validates the full production path without needing Bedrock LLM.
Exercises the same code path the agent uses during investigation.

Usage:
    OPENSEARCH_SERVERLESS_ENDPOINT=https://xxx.us-west-2.aoss.amazonaws.com \
    python scripts/test_opensearch_serverless_e2e.py
"""

import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import Config, DataSourceMode, LogSearchBackend, set_config, reset_config
from data_source_factory import create_log_search_source

ENDPOINT = os.environ.get("OPENSEARCH_SERVERLESS_ENDPOINT", "")
REGION = os.environ.get("AWS_REGION", "us-west-2")

# Each scenario: (name, query, time_start, time_end, service_filter, expected_substring)
SCENARIOS = [
    (
        "volte-call-drop-handover",
        "handover",
        datetime(2025, 3, 20, 3, 0),
        datetime(2025, 3, 25, 12, 0),
        "mobility-controller",
        "handover",
    ),
    (
        "iot-fleet-disconnect-cascade",
        "certificate",
        datetime(2024, 11, 12, 10, 0),
        datetime(2026, 3, 28, 12, 0),
        "certificate-rotator",
        "certificate",
    ),
    (
        "k8s-canary-silent-poisoning",
        "canary",
        datetime(2026, 3, 26, 2, 0),
        datetime(2026, 3, 27, 12, 0),
        "flagger-controller",
        "canary",
    ),
    (
        "ml-training-drift-schema-migration",
        "schema",
        datetime(2026, 3, 25, 1, 0),
        datetime(2026, 3, 25, 18, 0),
        "data-quality-monitor",
        "schema",
    ),
    (
        "care-transcript-supply-chain",
        "transcript",
        datetime(2026, 3, 10, 2, 0),
        datetime(2026, 3, 15, 12, 0),
        "care-transcript-pipeline",
        "transcript",
    ),
]


def run_scenario(name, query, time_start, time_end, service, expected):
    """Run a single scenario through the full factory path."""
    reset_config()
    cfg = Config(
        mode=DataSourceMode.PRODUCTION,
        region=REGION,
        model_id="test",
        max_tokens=4096,
        log_level="INFO",
        scenarios_dir=None,
        log_search_backend=LogSearchBackend.OPENSEARCH,
        bedrock_kb_id=None,
        cloudwatch_log_group_names=None,
        cloudwatch_log_group_prefix=None,
        athena_database=None,
        athena_table=None,
        athena_output_location=None,
        opensearch_endpoint=ENDPOINT,
        opensearch_index="rca-logs",
        opensearch_auth_mode="iam",
        opensearch_username=None,
        opensearch_password=None,
        opensearch_serverless=True,
        checkpoint_backend="memory",
        checkpoint_table_name=None,
        checkpoint_sqlite_path="./checkpoints.db",
        otel_enabled=False,
        otel_service_name="test",
        otel_exporter_endpoint=None,
        enabled_tools=None,
        memory_id=None,
        agent_config_table=None,
        agent_name="test",
    )
    set_config(cfg)

    # Create through factory (same path the agent uses)
    source = create_log_search_source()
    source.set_scenario(name)  # No-op for OpenSearch, but tests the interface

    # Search (returns formatted string, same as agent receives)
    result = source.search(
        query=query,
        time_start=time_start,
        time_end=time_end,
        service=service,
        limit=10,
    )

    reset_config()
    return result


def main():
    if not ENDPOINT:
        print("ERROR: Set OPENSEARCH_SERVERLESS_ENDPOINT environment variable")
        print(
            "Example: export OPENSEARCH_SERVERLESS_ENDPOINT=https://xxx.us-west-2.aoss.amazonaws.com"
        )
        sys.exit(1)

    print(f"Endpoint: {ENDPOINT}")
    print(f"Region:   {REGION}")
    print(
        f"Testing {len(SCENARIOS)} scenarios through Config → Factory → OpenSearch Serverless\n"
    )
    print("=" * 70)

    passed = 0
    failed = 0

    for name, query, ts_start, ts_end, service, expected in SCENARIOS:
        label = f"{name} (query={query!r}, service={service})"
        try:
            result = run_scenario(name, query, ts_start, ts_end, service, expected)

            if "Found" in result and expected.lower() in result.lower():
                # Extract match count from "Found N logs matching..."
                count = (
                    result.split("Found ")[1].split(" logs")[0]
                    if "Found " in result
                    else "?"
                )
                print(f"  PASS  {label} → {count} matches")
                passed += 1
            elif "No logs found" in result:
                print(f"  FAIL  {label} → No results returned")
                failed += 1
            else:
                print(f"  FAIL  {label} → Unexpected output: {result[:100]}")
                failed += 1

        except Exception as e:
            print(f"  ERROR {label} → {type(e).__name__}: {e}")
            failed += 1

    print("=" * 70)
    print(f"\nResults: {passed} passed, {failed} failed out of {len(SCENARIOS)}")

    if failed:
        sys.exit(1)
    else:
        print("\nAll scenarios pass through the full production path!")


if __name__ == "__main__":
    main()
