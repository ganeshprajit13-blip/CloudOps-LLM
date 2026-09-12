"""
FastAPI backend for the RCA Deep Research Agent.

Wraps the LangGraph agent with REST + SSE endpoints for the React frontend.
No changes to rca_agent.py — this is a pure API layer.

Usage:
    uvicorn src.api:app --reload --port 8000
"""

import asyncio
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from langgraph.types import Command
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse

# Ensure src is importable
import sys

_src_dir = Path(__file__).parent
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from auth import is_auth_enabled, CognitoAuthMiddleware  # noqa: E402
from checkpoint import create_async_checkpointer  # noqa: E402
from config import get_config, configure_logging  # noqa: E402
from rca_agent import build_orchestrator_graph, SCENARIOS_DIR  # noqa: E402
from stream_formatter import (  # noqa: E402
    INTERRUPT_NODE_MAP,
    process_dual_stream,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

_config = get_config()
configure_logging(_config.log_level)

_errors = _config.validate()
if _errors:
    for _e in _errors:
        logger.error("Config error: %s", _e)
    raise RuntimeError(f"Agent configuration invalid: {'; '.join(_errors)}")

# Initialized in lifespan (async required for SQLite checkpointer)
_checkpointer = None
_graph = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _checkpointer, _graph
    _checkpointer = await create_async_checkpointer()
    _graph = build_orchestrator_graph(checkpointer=_checkpointer)
    yield
    # Close the aiosqlite connection on shutdown
    if hasattr(_checkpointer, "conn") and hasattr(_checkpointer.conn, "close"):
        await _checkpointer.conn.close()


app = FastAPI(title="RCA Deep Research Agent", lifespan=lifespan)

limiter = Limiter(key_func=get_remote_address, default_limits=[])
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please slow down."},
    )


_cors_origins = os.environ.get(
    "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Session-Id"],
    max_age=3600,
)

_SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
}


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    for k, v in _SECURITY_HEADERS.items():
        response.headers[k] = v
    return response


if is_auth_enabled():
    app.add_middleware(CognitoAuthMiddleware)
    logger.info("Cognito JWT authentication enabled")
else:
    logger.info(
        "Authentication disabled (COGNITO_USER_POOL_ID / COGNITO_APP_CLIENT_ID not set)"
    )

# ---------------------------------------------------------------------------
# In-memory investigation store
# ---------------------------------------------------------------------------


@dataclass
class InvestigationState:
    id: str
    scenario_name: Optional[str]
    incident: str
    thread_config: dict
    started: bool = False
    trajectory: Optional[object] = None  # TrajectoryCapture instance when enabled
    created_at: float = field(default_factory=time.time)


_investigations: dict[str, InvestigationState] = {}
_MAX_INVESTIGATIONS = 1000
_INVESTIGATION_TTL = 86400  # 24 hours in seconds
_stream_semaphore = asyncio.Semaphore(10)


def _prune_investigations() -> None:
    """Remove expired investigations from the in-memory cache."""
    cutoff = time.time() - _INVESTIGATION_TTL
    expired = [k for k, v in _investigations.items() if v.created_at < cutoff]
    for k in expired:
        del _investigations[k]


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


MAX_INCIDENT_TEXT_LENGTH = 51200  # 50 KB


class CreateInvestigationRequest(BaseModel):
    scenario_name: Optional[str] = Field(
        None, max_length=256, pattern=r"^[a-zA-Z0-9._-]+$"
    )
    incident_text: Optional[str] = Field(None, max_length=MAX_INCIDENT_TEXT_LENGTH)
    include_trajectory: bool = False


class StreamRequest(BaseModel):
    message: Optional[str] = Field(None, max_length=MAX_INCIDENT_TEXT_LENGTH)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_scenario_dir(scenario_name: str) -> Path:
    """Validate scenario_name resolves within SCENARIOS_DIR. Returns resolved scenario dir."""
    scenario_dir = (SCENARIOS_DIR / scenario_name).resolve()
    if not scenario_dir.is_relative_to(SCENARIOS_DIR.resolve()):
        raise HTTPException(400, "Invalid scenario name")
    return scenario_dir


def _load_incident(scenario_name: str) -> str:
    """Load incident.md from a scenario directory."""
    scenario_dir = _validate_scenario_dir(scenario_name)
    incident_file = scenario_dir / "incident.md"
    if not incident_file.exists():
        raise HTTPException(
            404, f"Scenario '{scenario_name}' not found or has no incident.md"
        )
    return incident_file.read_text()


def _sse_line(event: str, data: dict) -> str:
    """Format an event as an SSE data line: data: {json}\n\n"""
    return f"data: {json.dumps({'event': event, 'data': data})}\n\n"


