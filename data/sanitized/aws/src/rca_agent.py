#!/usr/bin/env python3
"""
Deep Research RCA Agent - LangGraph Implementation with HITL

This demonstrates the Deep Research pattern for incident investigation using LangGraph:

1. CLARIFICATION: Ask clarifying questions to scope the incident
2. CONTEXT ENRICHMENT: Gather runbooks, past incidents, and log signals
3. HYPOTHESIS GENERATION: Generate hypotheses from enriched context
4. HUMAN-IN-THE-LOOP: User can review hypotheses, ask questions, or initiate investigation
4. DYNAMIC AGENT SPAWNING: Create investigation agents on-the-fly (one per hypothesis)
5. SYNTHESIS: Compare evidence across all investigations
6. FOLLOW-UP: User can ask questions about findings

Supports two modes (set via RCA_AGENT_MODE environment variable):
- LOCAL (default): File-based logs and context for demos
- PRODUCTION: Bedrock KB (S3 Vectors) + CloudWatch Logs

Environment variables:
- RCA_AGENT_MODE: "local" (default) or "production"
- BEDROCK_KB_ID: Bedrock Knowledge Base ID (required for production mode)
- CLOUDWATCH_LOG_GROUP_PREFIX: Log group prefix (production mode)
- CLOUDWATCH_LOG_GROUP_NAMES: Comma-separated log group names (production mode)

Run: python rca_agent.py [scenario_name]
"""

import asyncio
import json
import logging
import operator
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal, Optional, List, TypeVar

import boto3
from botocore.config import Config as BotoConfig
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    ToolMessage,
    BaseMessage,
    get_buffer_string,
)
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.types import Command, Send, interrupt
from pydantic import BaseModel, Field

# Ensure src directory is in path for local imports
_src_dir = Path(__file__).parent
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from checkpoint import create_async_checkpointer, create_checkpointer  # noqa: E402
from config import get_config, configure_logging  # noqa: E402
from data_source_factory import (  # noqa: E402
    create_context_source,
    create_log_search_source,
)
from telemetry import trace_node  # noqa: E402

# Logger (configured in main())
logger = logging.getLogger(__name__)

# Scenarios directory (for loading incident.md files)
SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"
DEFAULT_SCENARIO = "volte-call-drop-handover"

# Module-level LLM instance (initialized lazily)
_llm = None


def get_llm() -> ChatBedrockConverse:
    """Get or create the LLM instance."""
    global _llm
    if _llm is None:
        config = get_config()
        retry_config = BotoConfig(
            retries={"max_attempts": 10, "mode": "adaptive"},
            max_pool_connections=10,
            connect_timeout=10,
            read_timeout=300,
        )
        bedrock_client = boto3.client(
            "bedrock-runtime", region_name=config.region, config=retry_config
        )
        _llm = ChatBedrockConverse(
            model_id=config.model_id,
            temperature=0.0,
            max_tokens=config.max_tokens,
            client=bedrock_client,
            disable_streaming=False,  # Enable streaming (langchain-aws 1.4+ field name)
        )
    return _llm


# =============================================================================
# Pydantic Models for Structured Output
# =============================================================================


class Hypothesis(BaseModel):
    """A single hypothesis for investigation."""

    service: str = Field(description="The service or component to investigate")
    description: str = Field(description="Description of the potential root cause")
    search_terms: List[str] = Field(description="Specific terms to search for in logs")
    rationale: str = Field(
        description="Why this hypothesis is worth investigating based on context"
    )
    time_window_start: Optional[str] = Field(
        default=None, description="Start of investigation time window (ISO format)"
    )
    time_window_end: Optional[str] = Field(
        default=None, description="End of investigation time window (ISO format)"
    )


class Hypotheses(BaseModel):
    """Collection of hypotheses to investigate."""

    hypotheses: dict[int, Hypothesis] = Field(
        description="Prioritized hypotheses, keyed by priority (1=highest)"
    )


class RouteFromQuery(BaseModel):
    """Route user input to appropriate handler."""

    rationale: str = Field(description="Reasoning for the classification")
    classification: Literal[
        "iterate_on_hypotheses",
        "initiate_agents",
        "selective_investigation",
        "general_qa",
    ] = Field(description="Classification of user intent")


class SelectiveInvestigation(BaseModel):
    """Extract which hypothesis IDs the user wants to investigate."""

    hypothesis_ids: List[int] = Field(
        description="Hypothesis numbers the user wants to investigate"
    )


class IncidentClarification(BaseModel):
    """Determine if incident needs clarification before investigation."""

    needs_clarification: bool = Field(description="Whether more information is needed")
    missing_info: List[str] = Field(description="List of missing critical information")
    clarification_question: str = Field(
        description="A single concise question (1-2 sentences) to ask the user — no reasoning or preamble"
    )
    summary: str = Field(description="Summary of what we know so far")


class IncidentDetails(BaseModel):
    """Structured incident details after clarification."""

    incident_time: Optional[str] = Field(
        description="When the incident occurred (date and time)"
    )
    time_window_start: Optional[str] = Field(
        description="Start of investigation window in ISO format (e.g., '2024-03-15T14:00:00')"
    )
    time_window_end: Optional[str] = Field(
        description="End of investigation window in ISO format (e.g., '2024-03-15T14:30:00')"
    )
    affected_services: List[str] = Field(description="Services mentioned as affected")
    symptoms: List[str] = Field(description="Symptoms described")
    summary: str = Field(description="Complete incident summary with all details")


# =============================================================================
# Tools using @tool decorator
# =============================================================================


@tool(parse_docstring=True)
def search_logs(
    query: str,
    time_start: str,
    time_end: str,
    service: Optional[str] = None,
) -> str:
    """Search service logs for evidence within a time window.

    Searches are case-insensitive substring matches. "timer" matches "TIMER_EXPIRED",
    "handover_prep_timer", etc. Search for ONE term per call — compound phrases must
    appear as an exact substring in the log line.

    Omit the service filter on your first search to see results across all services.
    Then narrow with service filter in follow-up searches.

    Args:
        query: Single search term (e.g., 'timeout', 'deploy', 'config', '500ms'). Case-insensitive substring match.
        time_start: Start of time window in ISO format (e.g., '2026-03-15T14:00:00'). REQUIRED.
        time_end: End of time window in ISO format (e.g., '2026-03-15T14:30:00'). REQUIRED.
        service: Filter to a specific log source name. Omit to search ALL sources.

    Returns:
        Matching log entries with source file, timestamp, and content.
    """
    # This is a placeholder - actual data_source is injected at runtime in tool_node
    raise RuntimeError("search_logs must be called with data_source injected")


@tool(parse_docstring=True)
def think(reflection: str) -> str:
    """Analyze evidence and plan your next search. Call this after EVERY search.

    Use this to:
    - Extract specific technical values from search results (config names, error codes, versions)
    - Identify which services show evidence and which are silent
    - Decide what to search next and why
    - Connect findings across services into a causal chain
    - Note anomalies: unexpected values, missing data, suspicious timestamps

    Args:
        reflection: Your analysis of evidence so far and reasoning about next steps.

    Returns:
        Acknowledgment to continue investigation.
    """
    return f"Noted. Continue investigating based on: {reflection[:100]}..."


@tool(parse_docstring=True)
def list_log_sources() -> str:
    """List all available log sources. Call this FIRST before searching.

    Returns the names of all log sources (services) available for this investigation.
    Use these names as the service filter in search_logs. This helps you discover
    evidence in upstream or adjacent services beyond your primary hypothesis.

    Returns:
        A list of available log source names that can be used as service filters.
    """
    # Placeholder - actual data_source is injected at runtime in tool_node
    raise RuntimeError("list_log_sources must be called with data_source injected")


