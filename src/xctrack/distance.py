"""Distance calculation module using WGS84 ellipsoid and route optimization."""

from typing import Any, Dict, List, Tuple

from geopy.distance import geodesic
from pyproj import Geod

from .task import Task

# Configuration constants
DEFAULT_ANGLE_STEP = 10  # Angle step in degrees for perimeter point generation (5-15° for good accuracy/performance balance)

# Initialize WGS84 ellipsoid
geod = Geod(ellps="WGS84")


class TaskTurnpoint:
    """Turnpoint class for distance calculations."""

    def __init__(self, lat: float, lon: float, radius: float = 0):
        """Initialize a task turnpoint.

        Args:
            lat: Latitude in degrees
            lon: Longitude in degrees
            radius: Cylinder radius in meters
        """
        self.center = (lat, lon)
        self.radius = radius

    def perimeter_points(
        self, angle_step: int = DEFAULT_ANGLE_STEP
    ) -> List[Tuple[float, float]]:
        """Generate perimeter points around the turnpoint at given angle steps.

        Args:
            angle_step: Angle step in degrees

        Returns:
            List of (lat, lon) tuples representing points on the cylinder perimeter
        """
        if self.radius == 0:
            return [self.center]

        points = []
        for azimuth in range(0, 360, angle_step):
            lon, lat, _ = geod.fwd(self.center[1], self.center[0], azimuth, self.radius)
            points.append((lat, lon))
        return points


def _compute_optimal_route_dp(
    turnpoints: List[TaskTurnpoint],
    task_turnpoints=None,
    angle_step: int = DEFAULT_ANGLE_STEP,
    show_progress: bool = False,
    return_path: bool = False,
) -> Tuple[float, List[Tuple[float, float]]]:
    """Core dynamic programming algorithm for computing optimal routes through turnpoints.

    Args:
        turnpoints: List of TaskTurnpoint objects
        task_turnpoints: Optional list of original task turnpoints with type information
        angle_step: Angle step in degrees for perimeter point generation
        show_progress: Whether to show progress indicators
        return_path: Whether to return the actual path coordinates

    Returns:
        Tuple of (optimized_distance_meters, route_coordinates)
        If return_path is False, route_coordinates will be empty
    """
    if len(turnpoints) < 2:
        distance = 0.0
        path = (
            [(tp.center[0], tp.center[1]) for tp in turnpoints] if return_path else []
        )
        return distance, path

    if show_progress:
        print(
            f"    🔄 Optimizing route through {len(turnpoints)} turnpoints (angle step: {angle_step}°)..."
        )

    # Precompute perimeter points for all turnpoints
    perimeters = [tp.perimeter_points(angle_step) for tp in turnpoints]

    if show_progress:
        total_points = sum(len(p) for p in perimeters)
        print(f"    📍 Generated {total_points} perimeter points")

    # Get takeoff center
    takeoff_center = turnpoints[0].center

    # Initialize distance table
    dp = [{} for _ in turnpoints]

    # Initialize first turnpoint (takeoff)
    if return_path:
        dp[0] = {takeoff_center: (0, None)}
    else:
        dp[0] = {p: 0 for p in perimeters[0]}

    # Fill DP table using dynamic programming
    for i in range(1, len(turnpoints)):
        if show_progress:
            print(f"    ⚡ Processing turnpoint {i+1}/{len(turnpoints)}")

        # Handle non-return_path inside cylinder case before point loop
        if not return_path and i == 1:
            distance_to_center = geodesic(takeoff_center, turnpoints[i].center).meters
            if distance_to_center <= turnpoints[i].radius:
                dp[i] = {takeoff_center: 0}
                continue

        for curr_pt in perimeters[i]:
            min_dist = float("inf")
            best_prev_pt = None

            # Standard DP approach for all turnpoints
            if i == 1:
                leg_distance = geodesic(takeoff_center, curr_pt).meters
                min_dist = leg_distance
                best_prev_pt = takeoff_center
            else:
                for prev_pt, prev_dist_info in dp[i - 1].items():
                    prev_dist = prev_dist_info[0] if return_path else prev_dist_info
                    leg_distance = geodesic(prev_pt, curr_pt).meters
                    total_distance = prev_dist + leg_distance
                    if total_distance < min_dist:
                        min_dist = total_distance
                        best_prev_pt = prev_pt

            # Store result
            if return_path:
                dp[i][curr_pt] = (min_dist, best_prev_pt)
            else:
                dp[i][curr_pt] = min_dist

    # Find optimal distance and reconstruct path if needed
    if return_path:
        optimal_distance = min(dp[-1].values(), key=lambda x: x[0])[0]
        optimal_end_point = min(dp[-1].keys(), key=lambda p: dp[-1][p][0])
        route_coordinates = []
        current_point = optimal_end_point

        for i in range(len(turnpoints) - 1, -1, -1):
            route_coordinates.append(current_point)
            if i > 0 and current_point in dp[i]:
                prev_point = dp[i][current_point][1]
                current_point = prev_point if prev_point else takeoff_center

        route_coordinates.reverse()
        return optimal_distance, route_coordinates
    else:
        optimal_distance = min(dp[-1].values())
        return optimal_distance, []


