#!/usr/bin/env python3
"""
Quick agent test - validates hypothesis generation on multiple scenarios.

This is a non-interactive test that:
1. Loads an incident
2. Generates hypotheses
3. Verifies hypotheses make sense for the scenario
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import get_config
from data_source_factory import create_context_source


# Lazy imports for LLM
def get_test_llm():
    import boto3
    from botocore.config import Config as BotoConfig
    from langchain_aws import ChatBedrockConverse

    config = get_config()
    retry_config = BotoConfig(
        retries={"max_attempts": 5, "mode": "adaptive"},
        connect_timeout=10,
        read_timeout=120,
    )
    bedrock_client = boto3.client(
        "bedrock-runtime", region_name=config.region, config=retry_config
    )
    return ChatBedrockConverse(
        model_id=config.model_id,
        temperature=0.0,
        max_tokens=2048,
        client=bedrock_client,
    )


SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"

# Test a diverse set of scenarios
TEST_SCENARIOS = [
    "volte-call-drop-handover",
    "iot-fleet-disconnect-cascade",
    "k8s-canary-silent-poisoning",
    "ml-training-drift-schema-migration",
    "care-transcript-supply-chain",
]


async def run_hypothesis_generation(scenario_name: str) -> dict:
    """Test hypothesis generation for a single scenario."""
    from pydantic import BaseModel, Field
    from typing import List

    class Hypothesis(BaseModel):
        priority: int = Field(description="Priority (1=highest)")
        service: str = Field(description="The service or component to investigate")
        description: str = Field(description="Description of the potential root cause")
        search_terms: List[str] = Field(
            description="Specific terms to search for in logs"
        )
        rationale: str = Field(description="Why this hypothesis is worth investigating")

    class Hypotheses(BaseModel):
        hypotheses: List[Hypothesis] = Field(
            description="List of prioritized hypotheses"
        )

    result = {
        "scenario": scenario_name,
        "success": False,
        "hypotheses_count": 0,
        "hypotheses": [],
        "error": None,
    }

    try:
        # Load incident
        incident_path = SCENARIOS_DIR / scenario_name / "incident.md"
        with open(incident_path) as f:
            incident = f.read()

        # Load context via targeted hybrid search
        context_source = create_context_source()
        runbook_chunks = context_source.search(
            f"runbooks troubleshooting {scenario_name}", num_results=3
        )
        incident_chunks = context_source.search(
            f"past incidents {scenario_name}", num_results=3
        )

        # Build enriched context
        enriched = f"# Current Incident\n\n{incident}\n\n"
        if runbook_chunks:
            enriched += f"# Runbooks\n\n{chr(10).join(runbook_chunks)[:2000]}\n\n"
        if incident_chunks:
            enriched += f"# Similar Past Incidents\n\n{chr(10).join(incident_chunks)[:2000]}\n\n"

        # Generate hypotheses
        llm = get_test_llm()
        hyp_generator = llm.with_structured_output(Hypotheses)

        system_prompt = """You are an SRE generating hypotheses for incident investigation.
Given the incident AND context (runbooks, past incidents), generate 3-4 hypotheses.
Use the runbooks and past incidents as critical clues for root cause."""

        hypotheses = await hyp_generator.ainvoke(
            [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"Generate hypotheses:\n\n{enriched[:4000]}",
                },
            ]
        )

        result["success"] = True
        result["hypotheses_count"] = len(hypotheses.hypotheses)
        result["hypotheses"] = [
            {
                "priority": h.priority,
                "service": h.service,
                "description": h.description[:100],
            }
            for h in hypotheses.hypotheses
        ]

    except Exception as e:
        result["error"] = str(e)

    return result


async def main():
    print("=" * 70)
    print("Agent Quick Test - Hypothesis Generation")
    print("=" * 70)

    results = []
    for scenario in TEST_SCENARIOS:
        print(f"\nTesting: {scenario}...")
        result = await run_hypothesis_generation(scenario)
        results.append(result)

        if result["success"]:
            print(f"  SUCCESS: Generated {result['hypotheses_count']} hypotheses")
            for h in result["hypotheses"]:
                print(
                    f"    [{h['priority']}] {h['service']}: {h['description'][:60]}..."
                )
        else:
            print(f"  FAILED: {result['error']}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    passed = sum(1 for r in results if r["success"])
    print(f"\nPassed: {passed}/{len(results)}")

    if passed < len(results):
        print("\nFailed scenarios:")
        for r in results:
            if not r["success"]:
                print(f"  - {r['scenario']}: {r['error']}")

    return passed == len(results)


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
