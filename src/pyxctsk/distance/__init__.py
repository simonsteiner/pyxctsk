"""Distance calculation and route optimization for XCTrack tasks.

This file is the package's interface: it re-exports, and holds no logic of its
own. Everything a caller outside the package needs is named here —

- optimized route and distance through turnpoint cylinders per FAI S7F §7
  (Ding–Xie–Jiang alternating point-circle-point method)
- earth-model aware distances (WGS84 ellipsoid default, FAI sphere R = 6371 km)
- cumulative and per-leg task distances
- the optimizer's sweep limit, the one number here worth tuning, beside the
  convergence threshold the spec fixes

— while the work lives in focused submodules:

- :mod:`~pyxctsk.distance.turnpoint` — ``TaskTurnpoint``, the earth models,
  ``LocalPlane`` and the one planar solver every caller reaches
- :mod:`~pyxctsk.distance.route_optimization` — the shortest path through the
  cylinders
- :mod:`~pyxctsk.distance.task_distances` — per-leg and cumulative distances,
  projected from one optimized route
- :mod:`~pyxctsk.distance.goal_line` — the ``GoalLine`` deep module: length,
  endpoints and semicircular control zone, in one place

The goal line lives here rather than with the KML and GeoJSON writers that draw
it because the shapes of a task must not depend on the formats it is exported
to. Note that this is now the *only* reason: the second one — that distance
calculation needed the goal-line length itself — stopped being true when the
`TaskTurnpoint.goal_line_length` attribute that carried it turned out to be
written and never read. `export/` is `goal_line`'s only consumer today.

`goal_line` does depend on the optimizer, though: S7F 2025+ orients the line
against the optimized route point rather than a turnpoint centre, so the
line cannot be derived from the task alone. That edge runs the same way as
every other one here — `goal_line` → `task_distances` → `route_optimization`
→ `turnpoint` — so it adds no cycle.

Submodules import each other directly, never through this file, which is what
keeps the re-export layer free of the cycles it was split out to break.
"""

from .goal_line import (
    GoalLine,
    GoalLineOrientation,
    goal_line_length_from_turnpoints,
)
from .route_optimization import (
    CONVERGENCE_EPSILON_M,
    DEFAULT_NUM_ITERATIONS,
    OptimizedRoute,
    calculate_iteratively_refined_route,
    optimized_distance,
)
from .task_distances import (
    calculate_task_distances,
    task_distances_from_route,
    task_to_turnpoints,
)
from .turnpoint import (
    FAI_SPHERE_RADIUS_M,
    LocalPlane,
    TaskTurnpoint,
    distance_through_centers,
    geodesic_distance,
    plane_circle,
)

# Export all the main public functions and classes
__all__ = [
    # Core classes
    "LocalPlane",
    "plane_circle",
    "TaskTurnpoint",
    "GoalLine",
    "GoalLineOrientation",
    "OptimizedRoute",
    # Goal-line geometry
    "goal_line_length_from_turnpoints",
    # Main distance calculation functions
    "optimized_distance",
    "distance_through_centers",
    "geodesic_distance",
    "calculate_task_distances",
    "task_distances_from_route",
    "task_to_turnpoints",
    # SSS specific functions
    # Configuration
    "CONVERGENCE_EPSILON_M",
    "DEFAULT_NUM_ITERATIONS",
    "FAI_SPHERE_RADIUS_M",
    # Advanced functions
    "calculate_iteratively_refined_route",
]
