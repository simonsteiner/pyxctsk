"""Acceptance tests for the FAI S7F §7 / Ding-Xie-Jiang route optimization.

These tests encode the acceptance criteria from the route-optimization audit
(docs/Audit-of-pyxctsk-Route-Optimization.md):

- optimized distances match XCTrack's displayed optimized distance on real
  tasks (within 0.1% and 50 m on 5+ tasks; reference values are rounded to
  0.1 km, so a 50 m quantization allowance applies),
- nested/overlapping cylinders take the crossing case (no spurious detours),
- a previous point inside a cylinder yields the segment-circle intersection,
- goal-line tasks finish on the goal line, perpendicular to the incoming leg,
- iteration beyond the ε = 0.1 m convergence point changes nothing,
- optimized distance never exceeds the distance through centers (except for
  concentric turnpoints, where touching semantics *require* flying back out —
  behaviour XCTrack shares, see task_nohe).
"""

import json
import math
from pathlib import Path

import pytest
from pyproj import Geod

from pyxctsk import EarthModel
from pyxctsk.distance import (
    TaskTurnpoint,
    calculate_iteratively_refined_route,
    distance_through_centers,
    optimized_distance,
)
from pyxctsk.parser import parse_task
from pyxctsk.task_distances import _task_to_turnpoints

WGS84 = Geod(ellps="WGS84")

#: XCTrack reference values are displayed rounded to 0.1 km.
REF_QUANTIZATION_M = 50.0


def _load_reference_tasks(xctsk_dir: Path, json_dir: Path):
    """Yield (name, task, reference-optimized-km) for tasks with reference data."""
    for xctsk_file in sorted(xctsk_dir.glob("*.xctsk")):
        json_path = json_dir / f"{xctsk_file.stem}.json"
        if not json_path.exists():
            continue
        with open(json_path) as f:
            meta = json.load(f)["metadata"]
        ref_km = meta.get("distance_optimized_km")
        if not ref_km:
            continue
        yield xctsk_file.stem, parse_task(str(xctsk_file)), ref_km


def _has_concentric_pair(turnpoints: list[TaskTurnpoint]) -> bool:
    """True if any consecutive turnpoints share a center.

    Touching semantics then force an out-and-back leg, so the center distance
    is not an upper bound for the optimized distance.
    """
    return any(
        turnpoints[i].center == turnpoints[i + 1].center
        for i in range(len(turnpoints) - 1)
    )


class TestReferenceAccuracy:
    """Optimized distances vs. XCTrack's displayed values on real tasks."""

    def test_matches_xctrack_within_50m_on_5_plus_tasks(
        self, reference_tasks_dir: Path, reference_json_dir: Path
    ):
        """At least 5 real tasks match XCTrack within 0.1% and 50 m.

        The reference values are XCTrack's displayed distances rounded to
        0.1 km, so 50 m of quantization is added to both bounds.
        """
        matching = []
        for name, task, ref_km in _load_reference_tasks(
            reference_tasks_dir, reference_json_dir
        ):
            turnpoints = _task_to_turnpoints(task)
            calc_m = optimized_distance(turnpoints)
            ref_m = ref_km * 1000.0
            diff_m = abs(calc_m - ref_m)
            if diff_m <= 50.0 + REF_QUANTIZATION_M and diff_m <= (
                0.001 * ref_m + REF_QUANTIZATION_M
            ):
                matching.append((name, diff_m))

        assert len(matching) >= 5, (
            f"Only {len(matching)} tasks match XCTrack within 0.1%/50m "
            f"(+50m display rounding): {matching}"
        )

    def test_all_reference_tasks_within_one_percent(
        self, reference_tasks_dir: Path, reference_json_dir: Path
    ):
        """Every reference task stays within 1% of XCTrack's displayed value.

        XCTrack's own optimizer deviates from the true WGS84 optimum by up to
        ~1% on tasks with very large cylinders (30-66 km radii); this guards
        against gross regressions while the tighter check above covers the
        well-conditioned tasks.
        """
        count = 0
        for name, task, ref_km in _load_reference_tasks(
            reference_tasks_dir, reference_json_dir
        ):
            turnpoints = _task_to_turnpoints(task)
            calc_km = optimized_distance(turnpoints) / 1000.0
            rel = abs(calc_km - ref_km) / ref_km
            assert rel < 0.01, (
                f"{name}: optimized {calc_km:.2f}km differs from XCTrack "
                f"{ref_km:.1f}km by {rel:.2%}"
            )
            count += 1
        assert count >= 5, "Expected at least 5 reference tasks"

    def test_optimized_never_exceeds_centers(
        self, reference_tasks_dir: Path, reference_json_dir: Path
    ):
        """Optimized ≤ through-centers whenever the center polyline is feasible.

        For consecutive concentric turnpoints the center polyline never touches
        the smaller circle, so touching semantics legitimately exceed it (e.g.
        task_nohe, where XCTrack itself displays optimized 96.3 km > centers
        82.6 km); those tasks are checked in test_concentric_out_and_back.
        """
        for name, task, _ in _load_reference_tasks(
            reference_tasks_dir, reference_json_dir
        ):
            turnpoints = _task_to_turnpoints(task)
            if _has_concentric_pair(turnpoints):
                continue
            opt = optimized_distance(turnpoints)
            centers = distance_through_centers(turnpoints)
            assert opt <= centers + 0.01, (
                f"{name}: optimized {opt / 1000:.2f}km exceeds centers "
                f"{centers / 1000:.2f}km"
            )

    def test_concentric_out_and_back(
        self, reference_tasks_dir: Path, reference_json_dir: Path
    ):
        """task_nohe (concentric 10km/200m/10km/100m turnpoints) matches XCTrack.

        Touching each concentric circle in order forces mandatory out-and-back
        legs; XCTrack displays 96.3 km (> 82.6 km through centers) and the
        optimizer must reproduce that, not shortcut through the interior.
        """
        task_file = reference_tasks_dir / "task_nohe.xctsk"
        if not task_file.exists():
            pytest.skip("task_nohe.xctsk not available")
        turnpoints = _task_to_turnpoints(parse_task(str(task_file)))
        opt_km = optimized_distance(turnpoints) / 1000.0
        assert opt_km == pytest.approx(96.3, abs=0.15)
        assert opt_km > distance_through_centers(turnpoints) / 1000.0


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
        point = tp.optimal_point((lat_p, lon_p), (lat_n, lon_n))

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
        point = tp.optimal_point(prev_point, next_point)

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
        _, route = calculate_iteratively_refined_route(turnpoints)
        for lat, lon in route:
            assert abs(lon - 8.0) < 1e-4


