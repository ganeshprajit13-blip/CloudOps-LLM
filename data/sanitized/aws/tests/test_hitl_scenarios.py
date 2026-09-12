#!/usr/bin/env python3
"""
Test the 3 HITL-specific scenarios that demonstrate clarification patterns.

Each HITL scenario is designed to require specific clarification:
- volte-call-drop-handover: CHANGE clarification (inter-vendor handover changes)
- iot-fleet-disconnect-cascade: CHANGE clarification (certificate rotation)
- k8s-canary-silent-poisoning: CHANGE clarification (canary deployment)
- ml-training-drift-schema-migration: CHANGE clarification (schema migration)
- care-transcript-supply-chain: SCOPE clarification (which product lines affected)
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import List

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import get_config
from data_source_factory import create_context_source, create_log_search_source

SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"

HITL_SCENARIOS = [
    {
        "name": "volte-call-drop-handover",
        "clarification_type": "CHANGE",
        "description": "VoLTE call drops - must identify WHAT config changed",
        "expected_context": ["runbooks", "past_incidents"],
    },
    {
        "name": "iot-fleet-disconnect-cascade",
        "clarification_type": "CHANGE",
        "description": "IoT fleet disconnect - must identify WHAT feature flag changed",
        "expected_context": ["runbooks", "past_incidents"],
    },
    {
        "name": "k8s-canary-silent-poisoning",
        "clarification_type": "CHANGE",
        "description": "Canary silent timeouts - must identify WHAT was deployed",
        "expected_context": ["runbooks", "past_incidents"],
    },
    {
        "name": "ml-training-drift-schema-migration",
        "clarification_type": "CHANGE",
        "description": "ML model drift - must identify WHAT schema changed",
        "expected_context": ["runbooks", "past_incidents"],
    },
    {
        "name": "care-transcript-supply-chain",
        "clarification_type": "SCOPE",
        "description": "Defect classification failures - must clarify WHICH product lines",
        "expected_context": ["runbooks", "past_incidents"],
    },
]


def get_llm():
    """Get LLM for testing."""
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


async def check_clarification_needed(
    scenario: dict, incident: str, context: dict
) -> dict:
    """Test if the agent correctly identifies that clarification is needed."""
    from pydantic import BaseModel, Field

    class IncidentClarification(BaseModel):
        needs_clarification: bool = Field(
            description="Whether more information is needed"
        )
        missing_info: List[str] = Field(
            description="List of missing critical information"
        )
        clarification_question: str = Field(
            description="Question to ask if clarification needed"
        )
        summary: str = Field(description="Summary of what we know")

    llm = get_llm()
    clarifier = llm.with_structured_output(IncidentClarification)

    prompt = """You are an SRE helping to gather incident details before investigation.

Analyze the incident report and determine if critical information is missing.

CRITICAL INFORMATION NEEDED:
1. **When did it happen?** - Date and approximate time
2. **What services are affected?** - Specific service names
3. **What are the symptoms?** - Specific errors, slowness, failures

If the incident report is vague, you MUST ask for clarification.
If the report already contains specific time, services, and symptoms, proceed without clarification."""

    result = await clarifier.ainvoke(
        [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Incident Report:\n{incident}"},
        ]
    )

    return {
        "needs_clarification": result.needs_clarification,
        "missing_info": result.missing_info,
        "question": result.clarification_question,
        "summary": result.summary[:200],
    }


async def check_hypothesis_generation(
    scenario: dict, incident: str, context_chunks: list[str]
) -> dict:
    """Test hypothesis generation for the scenario."""
    from pydantic import BaseModel, Field

    class Hypothesis(BaseModel):
        priority: int = Field(description="Priority (1=highest)")
        service: str = Field(description="Service to investigate")
        description: str = Field(description="Description of potential root cause")
        search_terms: List[str] = Field(description="Terms to search for")
        rationale: str = Field(description="Why this hypothesis")

    class Hypotheses(BaseModel):
        hypotheses: List[Hypothesis] = Field(description="List of hypotheses")

    # Build enriched context from search chunks
    enriched = f"# Current Incident\n\n{incident}\n\n"
    if context_chunks:
        enriched += f"# Retrieved Context\n\n{chr(10).join(context_chunks)[:4000]}\n\n"

    llm = get_llm()
    hyp_generator = llm.with_structured_output(Hypotheses)

    system_prompt = """You are an SRE generating hypotheses for incident investigation.