@tool(parse_docstring=True)
def lookup_context(
    query: str,
    context_type: Optional[str] = None,
) -> str:
    """Look up runbooks or past incidents from the knowledge base.

    Use this to retrieve operational runbooks (service dependencies,
    troubleshooting steps) or similar past incidents. Call this when
    you need domain context to interpret evidence.

    Args:
        query: What to look up (e.g., service name, failure pattern, symptom).
        context_type: Type of context: "runbooks", "past_incidents", or "all". Defaults to "all".

    Returns:
        Relevant runbook content and/or past incident descriptions.
    """
    # Placeholder - actual context_source is injected at runtime in tool_node
    raise RuntimeError("lookup_context must be called with data_source injected")


# =============================================================================
# State Definitions
# =============================================================================

T = TypeVar("T")


def _take_first(a: T, b: T) -> T:
    """Reducer that keeps the first non-empty value (for fields that shouldn't merge)."""
    return a if a else b


class OrchestratorState(MessagesState):
    """State for the main orchestration graph."""

    incident: str  # The incident description
    incident_time: Optional[str]  # When the incident occurred (from clarification)
    time_window_start: Annotated[
        Optional[str], _take_first
    ]  # ISO format start of investigation window
    time_window_end: Annotated[
        Optional[str], _take_first
    ]  # ISO format end of investigation window
    incident_details: Optional[IncidentDetails]  # Structured incident details
    context: dict  # Retrieved context (runbooks, past incidents)
    enriched_context: str  # Combined incident + context
    current_hypotheses: Optional[Hypotheses]  # Generated hypotheses
    selected_hypotheses: Optional[
        List[int]
    ]  # Subset of hypothesis IDs to investigate (None = all)
    worker_messages: Annotated[list, operator.add]  # Accumulator for worker outputs
    synthesized_report: str  # Final synthesis
    scenario_name: Annotated[str, _take_first]  # Name of the scenario (for KB queries)
    investigation_complete: bool  # Whether investigation has been run


class WorkerState(MessagesState):
    """State for investigation worker agents."""

    worker_id: str
    worker_messages: Annotated[list, operator.add]
    n_iterations: int
    max_iterations: int
    hypothesis: Hypothesis
    scenario_name: Annotated[
        str, _take_first
    ]  # Scenario name (use reducer to avoid merge conflict)
    time_window_start: Annotated[
        Optional[str], _take_first
    ]  # ISO format time window start
    time_window_end: Annotated[Optional[str], _take_first]  # ISO format time window end
    available_log_sources: Annotated[
        Optional[str], _take_first
    ]  # Comma-separated log source names


# =============================================================================
# Context Loading and Enrichment
# =============================================================================


def render_hypotheses(hypotheses: Hypotheses) -> str:
    """Format hypotheses for display."""
    hyp_text = "## Generated Hypotheses\n\n"
    for priority, hyp in hypotheses.hypotheses.items():
        hyp_text += f"**Hypothesis {priority}**: {hyp.service}\n"
        hyp_text += f"  - Description: {hyp.description}\n"
        hyp_text += f"  - Search terms: {', '.join(hyp.search_terms)}\n"
        hyp_text += f"  - Rationale: {hyp.rationale}\n\n"

    hyp_text += "\n---\n**Options:**\n"
    hyp_text += "- Type feedback to modify hypotheses\n"
    hyp_text += "- Say 'investigate' or 'go' to start the investigation\n"
    hyp_text += "- Ask any questions about the incident or hypotheses\n"
    return hyp_text


# =============================================================================
# Orchestrator Nodes
# =============================================================================

CLARIFICATION_PROMPT = """You are an SRE helping to gather incident details before investigation.

Analyze the incident report and conversation so far. Determine if you have enough
information for a focused investigation.

Consider these dimensions — ask about the MOST CRITICAL one missing:

1. **TIMING**: When did this start? A specific date is needed for log searching.
   - Accept approximate dates ("around March 13th") and proceed.
   - If user gives a recurring pattern ("every Tuesday morning"), ask which specific
     occurrence to investigate first.
   - If the incident report already contains dates, do NOT re-ask.

2. **SCOPE**: Who or what is affected?
   - Platform (iOS/Android/Web), region, user segment, service, network type.
   - Only ask when the report says "some users" or scope is ambiguous.
   - If the incident clearly names affected services, do NOT re-ask.

3. **RECENT CHANGES**: What changed around the time the problem started?
   - Deployments, configuration changes, new features, traffic patterns.
   - Only ask when the report describes gradual onset or "started recently".
   - If the report already mentions a specific trigger, do NOT re-ask.

DATE REQUIREMENTS (when asking about timing):
- You need a specific calendar date with month, day, and year for log searching.
- Do NOT accept vague references like "recently", "a few days ago", or "this week".
- DO accept day-of-week patterns like "every Tuesday" — but follow up asking which
  specific date to investigate first.
- Do NOT guess or infer dates from the current date.

HANDLING "I DON'T KNOW" RESPONSES:
- If the user says they don't know, are unsure, or can't answer a question,
  do NOT re-ask the same question. Accept their answer and move on.
- If another dimension is still missing, ask about THAT instead.
- If you've already asked about all critical dimensions (or the user has said
  "unsure" to the most critical one), PROCEED with what you have
  (set needs_clarification=false). An approximate investigation is better
  than an infinite clarification loop.

WHEN TO PROCEED (set needs_clarification=false):
- You have a specific date/time AND enough scope to focus the investigation.
- If the incident report already contains these details, PROCEED immediately.
- The user has said "I don't know" or "unsure" to a critical question — proceed
  with available information rather than re-asking.
- Don't over-ask — if you can form useful search queries, proceed.

WHEN TO ASK (set needs_clarification=true):
- The report is too vague to form any useful search query.
- Ask about ONE dimension at a time — the most critical one.
- Never ask a question you've already asked in this conversation.

OUTPUT FORMAT:
- Your text response must be ONLY the clarifying question itself — 1-2 sentences max.
- Do NOT show your reasoning, analysis, or what you already know.
- Do NOT list what information you have vs what's missing.
- Do NOT explain why you're asking. Just ask.
- Good: "Were there any deployments or configuration changes around that time?"
- Bad: "Looking at this report, I have timing and scope, but recent changes are missing. Let me ask about that. Were there any deployments?"

Be concise. Ask ONE focused question."""


EXTRACT_DETAILS_PROMPT = """Extract structured incident details from the conversation.

Based on the incident report and any clarifications provided, extract:
1. Incident time (date and approximate time if mentioned)
2. Time window for investigation in ISO format:
   - time_window_start: e.g., "2026-03-15T09:45:00" (15 min before incident)
   - time_window_end: e.g., "2026-03-15T10:15:00" (15 min after incident)
   - If time is like "around 10am", create a 30-minute window centered on that time
3. Affected services
4. Symptoms described
5. A complete summary combining all information

DATE REQUIREMENTS:
- Only use dates that were EXPLICITLY stated by the user or in the incident report.
- Do NOT infer, guess, or assume dates. Do NOT resolve relative references like "last Tuesday"
  to a calendar date — those should have been clarified in the previous step.
- If no specific date was provided, leave time_window_start and time_window_end as null.

IMPORTANT: The time_window_start and time_window_end MUST be in ISO format (YYYY-MM-DDTHH:MM:SS).
If time wasn't explicitly mentioned, leave time_window_start and time_window_end as null."""


HYP_GEN_SYSTEM_PROMPT = """You are an SRE orchestrator for Deep Research investigation.

Given the incident details AND the pre-gathered context (runbooks, past incidents,
recent changes, error signals), generate hypotheses about potential root causes.

IMPORTANT:
- Use the runbooks to understand service dependencies and common failure modes
- Check if past incidents show similar patterns — they are CRITICAL clues
- USE any recent changes detected in the logs — configuration changes, deployments,
  or migrations near the incident timeline are strong root cause candidates
- USE error signals to identify which services are actually failing vs healthy
- The service showing errors might be the VICTIM, not the root cause
- Generate 3-4 hypotheses covering different potential root causes
- Each hypothesis should include specific search terms derived from the context
- If an incident TIME was provided, include time-specific search terms

Respond with structured hypotheses that can be investigated in parallel."""