def optimized_distance(
    turnpoints: List[TaskTurnpoint],
    angle_step: int = DEFAULT_ANGLE_STEP,
    show_progress: bool = False,
) -> float:
    """Compute the fully optimized distance through turnpoints using Dynamic Programming.

    This algorithm finds the shortest possible route through all turnpoint cylinders
    starting from the center of the take-off and computing the optimal path to
    perimeters of subsequent turnpoints.

    Args:
        turnpoints: List of TaskTurnpoint objects
        angle_step: Angle step in degrees for perimeter point generation
        show_progress: Whether to show progress indicators

    Returns:
        Optimized distance in meters
    """
    distance, _ = _compute_optimal_route_dp(
        turnpoints,
        angle_step=angle_step,
        show_progress=show_progress,
        return_path=False,
    )
    return distance


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


def _task_to_turnpoints(task: Task) -> List[TaskTurnpoint]:
    """Convert Task turnpoints to TaskTurnpoint objects.

    Args:
        task: Task object

    Returns:
        List of TaskTurnpoint objects
    """
    return [
        TaskTurnpoint(lat=tp.waypoint.lat, lon=tp.waypoint.lon, radius=tp.radius)
        for tp in task.turnpoints
    ]


def calculate_task_distances(
    task: Task, angle_step: int = DEFAULT_ANGLE_STEP, show_progress: bool = False
) -> Dict[str, Any]:
    """Calculate both center and optimized distances for a task.

    Args:
        task: Task object
        angle_step: Angle step in degrees for optimization
        show_progress: Whether to show progress indicators

    Returns:
        Dictionary containing distance calculations and turnpoint details
    """
    # Convert to TaskTurnpoint objects
    turnpoints = _task_to_turnpoints(task)

    if len(turnpoints) < 2:
        return {
            "center_distance_km": 0.0,
            "optimized_distance_km": 0.0,
            "savings_km": 0.0,
            "savings_percent": 0.0,
            "turnpoints": [],
        }

    # For distance calculations, use all turnpoints in sequence
    # SSS turnpoints are treated like any other turnpoint
    distance_turnpoints = turnpoints.copy()

    if show_progress:
        print("  📏 Calculating center distance...")

    # Calculate distances using all turnpoints
    center_dist = distance_through_centers(distance_turnpoints)

    if show_progress:
        print(f"  ✅ Center distance: {center_dist/1000.0:.1f}km")
        print("  🎯 Starting optimization...")

    opt_dist = optimized_distance(
        distance_turnpoints, angle_step=angle_step, show_progress=show_progress
    )

    if show_progress:
        print(f"  ✅ Optimized distance: {opt_dist/1000.0:.1f}km")

    # Convert to kilometers
    center_km = center_dist / 1000.0
    opt_km = opt_dist / 1000.0

    # Calculate savings
    savings_km = center_km - opt_km
    savings_percent = (savings_km / center_km * 100) if center_km > 0 else 0.0

    if show_progress:
        print(
            f"  📊 Calculating cumulative distances for {len(turnpoints)} turnpoints..."
        )

    # Calculate cumulative distances efficiently
    turnpoint_details = []
    cumulative_center = 0.0

    for i, (tp, task_tp) in enumerate(zip(task.turnpoints, turnpoints)):
        cumulative_opt = 0.0

        # Calculate cumulative distances for all turnpoints
        if i > 0:
            if show_progress and i > 1:
                print(f"    🔄 Turnpoint {i+1}/{len(turnpoints)}")

            # Calculate center distance incrementally
            prev_tp = turnpoints[i - 1]
            leg_distance = geodesic(prev_tp.center, task_tp.center).meters / 1000.0
            cumulative_center += leg_distance

            # For optimized distance, calculate using all turnpoints up to current
            partial_turnpoints = turnpoints[: i + 1]
            if len(partial_turnpoints) >= 2:
                cumulative_opt = (
                    optimized_distance(
                        partial_turnpoints,
                        angle_step=angle_step,
                        show_progress=False,
                    )
                    / 1000.0
                )

        turnpoint_details.append(
            {
                "index": i,
                "name": tp.waypoint.name,
                "lat": tp.waypoint.lat,
                "lon": tp.waypoint.lon,
                "radius": tp.radius,
                "type": tp.type.value if tp.type else "",
                "cumulative_center_km": round(cumulative_center, 1),
                "cumulative_optimized_km": round(cumulative_opt, 1),
            }
        )

    if show_progress:
        print("  ✅ All calculations complete")

    return {
        "center_distance_km": round(center_km, 1),
        "optimized_distance_km": round(opt_km, 1),
        "savings_km": round(savings_km, 1),
        "savings_percent": round(savings_percent, 1),
        "turnpoints": turnpoint_details,
        "optimization_angle_step": angle_step,
    }


