"""Test the OpenAI adapter with a stubbed client (no API key needed)."""

import json

from trajectorycheck.adapters import make_openai_agent
from trajectorycheck.evaluator import TrajectoryEvaluator
from trajectorycheck.rubric import Spec


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
