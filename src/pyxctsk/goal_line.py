"""Goal line geometry for LINE type goals.

This module owns everything about a task's goal line: how long it is, where
its endpoints sit, and the shape of its semicircular control zone. The
:class:`GoalLine` class is the single deep module that callers (GeoJSON and
KML generation, distance calculation) go through, so the goal-line rules live
in exactly one place.

The free functions kept here (``calculate_goal_line_endpoints``,
``generate_semicircle_arc``, ``get_goal_line_data``, ``should_skip_last_turnpoint``)
are thin adapters over the same core, retained for backwards compatibility.
"""

from dataclasses import dataclass

from pyproj import Geod

from .task import GoalType, Task

# Initialize WGS84 ellipsoid for geographical calculations
geod = Geod(ellps="WGS84")

# Constants for goal line visualization
GOAL_LINE_NUM_POINTS = 20
COORD_TOLERANCE = 1e-9


def goal_line_length_from_turnpoints(turnpoints) -> float | None:
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


def _find_previous_turnpoint(turnpoints, last_tp):
    """Find the previous turnpoint with different coordinates from the goal center.

    Args:
        turnpoints: List of turnpoints to search through
        last_tp: The last turnpoint (goal center)

    Returns:
        The previous turnpoint with different coordinates, or None if not found
    """
    for i in range(len(turnpoints) - 2, -1, -1):
        candidate_tp = turnpoints[i]
        # Check if coordinates are different (with small tolerance for floating point comparison)
        if (
            abs(candidate_tp.waypoint.lon - last_tp.waypoint.lon) > COORD_TOLERANCE
            or abs(candidate_tp.waypoint.lat - last_tp.waypoint.lat) > COORD_TOLERANCE
        ):
            return candidate_tp
    return None


def _endpoints_from_coords(
    center_lat: float,
    center_lon: float,
    prev_lat: float,
    prev_lon: float,
    goal_line_length: float,
) -> tuple[tuple[float, float], tuple[float, float], float]:
    """Core endpoint math operating on raw coordinates.

    Returns ((lon1, lat1), (lon2, lat2), forward_azimuth). The goal line is
    perpendicular to the approach direction from the previous point to the
    goal center, centred on the goal center.
    """
    # Calculate bearing from previous point to goal center
    forward_azimuth, _, _ = geod.inv(prev_lon, prev_lat, center_lon, center_lat)

    # Goal line is perpendicular to the approach direction
    perpendicular_azimuth_1 = (forward_azimuth + 90) % 360
    perpendicular_azimuth_2 = (forward_azimuth - 90) % 360

    half_length = goal_line_length / 2

    lon1, lat1, _ = geod.fwd(center_lon, center_lat, perpendicular_azimuth_1, half_length)
    lon2, lat2, _ = geod.fwd(center_lon, center_lat, perpendicular_azimuth_2, half_length)

    return (lon1, lat1), (lon2, lat2), forward_azimuth


def calculate_goal_line_endpoints(
    last_tp, prev_tp, goal_line_length: float
) -> tuple[tuple[float, float], tuple[float, float], float]:
    """Calculate the endpoints of the goal line and return the forward azimuth.

    Object adapter over :func:`_endpoints_from_coords`.

    Args:
        last_tp: The last turnpoint (goal center)
        prev_tp: The previous turnpoint to determine approach direction
        goal_line_length: Length of the goal line in meters

    Returns:
        Tuple of ((lon1, lat1), (lon2, lat2), forward_azimuth)
    """
    return _endpoints_from_coords(
        last_tp.waypoint.lat,
        last_tp.waypoint.lon,
        prev_tp.waypoint.lat,
        prev_tp.waypoint.lon,
        goal_line_length,
    )


