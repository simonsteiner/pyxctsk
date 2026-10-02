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

from dataclasses import dataclass, field

from ..exceptions import MismatchedRouteError, TaskValidationError
from ..model.task import GoalType, Task
from ..model.validation import ValidationRule
from .earth import EarthModelLike, canonical, geodesic_distance, name_of
from .route_optimization import OptimizedRoute, calculate_iteratively_refined_route
from .turnpoint import TaskTurnpoint


def task_to_turnpoints(task: Task) -> list[TaskTurnpoint]:
    """Convert a task's turnpoints into the cylinders distance code works on.

    **The one place that reads a goal's type off the model and turns it into
    geometry**, and now genuinely the only one: a LINE goal's cylinder is built
    with ``radius=0`` — the line is centred on the goal and perpendicular to
    the approach, so its optimal crossing is the goal center, degenerate
    approach included (S7F §6.2.3.1). Anything else stays a cylinder. The
    earth model is not copied onto the cylinders: it is the task's, and it is
    handed to the optimizer once.

    ``plane_circle`` used to apply the same rule a second time, from the goal
    type carried on each cylinder, and both docstrings claimed sole ownership
    while ``center_distance._goal_radius`` picked a side in prose. Owning it
    here is what lets that module read the answer off ``turnpoints[-1].radius``
    rather than re-deriving it, and what makes ``MeasuredTask.turnpoints``
    mean what it says.

    **A negative radius is refused here**, with the issue
    :meth:`Task.validate` reports for it, because this is where a radius
    becomes a size. Reading stays lenient — the full and QR formats both carry
    one, and ``--strict`` names it — but it cannot be measured: it used to
    surface as :class:`~pyxctsk.MismatchedRouteError` saying the *route* point
    was 11.0 m outside a cylinder of radius -11, blaming the optimizer for the
    task. Every role is refused alike, a takeoff and a LINE goal included,
    whose radius the route does not touch: no role makes a negative size mean
    one, and the drawing outlines it.

    Args:
        task (Task): Task object.

    Returns:
        List[TaskTurnpoint]: One cylinder per turnpoint, in task order.

    Raises:
        TaskValidationError: If a turnpoint's radius is negative, carrying one
            :attr:`~pyxctsk.model.validation.ValidationRule.NEGATIVE_RADIUS`
            issue per such turnpoint.
    """
    negative = [
        issue
        for issue in task.validate()
        if issue.rule is ValidationRule.NEGATIVE_RADIUS
    ]
    if negative:
        raise TaskValidationError(negative)

    # ``effective_goal``, not ``goal``: the cylinders are the task as *flown*,
    # so the format's CYLINDER default applies here — and it guarantees a type
    # whenever there is a turnpoint to be the goal. ``goal`` is what the file
    # said, which is validation's question rather than geometry's.
    goal = task.effective_goal
    line_goal = goal is not None and goal.type is GoalType.LINE

    last = len(task.turnpoints) - 1
    return [
        TaskTurnpoint(
            lat=tp.waypoint.lat,
            lon=tp.waypoint.lon,
            radius=0 if (i == last and line_goal) else tp.radius,
        )
        for i, tp in enumerate(task.turnpoints)
    ]


#: How far outside its cylinder a route point may sit and still be that
#: cylinder's. ProjectionCorrection (§7.1.7) snaps each point onto the true
#: boundary, so the optimizer's own routes land within millimetres; a metre is
#: slack for rounding, and nothing like the kilometres another task's route is
#: off by.
ROUTE_TOLERANCE_M = 1.0


@dataclass(frozen=True)
class MeasuredTask:
    """A task, its cylinders, and the optimized route through them.

    Build one with :meth:`from_task` and pass it on: every module that needs a
    task *and* its route takes this rather than the two separately, which is
    what makes a mismatched pair unrepresentable.

    **Unrepresentable, not merely undocumented.** The constructor is public —
    a test rendering a drawing without the optimizer hands it a route of its
    own choosing — so the constructor checks the pair rather than trusting
    it. The cylinders are not an argument at all: they are derived from the
    task, which is the one place the LINE-goal rule is applied. The route must
    then fit them: one point per turnpoint, measured on the task's earth model,
    and each point inside its cylinder. Another task's route fails the last
    check by kilometres; it used to produce a report 46 km short, with no error.

    A measured task is a snapshot. It holds the turnpoints and route as they
    were when it was built, so build it after the task is final — the same
    contract ``TaskDrawing`` has, which now holds one.

    Attributes:
        task: The task that was measured.
        route: The optimized route through its cylinders.
        turnpoints: The cylinders derived from the task, in task order, one per
            turnpoint. A LINE goal is a zero-radius point here.

    Raises:
        MismatchedRouteError: If ``route`` was not flown through ``task``'s
            cylinders on ``task``'s earth model.
    """

    task: Task
    route: OptimizedRoute
    turnpoints: tuple[TaskTurnpoint, ...] = field(init=False)

    def __post_init__(self) -> None:
        """Derive the cylinders and check the route fits them."""
        turnpoints = tuple(task_to_turnpoints(self.task))
        _check_route_fits(turnpoints, self.route, self.task.earth_model)
        object.__setattr__(self, "turnpoints", turnpoints)

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

        Raises:
            UnmeasurableRouteError: If the task's local plane cannot represent
                its route — turnpoints a quarter of the globe from the task
                area's centre, or a cylinder larger than the earth.
        """
        return cls(
            task=task,
            route=calculate_iteratively_refined_route(
                task_to_turnpoints(task), earth_model=task.earth_model
            ),
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


def _check_route_fits(
    turnpoints: tuple[TaskTurnpoint, ...],
    route: OptimizedRoute,
    earth_model: EarthModelLike,
) -> None:
    """Refuse a route that was not flown through these cylinders.

    Args:
        turnpoints: The task's cylinders.
        route: The route claimed to be flown through them.
        earth_model: The task's earth model.

    Raises:
        MismatchedRouteError: On a point count, an earth model, or a point
            outside its cylinder that does not match.
    """
    if len(route.points) != len(turnpoints):
        raise MismatchedRouteError(
            f"route has {len(route.points)} points for {len(turnpoints)} turnpoints"
        )
    if canonical(route.earth_model) is not canonical(earth_model):
        raise MismatchedRouteError(
            f"route measured on {name_of(route.earth_model)}, "
            f"task on {name_of(earth_model)}"
        )
    for i, (point, tp) in enumerate(zip(route.points, turnpoints)):
        off = geodesic_distance(point, tp.center, earth_model) - tp.radius
        if off > ROUTE_TOLERANCE_M:
            raise MismatchedRouteError(
                f"route point {i} is {off:.1f} m outside turnpoint {i}'s cylinder"
            )
