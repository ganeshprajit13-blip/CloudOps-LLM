#!/usr/bin/env python3

"""
Run scenarios end-to-end with full trajectory capture.
Uses the vague opening report from ground_truth.yaml as input (matching UI).
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import yaml

# Project setup
os.environ.setdefault("RCA_AGENT_MODE", "local")
os.environ.setdefault("BEDROCK_KB_ID", "1SQRXZN3J1")
os.environ.setdefault("LOG_LEVEL", "WARNING")

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.types import Command

SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"


def load_hitl_flow(scenario_name: str) -> dict:
    """Load hitl_flow from ground_truth.yaml."""
    gt_file = SCENARIOS_DIR / scenario_name / "ground_truth.yaml"
    gt = yaml.safe_load(gt_file.read_text())
    return gt.get("hitl_flow", {})


async def run_scenario(scenario_name: str) -> dict:
    """Run a single scenario using vague report + HITL responses."""
    from rca_agent import build_orchestrator_graph, build_initial_state
    from config import configure_logging

    configure_logging("WARNING")

    flow = load_hitl_flow(scenario_name)
    vague_report = flow["1_vague_report"]
    user_response = flow.get("3_user_response", "No additional context.")
    responses = [user_response, "go", "go"]

    graph = build_orchestrator_graph()
    initial_state = build_initial_state(vague_report, scenario_name)
    config = {"configurable": {"thread_id": f"traj-{scenario_name}-{int(time.time())}"}}

    trajectory = {
        "scenario": scenario_name,
        "vague_report": vague_report,
        "start_time": time.time(),
        "phases": [],
        "all_messages": [],
        "hypotheses": None,
        "synthesis": None,
    }

    def record_event(phase, node, content, msg_type="ai"):
        trajectory["all_messages"].append(
            {
                "phase": phase,
                "node": node,
                "type": msg_type,
                "content": content[:2000],
                "timestamp": time.time(),
            }
        )

    def process_events(events, phase):
        for node_name, output in events.items():
            trajectory["phases"].append({"node": node_name, "timestamp": time.time()})
            if "messages" in output:
                for msg in output["messages"]:
                    if isinstance(msg, AIMessage):
                        record_event(phase, node_name, msg.content, "ai")
                    elif isinstance(msg, ToolMessage):
                        record_event(phase, node_name, msg.content, "tool")
                    elif isinstance(msg, HumanMessage):
                        record_event(phase, node_name, msg.content, "human")
            if "current_hypotheses" in output and output["current_hypotheses"]:
                hyps = output["current_hypotheses"]
                if hasattr(hyps, "hypotheses"):
                    trajectory["hypotheses"] = [
                        {
                            "id": hid,
                            "title": h.description,
                            "service": h.service,
                            "search_terms": h.search_terms,
                        }
                        for hid, h in hyps.hypotheses.items()
                    ]
            if "synthesized_report" in output and output["synthesized_report"]:
                trajectory["synthesis"] = output["synthesized_report"]

    print(f"\n{'=' * 70}")
    print(f"  SCENARIO: {scenario_name}")
    print(f'  INPUT: "{vague_report[:80]}..."')
    print(f"{'=' * 70}")

    async for event in graph.astream(initial_state, config):
        process_events(event, "initial")

    response_idx = 0
    for _ in range(10):
        state = graph.get_state(config)
        if not state.next or response_idx >= len(responses):
            break
        response = responses[response_idx]
        response_idx += 1
        phase_name = f"response_{response_idx}"
        print(f"\n  [Waiting at: {list(state.next)}]")
        print(f"  >> USER: {response[:100]}{'...' if len(response) > 100 else ''}")
        record_event(phase_name, "user", response, "human")
        async for event in graph.astream(Command(resume=response), config):
            process_events(event, phase_name)

    # Check if graph still waiting
    state = graph.get_state(config)
    if state.next:
        print(f"\n  [Graph waiting at {list(state.next)} — no more responses]")

    trajectory["end_time"] = time.time()
    trajectory["total_duration_s"] = trajectory["end_time"] - trajectory["start_time"]
    return trajectory


def print_analysis(traj):
    """Print structured analysis."""
    print(f"\n{'=' * 70}")
    print(f"  ANALYSIS: {traj['scenario']}")
    print(f"{'=' * 70}")
    print(f"\n  Duration: {traj['total_duration_s']:.1f}s")

    nodes = [p["node"] for p in traj["phases"]]
    print(f"\n  Node transitions ({len(nodes)}):")
    for i, node in enumerate(nodes):
        print(f"    {i + 1}. {node}")

    # Clarification
    clarify = [
        m
        for m in traj["all_messages"]
        if m["node"] == "clarify_incident" and m["type"] == "ai"
    ]
    if clarify:
        print("\n  CLARIFICATION OUTPUT:")
        print(f"  {'—' * 60}")
        for m in clarify:
            print(f"    {m['content'][:500]}")
        print(f"  {'—' * 60}")

    if traj["hypotheses"]:
        print(f"\n  Hypotheses ({len(traj['hypotheses'])}):")
        for h in traj["hypotheses"]:
            print(f"    [{h['id']}] {h['service']}: {h['title'][:120]}")

    if traj["synthesis"]:
        print("\n  SYNTHESIS (first 1500 chars):")
        print(f"  {'—' * 60}")
        print(f"    {traj['synthesis'][:1500]}")
        print(f"  {'—' * 60}")

    # Quality checks
    print("\n  QUALITY CHECKS:")
    for m in clarify:
        content = m["content"]
        has_reasoning = any(
            w in content.lower()
            for w in [
                "looking at",
                "i have",
                "let me",
                "analyzing",
                "i can see",
                "i notice",
                "based on",
                "the report",
                "✓",
                "✗",
            ]
        )
        lines = [line.strip() for line in content.strip().split("\n") if line.strip()]
        print(
            f"    Clarification shows reasoning: {'YES ⚠️' if has_reasoning else 'NO ✓'}"
        )
        print(
            f"    Clarification line count: {len(lines)} {'(should be 1-3)' if len(lines) > 3 else '✓'}"
        )
    if traj["hypotheses"]:
        print(f"    Hypothesis count: {len(traj['hypotheses'])}")


async def main():
    scenarios = sys.argv[1:] or [
        "iot-fleet-disconnect-cascade",
        "k8s-canary-silent-poisoning",
    ]
    results = []
    for scenario in scenarios:
        traj = await run_scenario(scenario)
        results.append(traj)
        print_analysis(traj)

    output_path = Path(__file__).parent.parent / "trajectory_output.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n\nRaw trajectories saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
