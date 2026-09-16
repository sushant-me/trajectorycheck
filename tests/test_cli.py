"""Tests for the CLI contract.

`run` is the only command and the one the README documents, so its exit status
is the product: everything else in this package is a library. Before this file
there were no CLI tests at all, and the CI smoke test ran `--help`, which only
proves the module imports.

The shipped demo is deliberately broken about 45% of the time, which makes any
assertion about its pass rate flaky. `demo_agent` seeds itself with
`random.randint(0, 10**6)`, so pinning that call makes the outcome exact:

    Random(0).random() == 0.844...  -> correct
    Random(1).random() == 0.134...  -> wrong_tool

Every test below pins one of those two, so none of them depend on luck.
"""

from __future__ import annotations

import json
import random

import pytest

from trajectorycheck import __version__
from trajectorycheck.cli import main

ALWAYS_PASSES = 0
ALWAYS_FAILS = 1


@pytest.fixture
def pin_demo(monkeypatch):
    """Forces every demo run to the same seed-derived outcome."""

    def _pin(seed: int) -> None:
        monkeypatch.setattr(random, "randint", lambda a, b: seed)

    return _pin


def _report(capsys) -> dict:
    return json.loads(capsys.readouterr().out)


# --------------------------------------------------------------------------
# The default gate is strict
# --------------------------------------------------------------------------

def test_a_failing_run_exits_one(pin_demo, capsys):
    pin_demo(ALWAYS_FAILS)
    assert main(["run", "--runs", "5"]) == 1


def test_a_clean_run_exits_zero(pin_demo, capsys):
    pin_demo(ALWAYS_PASSES)
    assert main(["run", "--runs", "5"]) == 0


def test_the_gate_is_closed_by_default_not_open(pin_demo, capsys):
    """A gate that succeeds unless told otherwise is one nobody notices is off."""
    pin_demo(ALWAYS_FAILS)
    report = main(["run", "--runs", "3"])
    assert report == 1


# --------------------------------------------------------------------------
# --min-pass-rate
# --------------------------------------------------------------------------

def test_min_pass_rate_zero_accepts_a_failing_run(pin_demo, capsys):
    pin_demo(ALWAYS_FAILS)
    assert main(["run", "--runs", "5", "--min-pass-rate", "0.0"]) == 0


def test_min_pass_rate_one_still_rejects_a_failing_run(pin_demo, capsys):
    pin_demo(ALWAYS_FAILS)
    assert main(["run", "--runs", "5", "--min-pass-rate", "1.0"]) == 1


def test_min_pass_rate_one_accepts_a_clean_run(pin_demo, capsys):
    pin_demo(ALWAYS_PASSES)
    assert main(["run", "--runs", "5", "--min-pass-rate", "1.0"]) == 0


@pytest.mark.parametrize("value", ["1.5", "-0.2", "abc"])
def test_an_invalid_threshold_is_a_usage_error(value, capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["run", "--min-pass-rate", value])
    assert excinfo.value.code == 2


# --------------------------------------------------------------------------
# Output and metadata
# --------------------------------------------------------------------------

def test_the_report_carries_the_documented_keys(pin_demo, capsys):
    pin_demo(ALWAYS_FAILS)
    main(["run", "--runs", "4"])
    payload = _report(capsys)
    for key in ("runs", "passed", "pass_rate", "non_deterministic",
                "distinct_behaviors", "failure_counts", "results"):
        assert key in payload, key
    assert payload["runs"] == 4
    assert len(payload["results"]) == 4


def test_min_pass_rate_does_not_change_the_report(pin_demo, capsys):
    """The threshold gates the exit status; it must not alter what is reported."""
    pin_demo(ALWAYS_FAILS)
    main(["run", "--runs", "3"])
    without = _report(capsys)
    main(["run", "--runs", "3", "--min-pass-rate", "0.0"])
    with_flag = _report(capsys)
    assert without == with_flag


def test_version_comes_from_the_package(capsys):
    """A literal here is a second source of truth that silently drifts."""
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert __version__ in capsys.readouterr().out
