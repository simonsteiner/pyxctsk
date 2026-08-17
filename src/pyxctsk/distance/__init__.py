"""Distance calculation and route optimization for XCTrack tasks.

This file is the package's interface: it re-exports, and holds no logic of its
own. Everything a caller outside the package needs is named here —

- optimized route and distance through turnpoint cylinders per FAI S7F §7
  (Ding–Xie–Jiang alternating point-circle-point method)
- earth-model aware distances (WGS84 ellipsoid default, FAI sphere R = 6371 km)
- SSS (Start of Speed Section) entry point and info
- cumulative and per-leg task distances
- the tunable optimization parameters

— while the work lives in focused submodules:

- :mod:`~pyxctsk.distance.turnpoint` — ``TaskTurnpoint``, the earth models, the
  local Transverse Mercator projection and the planar optimal point
- :mod:`~pyxctsk.distance.route_optimization` — the shortest path through the
  cylinders
- :mod:`~pyxctsk.distance.task_distances` — per-leg and cumulative distances
- :mod:`~pyxctsk.distance.sss` — Start-of-Speed-Section entry point and info
- :mod:`~pyxctsk.distance.goal_line` — the ``GoalLine`` deep module: length,
  endpoints and semicircular control zone, in one place
- :mod:`~pyxctsk.distance.config` — convergence epsilon and sweep count

The goal line lives here rather than with the KML and GeoJSON writers that draw
it because distance calculation needs the same geometry — a LINE goal's
cylinder is sized from the goal-line length — and the shapes of a task must not
depend on the formats it is exported to.

Submodules import each other directly, never through this file, which is what
keeps the re-export layer free of the cycles it was split out to break.
"""

from .config import (
    CONVERGENCE_EPSILON_M,
    DEFAULT_NUM_ITERATIONS,
)
from .goal_line import (
    GoalLine,
    get_goal_line_data,
    goal_line_length_from_turnpoints,
    should_skip_last_turnpoint,
)
from .route_optimization import (
    OptimizedRoute,
    calculate_iteratively_refined_route,
    optimized_distance,
    optimized_route_coordinates,
)
from .sss import calculate_optimal_sss_entry_point, calculate_sss_info
from .task_distances import (
    calculate_cumulative_distances,
    calculate_task_distances,
    task_to_turnpoints,
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
    "GoalLine",
    "OptimizedRoute",
    # Goal-line geometry
    "get_goal_line_data",
    "goal_line_length_from_turnpoints",
    "should_skip_last_turnpoint",
    # Main distance calculation functions
    "optimized_distance",
    "optimized_route_coordinates",
    "distance_through_centers",
    "geodesic_distance",
    "calculate_task_distances",
    "calculate_cumulative_distances",
    "task_to_turnpoints",
    # SSS specific functions
    "calculate_sss_info",
    "calculate_optimal_sss_entry_point",
    # Configuration
    "CONVERGENCE_EPSILON_M",
    "DEFAULT_NUM_ITERATIONS",
    "FAI_SPHERE_RADIUS_M",
    # Advanced functions
    "calculate_iteratively_refined_route",
]