ROUTE_REQUEST_PROMPT = """You are routing user input in an incident investigation workflow.

Recent conversation:
<messages>
{messages}
</messages>

Current hypotheses have been generated. Classify the user's most recent message:

- "iterate_on_hypotheses": User wants to ADD, REMOVE, or MODIFY hypotheses (e.g., "add a hypothesis about...", "remove hypothesis 2", "change the search terms")
- "initiate_agents": User wants to START the investigation for ALL hypotheses (e.g., "investigate", "go", "start", "run", "let's do it", "looks good")
- "selective_investigation": User wants to investigate SPECIFIC hypotheses only (e.g., "investigate hypothesis 2 and 4", "only run 1 and 3", "skip hypothesis 2", "let's just do hypotheses 1, 3, 5")
- "general_qa": User is asking a QUESTION or making a comment that doesn't change hypotheses or start investigation (e.g., "what does this mean?", "tell me more about...", "why did you include...")

Classify the intent:"""


async def clarify_incident(
    state: OrchestratorState,
) -> Command[Literal["human_input_clarify", "extract_details"]]:
    """Check if incident needs clarification before proceeding.

    Uses bind_tools instead of with_structured_output so the LLM's reasoning
    text streams to the frontend via the "messages" namespace while the
    structured decision comes from the tool call.
    """
    logger.info("Step 2: Checking if clarification needed")

    llm = get_llm().bind_tools([IncidentClarification])

    conversation = get_buffer_string(messages=state["messages"])

    response = await llm.ainvoke(
        [
            {
                "role": "system",
                "content": CLARIFICATION_PROMPT
                + "\n\nYour text response must contain ONLY the question — no analysis, "
                "no reasoning, no preamble. Call the IncidentClarification tool "
                "with your structured decision.",
            },
            {
                "role": "user",
                "content": f"Incident Report:\n{state['incident']}\n\nConversation so far:\n{conversation}",
            },
        ]
    )

    # Extract structured decision from tool call
    if response.tool_calls:
        result = IncidentClarification(**response.tool_calls[0]["args"])
    else:
        # LLM chose not to call the tool — extract structured data from text
        logger.warning(
            "clarify_incident: LLM did not call tool, falling back to structured extraction"
        )
        extractor = get_llm().with_structured_output(IncidentClarification)
        result = await extractor.ainvoke(
            [
                {
                    "role": "user",
                    "content": f"Extract the clarification decision from this analysis:\n\n"
                    f"{_extract_text(response.content)}\n\nOriginal incident:\n{state['incident'][:500]}",
                }
            ]
        )

    # Always use structured fields — streamed text may contain reasoning/analysis
    # that shouldn't be shown to the user.
    if result.needs_clarification:
        logger.info(f"Clarification needed: {result.missing_info}")
        text = result.clarification_question
        return Command(
            goto="human_input_clarify",
            update={"messages": [AIMessage(content=text)]},
        )
    else:
        logger.info("Incident details sufficient, proceeding")
        text = f"**Incident Summary:** {result.summary}\n\nProceeding with investigation..."
        return Command(
            goto="extract_details",
            update={"messages": [AIMessage(content=text)]},
        )


async def human_input_clarify(
    state: OrchestratorState,
) -> Command[Literal["clarify_incident"]]:
    """Get clarification from user."""
    logger.info("Waiting for clarification...")

    user_input = interrupt("Please provide details:")

    return Command(
        goto="clarify_incident", update={"messages": [HumanMessage(content=user_input)]}
    )


async def extract_details(
    state: OrchestratorState,
) -> Command[Literal["hypothesis_generation"]]:
    """Extract structured incident details from conversation.

    Uses bind_tools so the LLM's summary text streams to the frontend while
    the structured fields come from the tool call.
    """
    logger.info("Extracting incident details")

    llm = get_llm().bind_tools([IncidentDetails])

    conversation = get_buffer_string(messages=state["messages"])

    response = await llm.ainvoke(
        [
            {
                "role": "system",
                "content": EXTRACT_DETAILS_PROMPT
                + "\n\nIMPORTANT: First summarize the confirmed incident details to the "
                "user in your message text (time, services, symptoms, investigation "
                "window), then call the IncidentDetails tool with the structured data. "
                "You MUST call the IncidentDetails tool after your summary.",
            },
            {
                "role": "user",
                "content": f"Original incident:\n{state['incident']}\n\nFull conversation:\n{conversation}",
            },
        ]
    )

    # Extract structured details from tool call
    if response.tool_calls:
        details = IncidentDetails(**response.tool_calls[0]["args"])
    else:
        logger.warning(
            "extract_details: LLM did not call tool, falling back to structured extraction"
        )
        extractor = get_llm().with_structured_output(IncidentDetails)
        details = await extractor.ainvoke(
            [
                {
                    "role": "user",
                    "content": f"Extract incident details from this summary:\n\n"
                    f"{_extract_text(response.content)}\n\nOriginal incident:\n{state['incident'][:500]}",
                }
            ]
        )

    # Build enriched context
    incident_summary = details.summary if details.summary else state["incident"]
    if details.incident_time:
        incident_summary = (
            f"**Incident Time:** {details.incident_time}\n\n{incident_summary}"
        )

    enriched_context = f"# Current Incident\n\n{incident_summary}\n\n"

    logger.info(
        f"Extracted details - Time: {details.incident_time}, Window: {details.time_window_start} to {details.time_window_end}, Services: {details.affected_services}"
    )

    # Use the LLM's streamed text as the message
    streamed_text = _extract_text(response.content)
    if not streamed_text:
        time_window_msg = ""
        if details.time_window_start and details.time_window_end:
            time_window_msg = f"\n- Investigation Window: {details.time_window_start} to {details.time_window_end}"
        elif details.incident_time:
            time_window_msg = "\n- Investigation Window: Not determined"
        services = (
            ", ".join(details.affected_services)
            if details.affected_services
            else "Not specified"
        )
        symptoms = ", ".join(details.symptoms) if details.symptoms else "Not specified"
        streamed_text = (
            f"**Incident Details Confirmed:**\n"
            f"- Time: {details.incident_time or 'Not specified'}{time_window_msg}\n"
            f"- Services: {services}\n"
            f"- Symptoms: {symptoms}\n\n"
            f"Generating hypotheses..."
        )
    text = streamed_text

    return Command(
        goto="context_enrichment",
        update={
            "incident_time": details.incident_time,
            "time_window_start": details.time_window_start,
            "time_window_end": details.time_window_end,
            "incident_details": details,
            "enriched_context": enriched_context,
            "messages": [AIMessage(content=text)],
        },
    )


# =============================================================================
# Probe terms for pre-hypothesis context enrichment
# =============================================================================

# Reduced probe sets — workers now have 25 iterations for deeper probing.
CHANGE_PROBE_TERMS = [
    "deploy",
    "config",
    "migration",
    "rollout",
    "upgrade",
]

ERROR_PROBE_TERMS = [
    "ERROR",
    "timeout",
    "failure",
]

# Cap on the combined KB context included in enriched_context.
_KB_CONTEXT_CAP = 4000
_CHANGE_CAP = 3000
_ERROR_CAP = 2000


def _infer_time_window(
    incident_time: Optional[str],
) -> Optional[tuple[str, str]]:
    """Try to extract a date from *incident_time* and create a +-24 h window.

    Used as a fallback when the LLM could not determine an explicit
    ``time_window_start`` / ``time_window_end`` but the user did mention
    a rough date (e.g. "around March 18, 2026").

    Returns ``(start_iso, end_iso)`` or ``None`` if parsing fails.
    """
    if not incident_time:
        return None
    try:
        from dateutil.parser import parse as dateutil_parse

        dt = dateutil_parse(incident_time, fuzzy=True)
        # Centre a 48-hour window around noon on the parsed date
        from datetime import timedelta

        centre = dt.replace(hour=12, minute=0, second=0, microsecond=0)
        start = centre - timedelta(hours=24)
        end = centre + timedelta(hours=24)
        return (start.strftime("%Y-%m-%dT%H:%M:%S"), end.strftime("%Y-%m-%dT%H:%M:%S"))
    except (ValueError, OverflowError):
        return None


