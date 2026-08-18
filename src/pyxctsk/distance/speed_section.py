"""The speed section's distance, per FAI Sporting Code S7F 2026 §7.2.

§7.2 defines two task distances, not one. The task distance is the optimized
path from launch to goal; the **speed section distance** is *"the distances of
the optimized path from launch to ESS, minus the distance of the pre-start
portion"*. It is what a pilot's time is measured over.

**It is not a prefix of the task route**, and that is the whole reason this
module exists rather than a method on :class:`~pyxctsk.distance.OptimizedRoute`.
The optimizer treats the last circle it is handed as the finish, so a route
ending at the ESS bends toward it instead of passing through on the way to
goal. S7F says so explicitly by optimizing a second, separate ``taskToESS``
route — and the same trap already cost this library a 5.09 km error when
cumulative distances were re-derived by optimizing truncated tasks.

Both of §7.2's numbers are then projections of that one route, which is what
:class:`SpeedSection` holds: the ESS distance is its total, the pre-start
distance is how far along it the start sits, and the speed section is the
difference.

S7F's own formulation ends ``taskToESS`` at the ESS *centre* and subtracts
``endOfSpeedSection.radius``; touching the boundary, as the optimizer does,
is the same number by construction — the boundary point is placed at exactly
``radius`` along the geodesic from the centre toward the previous point. The
task-distance formula has the same shape, and the two agree to 1.1 mm across
the reference corpus.
"""

from dataclasses import dataclass

from ..model.task import Task, TaskType, TurnpointType
from .measured_task import MeasuredTask, task_to_turnpoints
from .route_optimization import OptimizedRoute, calculate_iteratively_refined_route
from .turnpoint import TaskTurnpoint


def _role_index(task: Task, role: TurnpointType) -> int | None:
    """Return the index of the first turnpoint with this role, or None.

    Args:
        task: The task to search.
        role: The turnpoint type to find.

    Returns:
        The index, or None if no turnpoint carries the role.
    """
    for i, turnpoint in enumerate(task.turnpoints):
        if turnpoint.type == role:
            return i
    return None


@dataclass(frozen=True)
class SpeedSection:
    """A task's speed section and the route it is measured along (§7.2).

    Attributes:
        route: The optimized route from launch to ESS — S7F's ``taskToESS``,
            a *separate* optimization from the task's own route rather than a
            prefix of it.
        start_index: Where the SSS sits in :attr:`route`, so the pre-start
            portion can be split off.
    """

    route: OptimizedRoute
    start_index: int

    @classmethod
    def from_measured_task(cls, measured: MeasuredTask) -> "SpeedSection | None":
        """Build the speed section for an already-measured task.

        Reuses the measured task's cylinders — the LINE-goal rule is applied
        once, there — but not its route: §7.2's ``taskToESS`` is a separate
        optimization, which is the whole point of this module.

        Args:
            measured: The task and the route measured for it.

        Returns:
            A SpeedSection, or None for the same reasons :meth:`from_task`
            returns None.
        """
        return cls._from_turnpoints(measured.task, list(measured.turnpoints))

    @classmethod
    def from_task(cls, task: Task) -> "SpeedSection | None":
        """Build the speed section for a task.

        Args:
            task: The task to measure.

        Returns:
            A SpeedSection, or None if the task has no speed section to
            measure — an XC/Waypoints task, one missing an SSS or an ESS, or
            one whose ESS precedes its SSS. The last is a task
            :meth:`~pyxctsk.Task.validate` already reports as invalid
            (``SSS_AFTER_ESS``); there is no honest number to return for it.
        """
        # The *task type* decides whether there is a speed section at all, not
        # the turnpoint roles. An XC/Waypoints task is "a simple route from
        # waypoints without cylinders", and ``model/validation.py`` already
        # exempts it from the SSS/ESS rules on exactly that ground — so a
        # waypoints task carrying stray ``SSS``/``ESS`` annotations has no
        # speed section however they are arranged, and measuring one would let
        # unchecked annotations override the type.
        return cls._from_turnpoints(task, task_to_turnpoints(task))

    @classmethod
    def _from_turnpoints(
        cls, task: Task, task_turnpoints: list[TaskTurnpoint]
    ) -> "SpeedSection | None":
        """Find the speed section in a task whose cylinders are already derived."""
        if task.task_type == TaskType.WAYPOINTS:
            return None

        start = _role_index(task, TurnpointType.SSS)
        end = _role_index(task, TurnpointType.ESS)
        if start is None or end is None or start > end:
            return None

        # Slicing the task's own turnpoints keeps the goal handling: when the
        # ESS *is* the goal, the last entry carries the goal's type, so a LINE
        # goal stays the zero-radius point at its centre rather than becoming
        # a cylinder of half the line's length.
        turnpoints = task_turnpoints[: end + 1]
        if len(turnpoints) < 2:
            return None

        return cls(
            route=calculate_iteratively_refined_route(turnpoints),
            start_index=start,
        )

    @property
    def to_ess_m(self) -> float:
        """Optimized distance from launch to the ESS, in meters."""
        return self.route.total_m

    @property
    def pre_start_m(self) -> float:
        """Distance from launch to the start of the speed section, in meters."""
        return self.route.cumulative_m()[self.start_index]

    @property
    def distance_m(self) -> float:
        """The speed section distance in meters — §7.2's ``distanceSpeedSection``."""
        return self.to_ess_m - self.pre_start_m
