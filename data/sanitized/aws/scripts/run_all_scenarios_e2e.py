#!/usr/bin/env python3
"""
Run all 5 scenarios end-to-end IN PARALLEL and report whether each found the correct root cause.

Each scenario runs as a separate subprocess (via run_one_scenario_e2e.py) so they
execute concurrently against the LLM backend. Total wall time ≈ slowest scenario
instead of sum of all.
"""

import asyncio
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
ONE_SCENARIO_SCRIPT = SCRIPT_DIR / "run_one_scenario_e2e.py"

SCENARIOS = [
    "volte-call-drop-handover",
    "iot-fleet-disconnect-cascade",
    "k8s-canary-silent-poisoning",
    "ml-training-drift-schema-migration",
    "care-transcript-supply-chain",
]

# Keywords that must appear in synthesis to count as "found root cause".
# The agent needs to match at least 2 of these per scenario.
# Each list includes both precise terms and reasonable alternatives
# the agent might use when correctly identifying the root cause.
ROOT_CAUSE_KEYWORDS = {
    "volte-call-drop-handover": ["handover", "timer", "500ms", "500"],
    "iot-fleet-disconnect-cascade": [
        "ct_validation",
        "certificate transparency",
        "feature flag",
        "cloudflare",
        "ct validation",
    ],
    "k8s-canary-silent-poisoning": [
        "100ms",
        "interceptor",
        "connection pool",
        "pool-17",
        "5000ms",
        "context_not_set",
        "deadline_propagation",
    ],
    "ml-training-drift-schema-migration": [
        "user_id_v2",
        "backfill",
        "schema",
        "placeholder",
        "00000000",
        "migration",
        "feature_store",
        "column",
    ],
    "care-transcript-supply-chain": [
        "thermal",
        "supplier",
        "polymer",
        "thermal pad",
        "material change",
        "thermal interface",
        "component change",
    ],
}


async def run_one(scenario: str) -> dict:
    """Launch a subprocess for one scenario, parse JSON result."""
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        str(ONE_SCENARIO_SCRIPT),
        scenario,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        return {"scenario": scenario, "error": stderr.decode()[-500:]}

    # The last non-empty stdout line is our JSON result
    for line in reversed(stdout.decode().splitlines()):
        line = line.strip()
        if line and line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                pass

    return {"scenario": scenario, "error": "no JSON output from subprocess"}


def check_keywords(result: dict) -> dict:
    """Add keyword match results to a scenario result dict."""
    scenario = result["scenario"]
    synthesis = result.get("synthesis", result.get("synthesis_preview", ""))
    keywords = ROOT_CAUSE_KEYWORDS.get(scenario, [])
    synthesis_lower = synthesis.lower()
    matched = [kw for kw in keywords if kw.lower() in synthesis_lower]
    found = len(matched) >= 2
    result["found_root_cause"] = found
    result["matched_keywords"] = matched
    result["total_keywords"] = len(keywords)
    return result


async def main():
    # Allow running a subset: python run_all_scenarios_e2e.py k8s ml-training
    if len(sys.argv) > 1:
        scenarios = []
        for arg in sys.argv[1:]:
            matches = [s for s in SCENARIOS if arg in s]
            scenarios.extend(matches)
        if not scenarios:
            print(f"No scenarios matched: {sys.argv[1:]}", file=sys.stderr)
            sys.exit(2)
    else:
        scenarios = SCENARIOS

    print(f"Running {len(scenarios)} scenarios in parallel...", flush=True)

    # Launch all in parallel
    tasks = {s: asyncio.create_task(run_one(s)) for s in scenarios}
    results = []
    for scenario in scenarios:
        result = await tasks[scenario]
        result = check_keywords(result)
        results.append(result)

        status = "PASS" if result.get("found_root_cause") else "FAIL"
        error = result.get("error", "")
        if error:
            print(f"  [{status}] {scenario} — ERROR: {error[:200]}", flush=True)
        else:
            print(
                f"  [{status}] {scenario} — {len(result['matched_keywords'])}/{result['total_keywords']} keywords: {result['matched_keywords']}",
                flush=True,
            )
            if not result.get("found_root_cause"):
                print(
                    f"         preview: {result.get('synthesis_preview', '')[:300]}",
                    flush=True,
                )

    # Save trajectories to file for analysis
    traj_path = SCRIPT_DIR.parent / "trajectories_e2e.json"
    traj_data = {}
    for r in results:
        traj = r.pop("trajectory", None)
        if traj:
            traj_data[r["scenario"]] = traj
    if traj_data:
        traj_path.write_text(json.dumps(traj_data, indent=2))
        print(f"\nTrajectories saved to: {traj_path}", flush=True)

    # Summary
    print(f"\n{'=' * 70}", flush=True)
    passed = sum(1 for r in results if r.get("found_root_cause"))
    total = len(results)
    print(f"{passed}/{total} scenarios found correct root cause", flush=True)
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
