#!/usr/bin/env python3
"""
End-to-end test for HITL scenarios.
Runs the scenario with the vague opening report and pre-defined HITL
responses from ground_truth.yaml — matching the actual UI experience.
"""

import asyncio
import sys
from pathlib import Path

import yaml

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from langchain_core.messages import AIMessage
from langgraph.types import Command


def _load_hitl_flow(scenario_name: str) -> dict:
    """Load hitl_flow from ground_truth.yaml for a scenario."""
    gt_file = (
        Path(__file__).parent.parent / "scenarios" / scenario_name / "ground_truth.yaml"
    )
    gt = yaml.safe_load(gt_file.read_text())
    flow = gt.get("hitl_flow", {})
    if not flow.get("1_vague_report"):
        raise ValueError(f"Scenario {scenario_name} has no 1_vague_report in hitl_flow")
    return flow


async def run_hitl_test(scenario_name: str):
    """Run HITL scenario using the vague report + ground_truth responses."""
    from rca_agent import build_orchestrator_graph, build_initial_state
    from config import get_config, configure_logging

    config = get_config()
    configure_logging("INFO")

    # Load HITL flow from ground_truth
    flow = _load_hitl_flow(scenario_name)
    vague_report = flow["1_vague_report"]
    user_response = flow.get("3_user_response", "No additional context.")

    # Pre-defined responses: clarification answer, then start investigation
    responses = [user_response, "go", "go"]

    print(f"\n{'=' * 70}")
    print(f"Testing: {scenario_name}")
    print(f"Mode: {config.mode.value.upper()}")
    if config.mode.value == "production":
        print(
            f"Backend: {config.log_search_backend.value if config.log_search_backend else 'N/A'}"
        )
    print(f"{'=' * 70}\n")

    print("VAGUE REPORT (what the user sends):")
    print("-" * 50)
    print(vague_report)
    print()

    # Build graph
    graph = build_orchestrator_graph()

    # Start with vague report — NOT incident.md
    initial_state = build_initial_state(vague_report, scenario_name)

    config_dict = {"configurable": {"thread_id": f"test-{scenario_name}"}}

    # Run until first interrupt
    print("Starting investigation...\n")
    async for event in graph.astream(initial_state, config_dict):
        for node_name, output in event.items():
            if "messages" in output:
                for msg in output["messages"]:
                    if isinstance(msg, AIMessage):
                        print(
                            f"[{node_name}] {msg.content[:500]}{'...' if len(msg.content) > 500 else ''}\n"
                        )

    # Process pre-defined responses
    response_idx = 0
    max_iterations = 10
    iterations = 0

    while response_idx < len(responses) and iterations < max_iterations:
        iterations += 1
        state = graph.get_state(config_dict)

        if not state.next:
            print("\n[Graph completed]")
            break

        response = responses[response_idx]
        response_idx += 1

        print(f"\n>> USER INPUT: {response}")
        print("-" * 50)

        async for event in graph.astream(Command(resume=response), config_dict):
            for node_name, output in event.items():
                if "messages" in output:
                    for msg in output["messages"]:
                        if isinstance(msg, AIMessage):
                            content = msg.content
                            # Truncate very long outputs
                            if len(content) > 1000:
                                content = content[:1000] + "\n... [truncated]"
                            print(f"[{node_name}] {content}\n")

    print(f"\n{'=' * 70}")
    print(f"Test completed: {scenario_name}")
    print(f"{'=' * 70}\n")
    return True


async def main():
    scenario = sys.argv[1] if len(sys.argv) > 1 else "volte-call-drop-handover"
    await run_hitl_test(scenario)


if __name__ == "__main__":
    asyncio.run(main())
