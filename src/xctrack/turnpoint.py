"""TaskTurnpoint class and geometry calculations for distance optimization."""

from typing import List, Tuple, Optional
from geopy.distance import geodesic
from pyproj import Geod
from scipy.optimize import fminbound

from .optimization_config import DEFAULT_ANGLE_STEP

# Initialize WGS84 ellipsoid
geod = Geod(ellps="WGS84")


def _calculate_distance_through_point(
    start_point: Tuple[float, float],
    point: Tuple[float, float],
    end_point: Tuple[float, float],
) -> float:
    """Calculate total distance from start through point to end."""
    return geodesic(start_point, point).meters + geodesic(point, end_point).meters


def _find_optimal_cylinder_point(
    cylinder_center: Tuple[float, float],
    cylinder_radius: float,
    start_point: Tuple[float, float],
    end_point: Tuple[float, float],
) -> Tuple[float, float]:
    """Find optimal point on cylinder using continuous optimization.

    Uses scipy.optimize for precise optimization.

    Args:
        cylinder_center: (lat, lon) of cylinder center
        cylinder_radius: Radius in meters
        start_point: (lat, lon) of starting point
        end_point: (lat, lon) of ending point

    Returns:
        (lat, lon) of optimal point on cylinder perimeter
    """
    cylinder_lon, cylinder_lat = cylinder_center[1], cylinder_center[0]

    # Use continuous optimization
    def objective(azimuth):
        lon, lat, _ = geod.fwd(cylinder_lon, cylinder_lat, azimuth, cylinder_radius)
        point = (lat, lon)
        return _calculate_distance_through_point(start_point, point, end_point)

    optimal_azimuth = fminbound(objective, 0, 360, xtol=0.01)
    lon, lat, _ = geod.fwd(cylinder_lon, cylinder_lat, optimal_azimuth, cylinder_radius)
    return (lat, lon)


def _get_optimized_perimeter_points(
    turnpoint: "TaskTurnpoint",
    prev_point: Tuple[float, float],
    next_point: Tuple[float, float],
    angle_step: int = DEFAULT_ANGLE_STEP,
) -> List[Tuple[float, float]]:
    """Get optimized perimeter points for a turnpoint.

    Finds the optimal entry/exit points using scipy optimization.

    Args:
        turnpoint: TaskTurnpoint object
        prev_point: Previous point in route (for optimization)
        next_point: Next point in route (for optimization)
        angle_step: Angle step for uniform sampling fallback (if needed)

    Returns:
        List of (lat, lon) points on perimeter
    """
    # Handle goal lines
    if turnpoint.goal_type == "LINE":
        if prev_point:
            # For goal lines, we need the previous point to determine orientation
            optimal_point = turnpoint._find_optimal_goal_line_point(
                prev_point, next_point
            )
            return [optimal_point]
        else:
            # If no previous point available, return center
            return [turnpoint.center]

    if turnpoint.radius == 0:
        return [turnpoint.center]

    if prev_point and next_point:
        # Use optimized single point
        optimal_point = _find_optimal_cylinder_point(
            turnpoint.center, turnpoint.radius, prev_point, next_point
        )
        return [optimal_point]
    else:
        # Fall back to uniform sampling
        return turnpoint.perimeter_points(angle_step)


