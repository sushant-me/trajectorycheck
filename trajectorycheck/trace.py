"""Trace capture primitives."""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Step:
    """One tool invocation by the agent."""
    tool: str
    args: dict
    result: Any = None
    ok: bool = True


@dataclass
class Trace:
    """A full run of the agent on one task."""
    task: str
    steps: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "steps": [
                {"tool": s.tool, "args": s.args, "result": s.result, "ok": s.ok}
                for s in self.steps
            ],
        }