async def _stream_graph(inv: InvestigationState, resume_message: Optional[str] = None):
    """Generator yielding SSE-formatted text lines.

    Two modes:
    - Start (resume_message is None): run graph with initial state
    - Resume (resume_message is set): resume from interrupt with user input
    Stream ends after emitting either 'interrupt' or 'complete'.
    """
    config = inv.thread_config
    if inv.trajectory:
        config["configurable"]["trajectory"] = inv.trajectory

    if resume_message is not None:
        # Resume from HITL interrupt
        async for evt in process_dual_stream(
            _graph.astream(
                Command(resume=resume_message),
                config,
                stream_mode=["updates", "messages"],
                subgraphs=True,
            )
        ):
            yield _sse_line(evt["event"], evt["data"])
    elif not inv.started:
        # First invocation — start the graph
        inv.started = True
        from rca_agent import build_initial_state

        initial_state = build_initial_state(inv.incident, inv.scenario_name or "")

        yield _sse_line(
            "phase", {"phase": "clarification", "description": "Analyzing incident..."}
        )

        async for evt in process_dual_stream(
            _graph.astream(
                initial_state,
                config,
                stream_mode=["updates", "messages"],
                subgraphs=True,
            )
        ):
            yield _sse_line(evt["event"], evt["data"])

    # Check final state: interrupt or complete
    state = await _graph.aget_state(config)

    if not state.next:
        yield _sse_line(
            "phase", {"phase": "complete", "description": "Investigation complete"}
        )
        report = state.values.get("synthesized_report", "")
        complete_data: dict = {"report": report}
        if inv.trajectory:
            complete_data["trajectory"] = inv.trajectory.to_dict()
        yield _sse_line("complete", complete_data)
    else:
        # At an interrupt — emit and end stream
        next_node = list(state.next)[0]
        interrupt_type = INTERRUPT_NODE_MAP.get(next_node, "clarification")
        yield _sse_line(
            "interrupt",
            {
                "type": interrupt_type,
                "next_node": next_node,
                "prompt": f"Awaiting input at {next_node}",
                "status": "awaiting_input",
            },
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/health/deep")
async def health_deep():
    """Deep health check that tests backend connectivity."""
    checks = {}
    overall_ok = True

    # Test checkpointer connectivity
    try:
        if _checkpointer is None:
            checks["checkpointer"] = {"status": "error", "detail": "Not initialized"}
            overall_ok = False
        elif hasattr(_checkpointer, "conn"):
            # SQLite — attempt a simple query
            await _checkpointer.conn.execute("SELECT 1")
            checks["checkpointer"] = {"status": "ok", "backend": "sqlite"}
        elif hasattr(_checkpointer, "client"):
            # DynamoDB — verify table is reachable
            table_name = _config.checkpoint_table_name
            if table_name:
                _checkpointer.client.describe_table(TableName=table_name)
            checks["checkpointer"] = {"status": "ok", "backend": "dynamodb"}
        else:
            # MemorySaver or AgentCore
            checks["checkpointer"] = {"status": "ok", "backend": "memory"}
    except Exception:
        logger.exception("Deep health check: checkpointer failed")
        checks["checkpointer"] = {
            "status": "error",
            "detail": "Connectivity check failed",
        }
        overall_ok = False

    # Test graph initialization
    checks["graph"] = {"status": "ok" if _graph is not None else "error"}
    if _graph is None:
        overall_ok = False

    status_code = 200 if overall_ok else 503
    return JSONResponse(
        content={"status": "ok" if overall_ok else "degraded", "checks": checks},
        status_code=status_code,
    )


@app.get("/api/config/status")
@limiter.limit("10/minute")
async def config_status(request: Request):
    """Return agent configuration and backend readiness status."""
    from status import get_system_status

    return await get_system_status()


@app.get("/api/scenarios")
@limiter.limit("60/minute")
async def list_scenarios(request: Request):
    """List available investigation scenarios."""
    scenarios = []
    if SCENARIOS_DIR.exists():
        for d in sorted(SCENARIOS_DIR.iterdir()):
            if d.is_dir() and (d / "incident.md").exists():
                entry = {
                    "name": d.name,
                    "display_name": d.name.replace("-", " ").title(),
                    "description": d.name.replace("-", " ").title(),
                    "has_hitl": False,
                }
                gt_file = d / "ground_truth.yaml"
                if gt_file.exists():
                    try:
                        gt = yaml.safe_load(gt_file.read_text())
                        if gt.get("display_name"):
                            entry["display_name"] = gt["display_name"]
                        if gt.get("domain"):
                            entry["description"] = gt["domain"]
                        entry["has_hitl"] = gt.get("hitl_scenario", False)
                    except Exception as e:
                        logger.warning(
                            "Failed to parse ground_truth.yaml for %s: %s", d.name, e
                        )
                scenarios.append(entry)
    return {"scenarios": scenarios}


@app.get("/api/scenarios/{name}")
@limiter.limit("60/minute")
async def get_scenario(request: Request, name: str):
    """Get a scenario's incident text."""
    incident = _load_incident(name)
    return {"name": name, "incident": incident}


@app.get("/api/scenarios/{name}/docs")
@limiter.limit("60/minute")
async def get_scenario_docs(request: Request, name: str):
    """Return all scenario documentation files for the frontend reference panel."""
    scenario_dir = _validate_scenario_dir(name)
    if not scenario_dir.is_dir():
        raise HTTPException(404, f"Scenario '{name}' not found")

    docs: dict = {
        "incident": None,
        "context": {},
        "evidence": {},
        "readme": None,
        "ground_truth": None,
    }

    incident_file = scenario_dir / "incident.md"
    if incident_file.exists():
        docs["incident"] = incident_file.read_text()

    readme_file = scenario_dir / "README.md"
    if readme_file.exists():
        docs["readme"] = readme_file.read_text()

    gt_file = scenario_dir / "ground_truth.yaml"
    if gt_file.exists():
        try:
            docs["ground_truth"] = yaml.safe_load(gt_file.read_text())
        except Exception:
            logger.debug("Could not parse ground_truth.yaml for %s", scenario_dir.name)

    context_dir = scenario_dir / "context"
    if context_dir.is_dir():
        for f in sorted(context_dir.iterdir()):
            if f.is_file():
                docs["context"][f.name] = f.read_text()

    evidence_dir = scenario_dir / "evidence"
    if evidence_dir.is_dir():
        for f in sorted(evidence_dir.iterdir()):
            if f.is_file():
                docs["evidence"][f.name] = f.read_text()

    return docs


@app.post("/api/investigations")
@limiter.limit("10/minute")
async def create_investigation(request: Request, req: CreateInvestigationRequest):
    """Create a new investigation and return its ID."""
    if not req.scenario_name and not req.incident_text:
        raise HTTPException(400, "Provide scenario_name or incident_text")

    _prune_investigations()
    if len(_investigations) >= _MAX_INVESTIGATIONS:
        raise HTTPException(429, "Too many active investigations. Try again later.")

    inv_id = str(uuid.uuid4())

    if req.scenario_name and req.incident_text:
        # User provided their own description — use it exclusively so the
        # agent can ask clarifying questions (incident.md contains dates
        # that would bypass HITL). scenario_name is preserved on
        # InvestigationState for evidence/context file lookups.
        incident = req.incident_text
    elif req.scenario_name:
        incident = _load_incident(req.scenario_name)
    elif req.incident_text:
        incident = req.incident_text

    trajectory = None
    if req.include_trajectory:
        from trajectory import TrajectoryCapture

        trajectory = TrajectoryCapture(inv_id, req.scenario_name or "")

    inv = InvestigationState(
        id=inv_id,
        scenario_name=req.scenario_name,
        incident=incident,
        thread_config={"configurable": {"thread_id": f"investigation-{inv_id}"}},
        trajectory=trajectory,
    )
    _investigations[inv_id] = inv

    return {"investigation_id": inv_id}


@app.post("/api/investigations/{inv_id}/stream")
@limiter.limit("30/minute")
async def stream_investigation(
    request: Request, inv_id: str, req: StreamRequest = None
):
    """SSE stream of investigation events.

    First call (no message): starts the investigation.
    Subsequent calls (with message): resumes from HITL interrupt.
    """
    inv = _investigations.get(inv_id)
    if not inv:
        # Recover from server restart (e.g. uvicorn --reload) by checking the
        # checkpointer.  The LangGraph state is durable — only the lightweight
        # InvestigationState wrapper lives in memory.
        thread_config = {"configurable": {"thread_id": f"investigation-{inv_id}"}}
        saved = await _graph.aget_state(thread_config)
        if saved and saved.values:
            inv = InvestigationState(
                id=inv_id,
                scenario_name=saved.values.get("scenario_name", ""),
                incident=saved.values.get("incident", ""),
                thread_config=thread_config,
                started=True,
            )
            _investigations[inv_id] = inv
            logger.info("Recovered investigation %s from checkpointer", inv_id)
        else:
            raise HTTPException(404, "Investigation not found")

    resume_message = req.message if req else None

    try:
        await asyncio.wait_for(_stream_semaphore.acquire(), timeout=2.0)
    except asyncio.TimeoutError:
        raise HTTPException(
            429, "Too many concurrent investigations. Try again shortly."
        )

    async def event_generator():
        try:
            async for sse_line in _stream_graph(inv, resume_message):
                yield sse_line
        except Exception:
            logger.exception("Stream error for %s", inv_id)
            yield _sse_line(
                "error",
                {
                    "message": "An internal error occurred. Please try again or contact support.",
                    "investigation_id": inv_id,
                },
            )
        finally:
            _stream_semaphore.release()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Serve built frontend in production
# ---------------------------------------------------------------------------

_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount(
        "/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend"
    )
