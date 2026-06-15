"""Route optimization algorithms for XCTrack tasks using dynamic programming (DP).

This module provides core algorithms to compute the shortest possible route through a sequence of paragliding/hang gliding task turnpoints, accounting for cylinder radii, goal lines, and look-ahead bias. It implements:

- True dynamic programming with beam search to avoid greedy local minima
- Iterative refinement to reduce systematic bias from always targeting cylinder centers
- Support for both standard and refined look-ahead targets
- Utilities for reconstructing optimal paths and handling goal lines

All algorithms operate on immutable TaskTurnpoint dataclasses and use geodesic distance calculations. The main entry point is `calculate_iteratively_refined_route`, which performs multi-pass optimization for best accuracy.
"""

from collections import defaultdict

from geopy.distance import geodesic

from .optimization_config import DEFAULT_BEAM_WIDTH, get_optimization_config
from .turnpoint import TaskTurnpoint, TurnpointGeometry


def _init_dp_structure(turnpoints: list[TurnpointGeometry]) -> list[defaultdict]:
    """Initialize the dynamic programming data structure.

    Args:
        turnpoints (List[TaskTurnpoint]): List of TaskTurnpoint objects.

    Returns:
        List[defaultdict]: List of defaultdicts for DP computation.
    """
    # dp[i] maps candidate points on turnpoint i -> (best_distance, parent_point)
    dp: list[defaultdict] = [
        defaultdict(lambda: (float("inf"), None)) for _ in turnpoints
    ]

    # Initialize: start at takeoff center with distance 0
    dp[0][turnpoints[0].center] = (0.0, None)
    return dp


def _process_dp_stage(
    dp: list[defaultdict],
    i: int,
    turnpoints: list[TurnpointGeometry],
    beam_width: int,
    show_progress: bool,
) -> defaultdict:
    """Process one stage of the dynamic programming calculation.

    Args:
        dp (List[defaultdict]): The DP structure.
        i (int): Current stage index.
        turnpoints (List[TaskTurnpoint]): List of TaskTurnpoint objects.
        beam_width (int): Number of best candidates to keep.
        show_progress (bool): Whether to show progress.

    Returns:
        defaultdict: Updated DP structure for stage i.
    """
    current_tp = turnpoints[i]
    next_center = (
        turnpoints[i + 1].center if i + 1 < len(turnpoints) else current_tp.center
    )
    new_candidates: defaultdict = defaultdict(lambda: (float("inf"), None))

    # For each candidate point from previous turnpoint
    for prev_point, (prev_dist, _) in dp[i - 1].items():
        # The turnpoint resolves its own geometry (cylinder, goal line, or
        # zero-radius center) behind the TurnpointGeometry seam.
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
        result: defaultdict = defaultdict(lambda: (float("inf"), None))
        result.update(dict(best_items))
        return result
    else:
        return new_candidates


def _process_dp_stage_with_refined_target(
    dp: list[defaultdict],
    i: int,
    turnpoints: list[TurnpointGeometry],
    next_target: tuple[float, float] | None,
    beam_width: int,
    show_progress: bool,
) -> defaultdict:
    """Process one stage of the DP calculation using refined target for look-ahead.

    This modified version of _process_dp_stage uses the pre-calculated next target
    point instead of always using the center of the next turnpoint.

    Args:
        dp (List[defaultdict]): The DP structure.
        i (int): Current stage index.
        turnpoints (List[TaskTurnpoint]): List of TaskTurnpoint objects.
        next_target (Optional[Tuple[float, float]]): Pre-calculated target point for the next turnpoint.
        beam_width (int): Number of best candidates to keep.
        show_progress (bool): Whether to show progress.

    Returns:
        defaultdict: Updated DP structure for stage i.
    """
    current_tp = turnpoints[i]

    # Use provided next_target if available, otherwise fall back to center
    if next_target is None:
        next_center = (
            turnpoints[i + 1].center if i + 1 < len(turnpoints) else current_tp.center
        )
    else:
        next_center = next_target

    new_candidates: defaultdict = defaultdict(lambda: (float("inf"), None))

    # For each candidate point from previous turnpoint
    for prev_point, (prev_dist, _) in dp[i - 1].items():
        # Find optimal entry point on current turnpoint via the geometry seam.
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
        result: defaultdict = defaultdict(lambda: (float("inf"), None))
        result.update(dict(best_items))
        return result
    else:
        return new_candidates

    if show_progress:
        print(f"    📊 Keeping {len(result)} candidates")