def calculate_cumulative_distances(
    turnpoints: List[TaskTurnpoint], index: int, angle_step: int = DEFAULT_ANGLE_STEP
) -> Tuple[float, float]:
    """Calculate cumulative distances up to a specific turnpoint index.

    Args:
        turnpoints: List of TaskTurnpoint objects
        index: Index of the turnpoint (0-based)
        angle_step: Angle step for optimization calculations

    Returns:
        Tuple of (center_distance_km, optimized_distance_km)
    """
    if index == 0 or len(turnpoints) <= 1:
        return 0.0, 0.0

    partial_turnpoints = turnpoints[: index + 1]
    center_dist = distance_through_centers(partial_turnpoints) / 1000.0
    opt_dist = (
        optimized_distance(
            partial_turnpoints, angle_step=angle_step, show_progress=False
        )
        / 1000.0
    )

    return center_dist, opt_dist


def optimized_route_coordinates(
    turnpoints: List[TaskTurnpoint],
    task_turnpoints=None,
    angle_step: int = DEFAULT_ANGLE_STEP,
) -> List[Tuple[float, float]]:
    """Compute the fully optimized route coordinates through turnpoints using Dynamic Programming.

    This algorithm finds the shortest possible route through all turnpoint cylinders
    and returns the actual coordinates of the optimal path. All turnpoints including SSS
    are treated uniformly in the route calculation.

    Args:
        turnpoints: List of TaskTurnpoint objects
        task_turnpoints: Optional list of original task turnpoints with type information
        angle_step: Angle step in degrees for perimeter point generation

    Returns:
        List of (lat, lon) tuples representing the optimized route coordinates
    """
    # Calculate route through all turnpoints in sequence
    _, route_coordinates = _compute_optimal_route_dp(
        turnpoints,
        task_turnpoints=task_turnpoints,
        angle_step=angle_step,
        show_progress=False,
        return_path=True,
    )
    return route_coordinates


