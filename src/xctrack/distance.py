"""Distance calculation module using WGS84 ellipsoid and route optimization."""

from collections import defaultdict
from geopy.distance import geodesic
from pyproj import Geod
from scipy.optimize import fminbound
from typing import Any, Dict, List, Tuple, Optional

from .task import Task

# Configuration constants
DEFAULT_ANGLE_STEP = 10  # Angle step in degrees for perimeter point generation (5-15° for good accuracy/performance balance)
DEFAULT_BEAM_WIDTH = (
    10  # Number of best candidates to keep at each DP stage for beam search
)
DEFAULT_NUM_ITERATIONS = 5  # Default number of iterations for iterative refinement

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

    def optimal_point(
        self,
        prev_point: Tuple[float, float],
        next_point: Tuple[float, float],
    ) -> Tuple[float, float]:
        """Find the optimal point on this turnpoint's cylinder.

        Uses scipy's optimization for precise results.

        Args:
            prev_point: (lat, lon) of previous point in route
            next_point: (lat, lon) of next point in route

        Returns:
            (lat, lon) of optimal point on cylinder perimeter
        """
        if self.radius == 0:
            return self.center

        return _find_optimal_cylinder_point(
            self.center, self.radius, prev_point, next_point
        )

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
        return _get_optimized_perimeter_points(self, prev_point, next_point, angle_step)


