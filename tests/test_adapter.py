"""Test the OpenAI adapter with a stubbed client (no API key needed)."""

import json

from trajectorycheck.adapters import make_openai_agent
from trajectorycheck.evaluator import TrajectoryEvaluator
from trajectorycheck.rubric import Spec, score_trace
from trajectorycheck.trace import Step, Trace


class _Msg:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class _TC:
    def __init__(self, id, name, args):
        self.id = id
        self.function = type("F", (), {"name": name, "arguments": json.dumps(args)})()


class _Choice:
    def __init__(self, msg):
        self.message = msg


class _Resp:
    def __init__(self, msg):
        self.choices = [_Choice(msg)]


class _Client:
    """Stateless stub: always returns the same tool call (max_turns bounds the loop)."""
    def __init__(self, tool_name, tool_args):
        self.tool_name = tool_name
        self.tool_args = tool_args
        # make client.chat.completions.create(...) resolve to self.create(...)
        self.chat = self
        self.chat.completions = self

    def create(self, **kwargs):
        return _Resp(_Msg(tool_calls=[_TC("tc", self.tool_name, self.tool_args)]))


def _executor():
    return {"send": lambda to, note="": f"sent to {to}"}


def test_adapter_records_clean_trace():
    client = _Client("send", {"to": "support@bank"})
    agent = make_openai_agent(client, "gpt-test", _executor())
    spec = Spec(allowed_tools={"send"}, expected_tool="send",
                allowed_args={"send": {"to": {"support@bank"}}},
                dangerous_allowed={"send"})
    report = TrajectoryEvaluator(runs=3).evaluate(agent, "send a message", spec)
    assert report.passed == 3
    assert not report.non_deterministic


def test_adapter_flags_wrong_tool():
    client = _Client("lookup", {"q": "x"})
    agent = make_openai_agent(client, "gpt-test", _executor())
    spec = Spec(allowed_tools={"send"}, expected_tool="send")
    report = TrajectoryEvaluator(runs=2).evaluate(agent, "send a message", spec)
    assert report.failure_counts.get("wrong_tool", 0) == 2


def test_adapter_flags_bad_arg():
    client = _Client("send", {"to": "admin@bank"})
    agent = make_openai_agent(client, "gpt-test", _executor())
    spec = Spec(allowed_tools={"send"},
                allowed_args={"send": {"to": {"support@bank"}}})
    report = TrajectoryEvaluator(runs=2).evaluate(agent, "send a message", spec)
    assert report.failure_counts.get("bad_arg", 0) == 2


# --- tool results that are not JSON-serialisable ---------------------------
#
# The executor above returns an f-string, so nothing in this file exercised a
# tool returning an ordinary object. That is the gap: `json.dumps(result)` sits
# outside the tool's try/except, so a `datetime` or a set raised `TypeError` out
# of `agent(task)` and aborted the whole evaluation.

class _RaisingFreeClient(_Client):
    """Same stub, but the loop ends after the tool call so one step is recorded."""
    def __init__(self, tool_name, tool_args):
        super().__init__(tool_name, tool_args)
        self._calls = 0

    def create(self, **kwargs):
        self._calls += 1
        if self._calls == 1:
            return _Resp(_Msg(tool_calls=[_TC("tc", self.tool_name, self.tool_args)]))
        return _Resp(_Msg(content="done"))


def _agent_returning(value):
    return make_openai_agent(
        _RaisingFreeClient("emit", {}), "gpt-test", {"emit": lambda: value}
    )


def test_non_serialisable_tool_result_does_not_abort_the_run():
    import datetime

    trace = _agent_returning(datetime.datetime(2026, 9, 17, 2, 38))("t")
    assert [s.tool for s in trace.steps] == ["emit"]
    assert trace.steps[0].ok is True


def test_a_set_and_a_bare_object_are_also_survivable():
    assert _agent_returning({1, 2, 3})("t").steps[0].ok is True
    assert _agent_returning(object())("t").steps[0].ok is True


def test_serialisable_results_are_unchanged():
    """The fallback must not alter the common path."""
    from trajectorycheck.adapters import tool_result_content

    assert tool_result_content({"a": 1}) == json.dumps({"a": 1})
    assert tool_result_content("x") == json.dumps("x")
    assert tool_result_content(3) == "3"


def test_a_failing_tool_is_still_marked_bad():
    """`ok=False` belongs to the tool failing, not to serialisation."""
    def boom():
        raise ValueError("nope")

    agent = make_openai_agent(
        _RaisingFreeClient("emit", {}), "gpt-test", {"emit": boom}
    )
    trace = agent("t")
    assert trace.steps[0].ok is False
    assert "nope" in str(trace.steps[0].result)


# --- tool arguments are routinely lists and objects -------------------------
#
# Signatures are collected into a set, so a list- or dict-valued argument made
# the tuple unhashable and `non_deterministic` raised TypeError. The same value
# broke the allowed-argument membership test, which needs a hashable operand.
# Both are ordinary: any JSON-schema tool takes arrays.

def test_determinism_survives_list_and_object_arguments():
    for arg in (["a@b.c", "d@e.f"], {"kind": "urgent", "cc": ["x@y.z"]}, [1, 2, 3]):
        def agent(task, arg=arg):
            return Trace(task=task, steps=[Step("send", {"to": arg}, "sent")])

        spec = Spec(allowed_tools={"send"}, dangerous_allowed={"send"})
        report = TrajectoryEvaluator(runs=3).evaluate(agent, "send", spec)
        assert report.non_deterministic is False
        assert report.distinct_behaviors == 1
        assert report.to_dict()["runs"] == 3


def test_allowed_argument_check_survives_a_list_value():
    """The membership test must not raise when the actual value is unhashable."""
    t = Trace(task="x", steps=[Step("send", {"to": ["a@b.c"]}, "ok")])
    spec = Spec(allowed_tools={"send"},
                allowed_args={"send": {"to": {"a@b.c"}}},
                dangerous_allowed={"send"})
    # A list is not equal to the allowed scalar, so it is a bad argument - and
    # the scorer has to be able to say so rather than raise.
    assert "bad_arg" in score_trace(t, spec)


def test_determinism_still_detects_a_real_difference():
    """Guarding the crash must not flatten the signature."""
    calls = iter([{"to": "a@b.c"}, {"to": "d@e.f"}])

    def agent(task):
        arg = next(calls)
        return Trace(task=task, steps=[Step("send", arg, "sent")])

    spec = Spec(allowed_tools={"send"}, dangerous_allowed={"send"})
    report = TrajectoryEvaluator(runs=2).evaluate(agent, "send", spec)
    assert report.non_deterministic is True
    assert report.distinct_behaviors == 2
