"""Task distance calculations and turnpoint conversion utilities."""

from typing import Any, Dict, List, Optional, Tuple

from .task import Task, TurnpointType
from .turnpoint import TaskTurnpoint, distance_through_centers
from .route_optimization import calculate_iteratively_refined_route
from .optimization_config import get_optimization_config


def _task_to_turnpoints(task: Task) -> List[TaskTurnpoint]:
    """Convert Task turnpoints to TaskTurnpoint objects.

    Args:
        task: Task object

    Returns:
        List of TaskTurnpoint objects
    """
    # Determine if there's a goal and its type
    goal_type = None
    goal_line_length = None  # No default goal line length

    # Find ESS turnpoint (if any)
    ess_tp = None
    ess_tp_index = -1
    for i, tp in enumerate(task.turnpoints):
        if tp.type == TurnpointType.ESS:
            ess_tp = tp
            ess_tp_index = i
            break

    # Process goal if there are turnpoints
    if task.turnpoints:
        # Check if ESS is at the goal (last turnpoint)
        is_ess_goal = ess_tp_index == len(task.turnpoints) - 1

        # Goal can be explicitly defined or implicitly defined by the last turnpoint
        if task.goal:
            # Explicit goal definition
            goal_type = task.goal.type.value if task.goal.type else "CYLINDER"

            # For goal LINE type, get line length from goal or last turnpoint
            if goal_type == "LINE":
                # Use goal line length if specified, otherwise calculate from turnpoint radius
                if task.goal.line_length is not None:
                    goal_line_length = task.goal.line_length
                elif len(task.turnpoints) > 0:
                    last_tp = task.turnpoints[-1]
                    goal_line_length = float(last_tp.radius * 2)

    result = []

    for i, tp in enumerate(task.turnpoints):
        # Check if this is the goal turnpoint (last one)
        if i == len(task.turnpoints) - 1:
            # This is the goal turnpoint (last one in the list)
            if goal_type == "LINE":
                # This is a goal line turnpoint
                if goal_line_length is None and tp.radius > 0:
                    # Use last turnpoint radius to determine goal line length if not specified
                    goal_line_length = float(tp.radius * 2)

                result.append(
                    TaskTurnpoint(
                        lat=tp.waypoint.lat,
                        lon=tp.waypoint.lon,
                        radius=0,  # Goal lines have 0 radius (no cylinder)
                        goal_type=goal_type,
                        goal_line_length=goal_line_length,
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
                    )
                )
        else:
            # Regular turnpoint
            result.append(
                TaskTurnpoint(
                    lat=tp.waypoint.lat, lon=tp.waypoint.lon, radius=tp.radius
                )
            )

    return result


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
    angle_step: Optional[int] = None,
    beam_width: Optional[int] = None,
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
    from .distance import optimized_distance  # Import here to avoid circular imports

    config = get_optimization_config(angle_step, beam_width)
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
            from geopy.distance import geodesic

            leg_distance = geodesic(prev_tp.center, task_tp.center).meters / 1000.0
            cumulative_center += leg_distance

            # For optimized distance, calculate using all turnpoints up to current
            partial_turnpoints = task_distance_turnpoints[: i + 1]
            if len(partial_turnpoints) >= 2:
                cumulative_opt = (
                    optimized_distance(
                        partial_turnpoints,
                        angle_step=config["angle_step"],
                        show_progress=False,
                        beam_width=config["beam_width"],
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
    angle_step: Optional[int] = None,
    show_progress: bool = False,
    beam_width: Optional[int] = None,
    num_iterations: Optional[int] = None,
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
    from .distance import optimized_distance  # Import here to avoid circular imports

    config = get_optimization_config(angle_step, beam_width, num_iterations)
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
        angle_step=config["angle_step"],
        show_progress=show_progress,
        beam_width=config["beam_width"],
        num_iterations=config["num_iterations"],
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
        task.turnpoints,
        turnpoints,
        config["angle_step"],
        config["beam_width"],
        show_progress,
    )

    if show_progress:
        print("  ✅ All calculations complete")

    return {
        "center_distance_km": round(center_km, 1),
        "optimized_distance_km": round(opt_km, 1),
        "savings_km": round(savings_km, 1),
        "savings_percent": round(savings_percent, 1),
        "turnpoints": turnpoint_details,
        "optimization_angle_step": config["angle_step"],
        "beam_width": config["beam_width"],
    }


def calculate_cumulative_distances(
    turnpoints: List[TaskTurnpoint],
    index: int,
    angle_step: Optional[int] = None,
    beam_width: Optional[int] = None,
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
    from .distance import optimized_distance  # Import here to avoid circular imports

    if index == 0 or len(turnpoints) <= 1:
        return 0.0, 0.0

    config = get_optimization_config(angle_step, beam_width)

    partial_turnpoints = turnpoints[: index + 1]
    center_dist = distance_through_centers(partial_turnpoints) / 1000.0
    opt_dist = (
        optimized_distance(
            partial_turnpoints,
            angle_step=config["angle_step"],
            show_progress=False,
            beam_width=config["beam_width"],
        )
        / 1000.0
    )

    return center_dist, opt_dist