class TaskTurnpoint:
    """Turnpoint class for distance calculations."""

    def __init__(
        self,
        lat: float,
        lon: float,
        radius: float = 0,
        goal_type: str = None,
        goal_line_length: float = None,
    ):
        """Initialize a task turnpoint.

        Args:
            lat: Latitude in degrees
            lon: Longitude in degrees
            radius: Cylinder radius in meters
            goal_type: Type of goal (None, "CYLINDER", or "LINE")
            goal_line_length: Length of goal line in meters (None means calculate from radius)
        """
        self.center = (lat, lon)
        self.radius = radius
        self.goal_type = goal_type
        self.goal_line_length = goal_line_length

    def perimeter_points(
        self, angle_step: int = DEFAULT_ANGLE_STEP
    ) -> List[Tuple[float, float]]:
        """Generate perimeter points around the turnpoint at given angle steps.

        Args:
            angle_step: Angle step in degrees

        Returns:
            List of (lat, lon) tuples representing points on the cylinder perimeter
        """
        if self.goal_type == "LINE":
            # For goal lines, we need a previous point to determine orientation
            # This case is handled in goal_line_points() with a previous point
            return [self.center]

        if self.radius == 0:
            return [self.center]

        points = []
        for azimuth in range(0, 360, angle_step):
            lon, lat, _ = geod.fwd(self.center[1], self.center[0], azimuth, self.radius)
            points.append((lat, lon))
        return points

    def goal_line_points(
        self, prev_point: Tuple[float, float], angle_step: int = DEFAULT_ANGLE_STEP
    ) -> List[Tuple[float, float]]:
        """Generate points along a goal line.

        The goal line is perpendicular to the line from the previous point to the center,
        with the goal line center being in the middle of the line.

        Args:
            prev_point: Previous point in route (needed for goal line orientation)
            angle_step: Angle step in degrees for sampling points

        Returns:
            List of (lat, lon) tuples representing points on the goal line
        """
        if self.goal_type != "LINE":
            return self.perimeter_points(angle_step)

        # If goal line length is not specified, use a reasonable default
        # Note: this should normally not happen as we should calculate from radius
        # in _task_to_turnpoints, but this is a fallback
        goal_line_length = self.goal_line_length
        if goal_line_length is None:
            # Default to a standard FAI-style goal line of 400m if no better information
            goal_line_length = 400.0

        # Calculate bearing from previous point to goal center
        forward_azimuth, _, _ = geod.inv(
            prev_point[1], prev_point[0], self.center[1], self.center[0]
        )

        # Goal line is perpendicular to the approach direction
        perpendicular_azimuth_1 = (forward_azimuth + 90) % 360
        perpendicular_azimuth_2 = (forward_azimuth - 90) % 360

        # Calculate the endpoints of the goal line
        half_length = goal_line_length / 2
        lon1, lat1, _ = geod.fwd(
            self.center[1], self.center[0], perpendicular_azimuth_1, half_length
        )
        lon2, lat2, _ = geod.fwd(
            self.center[1], self.center[0], perpendicular_azimuth_2, half_length
        )

        # Sample points along the goal line
        points = []
        total_steps = int(360 / angle_step)

        # Add the endpoints and center point
        points.append((lat1, lon1))
        points.append(self.center)
        points.append((lat2, lon2))

        # Add semi-circle points behind the goal line
        # The semi-circle has radius = half_length and is on the opposite side from the approach
        back_azimuth = (forward_azimuth + 180) % 360
        for i in range(total_steps):
            angle = angle_step * i
            if angle > 180:
                continue  # Only create semi-circle, not full circle

            # Calculate point on semi-circle behind goal line
            semi_azimuth = (back_azimuth - 90 + angle) % 360
            lon, lat, _ = geod.fwd(
                self.center[1], self.center[0], semi_azimuth, half_length
            )
            points.append((lat, lon))

        return points

    def optimal_point(
        self,
        prev_point: Tuple[float, float],
        next_point: Tuple[float, float],
    ) -> Tuple[float, float]:
        """Find the optimal point on this turnpoint's cylinder or goal line.

        Uses scipy's optimization for precise results.

        Args:
            prev_point: (lat, lon) of previous point in route
            next_point: (lat, lon) of next point in route

        Returns:
            (lat, lon) of optimal point on cylinder perimeter or goal line
        """
        if self.goal_type == "LINE":
            return self._find_optimal_goal_line_point(prev_point, next_point)

        if self.radius == 0:
            return self.center

        return _find_optimal_cylinder_point(
            self.center, self.radius, prev_point, next_point
        )

    def _find_optimal_goal_line_point(
        self, prev_point: Tuple[float, float], next_point: Tuple[float, float]
    ) -> Tuple[float, float]:
        """Find the optimal point on the goal line.

        For a goal line, the optimal crossing point depends on:
        1. Direction of approach (from prev_point)
        2. The perpendicular line with the goal line center in the middle
        3. The semi-circle control zone behind the goal line

        Args:
            prev_point: (lat, lon) of previous point in route
            next_point: (lat, lon) of next point in route (may not be used for goal line)

        Returns:
            (lat, lon) of optimal point on the goal line or semi-circle control zone
        """
        # Calculate bearing from previous point to goal center
        forward_azimuth, _, distance_to_center = geod.inv(
            prev_point[1], prev_point[0], self.center[1], self.center[0]
        )

        # Goal line is perpendicular to the approach direction
        perpendicular_azimuth_1 = (forward_azimuth + 90) % 360
        perpendicular_azimuth_2 = (forward_azimuth - 90) % 360

        # If goal line length is not specified, use a reasonable default
        goal_line_length = self.goal_line_length
        if goal_line_length is None:
            # Default to a standard FAI-style goal line of 400m if no better information
            goal_line_length = 400.0

        # Calculate the endpoints of the goal line
        half_length = goal_line_length / 2
        lon1, lat1, _ = geod.fwd(
            self.center[1], self.center[0], perpendicular_azimuth_1, half_length
        )
        lon2, lat2, _ = geod.fwd(
            self.center[1], self.center[0], perpendicular_azimuth_2, half_length
        )

        # Calculate the points to test for optimization
        endpoint1 = (lat1, lon1)
        endpoint2 = (lat2, lon2)

        # For goal lines, the optimal crossing is typically the perpendicular projection
        # from the previous point onto the goal line

        # First, determine if the perpendicular projection falls on the goal line segment
        # Calculate vector from endpoint1 to endpoint2
        e1_to_e2_azimuth, _, e1_to_e2_distance = geod.inv(
            endpoint1[1], endpoint1[0], endpoint2[1], endpoint2[0]
        )

        # Calculate vector from endpoint1 to previous point
        e1_to_prev_azimuth, _, e1_to_prev_distance = geod.inv(
            endpoint1[1], endpoint1[0], prev_point[1], prev_point[0]
        )

        # Calculate angle difference to determine if projection falls on line segment
        angle_diff = abs((e1_to_e2_azimuth - e1_to_prev_azimuth + 180) % 360 - 180)
        if angle_diff > 90:
            # Projection falls outside line segment, use closest endpoint
            dist1 = geodesic(prev_point, endpoint1).meters
            dist2 = geodesic(prev_point, endpoint2).meters
            return endpoint1 if dist1 < dist2 else endpoint2

        # Calculate perpendicular projection onto goal line
        # We need to find the point on the goal line that forms a right angle with prev_point
        def objective(t):
            # Parametric representation of the line, t from 0 to 1
            # Calculate intermediate point on the goal line
            lon, lat, _ = geod.fwd(
                endpoint1[1], endpoint1[0], e1_to_e2_azimuth, t * e1_to_e2_distance
            )
            line_point = (lat, lon)

            # Calculate azimuth from prev_point to this point
            azimuth_to_point, _, _ = geod.inv(prev_point[1], prev_point[0], lon, lat)

            # The angle between this azimuth and the goal line azimuth should be 90 degrees
            # for the optimal projection. We want to minimize the deviation from 90 degrees.
            angle_diff = abs((azimuth_to_point - forward_azimuth + 180) % 360 - 180)
            return abs(angle_diff - 90)

        # Find the parameter t that minimizes the objective function
        optimal_t = fminbound(objective, 0, 1, xtol=0.0001)
        lon, lat, _ = geod.fwd(
            endpoint1[1], endpoint1[0], e1_to_e2_azimuth, optimal_t * e1_to_e2_distance
        )
        optimal_point = (lat, lon)

        return optimal_point

    def optimized_perimeter_points(
        self,
        prev_point: Tuple[float, float],
        next_point: Tuple[float, float],
        angle_step: int = DEFAULT_ANGLE_STEP,
    ) -> List[Tuple[float, float]]:
        """Get optimized perimeter points for this turnpoint.

        Args:
            prev_point: Previous point in route
            next_point: Next point in route
            angle_step: Angle step for fallback uniform sampling

        Returns:
            List of (lat, lon) points on perimeter
        """
        if self.goal_type == "LINE":
            # For goal lines, we need both a previous point and a special handling
            if prev_point:
                # Find optimal point on goal line
                optimal_point = self._find_optimal_goal_line_point(
                    prev_point, next_point
                )
                return [optimal_point]
            else:
                # Cannot optimize without previous point, return center
                return [self.center]

        return _get_optimized_perimeter_points(self, prev_point, next_point, angle_step)


def distance_through_centers(turnpoints: List[TaskTurnpoint]) -> float:
    """Calculate distance through turnpoint centers.

    Args:
        turnpoints: List of TaskTurnpoint objects

    Returns:
        Distance through centers in meters
    """
    if len(turnpoints) < 2:
        return 0.0

    total = 0.0
    for i in range(len(turnpoints) - 1):
        a = turnpoints[i].center
        b = turnpoints[i + 1].center
        total += geodesic(a, b).meters
    return total
