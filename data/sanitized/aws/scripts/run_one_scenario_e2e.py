#!/usr/bin/env python3

"""
Run a single scenario end-to-end and print JSON result.
Used by run_all_scenarios_e2e.py for parallel execution.

Mimics the UI path: starts with the vague report from ground_truth.yaml
hitl_flow (not the full incident.md), and uses 3_user_response for the
clarification — matching what a user would do in the frontend.
"""

import asyncio
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from langgraph.types import Command

SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"


def _load_hitl_flow(scenario_name: str) -> dict:
    """Load hitl_flow from ground_truth.yaml for a scenario."""
    gt_file = SCENARIOS_DIR / scenario_name / "ground_truth.yaml"
    gt = yaml.safe_load(gt_file.read_text())
    flow = gt.get("hitl_flow", {})
    if not flow.get("1_vague_report"):
        raise ValueError(f"Scenario {scenario_name} has no 1_vague_report in hitl_flow")
    return flow


async def run_scenario(scenario_name: str) -> dict:
    """Run one scenario and return result dict."""
    from rca_agent import build_orchestrator_graph, build_initial_state
    from config import reset_config, configure_logging
    from trajectory import TrajectoryCapture

    reset_config()
    configure_logging("WARNING")

    # Load HITL flow — use vague report (what the UI sends) instead of incident.md
    flow = _load_hitl_flow(scenario_name)
    vague_report = flow["1_vague_report"]
    user_response = flow.get("3_user_response", "No additional context.")

    # Responses: clarification answer from ground_truth, then approve investigation
    responses = [user_response, "go", "go"]

    trajectory = TrajectoryCapture(
        session_id=f"e2e-{scenario_name}", scenario_name=scenario_name
    )
    graph = build_orchestrator_graph()
    config_dict = {
        "configurable": {
            "thread_id": f"e2e-{scenario_name}",
            "trajectory": trajectory,
        }
    }

    # Use build_initial_state — same as the API layer (src/api.py)
    initial_state = build_initial_state(vague_report, scenario_name)

    response_idx = 0

    # Run until first interrupt
    async for event in graph.astream(initial_state, config_dict):
        pass

    # Process HITL responses
    max_iterations = 10
    iterations = 0
    while response_idx < len(responses) and iterations < max_iterations:
        iterations += 1
        state = graph.get_state(config_dict)
        if not state.next:
            break

        resp = responses[response_idx]
        response_idx += 1

        async for event in graph.astream(Command(resume=resp), config_dict):
            pass

    # Read synthesis from graph state
    final_state = graph.get_state(config_dict)
    synthesis = final_state.values.get("synthesized_report", "")

    traj_record = trajectory.finalize()

    return {
        "scenario": scenario_name,
        "synthesis_length": len(synthesis),
        "synthesis": synthesis,
        "synthesis_preview": synthesis[:500] if synthesis else "(empty)",
        "trajectory": traj_record.to_dict(),
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <scenario-name>", file=sys.stderr)
        sys.exit(2)

    scenario_name = sys.argv[1]
    # Validate scenario exists and has hitl_flow
    gt_file = SCENARIOS_DIR / scenario_name / "ground_truth.yaml"
    if not gt_file.exists():
        print(f"Unknown scenario: {scenario_name}", file=sys.stderr)
        sys.exit(2)

    result = asyncio.run(run_scenario(scenario_name))
    # Print JSON to stdout (only line without WARNING prefix)
    print(json.dumps(result))