class TestGoalLine:
    """Goal-line finish per S7F §6.2.3.1."""

    def test_goal_line_task_matches_reference(
        self, reference_tasks_dir: Path, reference_json_dir: Path
    ):
        """task_piga_line: finish sits on the goal line and distance matches."""
        task_file = reference_tasks_dir / "task_piga_line.xctsk"
        if not task_file.exists():
            pytest.skip("task_piga_line.xctsk not available")
        task = parse_task(str(task_file))
        turnpoints = _task_to_turnpoints(task)

        distance, route = calculate_iteratively_refined_route(turnpoints)
        assert distance / 1000.0 == pytest.approx(35.4, abs=0.1)

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
        goal = TaskTurnpoint(47.0, 8.0, 0, goal_type="LINE", goal_line_length=400.0)
        prev_point = (46.9, 7.95)
        finish = goal.optimal_point(prev_point, prev_point)
        assert finish == goal.center


class TestConvergence:
    """ε = 0.1 m convergence (S7F §7.1.3)."""

    def test_more_iterations_change_nothing(
        self, reference_tasks_dir: Path, reference_json_dir: Path
    ):
        """Beyond convergence, more sweeps change the result by < 0.1 m."""
        checked = 0
        for name, task, _ in _load_reference_tasks(
            reference_tasks_dir, reference_json_dir
        ):
            turnpoints = _task_to_turnpoints(task)
            base = optimized_distance(turnpoints)
            more = optimized_distance(turnpoints, num_iterations=500)
            assert abs(base - more) <= 0.1, (
                f"{name}: {abs(base - more):.3f} m change after convergence"
            )
            checked += 1
            if checked >= 5:
                break
        assert checked >= 5


class TestEarthModel:
    """earthModel field: WGS84 (default) vs FAI sphere (R = 6371 km)."""

    def test_fai_sphere_great_circle_distance(self):
        """Zero-radius points 1° apart along a meridian: exactly R·π/180."""
        turnpoints = [
            TaskTurnpoint(0.0, 8.0, 0, earth_model=EarthModel.FAI_SPHERE),
            TaskTurnpoint(1.0, 8.0, 0, earth_model=EarthModel.FAI_SPHERE),
        ]
        sphere_deg = 6_371_000.0 * math.pi / 180.0  # 111194.93 m
        assert optimized_distance(turnpoints) == pytest.approx(sphere_deg, abs=1.0)
        assert distance_through_centers(turnpoints) == pytest.approx(
            sphere_deg, abs=1.0
        )

    def test_wgs84_differs_from_sphere(self):
        """The same task measures differently on the two earth models."""
        wgs84_tps = [TaskTurnpoint(0.0, 8.0, 0), TaskTurnpoint(1.0, 8.0, 0)]
        sphere_tps = [
            TaskTurnpoint(0.0, 8.0, 0, earth_model="FAI_SPHERE"),
            TaskTurnpoint(1.0, 8.0, 0, earth_model="FAI_SPHERE"),
        ]
        wgs = optimized_distance(wgs84_tps)
        sph = optimized_distance(sphere_tps)
        # A meridian degree at the equator is ~110.57 km on WGS84.
        assert wgs == pytest.approx(110_574.4, abs=10.0)
        assert abs(wgs - sph) > 500.0

    def test_task_earth_model_propagates(self, reference_tasks_dir: Path):
        """_task_to_turnpoints carries the task's earthModel to every turnpoint."""
        task_file = reference_tasks_dir / "task_bevo.xctsk"
        if not task_file.exists():
            pytest.skip("task_bevo.xctsk not available")
        task = parse_task(str(task_file))
        object.__setattr__(task, "earth_model", EarthModel.FAI_SPHERE)
        turnpoints = _task_to_turnpoints(task)
        assert all(tp.earth_model == EarthModel.FAI_SPHERE for tp in turnpoints)
        # And the sphere distance differs measurably from the WGS84 one.
        object.__setattr__(task, "earth_model", None)
        wgs_tps = _task_to_turnpoints(task)
        assert abs(optimized_distance(turnpoints) - optimized_distance(wgs_tps)) > 50.0