def generate_semicircle_arc(
    center_lon: float,
    center_lat: float,
    start_azimuth: float,
    end_azimuth: float,
    through_azimuth: float,
    radius: float,
) -> list[tuple[float, float]]:
    """Generate arc points for a semi-circle.

    Args:
        center_lon: Center longitude
        center_lat: Center latitude
        start_azimuth: Starting azimuth in degrees
        end_azimuth: Ending azimuth in degrees
        through_azimuth: Intermediate azimuth to pass through
        radius: Radius in meters

    Returns:
        List of (lon, lat) coordinate tuples representing the arc
    """
    arc_points = []
    for i in range(GOAL_LINE_NUM_POINTS + 1):  # include endpoint
        if i <= GOAL_LINE_NUM_POINTS // 2:
            # First half: interpolate from start_azimuth to through_azimuth
            t = (i * 2) / GOAL_LINE_NUM_POINTS
            angle_diff = (through_azimuth - start_azimuth) % 360
            if angle_diff > 180:
                angle_diff -= 360
            angle = (start_azimuth + angle_diff * t) % 360
        else:
            # Second half: interpolate from through_azimuth to end_azimuth
            t = ((i - GOAL_LINE_NUM_POINTS // 2) * 2) / GOAL_LINE_NUM_POINTS
            angle_diff = (end_azimuth - through_azimuth) % 360
            if angle_diff > 180:
                angle_diff -= 360
            angle = (through_azimuth + angle_diff * t) % 360

        lon_arc, lat_arc, _ = geod.fwd(center_lon, center_lat, angle, radius)
        arc_points.append((lon_arc, lat_arc))
    return arc_points


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
        approach_from: (lat, lon) of the previous turnpoint defining the approach.
        length: Total goal-line length in meters.
    """

    center: tuple[float, float]
    approach_from: tuple[float, float]
    length: float

    @classmethod
    def from_task(cls, task: Task) -> "GoalLine | None":
        """Build the goal line for a task.

        Args:
            task: Task to derive the goal line from.

        Returns:
            A GoalLine if the task has a LINE goal with sufficient geometry, otherwise None.
        """
        if not (
            task.goal
            and task.goal.type == GoalType.LINE
            and task.turnpoints
            and len(task.turnpoints) >= 2
        ):
            return None

        last_tp = task.turnpoints[-1]
        prev_tp = _find_previous_turnpoint(task.turnpoints, last_tp)
        if prev_tp is None:
            return None

        length = task.goal.line_length
        if length is None:
            length = goal_line_length_from_turnpoints(task.turnpoints)
        if length is None:
            return None
        length = float(length)

        return cls(
            center=(last_tp.waypoint.lat, last_tp.waypoint.lon),
            approach_from=(prev_tp.waypoint.lat, prev_tp.waypoint.lon),
            length=length,
        )

    def endpoints(self) -> tuple[tuple[float, float], tuple[float, float], float]:
        """Return ((lon1, lat1), (lon2, lat2), forward_azimuth) for the line."""
        return _endpoints_from_coords(
            self.center[0],
            self.center[1],
            self.approach_from[0],
            self.approach_from[1],
            self.length,
        )

    def control_zone(self) -> list[tuple[float, float]]:
        """Return the control-zone polygon as a closed list of (lon, lat)."""
        (lon1, lat1), (lon2, lat2), forward_azimuth = self.endpoints()

        control_zone_radius = self.length / 2
        perpendicular_azimuth_1 = (forward_azimuth + 90) % 360
        perpendicular_azimuth_2 = (forward_azimuth - 90) % 360

        front_arc_points = generate_semicircle_arc(
            self.center[1],
            self.center[0],
            perpendicular_azimuth_2,
            perpendicular_azimuth_1,
            forward_azimuth,
            control_zone_radius,
        )

        # Closed polygon: endpoint2 -> front arc -> endpoint1 -> endpoint2
        return [(lon2, lat2)] + front_arc_points + [(lon1, lat1), (lon2, lat2)]

    def data(
        self,
    ) -> tuple[
        tuple[float, float], tuple[float, float], float, list[tuple[float, float]]
    ]:
        """Return (start, end, length, control_zone_coords) for rendering."""
        (lon1, lat1), (lon2, lat2), _ = self.endpoints()
        return (lon1, lat1), (lon2, lat2), self.length, self.control_zone()


def get_goal_line_data(
    task: Task,
) -> (
    tuple[tuple[float, float], tuple[float, float], float, list[tuple[float, float]]]
    | None
):
    """Get goal line data for LINE type goals.

    Thin adapter over :meth:`GoalLine.from_task` / :meth:`GoalLine.data`.

    Args:
        task: The task object

    Returns:
        Tuple of (goal_line_start, goal_line_end, goal_line_length, control_zone_coords)
        or None if not a LINE type goal or insufficient data
    """
    goal_line = GoalLine.from_task(task)
    if goal_line is None:
        return None
    return goal_line.data()


def should_skip_last_turnpoint(task: Task) -> bool:
    """Check if the last turnpoint should be skipped for LINE type goals.

    Args:
        task: The task object

    Returns:
        True if the last turnpoint should be skipped (for LINE goals)
    """
    return bool(
        task.goal
        and task.goal.type == GoalType.LINE
        and task.turnpoints
        and len(task.turnpoints) >= 2
    )
