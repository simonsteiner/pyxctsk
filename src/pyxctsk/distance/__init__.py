"""Distance calculation and route optimization for XCTrack tasks.

This file is the package's interface: it re-exports, and holds no logic of its
own. Everything a caller outside the package needs is named here —

- optimized route and distance through turnpoint cylinders per FAI S7F §7
  (Ding–Xie–Jiang alternating point-circle-point method)
- earth-model aware distances (WGS84 ellipsoid default, FAI sphere R = 6371 km)
- cumulative and per-leg task distances, and the speed section's own
  distance, which §7.2 defines as a separate optimization
- the optimizer's sweep limit, the one number here worth tuning, beside the
  convergence threshold the spec fixes

— while the work lives in focused submodules:

- :mod:`~pyxctsk.distance.turnpoint` — ``TaskTurnpoint``, the earth models,
  ``LocalPlane`` and the one planar solver every caller reaches
- :mod:`~pyxctsk.distance.route_optimization` — the shortest path through the
  cylinders
- :mod:`~pyxctsk.distance.measured_task` — ``MeasuredTask``, a task beside the
  optimized route flown for it. Every module that needs both takes this one
  value, so a task cannot be paired with another task's route
- :mod:`~pyxctsk.distance.task_distances` — per-leg and cumulative distances,
  projected from one measured task
- :mod:`~pyxctsk.distance.goal_line` — the ``GoalLine`` deep module: length,
  endpoints and semicircular control zone, in one place
- :mod:`~pyxctsk.distance.speed_section` — ``SpeedSection``, §7.2's second
  task distance. It is *not* a prefix of the task route: the optimizer
  treats the last circle it is handed as the finish, so S7F optimizes a
  separate ``taskToESS`` route and so does this
- :mod:`~pyxctsk.distance.report` — ``DistanceReport``, every number pyxctsk
  publishes about one task, with two renderings. This is the surface another
  implementation diffs against; it was two private functions inside ``cli.py``
- :mod:`~pyxctsk.distance.center_distance` — the "distance through centres"
  a task board publishes, which **S7F does not define**. The module states
  the reading pyxctsk proposes and keeps the alternatives so a vendor whose
  board disagrees can tell a convention apart from a bug

The goal line lives here rather than with the KML and GeoJSON writers that draw
it because the shapes of a task must not depend on the formats it is exported
to. Note that this is now the *only* reason: the second one — that distance
calculation needed the goal-line length itself — stopped being true when the
`TaskTurnpoint.goal_line_length` attribute that carried it turned out to be
written and never read. `export/` is `goal_line`'s only consumer today.

`goal_line` does depend on the optimizer, though: S7F 2025+ orients the line
against the optimized route point rather than a turnpoint centre, so the
line cannot be derived from the task alone. That edge runs the same way as
every other one here — `goal_line` → `measured_task` → `route_optimization`
→ `turnpoint` — so it adds no cycle.

Submodules import each other directly, never through this file, which is what
keeps the re-export layer free of the cycles it was split out to break.

**A task on the FAI sphere does not produce S7F task distances.** S7F 2026
§4.1 and §4.2 admit one earth model — *"distances between two geographic
points are calculated on the WGS84 ellipsoid"* — and offer no spherical
option; paragliding left the FAI sphere in 2018. ``earthModel`` is an XCTrack
format field, so a task declaring ``FAI_SPHERE`` is honoured here, throughout:
route, cylinder snapping and goal-line geometry all move to the sphere
together (ADR 0003). What comes out is what XCTrack would show and is not a
number a CIVL competition can be scored on — XCTrack's own documentation puts
the divergence at 200–300 m on a 50 km cylinder. This is deliberately not a
validation rule: the field is valid in the format being validated.
"""

from .center_distance import (
    PROPOSED_READING,
    CenterDistanceReading,
    center_distance,
    center_distance_readings,
)
from .goal_line import (
    GoalLine,
    GoalLineOrientation,
    goal_line_length_from_turnpoints,
)
from .measured_task import MeasuredTask, task_to_turnpoints
from .report import NOTES, S7F_EDITION, DistanceReport, TooFewTurnpointsError
from .route_optimization import (
    CONVERGENCE_EPSILON_M,
    DEFAULT_NUM_ITERATIONS,
    OptimizedRoute,
    calculate_iteratively_refined_route,
    optimized_distance,
)
from .speed_section import SpeedSection
from .task_distances import (
    TaskDistanceTable,
    TurnpointRow,
    calculate_task_distances,
    task_distances_from,
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
    "MeasuredTask",
    "DistanceReport",
    "LocalPlane",
    "plane_circle",
    "TaskTurnpoint",
    "GoalLine",
    "GoalLineOrientation",
    "CenterDistanceReading",
    "OptimizedRoute",
    "SpeedSection",
    # Goal-line geometry
    "goal_line_length_from_turnpoints",
    # Main distance calculation functions
    "optimized_distance",
    "distance_through_centers",
    "center_distance",
    "center_distance_readings",
    "PROPOSED_READING",
    "S7F_EDITION",
    "NOTES",
    "TooFewTurnpointsError",
    "geodesic_distance",
    "calculate_task_distances",
    "task_distances_from",
    "TaskDistanceTable",
    "TurnpointRow",
    "task_to_turnpoints",
    # Configuration
    "CONVERGENCE_EPSILON_M",
    "DEFAULT_NUM_ITERATIONS",
    "FAI_SPHERE_RADIUS_M",
    # Advanced functions
    "calculate_iteratively_refined_route",
]