def _backtrack_path(
    dp: list[defaultdict],
    best_point: tuple[float, float],
    turnpoints: list[TurnpointGeometry],
) -> list[tuple[float, float]]:
    """Backtrack through the DP structure to reconstruct the optimal path.

    Args:
        dp (List[defaultdict]): The DP structure.
        best_point (Tuple[float, float]): The best final point.
        turnpoints (List[TaskTurnpoint]): List of TaskTurnpoint objects.

    Returns:
        List[Tuple[float, float]]: List of coordinates forming the optimal path.
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
    turnpoints: list[TurnpointGeometry],
    show_progress: bool = False,
    return_path: bool = False,
    beam_width: int = DEFAULT_BEAM_WIDTH,
) -> tuple[float, list[tuple[float, float]]]:
    """Compute optimal route using dynamic programming with beam search.

    This method uses DP to consider multiple candidate paths and avoid
    the greedy local optimization trap that can occur with large cylinders.

    Args:
        turnpoints (List[TaskTurnpoint]): List of TaskTurnpoint objects.
        show_progress (bool): Whether to show progress indicators.
        return_path (bool): Whether to return the actual path coordinates.
        beam_width (int): Number of best candidates to keep at each stage.

    Returns:
        Tuple[float, List[Tuple[float, float]]]: Tuple of (optimized_distance_meters, route_coordinates).
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