def _build_context_queries(
    incident_details: Optional[IncidentDetails],
    scenario_name: str,
) -> list[str]:
    """Build 2-4 targeted KB queries from incident details.

    Derives queries from affected_services and symptoms so that
    hybrid search returns only the most relevant runbook sections
    and past incidents, rather than the full corpus.
    """
    queries: list[str] = []

    if incident_details:
        if incident_details.affected_services:
            services = " ".join(incident_details.affected_services[:3])
            queries.append(f"runbook troubleshooting {services}")

        if incident_details.symptoms:
            symptoms = " ".join(incident_details.symptoms[:3])
            queries.append(f"past incidents {symptoms}")

        if incident_details.affected_services and incident_details.symptoms:
            queries.append(
                f"{incident_details.affected_services[0]} "
                f"{incident_details.symptoms[0]} root cause"
            )

    # Fallback: at least one generic query if details are sparse
    if not queries:
        queries.append(f"troubleshooting guide {scenario_name}")
        queries.append(f"past incidents {scenario_name}")

    return queries


@trace_node("context_enrichment")
async def context_enrichment(
    state: OrchestratorState,
) -> Command[Literal["hypothesis_generation"]]:
    """Gather targeted context via hybrid search and light log probes.

    Uses query-based hybrid search (BM25 + semantic) to retrieve only
    the KB chunks relevant to the incident, instead of bulk-loading
    entire runbooks/past-incident files.  Workers can later call
    ``lookup_context`` for additional targeted retrieval.
    """
    from datetime import timedelta

    logger.info("Context enrichment: targeted KB queries + light log probes")

    scenario_name = state.get("scenario_name", "")
    enriched = state.get("enriched_context", "")
    incident_details = state.get("incident_details")

    # ------------------------------------------------------------------
    # 1. Targeted KB queries derived from incident details (hybrid search)
    # ------------------------------------------------------------------
    context_data: dict = {}
    kb_chunks: list[str] = []

    try:
        ctx_source = create_context_source()
    except RuntimeError as exc:
        logger.warning(
            f"Context enrichment: KB unavailable ({exc}), skipping KB queries"
        )
        ctx_source = None

    if ctx_source is not None:
        queries = _build_context_queries(incident_details, scenario_name)
        for q in queries:
            try:
                chunks = ctx_source.search(
                    query=q, num_results=3, scenario_name=scenario_name
                )
                kb_chunks.extend(chunks)
            except Exception as exc:
                logger.warning(f"Context enrichment: search failed for '{q}': {exc}")

    # Deduplicate (same chunk may match multiple queries)
    seen: set[str] = set()
    unique_chunks: list[str] = []
    for chunk in kb_chunks:
        key = chunk[:200]
        if key not in seen:
            seen.add(key)
            unique_chunks.append(chunk)

    if unique_chunks:
        kb_text = "\n\n---\n\n".join(unique_chunks)[:_KB_CONTEXT_CAP]
        enriched += f"# Retrieved Context (runbooks & past incidents)\n\n{kb_text}\n\n"
        context_data["kb_results"] = unique_chunks

    # ------------------------------------------------------------------
    # 2. Light log probes (reduced set — workers do the deep work)
    # ------------------------------------------------------------------
    time_start_str = state.get("time_window_start")
    time_end_str = state.get("time_window_end")

    # Fallback: if no explicit window but incident_time has a parseable date,
    # create a +-24h window for probes AND downstream workers.
    time_window_inferred = False
    if not time_start_str and not time_end_str and incident_details:
        inferred = _infer_time_window(incident_details.incident_time)
        if inferred:
            time_start_str, time_end_str = inferred
            time_window_inferred = True
            logger.info(
                "Context enrichment: inferred probe window from incident_time: "
                f"{time_start_str} to {time_end_str}"
            )

    change_lines: list[str] = []
    error_lines: list[str] = []

    if time_start_str and time_end_str:
        try:
            time_start = parse_iso_timestamp(time_start_str)
            time_end = parse_iso_timestamp(time_end_str)

            log_search = create_log_search_source()
            log_search.set_scenario(scenario_name)

            # Widen the window for change detection (3 days before incident)
            change_window_start = time_start - timedelta(days=3)

            for term in CHANGE_PROBE_TERMS:
                try:
                    result = log_search.search(
                        query=term,
                        time_start=change_window_start,
                        time_end=time_end,
                        limit=5,
                    )
                    if (
                        result
                        and "No logs found" not in result
                        and "ERROR" not in result
                    ):
                        change_lines.append(result)
                except Exception:
                    pass

            for term in ERROR_PROBE_TERMS:
                try:
                    result = log_search.search(
                        query=term,
                        time_start=time_start,
                        time_end=time_end,
                        limit=5,
                    )
                    if result and "No logs found" not in result:
                        error_lines.append(result)
                except Exception:
                    pass

        except Exception as exc:
            logger.warning(f"Context enrichment: log probe failed: {exc}")
    else:
        logger.info("Context enrichment: no time window available, skipping log probes")

    if change_lines:
        changes_text = "\n---\n".join(change_lines)[:_CHANGE_CAP]
        enriched += (
            f"# Recent Changes Detected (pre-incident window)\n\n{changes_text}\n\n"
        )
        context_data["change_signals"] = change_lines

    if error_lines:
        errors_text = "\n---\n".join(error_lines)[:_ERROR_CAP]
        enriched += f"# Error Signals Around Incident Time\n\n{errors_text}\n\n"
        context_data["error_signals"] = error_lines

    # ------------------------------------------------------------------
    # 3. Build status message for the frontend stream
    # ------------------------------------------------------------------
    summary_parts = []
    if kb_chunks:
        summary_parts.append(f"{len(set(c[:200] for c in kb_chunks))} KB chunks")
    elif context_data.get("runbooks"):
        summary_parts.append("runbooks")
    if context_data.get("past_incidents"):
        summary_parts.append("past incidents")
    if change_lines:
        summary_parts.append(f"{len(change_lines)} recent change signals")
    if error_lines:
        summary_parts.append(f"{len(error_lines)} error signals")

    if summary_parts:
        status = f"**Context gathered:** {', '.join(summary_parts)}. Generating hypotheses..."
    else:
        status = "No additional context found. Generating hypotheses from incident details..."

    logger.info(f"Context enrichment complete: {summary_parts}")

    update: dict = {
        "context": context_data,
        "enriched_context": enriched,
        "messages": [AIMessage(content=status)],
    }
    # Propagate inferred time window so downstream nodes (spawn_investigators,
    # workers) can use it for log searches.
    if time_window_inferred:
        update["time_window_start"] = time_start_str
        update["time_window_end"] = time_end_str

    return Command(
        goto="hypothesis_generation",
        update=update,
    )


