"""The "distance through centres" a task board publishes — a convention, not a rule.

**FAI Sporting Code S7F 2026 does not define this number.** §7.2 defines exactly
two task distances, the optimized one and the speed section's, and neither is
this. Nor do §3's definitions or §6's task-setting rules mention it: every
occurrence of "centre" in the document is the projection centre (§7.1.2,
§7.1.6), a control zone's centre point (§6.2.1, §6.2.2, §6.2.3.1), or the
goal-line construction. Task boards nonetheless print it beside the optimized
distance, which means every implementation has invented its own reading.

The readings are far apart. On the reference corpus's widest case,
``task_pepi`` — whose *optimized* distance is 92 km — three defensible answers
sit **39.9 km** from each other:

===================================  ========
:attr:`~CenterDistanceReading.LAUNCH_TO_GOAL`         321.4 km
:attr:`~CenterDistanceReading.LAUNCH_TO_GOAL_BOUNDARY`  321.2 km
:attr:`~CenterDistanceReading.START_TO_GOAL`           281.6 km
===================================  ========

:data:`PROPOSED_READING` is what pyxctsk publishes and what it proposes as the
common one: every turnpoint centre from launch to goal, measured geodesically on
the task's declared earth model, with consecutive duplicate turnpoints
contributing their (zero-length) leg like any other. It is the reading that
matches the published values of all 22 reference tasks to within 49 m — inside
the 0.1 km these boards round to — so it is very likely what the widely used
implementations already do. That agreement rests on nothing but coincidence of
convention, which is why stating it is worth doing.

The other readings are here for one purpose: a vendor whose board disagrees can
find out in one call whether the cause is a different reading or a different
bug. See ``docs/s7f-distance-reference.md``.

Two further variations are *not* offered as readings, because the task already
answers them. The earth model is whatever the task declares (ADR 0003) — on the
FAI sphere none of these are S7F distances at all, since §4.2 admits the WGS84
ellipsoid alone. And whether a leg is measured on the ellipsoid or a sphere is a
property of that choice, not a separate convention.
"""

from enum import Enum

from ..model.task import Task
from .measured_task import task_to_turnpoints
from .speed_section import speed_section_indices
from .turnpoint import geodesic_distance


class CenterDistanceReading(str, Enum):
    """The defensible readings of "distance through centres".

    S7F picks none of them; see the module docstring.

    Attributes:
        LAUNCH_TO_GOAL (str): Every turnpoint centre, launch through goal. The
            naive polyline, and :data:`PROPOSED_READING`.
        LAUNCH_TO_GOAL_BOUNDARY (str): The same, less the goal's *effective*
            radius, so the number ends where the optimized distance ends — on
            the goal cylinder's boundary rather than at its centre. Defensible
            on the grounds that the two published numbers should measure to the
            same place. Effective, because a LINE goal is a zero-radius point
            to the optimizer, whose route therefore ends at the goal centre:
            subtracting the turnpoint's radius there would put this reading
            100 m short of its own definition on ``task_fobe_line``, and a
            whole half-line short on a wide one.
        START_TO_GOAL (str): From the SSS centre rather than from launch,
            excluding the pre-start leg the way §7.2's speed section distance
            does. Undefined — and so None — for a task with no SSS.
    """

    LAUNCH_TO_GOAL = "LAUNCH_TO_GOAL"
    LAUNCH_TO_GOAL_BOUNDARY = "LAUNCH_TO_GOAL_BOUNDARY"
    START_TO_GOAL = "START_TO_GOAL"


#: The reading pyxctsk publishes, and proposes as the common one.
PROPOSED_READING = CenterDistanceReading.LAUNCH_TO_GOAL


def _polyline(points: list[tuple[float, float]], earth_model: object) -> float:
    """Total geodesic length through these (lat, lon) points, in metres."""
    return sum(
        geodesic_distance(points[i], points[i + 1], earth_model)
        for i in range(len(points) - 1)
    )


def _goal_radius(task: Task) -> float:
    """The radius the optimized route actually ends on, in metres.

    A LINE goal is a zero-radius point to the optimizer — the line is centred
    on the goal, so its optimal crossing is the goal centre — which is stated
    once, in ``task_to_turnpoints``. Reading it from there is what keeps this
    reading measuring to the same place the optimized distance does.

    Args:
        task: The task whose goal to size.

    Returns:
        The goal cylinder's radius in metres, or 0.0 for a LINE goal.
    """
    cylinders = task_to_turnpoints(task)
    return float(cylinders[-1].radius) if cylinders else 0.0


def center_distance(
    task: Task, reading: CenterDistanceReading = PROPOSED_READING
) -> float | None:
    """Return a task's distance through turnpoint centres, in metres.

    Args:
        task: The task to measure.
        reading: Which convention to apply. Defaults to
            :data:`PROPOSED_READING`; the others exist to diagnose a
            disagreement with another implementation, not to be chosen between
            on merit.

    Returns:
        The distance in metres, or None where the reading does not apply to
        this task: fewer than two turnpoints under any reading, and no SSS
        under :attr:`~CenterDistanceReading.START_TO_GOAL`.

    Raises:
        ValueError: If ``reading`` is not a :class:`CenterDistanceReading`.
    """
    turnpoints = task.turnpoints
    if len(turnpoints) < 2:
        return None

    if reading is CenterDistanceReading.START_TO_GOAL:
        # Where the speed section starts is one question with one owner, so
        # this reading cannot obey turnpoint roles that SpeedSection ignores.
        indices = speed_section_indices(task)
        if indices is None or len(turnpoints) - indices[0] < 2:
            return None
        turnpoints = turnpoints[indices[0] :]

    total = _polyline(
        [(tp.waypoint.lat, tp.waypoint.lon) for tp in turnpoints], task.earth_model
    )

    if reading is CenterDistanceReading.LAUNCH_TO_GOAL_BOUNDARY:
        return total - _goal_radius(task)
    if reading in (
        CenterDistanceReading.LAUNCH_TO_GOAL,
        CenterDistanceReading.START_TO_GOAL,
    ):
        return total
    raise ValueError(f"not a center-distance reading: {reading!r}")


def center_distance_readings(task: Task) -> dict[str, float | None]:
    """Return every reading of a task's centre distance, keyed by name.

    The diagnostic the module exists for: hand a vendor whose board disagrees
    this dictionary and the cause is either in it or it is a bug.

    Args:
        task: The task to measure.

    Returns:
        One entry per :class:`CenterDistanceReading`, in metres, with None for
        any that does not apply to this task.
    """
    return {
        reading.value: center_distance(task, reading)
        for reading in CenterDistanceReading
    }
