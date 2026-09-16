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

The bundled demo agent is *deliberately* broken ~45% of the time (wrong tool,
bad argument, or injected-instruction) — the evaluator flags each failure mode.
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
- A configurable CI threshold. The CLI already prints JSON and exits `1` when any
  run fails; what is missing is `--min-pass-rate` so a build can be gated on
  something other than "all runs clean".
- An injection-resistance battery — a corpus of planted instructions. Detection
  ships today (the `injected` tag, driven by `Spec.injected_instruction`); the
  corpus does not.

Cross-run **determinism scoring is already implemented** and reported per run:
`Report.non_deterministic` and `Report.distinct_behaviors` compare behaviour
signatures across runs. It appears here only because this section previously
described it as pending, after the code had shipped.

MIT.
