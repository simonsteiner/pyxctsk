"""Route optimization algorithms for XCTrack tasks using dynamic programming (DP).

This module provides core algorithms to compute the shortest possible route through a sequence of paragliding/hang gliding task turnpoints, accounting for cylinder radii, goal lines, and look-ahead bias. It implements:

- True dynamic programming with beam search to avoid greedy local minima
- Iterative refinement to reduce systematic bias from always targeting cylinder centers
- A single DP core (`_run_dp`) whose look-ahead target is a pluggable strategy
- Utilities for reconstructing optimal paths and handling goal lines

All algorithms operate on immutable TaskTurnpoint dataclasses and use geodesic distance calculations. The main entry point is `calculate_iteratively_refined_route`, which performs multi-pass optimization for best accuracy.
"""

from collections import defaultdict
from collections.abc import Callable, Sequence

from geopy.distance import geodesic

from .optimization_config import get_optimization_config
from .turnpoint import TaskTurnpoint, TurnpointGeometry

#: A look-ahead strategy maps a DP stage index to the target point used when
#: choosing the optimal entry point on that stage's turnpoint.
LookaheadStrategy = Callable[[int], tuple[float, float]]


def _center_lookahead(turnpoints: Sequence[TurnpointGeometry]) -> LookaheadStrategy:
    """Build the standard look-ahead strategy targeting cylinder centers.

    Args:
        turnpoints (Sequence[TurnpointGeometry]): The task turnpoints.

    Returns:
        LookaheadStrategy: Strategy returning the next turnpoint's center, or
        the current turnpoint's center for the final stage.
    """

    def target(i: int) -> tuple[float, float]:
        if i + 1 < len(turnpoints):
            return turnpoints[i + 1].center
        return turnpoints[i].center

    return target


def _route_lookahead(
    turnpoints: Sequence[TurnpointGeometry],
    previous_route: Sequence[tuple[float, float]],
) -> LookaheadStrategy:
    """Build a refined look-ahead strategy targeting a previous route's points.

    Using the previously optimized route as the look-ahead target (instead of
    cylinder centers) reduces the systematic bias of always aiming at the
    center of the next cylinder.

    Args:
        turnpoints (Sequence[TurnpointGeometry]): The task turnpoints.
        previous_route (Sequence[Tuple[float, float]]): Previously calculated
            optimal route coordinates.

    Returns:
        LookaheadStrategy: Strategy returning the previous route's point for
        the next stage, falling back to the current turnpoint's center for the
        final stage or an incomplete route.
    """

    def target(i: int) -> tuple[float, float]:
        if i < len(turnpoints) - 1 and i < len(previous_route) - 1:
            return previous_route[i + 1]
        return turnpoints[i].center

    return target


def _init_dp_structure(turnpoints: Sequence[TurnpointGeometry]) -> list[defaultdict]:
    """Initialize the dynamic programming data structure.

    Args:
        turnpoints (Sequence[TurnpointGeometry]): List of turnpoints.

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
    turnpoints: Sequence[TurnpointGeometry],
    next_target: tuple[float, float],
    beam_width: int,
) -> defaultdict:
    """Process one stage of the dynamic programming calculation.

    Args:
        dp (List[defaultdict]): The DP structure.
        i (int): Current stage index.
        turnpoints (Sequence[TurnpointGeometry]): List of turnpoints.
        next_target (Tuple[float, float]): Look-ahead target point for this stage.
        beam_width (int): Number of best candidates to keep.

    Returns:
        defaultdict: Updated DP structure for stage i.
    """
    current_tp = turnpoints[i]
    new_candidates: defaultdict = defaultdict(lambda: (float("inf"), None))

    # For each candidate point from previous turnpoint
    for prev_point, (prev_dist, _) in dp[i - 1].items():
        # The turnpoint resolves its own geometry (cylinder, goal line, or
        # zero-radius center) behind the TurnpointGeometry seam.
        optimal_point = current_tp.optimal_point(prev_point, next_target)

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
    return new_candidates


def _backtrack_path(
    dp: list[defaultdict],
    best_point: tuple[float, float],
    turnpoints: Sequence[TurnpointGeometry],
) -> list[tuple[float, float]]:
    """Backtrack through the DP structure to reconstruct the optimal path.

    Args:
        dp (List[defaultdict]): The DP structure.
        best_point (Tuple[float, float]): The best final point.
        turnpoints (Sequence[TurnpointGeometry]): List of turnpoints.

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


def _run_dp(
    turnpoints: Sequence[TurnpointGeometry],
    lookahead: LookaheadStrategy,
    beam_width: int,
    show_progress: bool = False,
) -> tuple[float, list[tuple[float, float]]]:
    """Run the DP route search with a pluggable look-ahead strategy.

    This is the single DP core: it initializes the DP structure, runs the
    forward pass (using ``lookahead`` to pick each stage's target point),
    selects the best final candidate, and backtracks the optimal path.

    Args:
        turnpoints (Sequence[TurnpointGeometry]): List of turnpoints.
        lookahead (LookaheadStrategy): Maps a stage index to its look-ahead
            target point (e.g. cylinder centers on the first pass, a previous
            route's points on refinement passes).
        beam_width (int): Number of best candidates to keep at each stage.
        show_progress (bool): Whether to show progress indicators.

    Returns:
        Tuple[float, List[Tuple[float, float]]]: Tuple of
        (optimized_distance_meters, route_coordinates).
    """
    dp = _init_dp_structure(turnpoints)

    # DP forward pass
    for i in range(1, len(turnpoints)):
        if show_progress:
            print(f"    ⚡ DP stage {i}/{len(turnpoints) - 1}")

        dp[i] = _process_dp_stage(dp, i, turnpoints, lookahead(i), beam_width)

    # Find the best final solution
    final_candidates = dp[-1]
    if not final_candidates:
        return 0.0, []

    best_point, (best_distance, _) = min(
        final_candidates.items(), key=lambda kv: kv[1][0]
    )

    if show_progress:
        print(f"    ✅ DP route: {best_distance / 1000.0:.3f}km")

    return best_distance, _backtrack_path(dp, best_point, turnpoints)


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

    best_distance, best_route = _run_dp(
        turnpoints,
        _center_lookahead(turnpoints),
        config["beam_width"],
        show_progress=show_progress,
    )
    current_route = best_route

    # Perform iterative refinement
    for iteration in range(1, config["num_iterations"]):
        if show_progress:
            print(
                f"    🔄 Refinement iteration {iteration}/{config['num_iterations'] - 1}..."
            )

        # Re-run the DP using the previous route's points as look-ahead targets
        new_distance, new_route = _run_dp(
            turnpoints,
            _route_lookahead(turnpoints, current_route),
            config["beam_width"],
            show_progress=show_progress,
        )

        # Check for improvement
        if new_distance < best_distance:
            best_distance = new_distance
            best_route = new_route
            current_route = new_route

            if show_progress:
                print(f"    ✅ Improved distance: {best_distance / 1000.0:.3f}km")
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
    task_turnpoints: object | None = None,  # Kept for backward compatibility
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