def calculate_optimal_sss_entry_point(
    sss_turnpoint: TaskTurnpoint,
    takeoff_center: Tuple[float, float],
    first_tp_after_sss_point: Tuple[float, float],
    angle_step: int = DEFAULT_ANGLE_STEP,
) -> Tuple[float, float]:
    """Calculate the optimal entry point for an SSS (Start Speed Section) turnpoint.

    This function finds the point on the SSS cylinder perimeter that minimizes the
    total distance from takeoff to the first turnpoint after SSS, passing through
    the SSS entry point.

    Args:
        sss_turnpoint: TaskTurnpoint object representing the SSS cylinder
        takeoff_center: (lat, lon) tuple of takeoff center coordinates
        first_tp_after_sss_point: (lat, lon) tuple of the target point on first TP after SSS
        angle_step: Angle step in degrees for perimeter point generation

    Returns:
        Tuple of (lat, lon) representing the optimal SSS entry point
    """
    # Generate perimeter points for the SSS turnpoint
    sss_perimeter = sss_turnpoint.perimeter_points(angle_step)

    # Find the point that minimizes total distance: takeoff -> SSS entry -> first TP after SSS
    best_sss_point = min(
        sss_perimeter,
        key=lambda p: geodesic(takeoff_center, p).meters
        + geodesic(p, first_tp_after_sss_point).meters,
    )

    return best_sss_point


def calculate_sss_info(
    task_turnpoints,
    route_coordinates: List[Tuple[float, float]],
    angle_step: int = DEFAULT_ANGLE_STEP,
) -> Dict[str, Any]:
    """Calculate SSS (Start Speed Section) information for a task.

    This function analyzes a task to find SSS turnpoints and calculates the optimal
    entry point and related information for display and route planning.

    Args:
        task_turnpoints: List of task turnpoints with type information
        route_coordinates: List of (lat, lon) tuples representing the optimized route
        angle_step: Angle step in degrees for perimeter point generation

    Returns:
        Dictionary containing SSS information or None if no SSS found:
        {
            'sss_center': {'lat': float, 'lon': float, 'radius': float},
            'optimal_entry_point': {'lat': float, 'lon': float},
            'first_tp_after_sss': {'lat': float, 'lon': float},
            'takeoff_center': {'lat': float, 'lon': float}
        }
    """
    if not task_turnpoints or len(task_turnpoints) < 2:
        return None

    # Get takeoff center
    takeoff_center = (task_turnpoints[0].waypoint.lat, task_turnpoints[0].waypoint.lon)

    # Find SSS turnpoint
    for i, tp in enumerate(task_turnpoints):
        if hasattr(tp, "type") and tp.type and tp.type.value == "SSS":
            # Found SSS turnpoint
            sss_tp = {
                "lat": tp.waypoint.lat,
                "lon": tp.waypoint.lon,
                "radius": tp.radius,
            }

            # Check if there's a turnpoint after SSS
            if i + 1 < len(task_turnpoints):
                first_tp_after_sss = {
                    "lat": task_turnpoints[i + 1].waypoint.lat,
                    "lon": task_turnpoints[i + 1].waypoint.lon,
                }

                # Determine the optimal point on the first TP after SSS from the route
                first_tp_after_sss_route_point = None
                if len(route_coordinates) > 1:
                    # Route starts with takeoff, then first TP after SSS
                    first_tp_after_sss_route_point = route_coordinates[1]
                else:
                    # Fallback to center coordinates
                    first_tp_after_sss_route_point = (
                        first_tp_after_sss["lat"],
                        first_tp_after_sss["lon"],
                    )

                # Calculate optimal SSS entry point using the centralized function
                sss_task_tp = TaskTurnpoint(tp.waypoint.lat, tp.waypoint.lon, tp.radius)
                best_sss_point = calculate_optimal_sss_entry_point(
                    sss_task_tp,
                    takeoff_center,
                    first_tp_after_sss_route_point,
                    angle_step,
                )

                optimal_sss_point = {"lat": best_sss_point[0], "lon": best_sss_point[1]}

                return {
                    "sss_center": sss_tp,
                    "optimal_entry_point": optimal_sss_point,
                    "first_tp_after_sss": first_tp_after_sss,
                    "takeoff_center": {
                        "lat": takeoff_center[0],
                        "lon": takeoff_center[1],
                    },
                }

    return None
