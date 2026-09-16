"""Evaluator: run an agent N times, score every trajectory, aggregate."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .rubric import Spec, score_trace
from .trace import Trace


@dataclass
class RunResult:
    run: int
    tags: list
    trace: Trace


@dataclass
class Report:
    task: str
    runs: int
    results: list = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if not r.tags)

    @property
    def failure_counts(self) -> dict:
        counts: dict = {}
        for r in self.results:
            for t in r.tags:
                counts[t] = counts.get(t, 0) + 1
        return counts

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "runs": self.runs,
            "passed": self.passed,
            "pass_rate": round(self.passed / self.runs, 3) if self.runs else 0.0,
            "failure_counts": self.failure_counts,
            "results": [
                {"run": r.run, "tags": r.tags, "trace": r.trace.to_dict()}
                for r in self.results
            ],
        }


class TrajectoryEvaluator:
    """Runs an agent repeatedly on a task and scores the trajectories."""

    def __init__(self, runs: int = 10):
        self.runs = runs

    def evaluate(self, agent: Callable[[str], Trace], task: str, spec: Spec) -> Report:
        report = Report(task=task, runs=self.runs)
        for i in range(self.runs):
            trace = agent(task)
            tags = score_trace(trace, spec)
            report.results.append(RunResult(run=i + 1, tags=tags, trace=trace))
        return report
