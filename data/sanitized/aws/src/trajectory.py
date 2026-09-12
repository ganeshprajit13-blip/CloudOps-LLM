"""
Trajectory capture for investigation evaluation.

Records tool calls, node transitions, and LLM token usage during an
investigation. Enabled per-request via includeTrajectory flag.

Usage:
    trajectory = TrajectoryCapture(session_id="inv-123", scenario_name="volte-call-drop-handover")

    # During investigation
    trajectory.record_tool_call("search_logs", {"query": "error"}, "Found 5 results", 1200.0, "worker-1")
    trajectory.record_node_transition("hypothesis_generation", "investigation", 350.0)
    trajectory.record_llm_usage(1500, 800)

    # After investigation
    record = trajectory.finalize()
    print(record.to_dict())
"""

import time
from dataclasses import dataclass


@dataclass
class ToolCallRecord:
    """A single tool invocation during an investigation."""

    tool_name: str
    tool_args: dict
    result_preview: str  # truncated result for storage
    duration_ms: float
    worker_id: str
    timestamp: float

    def to_dict(self) -> dict:
        return {
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "result_preview": self.result_preview,
            "duration_ms": round(self.duration_ms, 1),
            "worker_id": self.worker_id,
            "timestamp": self.timestamp,
        }


@dataclass
class NodeTransition:
    """A transition between graph nodes."""

    from_node: str
    to_node: str
    timestamp: float
    duration_ms: float

    def to_dict(self) -> dict:
        return {
            "from_node": self.from_node,
            "to_node": self.to_node,
            "timestamp": self.timestamp,
            "duration_ms": round(self.duration_ms, 1),
        }


@dataclass
class TrajectoryRecord:
    """Complete trajectory for an investigation."""

    session_id: str
    scenario_name: str
    tool_calls: list[ToolCallRecord]
    node_transitions: list[NodeTransition]
    total_duration_ms: float
    llm_input_tokens: int
    llm_output_tokens: int
    num_hypotheses: int
    num_workers: int

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "scenario_name": self.scenario_name,
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "node_transitions": [nt.to_dict() for nt in self.node_transitions],
            "total_duration_ms": round(self.total_duration_ms, 1),
            "llm_input_tokens": self.llm_input_tokens,
            "llm_output_tokens": self.llm_output_tokens,
            "num_hypotheses": self.num_hypotheses,
            "num_workers": self.num_workers,
            "num_tool_calls": len(self.tool_calls),
        }


class TrajectoryCapture:
    """Captures tool calls, node transitions, and LLM token counts during an investigation."""

    def __init__(self, session_id: str, scenario_name: str = ""):
        self._session_id = session_id
        self._scenario_name = scenario_name
        self._tool_calls: list[ToolCallRecord] = []
        self._transitions: list[NodeTransition] = []
        self._start_time = time.time()
        self._llm_input_tokens = 0
        self._llm_output_tokens = 0
        self._num_hypotheses = 0
        self._num_workers = 0
        self._last_node: str = ""

    def record_tool_call(
        self,
        tool_name: str,
        tool_args: dict,
        result: str,
        duration_ms: float,
        worker_id: str = "",
    ) -> None:
        """Record a tool invocation."""
        self._tool_calls.append(
            ToolCallRecord(
                tool_name=tool_name,
                tool_args=tool_args,
                result_preview=result[:200] if result else "",
                duration_ms=duration_ms,
                worker_id=worker_id,
                timestamp=time.time(),
            )
        )

    def record_node_transition(
        self,
        from_node: str,
        to_node: str,
        duration_ms: float = 0.0,
    ) -> None:
        """Record a graph node transition."""
        self._transitions.append(
            NodeTransition(
                from_node=from_node,
                to_node=to_node,
                timestamp=time.time(),
                duration_ms=duration_ms,
            )
        )
        self._last_node = to_node

    def record_llm_usage(self, input_tokens: int, output_tokens: int) -> None:
        """Accumulate LLM token usage."""
        self._llm_input_tokens += input_tokens
        self._llm_output_tokens += output_tokens

    def set_hypothesis_count(self, count: int) -> None:
        """Set the number of hypotheses generated."""
        self._num_hypotheses = count

    def set_worker_count(self, count: int) -> None:
        """Set the number of investigation workers spawned."""
        self._num_workers = count

    def finalize(self) -> TrajectoryRecord:
        """Finalize and return the trajectory record."""
        total_duration = (time.time() - self._start_time) * 1000
        return TrajectoryRecord(
            session_id=self._session_id,
            scenario_name=self._scenario_name,
            tool_calls=list(self._tool_calls),
            node_transitions=list(self._transitions),
            total_duration_ms=total_duration,
            llm_input_tokens=self._llm_input_tokens,
            llm_output_tokens=self._llm_output_tokens,
            num_hypotheses=self._num_hypotheses,
            num_workers=self._num_workers,
        )

    def to_dict(self) -> dict:
        """Shorthand for finalize().to_dict()."""
        return self.finalize().to_dict()
