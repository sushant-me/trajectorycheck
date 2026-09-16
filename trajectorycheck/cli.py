"""Command-line entry point.

Exit status is a contract, so it is stated rather than inferred:

    0   the run cleared the threshold
    1   the run did not clear the threshold
    2   usage error (argparse), e.g. an out-of-range --min-pass-rate

The default threshold is strict — every run must pass. That is deliberate: a
gate that succeeds unless told otherwise is one nobody notices is off. The
bundled demo is broken on purpose, so it fails under the default and is expected
to; pass ``--min-pass-rate`` to say what tolerance you actually want.
"""

from __future__ import annotations

import argparse
import json

from . import __version__
from .evaluator import TrajectoryEvaluator

EXIT_OK = 0
EXIT_BELOW_THRESHOLD = 1


def _fraction(text: str) -> float:
    """Parses a pass-rate threshold in [0, 1]."""
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a number") from None
    if not 0.0 <= value <= 1.0:
        raise argparse.ArgumentTypeError(
            f"{value} is out of range: a pass rate is a fraction between 0 and 1"
        )
    return value


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="trajectorycheck",
        description="Trajectory-level evaluation for AI agents.",
    )
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd")

    run = sub.add_parser(
        "run",
        help="evaluate the built-in demo agent and report the result",
        description=(
            "Runs the bundled demo agent, which is deliberately broken a fraction "
            "of the time so that every failure mode is exercised."
        ),
    )
    run.add_argument("--runs", type=int, default=10)
    run.add_argument(
        "--min-pass-rate",
        type=_fraction,
        default=None,
        metavar="FRACTION",
        help=(
            "succeed when the pass rate is at least this fraction (0-1); "
            "default is to require every run to pass"
        ),
    )
    return ap


def main(argv=None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)

    if args.cmd == "run":
        from .demo import DEMO

        report = TrajectoryEvaluator(runs=args.runs).evaluate(
            DEMO["agent"], DEMO["task"], DEMO["spec"]
        )
        print(json.dumps(report.to_dict(), indent=2))

        if args.min_pass_rate is None:
            cleared = report.passed == report.runs
        else:
            rate = report.passed / report.runs if report.runs else 0.0
            cleared = rate >= args.min_pass_rate
        return EXIT_OK if cleared else EXIT_BELOW_THRESHOLD

    ap.print_help()
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
