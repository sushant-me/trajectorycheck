# trajectorycheck

[![CI](https://github.com/sushant-me/trajectorycheck/actions/workflows/ci.yml/badge.svg)](https://github.com/sushant-me/trajectorycheck/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%20%7C%203.11%20%7C%203.13-blue)](https://github.com/sushant-me/trajectorycheck/actions/workflows/ci.yml)

Trajectory-level evaluation for AI agents. It grades **behavior** — the tools an
agent calls, the arguments it passes, the side effects it causes, and whether it
behaves the same across runs — instead of just the final answer.

## Why

In 2026 the AI industry's most-cited unsolved problem is that **agent evaluation is
broken**: a single conversation can "look perfect and still be broken" ([VentureBeat,
from LangChain / Conviva / CoreWeave leaders](https://venturebeat.com/data/a-single-ai-agent-conversation-can-look-perfect-and-still-be-broken-leaders-from-langchain-conviva-and-coreweave-said-at-vb-transform-2026)).
Answer-level evals miss the failures that matter in production: wrong tool calls,
bad arguments, unauthorized side effects, non-determinism, and prompt-injection
susceptibility. `trajectorycheck` scores those directly.

## What it scores

Failure taxonomy (one tag per detected problem):

- `wrong_tool` — called a tool outside the allowed/expected set
- `bad_arg` — passed an argument outside the allowed values
- `side_effect` — invoked a dangerous tool (transfer/send/write/execute/…) not explicitly authorised
- `no_action` — took no action at all
- `bad_result` — a step failed
- `injected` — followed a planted prompt-injection instruction

On top of the per-run tags, the report scores **behavioural consistency** across
runs: `non_deterministic` and `distinct_behaviors` compare a canonical signature
of every run's tool calls and arguments, so an agent that passes on average while
behaving differently each time is visible rather than averaged away.

## Usage

```python
from trajectorycheck import TrajectoryEvaluator
from trajectorycheck.rubric import Spec

evaluator = TrajectoryEvaluator(runs=10)
report = evaluator.evaluate(your_agent, "send a support message", spec)
print(report.to_dict())          # pass_rate, failure_counts, non_deterministic,
                                 # distinct_behaviors, per-run tags
```

An agent is just a function `agent(task: str) -> Trace` that returns the steps
`(tool, args, result)` it took. Works with any agent framework — write a thin
adapter that maps your framework's tool calls to `Step`s.

## Demo

```bash
pip install -e .
trajectorycheck run --runs 100
```

The bundled demo agent is *deliberately* broken ~45% of the time, across all
five failure modes the taxonomy can report from it — wrong tool, bad argument,
an unauthorised side effect via a planted injection, no action at all, and a
step that failed. A test pins that every tag fires, because one that no demo
reaches is one that can rot unnoticed.

**That command exits `1`, and that is correct.** The exit status is a gate, and
the gate is strict by default: every run must pass. Because the demo is designed
to fail, running it is expected to fail. Say what tolerance you actually want
with `--min-pass-rate`:

```bash
trajectorycheck run --runs 100 --min-pass-rate 0.4
```

The demo's true pass rate is about 0.55, so a threshold below it will hold: 0.4
is stable across runs, while 0.5 sits close enough to the mean that it flips
depending on the draw. (Thresholds that flip are worth noticing — a gate whose
verdict depends on luck is not measuring the thing you think it is.)

| exit | meaning |
|---|---|
| `0` | the run cleared the threshold |
| `1` | the run did not clear the threshold |
| `2` | usage error, e.g. an out-of-range `--min-pass-rate` |

The default is strict on purpose. A gate that succeeds unless you tell it
otherwise is one nobody notices is switched off, and this package exists to
catch things that look fine.

Run the tests with `python -m pytest tests/`.

## Adapters (real agents)

`trajectorycheck.adapters.make_openai_agent(client, model, tool_executor, tools=...)`
wraps an OpenAI function-calling loop into a trajectory-capturing agent — pass any
OpenAI SDK client or OpenAI-compatible endpoint (no hard dependency on `openai`).

```python
from trajectorycheck.adapters import make_openai_agent
agent = make_openai_agent(openai_client, "gpt-4o", {"send": send_fn}, tools=tool_schemas)
report = TrajectoryEvaluator(runs=10).evaluate(agent, "send a support message", spec)
```

## Roadmap

- Adapters for LangChain and other tool-calling frameworks. The OpenAI
  function-calling adapter is not future work — it is implemented above.
- An injection-resistance battery — a corpus of planted instructions. Detection
  ships today (the `injected` tag, driven by `Spec.injected_instruction`); the
  corpus does not.

Two items that used to be listed here have shipped. Cross-run **determinism
scoring** is implemented and reported per run (`Report.non_deterministic`,
`Report.distinct_behaviors`), and a **configurable CI threshold** now exists as
`--min-pass-rate`. Both were described as pending after the code had moved on;
this section is not a reliable source of truth about what is missing, and the
exit-code table above is.

MIT.
