"""Distance calculation and route optimization for XCTrack tasks using WGS84 ellipsoid.

This module provides a unified, minimal interface for all distance-related calculations
in the pyxctsk package. It exposes the main public API for:
- Optimized route and distance calculations through turnpoint cylinders per
  FAI S7F §7 (Ding-Xie-Jiang alternating point-circle-point method)
- Earth-model aware distances (WGS84 ellipsoid default, FAI sphere R = 6371 km)
- SSS (Start of Speed Section) entry point and info calculations
- Cumulative and per-leg task distance calculations
- Configuration of optimization parameters

All core logic is implemented in focused submodules; this module re-exports
main entry points for use by other code and CLI tools.
"""

# Import all the public API from the refactored modules
from .optimization_config import (
    CONVERGENCE_EPSILON_M,
    DEFAULT_ANGLE_STEP,
    DEFAULT_BEAM_WIDTH,
    DEFAULT_NUM_ITERATIONS,
    get_optimization_config,
)
from .route_optimization import (
    calculate_iteratively_refined_route,
    optimized_distance,
    optimized_route_coordinates,
)
from .sss_calculations import calculate_optimal_sss_entry_point, calculate_sss_info
from .task_distances import (
    calculate_cumulative_distances,
    calculate_task_distances,
)
from .turnpoint import (
    FAI_SPHERE_RADIUS_M,
    TaskTurnpoint,
    distance_through_centers,
    geodesic_distance,
)

# Export all the main public functions and classes
__all__ = [
    # Core classes
    "TaskTurnpoint",
    # Main distance calculation functions
    "optimized_distance",
    "optimized_route_coordinates",
    "distance_through_centers",
    "geodesic_distance",
    "calculate_task_distances",
    "calculate_cumulative_distances",
    # SSS specific functions
    "calculate_sss_info",
    "calculate_optimal_sss_entry_point",
    # Configuration
    "get_optimization_config",
    "CONVERGENCE_EPSILON_M",
    "DEFAULT_ANGLE_STEP",
    "DEFAULT_BEAM_WIDTH",
    "DEFAULT_NUM_ITERATIONS",
    "FAI_SPHERE_RADIUS_M",
    # Advanced functions
    "calculate_iteratively_refined_route",
]