@trace_node("hypothesis_generation")
async def hypothesis_generation(
    state: OrchestratorState,
) -> Command[Literal["human_input"]]:
    """Generate or update hypotheses using enriched context.

    Uses bind_tools so the LLM's reasoning streams while the structured
    hypothesis data comes from the tool call.
    """
    logger.info("Step 2: Hypothesis Generation")

    llm = get_llm().bind_tools([Hypotheses])

    streaming_instruction = (
        "\n\nIMPORTANT: First describe each hypothesis to the user in your message "
        "text — for each one, state the service, what might be wrong, and why it's "
        "worth investigating. Then call the Hypotheses tool with the structured data. "
        "You MUST call the Hypotheses tool after your explanation."
    )

    if state.get("current_hypotheses") and len(state["messages"]) > 2:
        response = await llm.ainvoke(
            [
                {
                    "role": "system",
                    "content": HYP_GEN_SYSTEM_PROMPT + streaming_instruction,
                },
                {
                    "role": "user",
                    "content": f"Original incident context:\n\n{state['enriched_context']}",
                },
                {
                    "role": "assistant",
                    "content": f"Previous hypotheses:\n{render_hypotheses(state['current_hypotheses'])}",
                },
                {
                    "role": "user",
                    "content": f"User feedback: {state['messages'][-1].content}\n\nPlease update the hypotheses based on this feedback.",
                },
            ]
        )
    else:
        response = await llm.ainvoke(
            [
                {
                    "role": "system",
                    "content": HYP_GEN_SYSTEM_PROMPT + streaming_instruction,
                },
                {
                    "role": "user",
                    "content": f"Generate hypotheses for this incident:\n\n{state['enriched_context']}",
                },
            ]
        )

    # Extract structured hypotheses from tool call
    if response.tool_calls:
        args = response.tool_calls[0]["args"]
        # Fix intermittent LLM issue: hypothesis values returned as JSON strings
        if "hypotheses" in args and isinstance(args["hypotheses"], dict):
            fixed = {}
            for k, v in args["hypotheses"].items():
                if isinstance(v, str):
                    try:
                        fixed[k] = json.loads(v)
                    except (json.JSONDecodeError, TypeError):
                        fixed[k] = v
                else:
                    fixed[k] = v
            args = {**args, "hypotheses": fixed}
        hypotheses = Hypotheses(**args)
    else:
        logger.warning(
            "hypothesis_generation: LLM did not call tool, falling back to structured extraction"
        )
        extractor = get_llm().with_structured_output(Hypotheses)
        hypotheses = await extractor.ainvoke(
            [
                {
                    "role": "user",
                    "content": f"Extract structured hypotheses from this analysis:\n\n"
                    f"{_extract_text(response.content)}\n\nIncident context:\n"
                    f"{state.get('enriched_context', state['incident'][:500])}",
                }
            ]
        )

    logger.info(f"Generated {len(hypotheses.hypotheses)} hypotheses")
    streamed_text = _extract_text(response.content)
    formatted = streamed_text or render_hypotheses(hypotheses)

    return Command(
        goto="human_input",
        update={
            "current_hypotheses": hypotheses,
            "messages": [AIMessage(content=formatted)],
        },
    )


async def human_input(
    state: OrchestratorState,
) -> Command[Literal["hypothesis_generation", "initiate_agents", "general_qa"]]:
    """Wait for human input and route based on intent."""
    logger.info("Waiting for human input...")

    # Interrupt and wait for user input
    user_input = interrupt("Your input:")

    # Add user message to state
    new_message = HumanMessage(content=user_input)

    # Route based on user intent
    route_prompt = ROUTE_REQUEST_PROMPT.format(
        messages=get_buffer_string(messages=state["messages"][-4:] + [new_message])
    )

    router = get_llm().with_structured_output(RouteFromQuery)
    route_decision = await router.ainvoke([HumanMessage(content=route_prompt)])

    logger.info(
        f"Route decision: {route_decision.classification} - {route_decision.rationale}"
    )

    if route_decision.classification == "iterate_on_hypotheses":
        return Command(goto="hypothesis_generation", update={"messages": [new_message]})
    elif route_decision.classification == "selective_investigation":
        # Extract which hypotheses the user wants to investigate
        extractor = get_llm().with_structured_output(SelectiveInvestigation)
        selection = await extractor.ainvoke(
            [
                HumanMessage(
                    content=f"The user said: {user_input}\n\n"
                    f"Available hypotheses: {list(state['current_hypotheses'].hypotheses.keys()) if state.get('current_hypotheses') else []}\n\n"
                    f"Extract which hypothesis numbers they want to investigate."
                )
            ]
        )
        selected_ids = selection.hypothesis_ids
        logger.info(f"Selective investigation: hypotheses {selected_ids}")
        return Command(
            goto="initiate_agents",
            update={
                "selected_hypotheses": selected_ids,
                "messages": [
                    new_message,
                    AIMessage(
                        content=f"Starting investigation for hypotheses {selected_ids}..."
                    ),
                ],
            },
        )
    elif route_decision.classification == "initiate_agents":
        return Command(
            goto="initiate_agents",
            update={
                "selected_hypotheses": None,
                "messages": [
                    new_message,
                    AIMessage(content="Starting investigation with all hypotheses..."),
                ],
            },
        )
    else:  # general_qa
        return Command(goto="general_qa", update={"messages": [new_message]})


async def general_qa(state: OrchestratorState) -> Command[Literal["human_input"]]:
    """Answer general questions about the incident or hypotheses."""
    logger.info("Answering general question...")

    # Build context for Q&A
    context_for_qa = f"""You are helping with an incident investigation.

Incident: {state["incident"][:500]}

Current hypotheses:
{render_hypotheses(state["current_hypotheses"]) if state.get("current_hypotheses") else "None generated yet"}

Investigation results:
{state.get("synthesized_report", "Investigation not yet run")}

Answer the user's question helpfully and concisely."""

    response = await get_llm().ainvoke(
        [
            {"role": "system", "content": context_for_qa},
            {"role": "user", "content": state["messages"][-1].content},
        ]
    )

    answer = (
        _extract_text(response.content)
        if hasattr(response, "content")
        else str(response)
    )

    return Command(goto="human_input", update={"messages": [AIMessage(content=answer)]})


async def initiate_agents(state: OrchestratorState) -> dict:
    """Placeholder node before spawning investigators."""
    selected = state.get("selected_hypotheses")
    total = len(state["current_hypotheses"].hypotheses)
    if selected:
        count = len(selected)
        msg = f"Initiating {count} investigation subagents..."
    else:
        msg = f"Initiating {total} investigation subagents..."
    logger.info(msg)
    return {"messages": [AIMessage(content=msg)]}


def spawn_investigators(state: OrchestratorState) -> list:
    """Dynamically spawn investigation agents for each hypothesis.

    When ``selected_hypotheses`` is set, only the specified hypothesis
    IDs are investigated.  Otherwise all hypotheses are investigated.

    The investigation time window is automatically extended backward
    (14 days before the incident window start) so that workers can
    discover upstream root causes that predate the visible symptoms.
    """
    from datetime import timedelta

    logger.info("Step 3: Spawning Investigation Agents")

    scenario_name = state.get("scenario_name")

    # Get time window from state (extracted during HITL clarification)
    time_window_start = state.get("time_window_start")
    time_window_end = state.get("time_window_end")

    # Extend the investigation window backward so workers can find root causes
    # that predate the symptom onset (e.g., a config/supplier change days before
    # complaints spike).  Each worker still receives the original incident window
    # for reference, but searches with the wider range.
    extended_start = time_window_start
    if time_window_start:
        try:
            ts = parse_iso_timestamp(time_window_start)
            extended_ts = ts - timedelta(days=14)
            extended_start = extended_ts.strftime("%Y-%m-%dT%H:%M:%S")
        except Exception:
            pass  # keep original if parsing fails

    # Discover available log sources so workers know valid service filter values
    available_log_sources = _discover_log_sources(scenario_name)

    # Filter hypotheses if the user selected a subset
    hypotheses = state["current_hypotheses"].hypotheses
    selected = state.get("selected_hypotheses")
    if selected is not None:
        hypotheses = {k: v for k, v in hypotheses.items() if k in selected}

    sends = [
        Send(
            "investigation_worker",
            {
                "messages": [],
                "worker_messages": [],
                "worker_id": f"investigator-{priority}",
                "n_iterations": 0,
                "max_iterations": 25,
                "hypothesis": hyp,
                "scenario_name": scenario_name,
                "time_window_start": hyp.time_window_start or extended_start,
                "time_window_end": hyp.time_window_end or time_window_end,
                "available_log_sources": available_log_sources,
            },
        )
        for priority, hyp in hypotheses.items()
    ]

    logger.info(
        f"Spawning {len(sends)} investigation agents, extended window: {extended_start} to {time_window_end}"
    )
    return sends