def _compute_optimal_route_dp(
    turnpoints: list[TaskTurnpoint],
    task_turnpoints=None,
    angle_step: int = 10,
    show_progress: bool = False,
    return_path: bool = False,
    beam_width: int = DEFAULT_BEAM_WIDTH,
) -> tuple[float, list[tuple[float, float]]]:
    """Core dynamic programming algorithm for computing optimal routes through turnpoints.

    Args:
        turnpoints (List[TaskTurnpoint]): List of TaskTurnpoint objects.
        task_turnpoints: Optional list of original task turnpoints with type information.
        angle_step (int): Angle step in degrees for perimeter point generation.
        show_progress (bool): Whether to show progress indicators.
        return_path (bool): Whether to return the actual path coordinates.
        beam_width (int): Number of best candidates to keep at each DP stage.

    Returns:
        Tuple[float, List[Tuple[float, float]]]: Tuple of (optimized_distance_meters, route_coordinates). If return_path is False, route_coordinates will be empty.
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

    # Check if the last turnpoint is a goal line
    if turnpoints[-1].goal_type == "LINE" and show_progress:
        print("    🏁 Last turnpoint is a goal line")

    # Use optimized approach with true DP and beam search
    return _compute_optimal_route_with_beam_search(
        turnpoints, show_progress, return_path, beam_width
    )


def _create_refined_turnpoints(
    turnpoints: list[TaskTurnpoint], previous_route: list[tuple[float, float]]
) -> list[TaskTurnpoint]:
    """Create turnpoints with refined target points based on previous optimization.

    Args:
        turnpoints (List[TaskTurnpoint]): Original turnpoints.
        previous_route (List[Tuple[float, float]]): Previously calculated optimal route coordinates.

    Returns:
        List[TaskTurnpoint]: List of turnpoints with refined target information.
    """
    # Create a deep copy to avoid modifying originals
    refined_turnpoints = []

    for i, tp in enumerate(turnpoints):
        new_tp = TaskTurnpoint(tp.center[0], tp.center[1], tp.radius)
        refined_turnpoints.append(new_tp)

    return refined_turnpoints


def _compute_optimal_route_with_refined_targets(
    turnpoints: list[TaskTurnpoint],
    previous_route: list[tuple[float, float]],
    angle_step: int | None = None,
    show_progress: bool = False,
    beam_width: int | None = None,
) -> tuple[float, list[tuple[float, float]]]:
    """Compute optimal route using previous route points as look-ahead targets.

    This function modifies the standard dynamic programming approach to use
    previously calculated optimal points as look-ahead targets, rather than
    always using the center of the next turnpoint.

    Args:
        turnpoints (List[TaskTurnpoint]): List of TaskTurnpoint objects.
        previous_route (List[Tuple[float, float]]): Previously calculated optimal route coordinates.
        angle_step (Optional[int]): Angle step in degrees for perimeter point generation.
        show_progress (bool): Whether to show progress indicators.
        beam_width (Optional[int]): Number of best candidates to keep at each DP stage.

    Returns:
        Tuple[float, List[Tuple[float, float]]]: Tuple of (optimized_distance_meters, route_coordinates).
    """
    config = get_optimization_config(angle_step, beam_width)
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
            dp, i, turnpoints, next_target, config["beam_width"], show_progress
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


def calculate_iteratively_refined_route(
    turnpoints: list[TaskTurnpoint],
    num_iterations: int | None = None,
    angle_step: int | None = None,
    show_progress: bool = False,
    beam_width: int | None = None,
) -> tuple[float, list[tuple[float, float]]]:
    """Calculate optimized route with iterative refinement to reduce look-ahead bias.

    This function implements a multi-pass optimization approach:
      1. First pass: Use cylinder centers as targets for look-ahead (standard approach)
      2. Subsequent passes: Use previously calculated optimal points as look-ahead targets
      3. Continue for a fixed number of iterations or until convergence

    This reduces the systematic bias created by always targeting the center of the next
    cylinder instead of its optimal entry point.

    Args:
        turnpoints (List[TaskTurnpoint]): List of TaskTurnpoint objects.
        num_iterations (Optional[int]): Number of refinement iterations to perform.
        angle_step (Optional[int]): Angle step in degrees for perimeter point generation.
        show_progress (bool): Whether to show progress indicators.
        beam_width (Optional[int]): Number of best candidates to keep at each DP stage.

    Returns:
        Tuple[float, List[Tuple[float, float]]]: Tuple of (optimized_distance_meters, route_coordinates).
    """
    config = get_optimization_config(angle_step, beam_width, num_iterations)
    if len(turnpoints) < 2:
        distance = 0.0
        path = [(tp.center[0], tp.center[1]) for tp in turnpoints]
        return distance, path

    # Check if last turnpoint is a goal line
    if turnpoints[-1].goal_type == "LINE":
        if show_progress:
            print("    🏁 Task has a goal line finish")

    # Initialize with standard optimization (using centers as look-ahead targets)
    if show_progress:
        print("    🔄 Initial optimization pass (using center look-ahead)...")

    current_distance, current_route = _compute_optimal_route_dp(
        turnpoints,
        angle_step=config["angle_step"],
        show_progress=show_progress,
        return_path=True,
        beam_width=config["beam_width"],
    )

    # Store initial results
    best_distance = current_distance
    best_route = current_route

    # Perform iterative refinement
    for iteration in range(1, config["num_iterations"]):
        if show_progress:
            print(
                f"    🔄 Refinement iteration {iteration}/{config['num_iterations']-1}..."
            )

        # Create modified turnpoints that use previous optimal points as targets
        refined_turnpoints = _create_refined_turnpoints(turnpoints, current_route)

        # Run optimization with updated look-ahead targets
        new_distance, new_route = _compute_optimal_route_with_refined_targets(
            refined_turnpoints,
            current_route,
            angle_step=config["angle_step"],
            show_progress=show_progress,
            beam_width=config["beam_width"],
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


def optimized_distance(
    turnpoints: list[TaskTurnpoint],
    angle_step: int | None = None,
    show_progress: bool = False,
    beam_width: int | None = None,
    num_iterations: int | None = None,
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
    config = get_optimization_config(angle_step, beam_width, num_iterations)

    distance, _ = calculate_iteratively_refined_route(
        turnpoints,
        num_iterations=config["num_iterations"],
        angle_step=config["angle_step"],
        show_progress=show_progress,
        beam_width=config["beam_width"],
    )
    return distance


def optimized_route_coordinates(
    turnpoints: list[TaskTurnpoint],
    task_turnpoints=None,  # Kept for backward compatibility
    angle_step: int | None = None,
    beam_width: int | None = None,
    num_iterations: int | None = None,
) -> list[tuple[float, float]]:
    """Compute the fully optimized route coordinates through turnpoints using iterative refinement.

    This algorithm finds the shortest possible route through all turnpoint cylinders
    and returns the actual coordinates of the optimal path using dynamic programming
    with beam search and iterative refinement to reduce the look-ahead bias.

    The iterative refinement approach performs multiple optimization passes to
    avoid the systematic bias of assuming the next target is at the center
    of the next turnpoint.

    Args:
        turnpoints: list[TaskTurnpoint] objects
        task_turnpoints: Optional list of original task turnpoints with type information
                         (kept for backward compatibility)
        angle_step: Angle step in degrees for perimeter point generation (fallback only)
        beam_width: Number of best candidates to keep at each DP stage
        num_iterations: Number of refinement iterations

    Returns:
        List of (lat, lon) tuples representing the optimized route coordinates
    """
    config = get_optimization_config(angle_step, beam_width, num_iterations)

    _, route_coordinates = calculate_iteratively_refined_route(
        turnpoints,
        num_iterations=config["num_iterations"],
        angle_step=config["angle_step"],
        show_progress=False,
        beam_width=config["beam_width"],
    )
    return route_coordinates
