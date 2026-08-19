"""Goal line geometry for LINE type goals.

This module owns everything about a task's goal line: how long it is, where
its endpoints sit, and the shape of its semicircular control zone. The
:class:`GoalLine` class is the single deep module that callers (GeoJSON and
KML generation, distance calculation) go through, so the goal-line rules live
in exactly one place.

:meth:`GoalLine.from_task` is the only answer to *"does this task have a goal
line?"*, and everything else derives from it — including which turnpoints a
writer should draw, since the goal line's presence is the whole reason to drop
the last one. Asking that question a second way is how the two answers came to
disagree: a LINE goal whose previous turnpoint sits at the same coordinates has
no approach direction and so no goal line, but a separate predicate dropped the
turnpoint anyway and the goal vanished from the output entirely.

**Which way the line faces is the one thing S7F changed here**, so it is the
one thing this module makes a parameter: :class:`GoalLineOrientation` picks
between the 2025-and-later rule (perpendicular to the *optimized route point*
on the last control zone before goal) and the 2024 one (perpendicular to that
turnpoint's *centre*). Everything else — the length, the perpendicular, the
semicircle behind it — is identical in both editions and is not configurable.

Orientation is where this module gained a dependency on the optimizer: under
the current rule a goal line cannot be derived from the task alone. That is why
:meth:`GoalLine.from_measured_task` is the primary constructor — a caller
holding a :class:`~pyxctsk.distance.MeasuredTask` passes it rather than paying
for a second optimization, and cannot pass a route belonging to a *different*
task, which the optional ``route`` argument this replaced could not prevent.
:meth:`GoalLine.from_task` remains for a caller holding only a task, and under
the 2024 orientation it still optimizes nothing at all.

Everything else here is :class:`GoalLine`'s own implementation. Callers use the
object: ``length``, ``approach_azimuth()``, ``endpoints()`` and
``control_zone()``. There is deliberately no tuple-shaped accessor beside them
— the writers used to unpack a positional 4-tuple that carried exactly those
answers, and the endpoint math itself used to be a free function taking six
positional floats that the method built by unpacking its own two points.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from ..model.task import GoalType, Task, Turnpoint
from .earth import EarthModelLike, geod_for_earth_model
from .measured_task import MeasuredTask

# Constants for goal line visualization
GOAL_LINE_NUM_POINTS = 20
COORD_TOLERANCE = 1e-9


class GoalLineOrientation(str, Enum):
    """Which edition of S7F §6.2.3.1 decides where the goal line points.

    The rule changed in the 2025 edition, whose change list records it as
    *"Orientation of Goal Line: Follow optimized route, instead of turnpoint
    centres"*. Both readings are kept because they answer different questions:
    one is the current scoring code, the other is what a task drawn before
    2025 — and, as far as we know, what XCTrack itself — shows.

    Attributes:
        OPTIMIZED_ROUTE (str): S7F 2025 and later. The approach comes from the
            optimized route point on the last control zone before goal, the
            point the task-distance calculation already found.
        TURNPOINT_CENTERS (str): S7F 2024. The approach comes from the centre
            of *"the last turn point that is different from the goal line
            centre"*.
    """

    OPTIMIZED_ROUTE = "OPTIMIZED_ROUTE"
    TURNPOINT_CENTERS = "TURNPOINT_CENTERS"


#: What :meth:`GoalLine.from_task` uses when the caller does not say. The 2026
#: edition is what the rest of ``distance/`` implements, so this is the one
#: that keeps a task's geometry and its distances on the same edition.
DEFAULT_ORIENTATION = GoalLineOrientation.OPTIMIZED_ROUTE


def goal_line_length_from_turnpoints(
    turnpoints: Sequence[Turnpoint],
) -> float | None:
    """Return the goal-line length implied by the turnpoints.

    The single source of the rule that a goal line's total length is twice
    the last turnpoint's radius (the radius represents half of the line).

    Args:
        turnpoints: The task's turnpoints.

    Returns:
        The length in meters, or None if there are no turnpoints.
    """
    if not turnpoints:
        return None
    return float(turnpoints[-1].radius * 2)


def _last_distinct_point(
    points: "list[tuple[float, float]]", goal_center: tuple[float, float]
) -> tuple[float, float] | None:
    """Return the last of ``points`` that does not sit on the goal center.

    A goal line needs an approach direction, and a candidate coincident with
    the goal gives none. Both orientation rules need this same walk-backwards
    — one over turnpoint centers, one over optimized route points — so it is
    written once over bare coordinates rather than twice over the objects
    that carry them.

    Args:
        points: (lat, lon) candidates in task order, excluding the goal.
        goal_center: (lat, lon) of the goal.

    Returns:
        The last (lat, lon) distinct from the goal, or None if every candidate
        coincides with it.
    """
    for lat, lon in reversed(points):
        # Tolerance rather than equality: these arrive from a projection round
        # trip on the optimized-route path, so they are never bit-exact.
        if (
            abs(lat - goal_center[0]) > COORD_TOLERANCE
            or abs(lon - goal_center[1]) > COORD_TOLERANCE
        ):
            return (lat, lon)
    return None


def _semicircle_arc(
    center: tuple[float, float],
    forward_azimuth: float,
    radius: float,
    earth_model: EarthModelLike = None,
) -> list[tuple[float, float]]:
    """The control zone's boundary: 180° centred on the approach direction.

    A uniform sweep from ``forward_azimuth - 90`` to ``forward_azimuth + 90``,
    which is the front half of the circle — the side a pilot crosses from.

    It used to take a start, an end *and* a through azimuth and interpolate the
    two halves separately, each normalizing its own angle difference into
    (-180, 180]. Its one caller has only ever passed those three azimuths, for
    which both halves reduce to this single step; the generality bought nothing
    and was what made the function long enough to need two branches. Old
    against new over 300 randomized (lat, lon, azimuth, radius) combinations
    agrees to 7e-15° — 1e-9 m, which is float-ordering noise. Across
    the reference corpus's GeoJSON, 3 of 1748 floats move at all.

    Args:
        center: (lat, lon) of the goal.
        forward_azimuth: The approach direction, in degrees.
        radius: The control zone's radius in meters.
        earth_model: Earth model selector (``EarthModel`` member, its string
            value, or None for WGS84).

    Returns:
        ``GOAL_LINE_NUM_POINTS + 1`` (lon, lat) points, endpoint included.
    """
    geod = geod_for_earth_model(earth_model)
    lat, lon = center
    return [
        geod.fwd(
            lon,
            lat,
            (forward_azimuth - 90 + 180 * i / GOAL_LINE_NUM_POINTS) % 360,
            radius,
        )[:2]
        for i in range(GOAL_LINE_NUM_POINTS + 1)
    ]


@dataclass(frozen=True)
class GoalLine:
    """A task's goal line — the single source of goal-line geometry.

    A goal line is a finite segment centred on the goal (the last turnpoint),
    perpendicular to the final approach direction, with a semicircular control
    zone in front of it. This class concentrates all knowledge of that
    geometry behind a small interface so visualization and distance code need
    not re-derive it.

    Attributes:
        center: (lat, lon) of the goal (last turnpoint).
        approach_from: (lat, lon) of the point the line is oriented against —
            per :class:`GoalLineOrientation`, either the optimized route point
            on the last control zone before goal or that turnpoint's centre.
            The line is perpendicular to the direction from here to
            :attr:`center`, so this is the whole of what "which way does the
            goal face" depends on.
        length: Total goal-line length in meters.
        earth_model: The model the geometry is measured on (an ``EarthModel``
            member, its string value, or None for WGS84), per ADR 0003. A task
            declaring the FAI sphere used to get its route measured on the
            sphere and its goal line on the ellipsoid, in one document.
    """

    center: tuple[float, float]
    approach_from: tuple[float, float]
    length: float
    earth_model: EarthModelLike = None

    @classmethod
    def from_task(
        cls,
        task: Task,
        orientation: GoalLineOrientation = DEFAULT_ORIENTATION,
    ) -> "GoalLine | None":
        """Build the goal line for a task.

        Measures the task when the orientation needs a route, which the
        default one does. A caller that already holds a ``MeasuredTask``
        should use :meth:`from_measured_task` instead; the 2024 orientation
        needs no route and measures nothing either way.

        Args:
            task: Task to derive the goal line from.
            orientation: Which edition's rule decides the approach direction.
                Defaults to the current one, :attr:`~GoalLineOrientation.OPTIMIZED_ROUTE`.

        Returns:
            A GoalLine if the task has a LINE goal with sufficient geometry, otherwise None.
        """
        if not cls._has_line_goal(task):
            return None
        if orientation is GoalLineOrientation.TURNPOINT_CENTERS:
            return cls._build(task, cls._center_candidates(task))
        return cls.from_measured_task(MeasuredTask.from_task(task), orientation)

    @classmethod
    def from_measured_task(
        cls,
        measured: MeasuredTask,
        orientation: GoalLineOrientation = DEFAULT_ORIENTATION,
    ) -> "GoalLine | None":
        """Build the goal line for an already-measured task.

        The primary constructor: S7F 2025+ orients the line against the
        optimized route point on the last control zone before goal, so the
        line needs a route, and taking the measured task means it is
        necessarily *this* task's route.

        Args:
            measured: The task and the route measured for it.
            orientation: Which edition's rule decides the approach direction.
                Defaults to the current one, :attr:`~GoalLineOrientation.OPTIMIZED_ROUTE`.

        Returns:
            A GoalLine if the task has a LINE goal with sufficient geometry, otherwise None.
        """
        task = measured.task
        if not cls._has_line_goal(task):
            return None

        if orientation is GoalLineOrientation.TURNPOINT_CENTERS:
            candidates = cls._center_candidates(task)
        else:
            candidates = list(measured.route.points[:-1])
        return cls._build(task, candidates)

    @staticmethod
    def _has_line_goal(task: Task) -> bool:
        """Whether this task has a LINE goal with enough turnpoints to orient one."""
        goal = task.effective_goal
        return bool(goal and goal.type == GoalType.LINE and len(task.turnpoints) >= 2)

    @staticmethod
    def _center_candidates(task: Task) -> list[tuple[float, float]]:
        """The 2024 rule's approach candidates: every turnpoint centre before goal."""
        return [(tp.waypoint.lat, tp.waypoint.lon) for tp in task.turnpoints[:-1]]

    @classmethod
    def _build(
        cls, task: Task, candidates: list[tuple[float, float]]
    ) -> "GoalLine | None":
        """Assemble the line from its approach candidates, or None if it has none."""
        last_tp = task.turnpoints[-1]
        center = (last_tp.waypoint.lat, last_tp.waypoint.lon)

        approach_from = _last_distinct_point(candidates, center)
        if approach_from is None:
            return None

        length = goal_line_length_from_turnpoints(task.turnpoints)
        if length is None:
            return None

        return cls(
            center=center,
            approach_from=approach_from,
            length=length,
            earth_model=task.earth_model,
        )

    def approach_azimuth(self) -> float:
        """The direction the line is crossed from, in degrees.

        Everything else here is perpendicular to it or centred on it.

        Returns:
            The geodesic azimuth from :attr:`approach_from` to :attr:`center`.
        """
        geod = geod_for_earth_model(self.earth_model)
        azimuth, _, _ = geod.inv(
            self.approach_from[1], self.approach_from[0], self.center[1], self.center[0]
        )
        return float(azimuth)

    def endpoints(self) -> tuple[tuple[float, float], tuple[float, float], float]:
        """Return ((lon1, lat1), (lon2, lat2), forward_azimuth) for the line.

        The line is perpendicular to :meth:`approach_azimuth`, centred on the
        goal, and measured on the task's earth model so it agrees with the
        distances the same task reports.

        The math used to sit in a free function taking six positional floats,
        which this method built by unpacking its own two (lat, lon) tuples —
        in a module that flips axis order between neighbouring lines, where
        swapping two of six floats costs a rotated goal line.
        """
        geod = geod_for_earth_model(self.earth_model)
        azimuth = self.approach_azimuth()
        lat, lon = self.center
        half_length = self.control_zone_radius

        lon1, lat1, _ = geod.fwd(lon, lat, (azimuth + 90) % 360, half_length)
        lon2, lat2, _ = geod.fwd(lon, lat, (azimuth - 90) % 360, half_length)
        return (lon1, lat1), (lon2, lat2), azimuth

    @property
    def control_zone_radius(self) -> float:
        """Half the line: the control zone's radius, and each endpoint's reach.

        S7F §6.2.3.1 gives the semicircular control zone the line's half-length
        as its radius, so this is one number with one owner. Both export writers
        used to recompute ``length / 2`` to caption it, beside the two places
        here that need it as geometry — one rule in three modules.
        """
        return self.length / 2

    def control_zone(self) -> list[tuple[float, float]]:
        """Return the control-zone polygon as a closed list of (lon, lat)."""
        (lon1, lat1), (lon2, lat2), forward_azimuth = self.endpoints()
        front_arc = _semicircle_arc(
            self.center, forward_azimuth, self.control_zone_radius, self.earth_model
        )
        # Closed polygon: endpoint2 -> front arc -> endpoint1 -> endpoint2
        return [(lon2, lat2)] + front_arc + [(lon1, lat1), (lon2, lat2)]
