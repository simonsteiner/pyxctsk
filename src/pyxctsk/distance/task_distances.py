"""Task distance calculations and turnpoint conversion utilities for XCTrack tasks.

This module provides functions to:
- Convert task turnpoints to internal representations for distance calculations
- Compute center and optimized (shortest possible) task distances
- Calculate cumulative and per-leg distances for each turnpoint
- Support both cylinder and line goal types, with correct handling of goal definitions
- Return detailed distance breakdowns for use in analysis and visualization
"""

from typing import Any

from ..model.task import Task
from .goal_line import goal_line_length_from_turnpoints
from .route_optimization import OptimizedRoute, calculate_iteratively_refined_route
from .turnpoint import TaskTurnpoint, distance_through_centers, geodesic_distance


def task_to_turnpoints(task: Task) -> list[TaskTurnpoint]:
    """Convert a task's turnpoints into the cylinders distance code works on.

    The one place that reads a goal's type off the model and turns it into
    geometry: a LINE goal becomes a zero-radius point carrying the goal-line
    length, anything else stays a cylinder, and every turnpoint inherits the
    task's earth model.

    Args:
        task (Task): Task object.

    Returns:
        List[TaskTurnpoint]: List of TaskTurnpoint objects.
    """
    # Determine if there's a goal and its type
    goal_type = None
    goal_line_length = None  # None unless the goal is a line

    # Process goal if there are turnpoints
    if task.turnpoints and task.goal:
        goal_type = task.goal.type.value if task.goal.type else "CYLINDER"

        # A goal line's length is always twice the last turnpoint's radius.
        if goal_type == "LINE":
            goal_line_length = goal_line_length_from_turnpoints(task.turnpoints)

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
                        goal_line_length=goal_line_length,
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


def _calculate_savings(center_km: float, opt_km: float) -> tuple[float, float]:
    """Calculate distance savings in km and percentage.

    Args:
        center_km (float): Center distance in km.
        opt_km (float): Optimized distance in km.

    Returns:
        Tuple[float, float]: Tuple of (savings_km, savings_percent).
    """
    savings_km = center_km - opt_km
    savings_percent = (savings_km / center_km * 100) if center_km > 0 else 0.0
    return savings_km, savings_percent


def _create_turnpoint_details(
    task_turnpoints,
    task_distance_turnpoints: list[TaskTurnpoint],
    route: OptimizedRoute,
) -> list[dict[str, Any]]:
    """Create detailed turnpoint information including cumulative distances.

    The optimized column is read off ``route`` rather than recomputed. Both
    are distances along one route, so a turnpoint's cumulative optimized
    distance is by construction a prefix of the task's optimized distance —
    which is what re-optimizing a truncated task did not give: the optimizer
    treats the last circle of whatever it is handed as the finish, so the
    truncated optimum bent the route towards turnpoint i instead of passing
    through it, understating the prefix by up to 5 km on the reference tasks.

    Args:
        task_turnpoints: Original task turnpoints.
        task_distance_turnpoints (List[TaskTurnpoint]): Distance calculation turnpoints.
        route (OptimizedRoute): The task's optimized route.

    Returns:
        List[Dict[str, Any]]: List of dictionaries with turnpoint details.
    """
    turnpoint_details = []
    cumulative_center = 0.0
    cumulative_optimized = route.cumulative_m()

    for i, (tp, task_tp) in enumerate(zip(task_turnpoints, task_distance_turnpoints)):
        # Calculate cumulative distances for all turnpoints
        if i > 0:
            # Calculate center distance incrementally
            prev_tp = task_distance_turnpoints[i - 1]
            leg_distance = (
                geodesic_distance(prev_tp.center, task_tp.center, task_tp.earth_model)
                / 1000.0
            )
            cumulative_center += leg_distance

        cumulative_opt = (
            cumulative_optimized[i] / 1000.0 if i < len(cumulative_optimized) else 0.0
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
    show_progress: bool = False,
    num_iterations: int | None = None,
) -> dict[str, Any]:
    """Calculate both center and optimized distances for a task.

    Args:
        task (Task): Task object.
        show_progress (bool): Whether to show progress indicators.
        num_iterations (Optional[int]): Maximum number of alternating sweeps.

    Returns:
        Dict[str, Any]: Dictionary containing distance calculations and turnpoint details.
    """
    # Convert to TaskTurnpoint objects
    turnpoints = task_to_turnpoints(task)

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
        print(f"  ✅ Center distance: {center_dist / 1000.0:.1f}km")
        print("  🎯 Starting optimized calculation...")

    # One optimizer run for the whole task; the per-turnpoint column below is a
    # projection of this route, not a second optimization per prefix.
    route = calculate_iteratively_refined_route(
        distance_turnpoints,
        show_progress=show_progress,
        num_iterations=num_iterations,
    )
    opt_dist = route.total_m

    if show_progress:
        print(f"  ✅ Optimized distance: {opt_dist / 1000.0:.1f}km")

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
        route,
    )

    if show_progress:
        print("  ✅ All calculations complete")

    return {
        "center_distance_km": round(center_km, 1),
        "optimized_distance_km": round(opt_km, 1),
        "savings_km": round(savings_km, 1),
        "savings_percent": round(savings_percent, 1),
        "turnpoints": turnpoint_details,
    }
