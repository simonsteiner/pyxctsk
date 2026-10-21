"""Optimizer cases for the FAI S7F §7 / Ding-Xie-Jiang route optimization.

These tests encode acceptance criteria from the route-optimization audit
(docs/arch-review/2026-07-07-route-optimization-audit.md):

- nested/overlapping cylinders take the crossing case (no spurious detours),
- a previous point inside a cylinder yields the segment-circle intersection,
- goal-line tasks finish on the goal line, perpendicular to the incoming leg,
- iteration beyond the ε = 0.1 m convergence point changes nothing.

Reference accuracy and the one-solver check are `test_xctrack_accuracy.py`; the
optimizer's internals are `test_route_optimization.py`.
"""

import pytest
from pyproj import Geod

from pyxctsk.distance import (
    TaskTurnpoint,
    calculate_iteratively_refined_route,
    distance_through_centers,
    optimized_distance,
)
from pyxctsk.distance.measured_task import task_to_turnpoints
from pyxctsk.distance.plane import LocalPlane
from pyxctsk.distance.route_optimization import boundary_point
from tests.corpus import reference_task, tasks_with_reference_distance

WGS84 = Geod(ellps="WGS84")

#: Convergence is a property of the algorithm, not of any one task, so it is
#: checked on a sample rather than all 22 — each case runs the optimizer twice,
#: the second time to 500 sweeps. The sample is named in the test ids.
CONVERGENCE_SAMPLE = tasks_with_reference_distance()[:5]


class TestCrossingCase:
    """GetOptPi crossing situations (Ding et al. Theorem 1)."""

    def test_prev_inside_yields_segment_circle_intersection(self):
        """A previous point inside the cylinder gives the boundary crossing.

        Hand-computed: cylinder center (47, 8), r = 5000 m; previous point
        2000 m due east of the center (inside), next point 20000 m due east.
        The prev→next segment runs due east, so the optimal point is exactly
        5000 m due east of the center.
        """
        center = (47.0, 8.0)
        lon_p, lat_p, _ = WGS84.fwd(center[1], center[0], 90.0, 2_000.0)
        lon_n, lat_n, _ = WGS84.fwd(center[1], center[0], 90.0, 20_000.0)
        lon_e, lat_e, _ = WGS84.fwd(center[1], center[0], 90.0, 5_000.0)

        tp = TaskTurnpoint(center[0], center[1], 5_000.0)
        # The task's own plane, which is the projection the optimizer builds —
        # these used to take a default plane centred on this turnpoint alone,
        # a projection no shipped code path ever constructs.
        plane = LocalPlane.around([tp.center, (lat_p, lon_p), (lat_n, lon_n)])
        point = boundary_point(tp, (lat_p, lon_p), (lat_n, lon_n), plane)

        _, _, err = WGS84.inv(point[1], point[0], lon_e, lat_e)
        assert err < 1.0, f"crossing point off by {err:.2f} m"
        # And it must sit exactly on the boundary.
        _, _, dist_to_center = WGS84.inv(point[1], point[0], center[1], center[0])
        assert dist_to_center == pytest.approx(5_000.0, abs=0.01)

    def test_crossing_point_adds_no_distance(self):
        """When the leg already crosses the cylinder, the detour is zero."""
        prev_point = (46.8, 8.0)
        next_point = (47.2, 8.0)
        tp = TaskTurnpoint(47.0, 8.0, 3_000.0)
        plane = LocalPlane.around([tp.center, prev_point, next_point])
        point = boundary_point(tp, prev_point, next_point, plane)

        _, _, direct = WGS84.inv(
            prev_point[1], prev_point[0], next_point[1], next_point[0]
        )
        _, _, leg1 = WGS84.inv(prev_point[1], prev_point[0], point[1], point[0])
        _, _, leg2 = WGS84.inv(point[1], point[0], next_point[1], next_point[0])
        assert leg1 + leg2 - direct < 1.0

    def test_nested_cylinder_no_spurious_detour(self):
        """A small turnpoint inside a large start cylinder routes straight through.

        Task: takeoff → large SSS cylinder (r=20 km) → small turnpoint (r=1 km,
        its center inside the SSS circle) → goal. Both circles are crossed by
        the direct path, so the optimized distance must not exceed the straight
        takeoff→goal-boundary geodesic, and must be well below the center path.
        """
        takeoff = TaskTurnpoint(47.0, 8.0)
        sss = TaskTurnpoint(47.30, 8.0, 20_000.0)  # takeoff→center ≈ 33 km
        small = TaskTurnpoint(47.35, 8.0, 1_000.0)  # inside the SSS circle
        goal = TaskTurnpoint(47.6, 8.0, 400.0)
        turnpoints = [takeoff, sss, small, goal]

        opt = optimized_distance(turnpoints)
        centers = distance_through_centers(turnpoints)

        # Straight geodesic from takeoff to the goal boundary is the lower
        # bound; every cylinder lies on it, so the optimum must reach it.
        _, _, direct = WGS84.inv(8.0, 47.0, 8.0, 47.6)
        assert opt == pytest.approx(direct - 400.0, abs=1.0)
        assert opt <= centers

        # The route point on each intermediate circle lies on the straight
        # line (crossing case): no out-and-back deviation in longitude.
        route = calculate_iteratively_refined_route(turnpoints).points
        for lat, lon in route:
            assert abs(lon - 8.0) < 1e-4


class TestGoalLine:
    """Goal-line finish per S7F §6.2.3.1."""

    def test_goal_line_task_matches_reference(self):
        """task_piga_line: finish sits on the goal line and distance matches."""
        task = reference_task("task_piga_line").task
        turnpoints = task_to_turnpoints(task)

        optimized = calculate_iteratively_refined_route(turnpoints)
        route = optimized.points
        assert optimized.total_m / 1000.0 == pytest.approx(35.4, abs=0.1)

        # The goal line is centred on the goal and perpendicular to the
        # incoming optimized leg, so its center is the optimal crossing: the
        # finish point must be the goal center — which lies on the line for
        # any orientation, and trivially satisfies perpendicularity.
        goal_center = turnpoints[-1].center
        assert route[-1][0] == pytest.approx(goal_center[0], abs=1e-9)
        assert route[-1][1] == pytest.approx(goal_center[1], abs=1e-9)

    def test_finish_point_perpendicular_foot_is_center(self):
        """The optimal crossing of a goal line is the goal center.

        The line is oriented perpendicular to the incoming leg (§6.2.3.1), so
        the perpendicular foot from the incoming point is the center itself.
        """
        goal = TaskTurnpoint(47.0, 8.0, 0)
        prev_point = (46.9, 7.95)
        plane = LocalPlane.around([goal.center, prev_point])
        finish = boundary_point(goal, prev_point, prev_point, plane)
        assert finish == goal.center


class TestConvergence:
    """ε = 0.1 m convergence (S7F §7.1.3)."""

    @pytest.mark.parametrize("reference", CONVERGENCE_SAMPLE, ids=str)
    def test_more_iterations_change_nothing(self, reference):
        """Beyond convergence, more sweeps change the result by < 0.1 m."""
        turnpoints = task_to_turnpoints(reference.task)
        base = optimized_distance(turnpoints)
        more = optimized_distance(turnpoints, num_iterations=500)

        assert abs(base - more) <= 0.1, (
            f"{reference.stem}: {abs(base - more):.3f} m change after convergence"
        )
