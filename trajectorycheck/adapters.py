"""Adapters that instrument real agent frameworks and record trajectories.

The adapter contract is dependency-free: you pass your own client, so it works
with the OpenAI SDK or any OpenAI-compatible endpoint (no hard dependency).
"""

from __future__ import annotations

import json
from typing import Any, Callable, Optional

from .trace import Step, Trace

ToolExecutor = dict[str, Callable[..., Any]]


def tool_result_content(result: Any) -> str:
    """Serialise a tool result for the wire without ever raising.

    The chat API only accepts a string for a tool message, but a tool may return
    anything - a `datetime`, a dataclass, a set, an ORM row, a client object.
    `json.dumps` raises `TypeError` on all of those, and that exception used to
    escape `agent(task)` and abort the whole evaluation.

    An evaluator exists to observe an agent and score what it did; it must not be
    the thing that crashes on an ordinary return value. Falling back to `str`
    keeps the loop alive and keeps the trajectory scoreable.
    """
    try:
        return json.dumps(result)
    except (TypeError, ValueError):
        return json.dumps(str(result))


def make_openai_agent(
    client,
    model: str,
    tool_executor: ToolExecutor,
    tools: Optional[list] = None,
    max_turns: int = 10,
) -> Callable[[str], Trace]:
    """Wrap an OpenAI function-calling loop into a trajectory-capturing agent.

    `client` is anything with `client.chat.completions.create(**kwargs)` returning
    an object with `choices[0].message` (`.content`, `.tool_calls`). `tools` is the
    OpenAI tool-schema list (optional; omit if the client is already configured).
    """
    def agent(task: str) -> Trace:
        trace = Trace(task=task)
        messages: list = [{"role": "user", "content": task}]
        for _ in range(max_turns):
            kwargs: dict = {"model": model, "messages": messages}
            if tools:
                kwargs["tools"] = tools
            resp = client.chat.completions.create(**kwargs)
            msg = resp.choices[0].message
            messages.append(msg)
            if not getattr(msg, "tool_calls", None):
                break
            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {"_raw": tc.function.arguments}
                fn = tool_executor.get(name)
                if fn is None:
                    trace.steps.append(Step(name, args, None, ok=False))
                    messages.append({
                        "role": "tool", "tool_call_id": tc.id,
                        "content": json.dumps({"error": "unknown tool"}),
                    })
                    continue
                try:
                    result = fn(**args)
                    ok = True
                except Exception as exc:  # tool raised -> bad_result
                    result = str(exc)
                    ok = False
                trace.steps.append(Step(name, args, result, ok=ok))
                messages.append({
                    "role": "tool", "tool_call_id": tc.id,
                    "content": tool_result_content(result),
                })
        return trace

    return agent