def _discover_log_sources(scenario_name: Optional[str] = None) -> Optional[str]:
    """Discover available log source names from the configured data source.

    Returns a comma-separated string of source names, or None if unavailable.
    """
    try:
        log_search = create_log_search_source()
        if scenario_name:
            log_search.set_scenario(scenario_name)
        sources = log_search.list_sources()
        if sources:
            return ", ".join(sources)
    except Exception as e:
        logger.warning(f"Could not discover log sources: {e}")
    return None


@trace_node("synthesize_findings")
async def synthesize_findings(
    state: OrchestratorState,
) -> Command[Literal["human_input_post"]]:
    """Synthesize findings from all investigation workers."""
    logger.info("Step 4: Synthesizing Findings")

    # Group messages by worker
    worker_findings = {}
    for item in state["worker_messages"]:
        if isinstance(item, dict) and "worker_id" in item:
            wid = item["worker_id"]
            if wid not in worker_findings:
                worker_findings[wid] = []
            worker_findings[wid].append(item)

    # Format findings for synthesis
    findings_text = ""
    for worker_id, messages in worker_findings.items():
        findings_text += f"\n\n## {worker_id} Findings:\n"
        for msg in messages:
            # Handle both old format (with message key) and new format (with content key)
            if isinstance(msg, dict):
                if msg.get("type") == "ai":
                    content = _extract_text(msg.get("content", ""))
                    findings_text += f"\n{content}\n"
                elif "message" in msg and isinstance(msg["message"], AIMessage):
                    findings_text += f"\n{_extract_text(msg['message'].content)}\n"

    # Synthesize with LLM
    synthesis_prompt = """You are synthesizing findings from multiple investigation agents.

Each agent investigated one hypothesis independently. Review ALL findings and determine
the TRUE root cause based on evidence quality.

CRITICAL REASONING RULES:
- Distinguish ROOT CAUSE from DOWNSTREAM SYMPTOM. A root cause is the originating
  change or failure. Downstream effects (missing logs, retry storms) are consequences.
  Always ask: "What CAUSED this?" and trace to the earliest triggering event.
- Prefer hypotheses backed by SPECIFIC LOG EVIDENCE (timestamps, config entries, error
  codes, exact values) over hypotheses argued from absence of evidence.
- When multiple hypotheses form a causal chain (A → B → C), identify A as root cause.
- A configuration change with a matching timeline is stronger than a symptom pattern.
- When ALL hypotheses lack direct log evidence, reason about which failure mode best
  explains the observed pattern — including ABSENCE of logs. Transport-layer failures
  (TLS, DNS, routing) may leave no application logs; that absence is a diagnostic signal.

SYNTHESIS REQUIREMENTS:
- Name SPECIFIC technical values from the evidence: config parameter names and values
  (e.g., timer=500ms, flag=enabled), error codes, version numbers, UUIDs, timestamps.
- Quote actual log entries when available — these are the proof.
- When agents found corroborating evidence across services, connect the dots explicitly.
- Identify the EARLIEST event in the causal chain as the root cause.

Provide:
ROOT CAUSE: [the specific change/failure and why — cite the config value, flag, version,
  or parameter that caused it, with the exact value from logs]
EVIDENCE: [specific log entries with timestamps and source services]
CONFIDENCE: [HIGH/MEDIUM/LOW]
RECOMMENDED ACTIONS: [what to do next — be specific about what to change/revert]"""

    response = await get_llm().ainvoke(
        [
            {"role": "system", "content": synthesis_prompt},
            {
                "role": "user",
                "content": f"Synthesize these investigation findings:\n{findings_text}",
            },
        ]
    )

    synthesis = (
        _extract_text(response.content)
        if hasattr(response, "content")
        else str(response)
    )

    report = f"{synthesis}\n\n---\n**You can now ask follow-up questions about the findings.**"

    return Command(
        goto="human_input_post",
        update={
            "synthesized_report": synthesis,
            "investigation_complete": True,
            "messages": [AIMessage(content=report)],
        },
    )


async def human_input_post(
    state: OrchestratorState,
) -> Command[Literal["general_qa", END]]:
    """Handle post-investigation human input."""
    logger.info("Post-investigation: waiting for human input...")

    user_input = interrupt("Follow-up question (or 'done' to finish):")

    if user_input.lower().strip() in ["done", "exit", "quit", "end", "finish"]:
        return Command(
            goto=END,
            update={
                "messages": [
                    HumanMessage(content=user_input),
                    AIMessage(content="Investigation complete. Goodbye!"),
                ]
            },
        )

    return Command(
        goto="general_qa", update={"messages": [HumanMessage(content=user_input)]}
    )


# =============================================================================
# Worker Nodes
# =============================================================================

INVESTIGATION_PROMPT = """You are Investigation Agent {worker_id}, investigating ONE hypothesis.

HYPOTHESIS: {hypothesis}
SERVICE: {service}
SUGGESTED SEARCH TERMS: {search_terms}
TIME WINDOW: {time_start} to {time_end}
AVAILABLE LOG SOURCES: {available_log_sources}

You have up to {max_iterations} tool calls. Use them strategically — breadth first, then depth.

== SEARCH MECHANICS ==
- Searches use case-insensitive substring matching: "timer" matches "handover_prep_timer",
  "TIMER_EXPIRED", and "Timer configuration".
- Search ONE term per call. Multi-word phrases must appear as an exact substring.
- ALWAYS pass time_start and time_end. Use the window above.
- The service filter matches words in log source names listed above. Use those exact names
  (e.g., "mobility-controller"), NOT abstract component names (e.g., "MME").

== INVESTIGATION PROCEDURE ==
1. **Start searching immediately** — the log sources are already listed above. Do NOT
   waste a call on list_log_sources unless the list above says "Not available".
2. **Broad search first** — search WITHOUT a service filter using your most specific term.
3. **Targeted follow-up** — narrow to specific services where you found hits.
4. **Cross-service tracing** — root causes often originate UPSTREAM. If service A
   shows symptoms, search service B for the triggering change.
5. **Build the causal chain** — each search should build on previous results.

== SEARCH TERM STRATEGY ==
- Start with your suggested search terms — one per call.
- If zero results: try SHORTER terms. "interceptor" instead of "gRPC interceptor".
- Try RELATED terms: "config" → "enabled", "disabled", "set to", "changed".
- Try terms for specific VALUES: error codes, timeout values, version numbers.
- Try single words: "backfill", "migration", "deploy", "timeout", "deadline".
- When you find a specific value (e.g., "100ms", "500ms", a UUID), search for it
  across other services to trace the causal chain.

== CONTEXT LOOKUP ==
If you need operational context (runbook details, similar past incidents, architecture info),
call lookup_context with a specific query describing what you need.
Example: lookup_context(query="handover timeout configuration", context_type="runbooks")
This performs a targeted hybrid search — use specific terms, not generic ones.
Your primary job is evidence collection via search_logs; use lookup_context only when
you need domain knowledge to interpret what you're finding.

== WHEN A SEARCH FINDS RESULTS ==
Do NOT stop. Extract the key technical details and search for those specific values
in other services. Build a complete causal chain.

== USE THE THINK TOOL SPARINGLY ==
Only call think when you have accumulated multiple search results and need to
reason about what to search next. Do NOT call think after every single search —
instead, just make your next search call directly. Save think for when you are
halfway through and need to reassess your strategy.

== CONCLUSION FORMAT ==
HYPOTHESIS: [restate your hypothesis]
EVIDENCE: [specific log entries with timestamps, config values, error codes — quote them]
CONCLUSION: [SUPPORTED / REFUTED / INCONCLUSIVE] with reasoning
KEY TECHNICAL DETAILS: [list specific values: timer=500ms, flag=enabled, version=3.8.0, etc.]"""


