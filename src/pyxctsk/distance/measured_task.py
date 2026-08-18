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

from ..model.task import Task
from .route_optimization import OptimizedRoute, calculate_iteratively_refined_route
from .turnpoint import TaskTurnpoint


def task_to_turnpoints(task: Task) -> list[TaskTurnpoint]:
    """Convert a task's turnpoints into the cylinders distance code works on.

    The one place that reads a goal's type off the model and turns it into
    geometry: a LINE goal becomes a zero-radius point — the line is centred on
    the goal and perpendicular to the approach, so its optimal crossing is the
    goal center — anything else stays a cylinder, and every turnpoint inherits
    the task's earth model.

    Args:
        task (Task): Task object.

    Returns:
        List[TaskTurnpoint]: List of TaskTurnpoint objects.
    """
    # Determine if there's a goal and its type
    goal_type = None
    if task.turnpoints and task.goal:
        goal_type = task.goal.type.value if task.goal.type else "CYLINDER"

    result = []
    earth_model = task.earth_model

    for i, tp in enumerate(task.turnpoints):
        # Check if this is the goal turnpoint (last one)
        if i == len(task.turnpoints) - 1:
            # This is the goal turnpoint (last one in the list)
            if goal_type == "LINE":
                # This is a goal line turnpoint
                result.append(
                    TaskTurnpoint(
                        lat=tp.waypoint.lat,
                        lon=tp.waypoint.lon,
                        radius=0,  # Goal lines have 0 radius (no cylinder)
                        goal_type=goal_type,
                        earth_model=earth_model,
                    )
                )
            else:
                # This is a regular cylinder goal (or no explicit goal type defined)
                result.append(
                    TaskTurnpoint(
                        lat=tp.waypoint.lat,
                        lon=tp.waypoint.lon,
                        radius=tp.radius,
                        goal_type=goal_type,
                        earth_model=earth_model,
                    )
                )
        else:
            # Regular turnpoint
            result.append(
                TaskTurnpoint(
                    lat=tp.waypoint.lat,
                    lon=tp.waypoint.lon,
                    radius=tp.radius,
                    earth_model=earth_model,
                )
            )

    return result


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
    def from_task(cls, task: Task, num_iterations: int | None = None) -> "MeasuredTask":
        """Measure a task, optimizing its route once.

        Args:
            task: The task to measure.
            num_iterations: Maximum number of alternating sweeps, or None for
                the default.

        Returns:
            The measured task.
        """
        turnpoints = task_to_turnpoints(task)
        return cls(
            task=task,
            turnpoints=tuple(turnpoints),
            route=calculate_iteratively_refined_route(
                turnpoints,
                num_iterations=num_iterations,
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
