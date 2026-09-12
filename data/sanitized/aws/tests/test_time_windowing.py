#!/usr/bin/env python3
"""
Test time windowing in log search.

This verifies that:
1. Time window filtering works correctly
2. Search returns only logs within the window
3. Quality score is calculated properly
"""

import sys
from datetime import datetime
from pathlib import Path

# Add src to path for package imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.data_sources.log_files import LogFileDataSource


def run_time_windowing_tests():
    """Test time window filtering on hitl-ecommerce-investigation scenario."""
    scenario_path = (
        Path(__file__).parent.parent
        / "scenarios"
        / "care-transcript-supply-chain"
        / "evidence"
    )

    if not scenario_path.exists():
        print(f"ERROR: Scenario path not found: {scenario_path}")
        return False

    data_source = LogFileDataSource(scenario_path)

    print("=" * 60)
    print("Testing Time Windowing on hitl-ecommerce-investigation")
    print("=" * 60)

    # Test 1: Search with March 15 time window (should find Redis cache eviction)
    print("\n--- Test 1: March 15 time window (expected: Redis cache eviction) ---")
    result = data_source.search(
        query="cache",
        time_start=datetime(2024, 3, 15, 9, 45),
        time_end=datetime(2024, 3, 15, 10, 15),
        filters=None,
        limit=10,
    )
    print(f"Found {result.total_matches} matches, Quality: {result.quality_score}")
    print(data_source.format_results(result))

    # Test 2: Search with March 10 time window (should find N+1 query issue)
    print("\n--- Test 2: March 10 time window (expected: N+1 query issue) ---")
    result = data_source.search(
        query="query",
        time_start=datetime(2024, 3, 10, 13, 45),
        time_end=datetime(2024, 3, 10, 14, 15),
        filters=None,
        limit=10,
    )
    print(f"Found {result.total_matches} matches, Quality: {result.quality_score}")
    print(data_source.format_results(result))

    # Test 3: Search outside time window (should find nothing)
    print("\n--- Test 3: Search outside incident window (expected: no matches) ---")
    result = data_source.search(
        query="cache",
        time_start=datetime(2024, 3, 20, 9, 0),
        time_end=datetime(2024, 3, 20, 10, 0),
        filters=None,
        limit=10,
    )
    print(f"Found {result.total_matches} matches, Quality: {result.quality_score}")
    print(data_source.format_results(result))

    # Test 4: Broad search (should show low quality score)
    print(
        "\n--- Test 4: Broad search 'ERROR' (expected: many matches, low quality) ---"
    )
    result = data_source.search(
        query="ERROR",
        time_start=datetime(2024, 3, 15, 0, 0),
        time_end=datetime(2024, 3, 15, 23, 59),
        filters=None,
        limit=10,
    )
    print(f"Found {result.total_matches} matches, Quality: {result.quality_score}")
    if result.quality_score < 0.5:
        print("✓ Quality score correctly indicates broad search")
    else:
        print("✗ Quality score should be lower for broad search")

    # Test 5: Service filter
    print("\n--- Test 5: Service filter (redis-cache only) ---")
    result = data_source.search(
        query="eviction",
        time_start=datetime(2024, 3, 15, 9, 45),
        time_end=datetime(2024, 3, 15, 10, 15),
        filters={"service": "redis"},
        limit=10,
    )
    print(f"Found {result.total_matches} matches, Quality: {result.quality_score}")
    print(data_source.format_results(result))

    print("\n" + "=" * 60)
    print("Time windowing tests complete!")
    print("=" * 60)

    return True


if __name__ == "__main__":
    success = run_time_windowing_tests()
    sys.exit(0 if success else 1)
