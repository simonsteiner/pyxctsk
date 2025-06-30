"""Distance calculation module using WGS84 ellipsoid and route optimization.

This module provides a simplified interface to the distance calculation functionality
that has been refactored into smaller, focused modules.
"""

from typing import Any, Dict, List, Optional, Tuple

# Import all the public API from the refactored modules
from .optimization_config import (
    DEFAULT_ANGLE_STEP,
    DEFAULT_BEAM_WIDTH,
    DEFAULT_NUM_ITERATIONS,
    get_optimization_config,
)
from .turnpoint import TaskTurnpoint, distance_through_centers
from .route_optimization import calculate_iteratively_refined_route
from .task_distances import (
    calculate_task_distances,
    calculate_cumulative_distances,
    _task_to_turnpoints,
)
from .sss_calculations import calculate_sss_info, calculate_optimal_sss_entry_point
from .task import Task


def optimized_distance(
    turnpoints: List[TaskTurnpoint],
    angle_step: Optional[int] = None,
    show_progress: bool = False,
    beam_width: Optional[int] = None,
    num_iterations: Optional[int] = None,
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
    turnpoints: List[TaskTurnpoint],
    task_turnpoints=None,  # Kept for backward compatibility
    angle_step: Optional[int] = None,
    beam_width: Optional[int] = None,
    num_iterations: Optional[int] = None,
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
    config = get_optimization_config(angle_step, beam_width, num_iterations)

    _, route_coordinates = calculate_iteratively_refined_route(
        turnpoints,
        num_iterations=config["num_iterations"],
        angle_step=config["angle_step"],
        show_progress=False,
        beam_width=config["beam_width"],
    )
    return route_coordinates


# Export all the main public functions and classes
__all__ = [
    # Core classes
    "TaskTurnpoint",
    # Main distance calculation functions
    "optimized_distance",
    "optimized_route_coordinates",
    "distance_through_centers",
    "calculate_task_distances",
    "calculate_cumulative_distances",
    # SSS specific functions
    "calculate_sss_info",
    "calculate_optimal_sss_entry_point",
    # Configuration
    "get_optimization_config",
    "DEFAULT_ANGLE_STEP",
    "DEFAULT_BEAM_WIDTH",
    "DEFAULT_NUM_ITERATIONS",
    # Advanced functions
    "calculate_iteratively_refined_route",
]
