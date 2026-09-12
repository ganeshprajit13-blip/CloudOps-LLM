#!/usr/bin/env python3
"""
Test HITL flow with programmed responses.

This tests the LOCAL mode HITL scenario without requiring interactive input.
"""

import asyncio
import os
import sys
from pathlib import Path

# Ensure LOCAL mode
os.environ["RCA_AGENT_MODE"] = "local"

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import reset_config, get_config  # noqa: E402

reset_config()

from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402
from langgraph.types import Command  # noqa: E402
from rca_agent import build_orchestrator_graph, SCENARIOS_DIR  # noqa: E402


# HITL scenarios with their expected responses and root causes
HITL_SCENARIOS = {
    "volte-call-drop-handover": {
        "responses": [
            "Only handovers between Ericsson and Nokia towers show the issue. handover_prep_timer was reduced from 2000ms to 500ms on March 29.",
            "go",
            "done",
        ],
        "expected_keywords": ["handover", "timer", "ericsson", "nokia"],
        "clarification_type": "change",
    },
    "iot-fleet-disconnect-cascade": {
        "responses": [
            "Auth service deployed v3.8.0 with new CT validation feature flag 36 hours ago. Only enabled for us-* and ca-* segments.",
            "go",
            "done",
        ],
        "expected_keywords": ["ct_validation", "feature", "cloudflare", "timeout"],
        "clarification_type": "change",
    },
    "care-transcript-supply-chain": {
        "responses": [
            "ProSensor Hub only, concentrated in Southeast and Southwest US. Supplier switched thermal pad material March 15.",
            "go",
            "done",
        ],
        "expected_keywords": ["thermal", "supplier", "classification"],
        "clarification_type": "scope",
    },
}


async def run_scenario(scenario_name: str, scenario_config: dict) -> dict:
    """Test a single HITL scenario."""
    scenario_path = SCENARIOS_DIR / scenario_name

    print("=" * 70)
    print(f"Testing HITL Flow: {scenario_name}")
    print(f"Clarification Type: {scenario_config['clarification_type']}")
    print(f"Mode: {get_config().mode}")
    print("=" * 70)

    # Load incident
    with open(scenario_path / "incident.md") as f:
        incident = f.read()

    print("\nINCIDENT REPORT:")
    print("-" * 50)
    print(incident[:300] + "..." if len(incident) > 300 else incident)
    print()

    # Build graph
    graph = build_orchestrator_graph()

    initial_state = {
        "messages": [HumanMessage(content=incident)],
        "incident": incident,
        "incident_time": None,
        "incident_details": None,
        "context": {},
        "enriched_context": "",
        "current_hypotheses": None,
        "worker_messages": [],
        "synthesized_report": "",
        "scenario_name": scenario_name,
        "investigation_complete": False,
    }

    config = {"configurable": {"thread_id": f"test-{scenario_name}"}}

    responses = scenario_config["responses"]
    response_idx = 0
    max_iterations = 20  # Safety limit
    iteration = 0

    print("\nRunning HITL flow with programmed responses...")
    print("-" * 50)

    # Initial run
    async for event in graph.astream(initial_state, config):
        for node_name, output in event.items():
            if "messages" in output:
                for msg in output["messages"]:
                    if isinstance(msg, AIMessage):
                        print(f"\n[{node_name}]")
                        print(
                            msg.content[:500] + "..."
                            if len(msg.content) > 500
                            else msg.content
                        )

    # Continue with programmed responses
    while response_idx < len(responses) and iteration < max_iterations:
        iteration += 1
        state = graph.get_state(config)

        if not state.next:
            print("\n" + "=" * 70)
            print("Flow completed!")
            break

        # Get next response
        user_input = responses[response_idx]
        response_idx += 1

        print(f"\n>> USER INPUT: {user_input}")
        print("-" * 50)

        # Resume with response
        async for event in graph.astream(Command(resume=user_input), config):
            for node_name, output in event.items():
                if "messages" in output:
                    for msg in output["messages"]:
                        if isinstance(msg, AIMessage):
                            print(f"\n[{node_name}]")
                            content = msg.content
                            # Truncate very long messages
                            if len(content) > 1000:
                                content = (
                                    content[:1000]
                                    + f"\n... (truncated, {len(msg.content)} chars total)"
                                )
                            print(content)

    if iteration >= max_iterations:
        print("\nWARNING: Hit max iterations limit")

    print("\n" + "=" * 70)
    print("Scenario test complete!")
    print("=" * 70)

    # Check final state
    result = {"scenario": scenario_name, "success": False, "keywords_found": []}
    final_state = graph.get_state(config)

    if final_state.values.get("synthesized_report"):
        print("\nSYNTHESIS REPORT GENERATED: Yes")
        report = final_state.values["synthesized_report"].lower()

        # Check for expected keywords
        for keyword in scenario_config["expected_keywords"]:
            if keyword.lower() in report:
                result["keywords_found"].append(keyword)

        if result["keywords_found"]:
            print(f"EXPECTED KEYWORDS FOUND: {result['keywords_found']}")
            result["success"] = True
        else:
            print(
                f"EXPECTED KEYWORDS NOT FOUND: {scenario_config['expected_keywords']}"
            )
    else:
        print("\nSYNTHESIS REPORT GENERATED: No")

    return result


async def run_hitl_flow():
    """Test the HITL flow with programmed responses."""
    # Check if specific scenario requested
    if len(sys.argv) > 1:
        scenario_name = sys.argv[1]
        if scenario_name not in HITL_SCENARIOS:
            print(f"Unknown scenario: {scenario_name}")
            print(f"Available: {list(HITL_SCENARIOS.keys())}")
            return
        scenarios_to_test = {scenario_name: HITL_SCENARIOS[scenario_name]}
    else:
        scenarios_to_test = HITL_SCENARIOS

    results = []
    for name, config in scenarios_to_test.items():
        try:
            result = await run_scenario(name, config)
            results.append(result)
        except Exception as e:
            print(f"\nERROR testing {name}: {e}")
            results.append({"scenario": name, "success": False, "error": str(e)})
        print("\n")

    # Summary
    print("=" * 70)
    print("HITL TEST SUMMARY")
    print("=" * 70)
    for r in results:
        status = "PASS" if r.get("success") else "FAIL"
        keywords = r.get("keywords_found", [])
        error = r.get("error", "")
        print(f"{r['scenario']}: {status}")
        if keywords:
            print(f"  Keywords found: {keywords}")
        if error:
            print(f"  Error: {error}")

    passed = sum(1 for r in results if r.get("success"))
    print(f"\nTotal: {passed}/{len(results)} passed")


if __name__ == "__main__":
    asyncio.run(run_hitl_flow())