def _compute_optimal_route_dp(
    turnpoints: List[TaskTurnpoint],
    task_turnpoints=None,
    angle_step: int = DEFAULT_ANGLE_STEP,
    show_progress: bool = False,
    return_path: bool = False,
    beam_width: int = DEFAULT_BEAM_WIDTH,
) -> Tuple[float, List[Tuple[float, float]]]:
    """Core dynamic programming algorithm for computing optimal routes through turnpoints.

    Args:
        turnpoints: List of TaskTurnpoint objects
        task_turnpoints: Optional list of original task turnpoints with type information
        angle_step: Angle step in degrees for perimeter point generation
        show_progress: Whether to show progress indicators
        return_path: Whether to return the actual path coordinates
        beam_width: Number of best candidates to keep at each DP stage

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
            f"    🔄 Computing optimized route through {len(turnpoints)} turnpoints..."
        )

    # Use optimized approach with true DP and beam search
    return _compute_optimal_route_with_beam_search(
        turnpoints, show_progress, return_path, beam_width
    )


def _init_dp_structure(turnpoints: List[TaskTurnpoint]) -> List[defaultdict]:
    """Initialize the dynamic programming data structure.

    Args:
        turnpoints: List of TaskTurnpoint objects

    Returns:
        List of defaultdicts for DP computation
    """
    # dp[i] maps candidate points on turnpoint i -> (best_distance, parent_point)
    dp = [defaultdict(lambda: (float("inf"), None)) for _ in turnpoints]

    # Initialize: start at takeoff center with distance 0
    dp[0][turnpoints[0].center] = (0.0, None)
    return dp


def _process_dp_stage(
    dp: List[defaultdict],
    i: int,
    turnpoints: List[TaskTurnpoint],
    beam_width: int,
    show_progress: bool,
) -> defaultdict:
    """Process one stage of the dynamic programming calculation.

    Args:
        dp: The DP structure
        i: Current stage index
        turnpoints: List of TaskTurnpoint objects
        beam_width: Number of best candidates to keep
        show_progress: Whether to show progress

    Returns:
        Updated DP structure for stage i
    """
    current_tp = turnpoints[i]
    next_center = (
        turnpoints[i + 1].center if i + 1 < len(turnpoints) else current_tp.center
    )
    new_candidates = defaultdict(lambda: (float("inf"), None))

    # For each candidate point from previous turnpoint
    for prev_point, (prev_dist, _) in dp[i - 1].items():
        # Find optimal entry point on current turnpoint
        if current_tp.radius == 0:
            optimal_point = current_tp.center
        else:
            optimal_point = current_tp.optimal_point(prev_point, next_center)

        # Calculate leg distance and total distance
        leg_distance = geodesic(prev_point, optimal_point).meters
        total_distance = prev_dist + leg_distance

        # Keep the best distance for this optimal point
        if total_distance < new_candidates[optimal_point][0]:
            new_candidates[optimal_point] = (total_distance, prev_point)

    # Beam search: keep only the best beam_width candidates
    if len(new_candidates) > beam_width:
        best_items = sorted(new_candidates.items(), key=lambda kv: kv[1][0])[
            :beam_width
        ]
        result = dict(best_items)
    else:
        result = dict(new_candidates)

    if show_progress:
        print(f"    📊 Keeping {len(result)} candidates")

    return result


def _backtrack_path(
    dp: List[defaultdict],
    best_point: Tuple[float, float],
    turnpoints: List[TaskTurnpoint],
) -> List[Tuple[float, float]]:
    """Backtrack through the DP structure to reconstruct the optimal path.

    Args:
        dp: The DP structure
        best_point: The best final point
        turnpoints: List of TaskTurnpoint objects

    Returns:
        List of coordinates forming the optimal path
    """
    path_points = []
    current_point = best_point

    for i in range(len(turnpoints) - 1, -1, -1):
        path_points.append(current_point)
        if i > 0:
            _, parent_point = dp[i][current_point]
            current_point = parent_point

    return list(reversed(path_points))


def _compute_optimal_route_with_beam_search(
    turnpoints: List[TaskTurnpoint],
    show_progress: bool = False,
    return_path: bool = False,
    beam_width: int = DEFAULT_BEAM_WIDTH,
) -> Tuple[float, List[Tuple[float, float]]]:
    """Compute optimal route using dynamic programming with beam search.

    This method uses DP to consider multiple candidate paths and avoid
    the greedy local optimization trap that can occur with large cylinders.

    Args:
        turnpoints: List of TaskTurnpoint objects
        show_progress: Whether to show progress indicators
        return_path: Whether to return the actual path coordinates
        beam_width: Number of best candidates to keep at each stage

    Returns:
        Tuple of (optimized_distance_meters, route_coordinates)
    """
    if show_progress:
        print("    🎯 Using true DP with beam search...")

    # Initialize DP structure
    dp = _init_dp_structure(turnpoints)

    # DP forward pass
    for i in range(1, len(turnpoints)):
        if show_progress:
            print(f"    ⚡ DP stage {i}/{len(turnpoints)-1}")

        dp[i] = _process_dp_stage(dp, i, turnpoints, beam_width, show_progress)

    # Find the best final solution
    final_candidates = dp[-1]
    if not final_candidates:
        return 0.0, []

    best_point, (best_distance, _) = min(
        final_candidates.items(), key=lambda kv: kv[1][0]
    )

    if show_progress:
        print(f"    ✅ DP route: {best_distance/1000.0:.3f}km")

    # Reconstruct path if needed
    route_points = []
    if return_path:
        route_points = _backtrack_path(dp, best_point, turnpoints)

    return best_distance, route_points


def optimized_distance(
    turnpoints: List[TaskTurnpoint],
    angle_step: int = DEFAULT_ANGLE_STEP,
    show_progress: bool = False,
    beam_width: int = DEFAULT_BEAM_WIDTH,
    num_iterations: int = DEFAULT_NUM_ITERATIONS,
) -> float:
    """Compute the fully optimized distance through turnpoints using iterative refinement.

    This algorithm finds the shortest possible route through all turnpoint cylinders
    starting from the center of the take-off and computing the optimal path using
    dynamic programming with beam search and iterative refinement to reduce look-ahead bias.

    The iterative refinement approach performs multiple optimization passes to
    avoid the systematic bias of assuming the next target is at the center
    of the next turnpoint.

    Args:
        turnpoints: List of TaskTurnpoint objects
        angle_step: Angle step in degrees for perimeter point generation (fallback only)
        show_progress: Whether to show progress indicators
        beam_width: Number of best candidates to keep at each DP stage
        num_iterations: Number of refinement iterations

    Returns:
        Optimized distance in meters
    """
    distance, _ = calculate_iteratively_refined_route(
        turnpoints,
        num_iterations=num_iterations,
        angle_step=angle_step,
        show_progress=show_progress,
        beam_width=beam_width,
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


def _calculate_savings(center_km: float, opt_km: float) -> Tuple[float, float]:
    """Calculate distance savings in km and percentage.

    Args:
        center_km: Center distance in km
        opt_km: Optimized distance in km

    Returns:
        Tuple of (savings_km, savings_percent)
    """
    savings_km = center_km - opt_km
    savings_percent = (savings_km / center_km * 100) if center_km > 0 else 0.0
    return savings_km, savings_percent


def _create_turnpoint_details(
    task_turnpoints,
    task_distance_turnpoints: List[TaskTurnpoint],
    angle_step: int = DEFAULT_ANGLE_STEP,
    beam_width: int = DEFAULT_BEAM_WIDTH,
    show_progress: bool = False,
) -> List[Dict[str, Any]]:
    """Create detailed turnpoint information including cumulative distances.

    Args:
        task_turnpoints: Original task turnpoints
        task_distance_turnpoints: Distance calculation turnpoints
        angle_step: Angle step for optimization
        beam_width: Beam width for DP
        show_progress: Whether to show progress

    Returns:
        List of dictionaries with turnpoint details
    """
    turnpoint_details = []
    cumulative_center = 0.0

    for i, (tp, task_tp) in enumerate(zip(task_turnpoints, task_distance_turnpoints)):
        cumulative_opt = 0.0

        # Calculate cumulative distances for all turnpoints
        if i > 0:
            if show_progress and i > 1:
                print(f"    🔄 Turnpoint {i+1}/{len(task_distance_turnpoints)}")

            # Calculate center distance incrementally
            prev_tp = task_distance_turnpoints[i - 1]
            leg_distance = geodesic(prev_tp.center, task_tp.center).meters / 1000.0
            cumulative_center += leg_distance

            # For optimized distance, calculate using all turnpoints up to current
            partial_turnpoints = task_distance_turnpoints[: i + 1]
            if len(partial_turnpoints) >= 2:
                cumulative_opt = (
                    optimized_distance(
                        partial_turnpoints,
                        angle_step=angle_step,
                        show_progress=False,
                        beam_width=beam_width,
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

    return turnpoint_details


def calculate_task_distances(
    task: Task,
    angle_step: int = DEFAULT_ANGLE_STEP,
    show_progress: bool = False,
    beam_width: int = DEFAULT_BEAM_WIDTH,
    num_iterations: int = DEFAULT_NUM_ITERATIONS,
) -> Dict[str, Any]:
    """Calculate both center and optimized distances for a task.

    Args:
        task: Task object
        angle_step: Angle step in degrees for optimization fallback
        show_progress: Whether to show progress indicators
        beam_width: Number of best candidates to keep at each DP stage
        num_iterations: Number of refinement iterations

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
        print("  🎯 Starting optimized calculation...")

    opt_dist = optimized_distance(
        distance_turnpoints,
        angle_step=angle_step,
        show_progress=show_progress,
        beam_width=beam_width,
        num_iterations=num_iterations,
    )

    if show_progress:
        print(f"  ✅ Optimized distance: {opt_dist/1000.0:.1f}km")

    # Convert to kilometers
    center_km = center_dist / 1000.0
    opt_km = opt_dist / 1000.0

    # Calculate savings
    savings_km, savings_percent = _calculate_savings(center_km, opt_km)

    if show_progress:
        print(
            f"  📊 Calculating cumulative distances for {len(turnpoints)} turnpoints..."
        )

    # Calculate turnpoint details
    turnpoint_details = _create_turnpoint_details(
        task.turnpoints, turnpoints, angle_step, beam_width, show_progress
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
        "beam_width": beam_width,
    }


