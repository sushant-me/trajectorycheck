"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys

from .evaluator import TrajectoryEvaluator
from .rubric import Spec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="trajectorycheck",
        description="Trajectory-level evaluation for AI agents.",
    )
    ap.add_argument("--version", action="version", version="0.1.0")
    sub = ap.add_subparsers(dest="cmd")

    run = sub.add_parser("run", help="run the built-in demo agent")
    run.add_argument("--runs", type=int, default=10)

    args = ap.parse_args(argv)

    if args.cmd == "run":
        from .demo import DEMO
        ev = TrajectoryEvaluator(runs=args.runs)
        report = ev.evaluate(DEMO["agent"], DEMO["task"], DEMO["spec"])
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.passed == report.runs else 1

    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