from stream_formatter import extract_text_content as _extract_text  # noqa: E402


def tag_messages(worker_id: str, messages: list) -> list:
    """Tag messages with worker ID for aggregation. Stores content as strings for serialization."""
    tagged = []
    for m in messages:
        if isinstance(m, dict) and "worker_id" in m:
            tagged.append(m)
        elif isinstance(m, AIMessage):
            # Store as serializable dict with content string
            tagged.append(
                {
                    "worker_id": worker_id,
                    "content": _extract_text(m.content),
                    "type": "ai",
                }
            )
        elif isinstance(m, ToolMessage):
            tagged.append(
                {
                    "worker_id": worker_id,
                    "content": _extract_text(m.content),
                    "type": "tool",
                    "tool_call_id": m.tool_call_id,
                }
            )
        elif isinstance(m, dict):
            tagged.append({"worker_id": worker_id, **m})
        else:
            tagged.append(
                {"worker_id": worker_id, "content": str(m), "type": "unknown"}
            )
    return tagged


@trace_node("investigation_reasoning")
async def investigation_reasoning(
    state: WorkerState,
) -> Command[Literal[END, "investigation_tool"]]:
    """Worker reasoning node - decides what to search or concludes."""
    worker_id = state["worker_id"]
    hypothesis = state["hypothesis"]
    n_iterations = state.get("n_iterations", 0) + 1

    logger.info(f"{worker_id}: Reasoning iteration {n_iterations}")

    # Bind tools from registry to LLM
    from tool_registry import get_tool_registry

    tools = get_tool_registry().get_schemas()
    llm_with_tools = get_llm().bind_tools(tools)

    # Build system prompt with time window
    time_start = state.get("time_window_start") or "Not specified"
    time_end = state.get("time_window_end") or "Not specified"

    available_log_sources = state.get("available_log_sources") or "Not available"

    system_prompt = INVESTIGATION_PROMPT.format(
        worker_id=worker_id,
        hypothesis=hypothesis.description,
        service=hypothesis.service,
        search_terms=", ".join(hypothesis.search_terms),
        max_iterations=state["max_iterations"],
        time_start=time_start,
        time_end=time_end,
        available_log_sources=available_log_sources,
    )

    # Get worker messages or initialize
    if state["worker_messages"]:
        messages = [{"role": "system", "content": system_prompt}]
        for item in state["worker_messages"]:
            if isinstance(item, dict):
                # New serializable format
                if item.get("type") == "ai":
                    # Reconstruct AI message with tool calls if present
                    content = item.get("content", "")
                    tool_calls = item.get("tool_calls")
                    if tool_calls:
                        messages.append(
                            AIMessage(content=content, tool_calls=tool_calls)
                        )
                    else:
                        messages.append({"role": "assistant", "content": content})
                elif item.get("type") == "tool":
                    messages.append(
                        ToolMessage(
                            content=item.get("content", ""),
                            tool_call_id=item.get("tool_call_id", ""),
                        )
                    )
                # Old format compatibility
                elif "message" in item:
                    msg = item["message"]
                    if isinstance(msg, AIMessage):
                        messages.append({"role": "assistant", "content": msg.content})
                    elif isinstance(msg, ToolMessage):
                        messages.append(msg)
                    elif isinstance(msg, dict):
                        messages.append(msg)
            elif isinstance(item, BaseMessage):
                messages.append(item)
    else:
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Investigate this hypothesis: {hypothesis.description}\n\nStart with a broad search_logs call (no service filter) using your most specific suggested search term.",
            },
        ]

    # Invoke LLM
    ai_message = await llm_with_tools.ainvoke(messages)

    # Check if we should continue with tools or conclude
    if ai_message.tool_calls and n_iterations <= state["max_iterations"]:
        logger.info(f"{worker_id}: Calling tools")
        # Store AI message with tool calls - need to keep the actual message for tool execution
        return Command(
            goto="investigation_tool",
            update={
                "worker_messages": [
                    {
                        "worker_id": worker_id,
                        "content": _extract_text(ai_message.content),
                        "type": "ai",
                        "tool_calls": ai_message.tool_calls,  # Keep tool calls for execution
                    }
                ],
                "n_iterations": n_iterations,
            },
        )

    # Done — only return the NEW final message.  Prior messages are already
    # in state["worker_messages"] via operator.add from earlier iterations.
    tagged_final = tag_messages(worker_id, [ai_message])

    logger.info(f"{worker_id}: Investigation complete after {n_iterations} iterations")

    return Command(
        goto=END,
        update={"worker_messages": tagged_final, "n_iterations": n_iterations},
    )


def parse_iso_timestamp(ts_str: str) -> datetime:
    """Parse ISO timestamp string to datetime."""
    from parsing_utils import parse_timestamp

    result = parse_timestamp(ts_str)
    if result is None:
        raise ValueError(f"Cannot parse timestamp: {ts_str}")
    return result


@trace_node("investigation_tool")
async def investigation_tool(state: WorkerState, config: dict = None) -> dict:
    """Worker tool execution node - searches CloudWatch Logs."""
    worker_id = state["worker_id"]
    logger.info(f"{worker_id}: Executing tools")

    # Get last AI message with tool calls
    tool_calls = None
    for item in reversed(state["worker_messages"]):
        if isinstance(item, dict):
            # New format: tool_calls stored directly
            if item.get("type") == "ai" and item.get("tool_calls"):
                tool_calls = item["tool_calls"]
                break
            # Old format: message is AIMessage
            elif "message" in item:
                msg = item["message"]
                if isinstance(msg, AIMessage) and msg.tool_calls:
                    tool_calls = msg.tool_calls
                    break

    if not tool_calls:
        return {"worker_messages": []}

    # Create log search source (LOCAL: file-based, PRODUCTION: CloudWatch)
    log_search = create_log_search_source()

    # Get scenario name and set it on the log search source
    # (Required for LOCAL mode to find the right evidence directory)
    scenario_name = state.get("scenario_name")
    if scenario_name:
        log_search.set_scenario(scenario_name)

    # Get default time window from state
    default_time_start = state.get("time_window_start")
    default_time_end = state.get("time_window_end")

    # Execute tool calls via registry
    from tool_registry import get_tool_registry

    registry = get_tool_registry()

    # Create context source for lookup_context tool (optional — KB may not be configured)
    try:
        context_source = create_context_source()
    except RuntimeError:
        context_source = None

    tool_context = {
        "log_search": log_search,
        "context_source": context_source,
        "scenario_name": scenario_name,
        "default_time_start": default_time_start,
        "default_time_end": default_time_end,
        "worker_id": worker_id,
    }

    # Trajectory capture (optional — threaded via LangGraph configurable from API layer)
    trajectory = None
    if config:
        configurable = config.get("configurable", {})
        trajectory = configurable.get("trajectory")

    tool_messages = []
    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        logger.info(f"{worker_id}: Tool call - {tool_name}({tool_args})")

        executor = registry.get_executor(tool_name)
        if executor:
            import time as _time

            _t0 = _time.time()
            result = executor(tool_args, tool_context)
            _duration_ms = (_time.time() - _t0) * 1000
            if trajectory:
                trajectory.record_tool_call(
                    tool_name,
                    tool_args,
                    result[:200] if result else "",
                    _duration_ms,
                    worker_id,
                )
        else:
            result = f"Unknown tool: {tool_name}"

        tool_messages.append(ToolMessage(content=result, tool_call_id=tool_call["id"]))

    # Convert to serializable format
    return {
        "worker_messages": [
            {
                "worker_id": worker_id,
                "content": _extract_text(msg.content),
                "type": "tool",
                "tool_call_id": msg.tool_call_id,
            }
            for msg in tool_messages
        ]
    }


