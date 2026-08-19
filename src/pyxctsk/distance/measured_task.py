"""A task beside the optimized route flown for it.

Every number S7F §7 defines is measured along one route, and that route belongs
to one task. Nothing used to bind the two: "the optimized route of this task"
was a two-step incantation — convert the turnpoints, then optimize them — and
each caller wrote it out, so the pairing survived only as a sentence in two
docstrings that no caller and no type checker could check. Handing
``task_distances_from_route`` a task and *another* task's route returned a
fully formed report 12.8 km out, reporting 36.9% savings, with no error; the
reverse direction filled the cumulative column with a silent tail of zeros.

:class:`MeasuredTask` is that pair as one value, so the mismatch stops being
representable rather than staying documented. It holds three things and derives
the rest:

- the ``Task``, for names, roles and radii,
- the ``TaskTurnpoint`` cylinders derived from it — which is where a LINE goal
  becomes a zero-radius point, the one place that rule is applied,
- the ``OptimizedRoute`` through those cylinders.

It deliberately does **not** hold the speed section, the goal line or the
centre distance. The speed section optimizes its own separate launch-to-ESS
route (§7.2), the goal line is only oriented against this one, and the centre
distance touches no route at all — each is its own module, and each takes a
measured task rather than being folded into it. That keeps the edges running
one way: ``goal_line`` and ``speed_section`` depend on this module, and it
depends on neither.
"""

from dataclasses import dataclass

from ..model.task import GoalType, Task
from .route_optimization import OptimizedRoute, calculate_iteratively_refined_route
from .turnpoint import TaskTurnpoint


def task_to_turnpoints(task: Task) -> list[TaskTurnpoint]:
    """Convert a task's turnpoints into the cylinders distance code works on.

    **The one place that reads a goal's type off the model and turns it into
    geometry**, and now genuinely the only one: a LINE goal's cylinder is built
    with ``radius=0`` — the line is centred on the goal and perpendicular to
    the approach, so its optimal crossing is the goal center, degenerate
    approach included (S7F §6.2.3.1). Anything else stays a cylinder, and every
    turnpoint inherits the task's earth model.

    ``plane_circle`` used to apply the same rule a second time, from the goal
    type carried on each cylinder, and both docstrings claimed sole ownership
    while ``center_distance._goal_radius`` picked a side in prose. Owning it
    here is what lets that module read the answer off ``turnpoints[-1].radius``
    rather than re-deriving it, and what makes ``MeasuredTask.turnpoints``
    mean what it says.

    Args:
        task (Task): Task object.

    Returns:
        List[TaskTurnpoint]: One cylinder per turnpoint, in task order.
    """
    # ``effective_goal``, not ``goal``: the cylinders are the task as *flown*,
    # so the format's CYLINDER default applies here. ``goal`` is what the file
    # said, which is validation's question rather than geometry's.
    goal = task.effective_goal
    # Parenthesized rather than left to precedence. A conditional expression
    # binds less tightly than ``or``, so the unparenthesized form means the
    # same thing — but it reads as though ``goal.type`` were evaluated before
    # the ``if goal`` guard, and a reviewer of this line read it that way.
    goal_type = (goal.type or GoalType.CYLINDER) if goal else None

    last = len(task.turnpoints) - 1
    return [
        TaskTurnpoint(
            lat=tp.waypoint.lat,
            lon=tp.waypoint.lon,
            radius=0 if (i == last and goal_type is GoalType.LINE) else tp.radius,
            earth_model=task.earth_model,
        )
        for i, tp in enumerate(task.turnpoints)
    ]


@dataclass(frozen=True)
class MeasuredTask:
    """A task, its cylinders, and the optimized route through them.

    Build one with :meth:`from_task` and pass it on: every module that needs a
    task *and* its route takes this rather than the two separately, which is
    what makes a mismatched pair unrepresentable.

    A measured task is a snapshot. It holds the turnpoints and route as they
    were when it was built, so build it after the task is final — the same
    contract ``TaskDrawing`` has, which now holds one.

    Attributes:
        task: The task that was measured.
        turnpoints: The cylinders derived from it, in task order, one per
            turnpoint. A LINE goal is a zero-radius point here.
        route: The optimized route through those cylinders.
    """

    task: Task
    turnpoints: tuple[TaskTurnpoint, ...]
    route: OptimizedRoute

    @classmethod
    def from_task(cls, task: Task) -> "MeasuredTask":
        """Measure a task, optimizing its route once.

        The sweep limit is deliberately not a parameter here. It is a knob on
        the optimizer — reach for ``calculate_iteratively_refined_route`` if
        you need it — and threading it up through every layer that merely
        forwards it is the shape ADR 0004 removed for ``angle_step`` and
        ``beam_width``. Nothing but one convergence test has ever set it.

        Args:
            task: The task to measure.

        Returns:
            The measured task.
        """
        turnpoints = task_to_turnpoints(task)
        return cls(
            task=task,
            turnpoints=tuple(turnpoints),
            route=calculate_iteratively_refined_route(turnpoints),
        )

    @property
    def total_m(self) -> float:
        """The task's optimized distance in meters — S7F §7.2's task distance."""
        return self.route.total_m

    def cumulative_m(self) -> list[float]:
        """Distance along the route to each turnpoint, in meters.

        A projection of :attr:`route`, so turnpoint *i*'s entry is by
        construction a prefix of the total. Re-optimizing ``turnpoints[:i+1]``
        gives a different number — the optimizer treats the last circle it is
        handed as the finish — which is the bug this value exists to prevent.

        Returns:
            Cumulative distances in meters, one per turnpoint, starting at 0.0.
        """
        return self.route.cumulative_m()