def calculate_cumulative_distances(
    turnpoints: List[TaskTurnpoint],
    index: int,
    angle_step: int = DEFAULT_ANGLE_STEP,
    beam_width: int = DEFAULT_BEAM_WIDTH,
) -> Tuple[float, float]:
    """Calculate cumulative distances up to a specific turnpoint index.

    Args:
        turnpoints: List of TaskTurnpoint objects
        index: Index of the turnpoint (0-based)
        angle_step: Angle step for optimization calculations (fallback only)
        beam_width: Number of best candidates to keep at each DP stage

    Returns:
        Tuple of (center_distance_km, optimized_distance_km)
    """
    if index == 0 or len(turnpoints) <= 1:
        return 0.0, 0.0

    partial_turnpoints = turnpoints[: index + 1]
    center_dist = distance_through_centers(partial_turnpoints) / 1000.0
    opt_dist = (
        optimized_distance(
            partial_turnpoints,
            angle_step=angle_step,
            show_progress=False,
            beam_width=beam_width,
            num_iterations=DEFAULT_NUM_ITERATIONS,
        )
        / 1000.0
    )

    return center_dist, opt_dist


def optimized_route_coordinates(
    turnpoints: List[TaskTurnpoint],
    task_turnpoints=None,  # Kept for backward compatibility
    angle_step: int = DEFAULT_ANGLE_STEP,
    beam_width: int = DEFAULT_BEAM_WIDTH,
    num_iterations: int = DEFAULT_NUM_ITERATIONS,
) -> List[Tuple[float, float]]:
    """Compute the fully optimized route coordinates through turnpoints using iterative refinement.

    This algorithm finds the shortest possible route through all turnpoint cylinders
    and returns the actual coordinates of the optimal path using dynamic programming
    with beam search and iterative refinement to reduce the look-ahead bias.

    The iterative refinement approach performs multiple optimization passes to
    avoid the systematic bias of assuming the next target is at the center
    of the next turnpoint.

    Args:
        turnpoints: List[TaskTurnpoint] objects
        task_turnpoints: Optional list of original task turnpoints with type information
                         (kept for backward compatibility)
        angle_step: Angle step in degrees for perimeter point generation (fallback only)
        beam_width: Number of best candidates to keep at each DP stage
        num_iterations: Number of refinement iterations

    Returns:
        List of (lat, lon) tuples representing the optimized route coordinates
    """
    _, route_coordinates = calculate_iteratively_refined_route(
        turnpoints,
        num_iterations=num_iterations,
        angle_step=angle_step,
        show_progress=False,
        beam_width=beam_width,
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


def _find_sss_turnpoint(task_turnpoints) -> Optional[Tuple[int, Any]]:
    """Find the SSS turnpoint in a task.

    Args:
        task_turnpoints: List of task turnpoints

    Returns:
        Tuple of (index, turnpoint) or None if not found
    """
    for i, tp in enumerate(task_turnpoints):
        if hasattr(tp, "type") and tp.type and tp.type.value == "SSS":
            return i, tp
    return None


def _get_first_tp_after_sss_point(
    task_turnpoints, sss_index: int, route_coordinates: List[Tuple[float, float]]
) -> Optional[Tuple[Dict[str, float], Tuple[float, float]]]:
    """Get the first turnpoint after SSS and its route point.

    Args:
        task_turnpoints: List of task turnpoints
        sss_index: Index of the SSS turnpoint
        route_coordinates: List of route coordinates

    Returns:
        Tuple of (turnpoint_dict, route_point) or None if not available
    """
    if sss_index + 1 >= len(task_turnpoints):
        return None

    next_tp = task_turnpoints[sss_index + 1]
    next_tp_dict = {
        "lat": next_tp.waypoint.lat,
        "lon": next_tp.waypoint.lon,
    }

    # Determine the optimal point on the first TP after SSS from the route
    route_point = None
    if len(route_coordinates) > 1:
        # Route starts with takeoff, then first TP after SSS
        route_point = route_coordinates[1]
    else:
        # Fallback to center coordinates
        route_point = (next_tp_dict["lat"], next_tp_dict["lon"])

    return next_tp_dict, route_point


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
    sss_result = _find_sss_turnpoint(task_turnpoints)
    if not sss_result:
        return None

    sss_index, tp = sss_result

    # Extract SSS center and radius
    sss_tp = {
        "lat": tp.waypoint.lat,
        "lon": tp.waypoint.lon,
        "radius": tp.radius,
    }

    # Get first turnpoint after SSS
    next_tp_result = _get_first_tp_after_sss_point(
        task_turnpoints, sss_index, route_coordinates
    )
    if not next_tp_result:
        return None

    first_tp_after_sss, first_tp_after_sss_route_point = next_tp_result

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


def calculate_iteratively_refined_route(
    turnpoints: List[TaskTurnpoint],
    num_iterations: int = DEFAULT_NUM_ITERATIONS,
    angle_step: int = DEFAULT_ANGLE_STEP,
    show_progress: bool = False,
    beam_width: int = DEFAULT_BEAM_WIDTH,
) -> Tuple[float, List[Tuple[float, float]]]:
    """Calculate optimized route with iterative refinement to reduce look-ahead bias.

    This function implements a multi-pass optimization approach:
    1. First pass: Use cylinder centers as targets for look-ahead (standard approach)
    2. Subsequent passes: Use previously calculated optimal points as look-ahead targets
    3. Continue for a fixed number of iterations or until convergence

    This reduces the systematic bias created by always targeting the center of the next
    cylinder instead of its optimal entry point.

    Args:
        turnpoints: List of TaskTurnpoint objects
        num_iterations: Number of refinement iterations to perform
        angle_step: Angle step in degrees for perimeter point generation
        show_progress: Whether to show progress indicators
        beam_width: Number of best candidates to keep at each DP stage

    Returns:
        Tuple of (optimized_distance_meters, route_coordinates)
    """
    if len(turnpoints) < 2:
        distance = 0.0
        path = [(tp.center[0], tp.center[1]) for tp in turnpoints]
        return distance, path

    # Initialize with standard optimization (using centers as look-ahead targets)
    if show_progress:
        print(f"    🔄 Initial optimization pass (using center look-ahead)...")

    current_distance, current_route = _compute_optimal_route_dp(
        turnpoints,
        angle_step=angle_step,
        show_progress=show_progress,
        return_path=True,
        beam_width=beam_width,
    )

    # Store initial results
    best_distance = current_distance
    best_route = current_route

    # Perform iterative refinement
    for iteration in range(1, num_iterations):
        if show_progress:
            print(f"    🔄 Refinement iteration {iteration}/{num_iterations-1}...")

        # Create modified turnpoints that use previous optimal points as targets
        refined_turnpoints = _create_refined_turnpoints(turnpoints, current_route)

        # Run optimization with updated look-ahead targets
        new_distance, new_route = _compute_optimal_route_with_refined_targets(
            refined_turnpoints,
            current_route,
            angle_step=angle_step,
            show_progress=show_progress,
            beam_width=beam_width,
        )

        # Check for improvement
        if new_distance < best_distance:
            best_distance = new_distance
            best_route = new_route
            current_route = new_route

            if show_progress:
                print(f"    ✅ Improved distance: {best_distance/1000.0:.3f}km")
        else:
            if show_progress:
                print(f"    ⚠️ No improvement in iteration {iteration}, stopping")
            break

    return best_distance, best_route


def _create_refined_turnpoints(
    turnpoints: List[TaskTurnpoint], previous_route: List[Tuple[float, float]]
) -> List[TaskTurnpoint]:
    """Create turnpoints with refined target points based on previous optimization.

    Args:
        turnpoints: Original turnpoints
        previous_route: Previously calculated optimal route coordinates

    Returns:
        List of turnpoints with refined target information
    """
    # Create a deep copy to avoid modifying originals
    refined_turnpoints = []

    for i, tp in enumerate(turnpoints):
        new_tp = TaskTurnpoint(tp.center[0], tp.center[1], tp.radius)
        refined_turnpoints.append(new_tp)

    return refined_turnpoints


def _compute_optimal_route_with_refined_targets(
    turnpoints: List[TaskTurnpoint],
    previous_route: List[Tuple[float, float]],
    angle_step: int = DEFAULT_ANGLE_STEP,
    show_progress: bool = False,
    beam_width: int = DEFAULT_BEAM_WIDTH,
) -> Tuple[float, List[Tuple[float, float]]]:
    """Compute optimal route using previous route points as look-ahead targets.

    This function modifies the standard dynamic programming approach to use
    previously calculated optimal points as look-ahead targets, rather than
    always using the center of the next turnpoint.

    Args:
        turnpoints: List of TaskTurnpoint objects
        previous_route: Previously calculated optimal route coordinates
        angle_step: Angle step in degrees for perimeter point generation
        show_progress: Whether to show progress indicators
        beam_width: Number of best candidates to keep at each DP stage

    Returns:
        Tuple of (optimized_distance_meters, route_coordinates)
    """
    if show_progress:
        print("    🎯 Using refined targets for DP optimization...")

    # Initialize DP structure
    dp = _init_dp_structure(turnpoints)

    # DP forward pass with refined targets
    for i in range(1, len(turnpoints)):
        if show_progress:
            print(f"    ⚡ DP stage {i}/{len(turnpoints)-1}")

        # Get the look-ahead point from the previous route
        next_target = None
        if i < len(turnpoints) - 1 and i < len(previous_route) - 1:
            next_target = previous_route[i + 1]
        else:
            # Fallback to center for last turnpoint or if route is incomplete
            next_target = turnpoints[i].center if i < len(turnpoints) else None

        # Process this stage using the refined target for look-ahead
        dp[i] = _process_dp_stage_with_refined_target(
            dp, i, turnpoints, next_target, beam_width, show_progress
        )

    # Find the best final solution
    final_candidates = dp[-1]
    if not final_candidates:
        return 0.0, []

    best_point, (best_distance, _) = min(
        final_candidates.items(), key=lambda kv: kv[1][0]
    )

    if show_progress:
        print(f"    ✅ Refined DP route: {best_distance/1000.0:.3f}km")

    # Reconstruct path
    route_points = _backtrack_path(dp, best_point, turnpoints)

    return best_distance, route_points


def _process_dp_stage_with_refined_target(
    dp: List[defaultdict],
    i: int,
    turnpoints: List[TaskTurnpoint],
    next_target: Optional[Tuple[float, float]],
    beam_width: int,
    show_progress: bool,
) -> defaultdict:
    """Process one stage of the DP calculation using refined target for look-ahead.

    This modified version of _process_dp_stage uses the pre-calculated next target
    point instead of always using the center of the next turnpoint.

    Args:
        dp: The DP structure
        i: Current stage index
        turnpoints: List of TaskTurnpoint objects
        next_target: Pre-calculated target point for the next turnpoint
        beam_width: Number of best candidates to keep
        show_progress: Whether to show progress

    Returns:
        Updated DP structure for stage i
    """
    current_tp = turnpoints[i]

    # Use provided next_target if available, otherwise fall back to center
    if next_target is None:
        next_center = (
            turnpoints[i + 1].center if i + 1 < len(turnpoints) else current_tp.center
        )
    else:
        next_center = next_target

    new_candidates = defaultdict(lambda: (float("inf"), None))

    # For each candidate point from previous turnpoint
    for prev_point, (prev_dist, _) in dp[i - 1].items():
        # Find optimal entry point on current turnpoint
        if current_tp.radius == 0:
            optimal_point = current_tp.center
        else:
            optimal_point = current_tp.optimal_point(prev_point, next_center)

        # Calculate leg distance and total distance
        leg_distance = geodesic(prev_point, optimal_point).meters
        total_distance = prev_dist + leg_distance

        # Keep the best distance for this optimal point
        if total_distance < new_candidates[optimal_point][0]:
            new_candidates[optimal_point] = (total_distance, prev_point)

    # Beam search: keep only the best beam_width candidates
    if len(new_candidates) > beam_width:
        best_items = sorted(new_candidates.items(), key=lambda kv: kv[1][0])[
            :beam_width
        ]
        result = dict(best_items)
    else:
        result = dict(new_candidates)

    if show_progress:
        print(f"    📊 Keeping {len(result)} candidates")

    return result