# =============================================================================
# Graph Construction
# =============================================================================


def build_orchestrator_graph(checkpointer=None):
    """Build the main orchestrator graph with HITL and clarification.

    Args:
        checkpointer: Optional LangGraph checkpointer for state persistence.
                      If None, uses MemorySaver (in-memory).
                      For AgentCore deployment, pass AgentCoreMemorySaver.
    """
    builder = StateGraph(OrchestratorState)

    # Add nodes
    builder.add_node("clarify_incident", clarify_incident)
    builder.add_node("human_input_clarify", human_input_clarify)
    builder.add_node("extract_details", extract_details)
    builder.add_node("context_enrichment", context_enrichment)
    builder.add_node("hypothesis_generation", hypothesis_generation)
    builder.add_node("human_input", human_input)
    builder.add_node("general_qa", general_qa)
    builder.add_node("initiate_agents", initiate_agents)
    builder.add_node("investigation_worker", build_worker_graph())
    builder.add_node("synthesize_findings", synthesize_findings)
    builder.add_node("human_input_post", human_input_post)

    # Add edges
    # Phase 1: Clarification
    builder.add_edge(START, "clarify_incident")
    # clarify_incident routes via Command to: human_input_clarify or extract_details
    # human_input_clarify routes via Command back to: clarify_incident
    # extract_details routes via Command to: context_enrichment
    # context_enrichment routes via Command to: hypothesis_generation

    # Phase 2: Hypothesis review (human_input routes via Command)
    # hypothesis_generation routes to human_input via Command
    # human_input routes via Command to: hypothesis_generation, initiate_agents (all or selective), or general_qa
    # general_qa routes back to human_input via Command

    # Phase 3: Investigation
    # Dynamic spawning: initiate_agents -> spawn_investigators -> investigation_worker
    builder.add_conditional_edges(
        "initiate_agents", spawn_investigators, ["investigation_worker"]
    )

    # All workers converge to synthesis
    builder.add_edge("investigation_worker", "synthesize_findings")
    # synthesize_findings routes to human_input_post via Command
    # human_input_post routes via Command to: general_qa or END

    # Checkpointer for HITL (use provided or create from config)
    if checkpointer is None:
        checkpointer = create_checkpointer()

    return builder.compile(checkpointer=checkpointer)


def build_worker_graph():
    """Build the investigation worker subgraph."""
    builder = StateGraph(WorkerState)

    builder.add_node("investigation_reasoning", investigation_reasoning)
    builder.add_node("investigation_tool", investigation_tool)

    builder.add_edge(START, "investigation_reasoning")
    builder.add_edge("investigation_tool", "investigation_reasoning")

    return builder.compile()


def build_initial_state(incident: str, scenario_name: str = "") -> dict:
    """Build the initial graph state for a new investigation."""
    return {
        "messages": [HumanMessage(content=incident)],
        "incident": incident,
        "incident_time": None,
        "incident_details": None,
        "context": {},
        "enriched_context": "",
        "current_hypotheses": None,
        "selected_hypotheses": None,
        "worker_messages": [],
        "synthesized_report": "",
        "scenario_name": scenario_name,
        "investigation_complete": False,
    }


# =============================================================================
# Main Entry Point
# =============================================================================


def _load_vague_report(scenario_path: Path) -> str | None:
    """Load the vague opening report from ground_truth.yaml hitl_flow."""
    import yaml

    gt_file = scenario_path / "ground_truth.yaml"
    if not gt_file.exists():
        return None
    try:
        gt = yaml.safe_load(gt_file.read_text())
        flow = gt.get("hitl_flow", {})
        return flow.get("1_vague_report")
    except Exception:
        return None


async def run_investigation(
    scenario_name: str = DEFAULT_SCENARIO, incident_file: str = None
):
    """Run a Deep Research RCA investigation with HITL.

    By default, starts with the vague opening report from ground_truth.yaml
    (matching the UI experience). Falls back to incident.md if no HITL flow
    is defined.

    Args:
        scenario_name: Name of the scenario to investigate
        incident_file: Optional path to custom incident file (e.g., for CloudWatch demos)
    """
    scenario_path = SCENARIOS_DIR / scenario_name

    if not scenario_path.exists():
        available = [d.name for d in SCENARIOS_DIR.iterdir() if d.is_dir()]
        logger.error(f"Scenario '{scenario_name}' not found. Available: {available}")
        print(f"Error: Scenario '{scenario_name}' not found")
        print(f"Available: {available}")
        sys.exit(1)

    print("=" * 70)
    print(f"Deep Research RCA Agent - {scenario_name}")
    print("=" * 70)

    # Load incident text: custom file > vague report from ground_truth > incident.md
    if incident_file:
        incident_path = Path(incident_file)
        if not incident_path.exists():
            logger.error(f"Incident file not found: {incident_file}")
            print(f"Error: Incident file not found: {incident_file}")
            sys.exit(1)
        logger.info(f"Using custom incident file: {incident_file}")
        print(f"Using custom incident file: {incident_file}")
        with open(incident_path) as f:
            incident = f.read()
    else:
        vague = _load_vague_report(scenario_path)
        if vague:
            incident = vague
            logger.info("Using vague report from ground_truth.yaml (matches UI flow)")
        else:
            with open(scenario_path / "incident.md") as f:
                incident = f.read()
            logger.info("No HITL flow found, falling back to incident.md")

    print("\nINCIDENT REPORT:")
    print("-" * 50)
    print(incident[:500] + "..." if len(incident) > 500 else incident)
    print()

    # Build graph (async checkpointer for SQLite compatibility)
    checkpointer = await create_async_checkpointer()
    graph = build_orchestrator_graph(checkpointer=checkpointer)

    initial_state = build_initial_state(incident, scenario_name)

    # Create thread config for checkpointing
    config = {"configurable": {"thread_id": f"investigation-{scenario_name}"}}

    print("\nRunning Deep Research Investigation with Human-in-the-Loop...\n")

    # Run until first interrupt — stream tokens in real-time
    async for message_chunk, metadata in graph.astream(
        initial_state, config, stream_mode="messages"
    ):
        if hasattr(message_chunk, "content") and message_chunk.content:
            print(message_chunk.content, end="", flush=True)
    print()  # newline after streaming

    # Interactive loop for HITL
    while True:
        try:
            # Check graph state
            state = await graph.aget_state(config)

            if state.next:
                # Graph is waiting for input
                print("\n" + "-" * 50)
                user_input = input(">> ")

                if user_input.lower().strip() in ["quit", "exit", "q"]:
                    print("Exiting investigation.")
                    break

                # Resume with user input — stream tokens in real-time
                async for message_chunk, metadata in graph.astream(
                    Command(resume=user_input), config, stream_mode="messages"
                ):
                    if hasattr(message_chunk, "content") and message_chunk.content:
                        print(message_chunk.content, end="", flush=True)
                print()  # newline after streaming
            else:
                # Graph has completed
                print("\n" + "=" * 70)
                print("Deep Research Investigation Complete")
                print("=" * 70)
                break

        except KeyboardInterrupt:
            print("\n\nInterrupted by user.")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            break


def main():
    """CLI entry point."""
    import argparse

    # Load config and configure logging
    config = get_config()
    configure_logging(config.log_level)

    logger.info(f"Agent configuration: {config}")

    errors = config.validate()
    if errors:
        for err in errors:
            logger.error(f"Config error: {err}")
        print("Configuration errors:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Deep Research RCA Agent")
    parser.add_argument(
        "scenario",
        nargs="?",
        default=DEFAULT_SCENARIO,
        help="Scenario name to investigate",
    )
    parser.add_argument(
        "--incident",
        "-i",
        dest="incident_file",
        help="Path to custom incident file (e.g., incident_cloudwatch.md)",
    )

    args = parser.parse_args()
    asyncio.run(run_investigation(args.scenario, args.incident_file))


if __name__ == "__main__":
    main()
