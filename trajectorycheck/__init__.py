"""trajectorycheck — trajectory-level evaluation for AI agents.

Grades *behavior* (tool calls, arguments, side effects, determinism) rather
than the final answer, to catch the "looks perfect but is broken" failures
that answer-level evals miss.

The documented entry point is the top-level import:

    from trajectorycheck import TrajectoryEvaluator
    from trajectorycheck.rubric import Spec

That first line raised ImportError until 0.1.2: this module exported nothing,
so the README's headline example failed on its first statement and the classes
were reachable only by their defining module paths.
"""

from .evaluator import Report, TrajectoryEvaluator
from .rubric import Spec
from .trace import Step, Trace

__version__ = "0.1.2"

__all__ = [
    "Report",
    "Spec",
    "Step",
    "Trace",
    "TrajectoryEvaluator",
    "__version__",
]