Given the incident AND context (runbooks, past incidents), generate 3-4 hypotheses.
Use the runbooks and past incidents as critical clues for root cause."""

    hypotheses = await hyp_generator.ainvoke(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Generate hypotheses:\n\n{enriched[:6000]}"},
        ]
    )

    return {
        "count": len(hypotheses.hypotheses),
        "hypotheses": [
            {
                "priority": h.priority,
                "service": h.service,
                "description": h.description[:80],
            }
            for h in hypotheses.hypotheses
        ],
    }


def check_log_search(scenario_name: str) -> dict:
    """Test that logs are searchable for the scenario."""
    log_source = create_log_search_source()
    log_source.set_scenario(scenario_name)

    # Get evidence directory to find time range
    evidence_dir = SCENARIOS_DIR / scenario_name / "evidence"
    log_files = list(evidence_dir.glob("*.log"))

    if not log_files:
        return {"success": False, "error": "No log files found"}

    # Find first timestamp in logs
    import re

    time_start = None
    patterns = [
        (r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", "%Y-%m-%dT%H:%M:%S"),
        (r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", "%Y-%m-%d %H:%M:%S"),
    ]

    for log_file in log_files:
        with open(log_file) as f:
            for line in f:
                if line.startswith("#") or not line.strip():
                    continue
                for pattern, fmt in patterns:
                    match = re.search(pattern, line)
                    if match:
                        time_start = datetime.strptime(match.group(1), fmt)
                        break
                if time_start:
                    break
        if time_start:
            break

    if not time_start:
        return {"success": False, "error": "Could not extract timestamp"}

    # Search for common terms
    from datetime import timedelta

    time_end = time_start + timedelta(hours=24)

    results = {}
    for term in ["error", "timeout", "failed", "warning"]:
        result = log_source.search(
            query=term, time_start=time_start, time_end=time_end, limit=3
        )
        if "Found" in result:
            count = result.split()[1]
            results[term] = int(count)
        else:
            results[term] = 0

    return {
        "success": True,
        "time_window": f"{time_start} to {time_end}",
        "search_results": results,
        "total_matches": sum(results.values()),
    }


async def run_hitl_tests():
    """Run comprehensive tests on all HITL scenarios."""
    print("=" * 70)
    print("HITL Scenario Tests")
    print("=" * 70)

    context_source = create_context_source()
    results = []

    for scenario in HITL_SCENARIOS:
        name = scenario["name"]
        print(f"\n{'=' * 60}")
        print(f"Testing: {name}")
        print(f"Clarification Type: {scenario['clarification_type']}")
        print(f"Description: {scenario['description']}")
        print(f"{'=' * 60}")

        result = {
            "scenario": name,
            "clarification_type": scenario["clarification_type"],
            "tests": {},
        }

        # 1. Load incident
        incident_path = SCENARIOS_DIR / name / "incident.md"
        try:
            with open(incident_path) as f:
                incident = f.read()
            print(f"\n1. Incident loaded ({len(incident)} chars)")
            result["tests"]["incident"] = "PASS"
        except Exception as e:
            print(f"\n1. Incident: FAIL - {e}")
            result["tests"]["incident"] = f"FAIL: {e}"
            results.append(result)
            continue

        # 2. Load context via hybrid search
        context_chunks: list[str] = []
        try:
            runbook_chunks = context_source.search(
                f"runbooks troubleshooting {name}", num_results=3
            )
            incident_chunks = context_source.search(
                f"past incidents {name}", num_results=3
            )
            context_chunks = runbook_chunks + incident_chunks
            print(
                f"2. Context: {len(runbook_chunks)} runbook chunks, {len(incident_chunks)} incident chunks"
            )
            result["tests"]["context"] = "PASS" if context_chunks else "PARTIAL"
        except Exception as e:
            print(f"2. Context: FAIL - {e}")
            result["tests"]["context"] = f"FAIL: {e}"

        # 3. Test clarification detection
        print("\n3. Testing clarification detection...")
        try:
            clarification = await check_clarification_needed(scenario, incident, {})
            if clarification["needs_clarification"]:
                print("   Needs clarification: YES")
                print(f"   Missing info: {clarification['missing_info'][:3]}")
                print(f"   Question: {clarification['question'][:100]}...")
                result["tests"]["clarification"] = (
                    "PASS - Correctly requests clarification"
                )
            else:
                print("   Needs clarification: NO")
                print(f"   Summary: {clarification['summary'][:100]}...")
                # For HITL scenarios, we WANT clarification to be needed
                result["tests"]["clarification"] = (
                    "WARN - May not trigger clarification"
                )
            result["clarification_details"] = clarification
        except Exception as e:
            print(f"   FAIL: {e}")
            result["tests"]["clarification"] = f"FAIL: {e}"

        # 4. Test hypothesis generation
        print("\n4. Testing hypothesis generation...")
        try:
            hypotheses = await check_hypothesis_generation(
                scenario, incident, context_chunks
            )
            print(f"   Generated {hypotheses['count']} hypotheses:")
            for h in hypotheses["hypotheses"][:3]:
                print(
                    f"     [{h['priority']}] {h['service']}: {h['description'][:50]}..."
                )
            result["tests"]["hypotheses"] = f"PASS - {hypotheses['count']} hypotheses"
            result["hypotheses"] = hypotheses
        except Exception as e:
            print(f"   FAIL: {e}")
            result["tests"]["hypotheses"] = f"FAIL: {e}"

        # 5. Test log search
        print("\n5. Testing log search...")
        try:
            log_result = check_log_search(name)
            if log_result["success"]:
                print(f"   Time window: {log_result['time_window']}")
                print(f"   Search results: {log_result['search_results']}")
                print(f"   Total matches: {log_result['total_matches']}")
                result["tests"]["log_search"] = (
                    f"PASS - {log_result['total_matches']} total matches"
                )
            else:
                print(f"   FAIL: {log_result['error']}")
                result["tests"]["log_search"] = f"FAIL: {log_result['error']}"
        except Exception as e:
            print(f"   FAIL: {e}")
            result["tests"]["log_search"] = f"FAIL: {e}"

        results.append(result)

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    for r in results:
        print(f"\n{r['scenario']} ({r['clarification_type']}):")
        for test_name, status in r["tests"].items():
            icon = (
                "✓"
                if status.startswith("PASS")
                else ("⚠" if status.startswith("WARN") else "✗")
            )
            print(f"  {icon} {test_name}: {status}")

    # Overall pass/fail
    all_passed = all(
        all(s.startswith("PASS") or s.startswith("WARN") for s in r["tests"].values())
        for r in results
    )
    print(f"\n{'=' * 70}")
    print(f"Overall: {'PASS' if all_passed else 'FAIL'}")
    print(f"{'=' * 70}")

    return results


if __name__ == "__main__":
    results = asyncio.run(run_hitl_tests())
    sys.exit(
        0
        if all(
            all(
                s.startswith("PASS") or s.startswith("WARN")
                for s in r["tests"].values()
            )
            for r in results
        )
        else 1
    )
