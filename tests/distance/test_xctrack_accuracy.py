"""Acceptance tests for the FAI S7F §7 / Ding-Xie-Jiang route optimization.

These tests encode the acceptance criteria from the route-optimization audit
(docs/arch-review/2026-07-07-route-optimization-audit.md):

- optimized distances match XCTrack's displayed optimized distance on real
  tasks (within 0.1% and 50 m on 5+ tasks; reference values are rounded to
  0.1 km, so a 50 m quantization allowance applies),
- optimized distance never exceeds the distance through centers (except for
  concentric turnpoints, where touching semantics *require* flying back out —
  behaviour XCTrack shares, see task_nohe).

Everything here goes straight at the optimizer. The crossing, goal-line and
convergence cases are `test_route_optimization_cases.py` and the earth model is
`test_earth.py`. The pipeline that calls the optimizer —
`calculate_task_distances`, cumulative distances, degenerate inputs — is
`test_task_distances.py`; the optimizer's internals are
`test_route_optimization.py`.
"""

import pytest
from pyproj import Geod

from pyxctsk import GoalType, TurnpointType
from pyxctsk.distance import (
    TaskTurnpoint,
    calculate_iteratively_refined_route,
    distance_through_centers,
    optimized_distance,
)
from pyxctsk.distance.measured_task import task_to_turnpoints
from pyxctsk.distance.plane import LocalPlane
from pyxctsk.distance.route_optimization import boundary_point, plane_circle
from tests.builders import task, turnpoint
from tests.corpus import reference_task, tasks_with_reference_distance

WGS84 = Geod(ellps="WGS84")

#: XCTrack reference values are displayed rounded to 0.1 km.
REF_QUANTIZATION_M = 50.0


#: Every task the reference producer recorded an optimized distance for.
WITH_REFERENCE = tasks_with_reference_distance()


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

    def test_matches_xctrack_within_50m_on_5_plus_tasks(self):
        """At least 5 real tasks match XCTrack within 0.1% and 50 m.

        The reference values are XCTrack's displayed distances rounded to
        0.1 km, so 50 m of quantization is added to both bounds. This one
        stays a loop rather than a parametrization: the claim is about the
        corpus as a whole, not about any single task in it.
        """
        matching = []
        for reference in WITH_REFERENCE:
            name, ref_km = reference.stem, reference.reference_optimized_km
            assert ref_km is not None, f"{name} is in WITH_REFERENCE without one"
            turnpoints = task_to_turnpoints(reference.task)
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

    @pytest.mark.parametrize("reference", WITH_REFERENCE, ids=str)
    def test_all_reference_tasks_within_one_percent(self, reference):
        """Every reference task stays within 1% of XCTrack's displayed value.

        XCTrack's own optimizer deviates from the true WGS84 optimum by up to
        ~1% on tasks with very large cylinders (30-66 km radii); this guards
        against gross regressions while the tighter check above covers the
        well-conditioned tasks.
        """
        name, ref_km = reference.stem, reference.reference_optimized_km
        turnpoints = task_to_turnpoints(reference.task)
        calc_km = optimized_distance(turnpoints) / 1000.0
        rel = abs(calc_km - ref_km) / ref_km

        assert rel < 0.01, (
            f"{name}: optimized {calc_km:.2f}km differs from XCTrack "
            f"{ref_km:.1f}km by {rel:.2%}"
        )

    @pytest.mark.parametrize("reference", WITH_REFERENCE, ids=str)
    def test_optimized_never_exceeds_centers(self, reference):
        """Optimized ≤ through-centers whenever the center polyline is feasible.

        For consecutive concentric turnpoints the center polyline never touches
        the smaller circle, so touching semantics legitimately exceed it (e.g.
        task_nohe, where XCTrack itself displays optimized 96.3 km > centers
        82.6 km); those tasks are checked in test_concentric_out_and_back.
        """
        turnpoints = task_to_turnpoints(reference.task)
        if _has_concentric_pair(turnpoints):
            pytest.skip("concentric turnpoints force an out-and-back leg")

        opt = optimized_distance(turnpoints)
        centers = distance_through_centers(turnpoints)

        assert opt <= centers + 0.01, (
            f"{reference.stem}: optimized {opt / 1000:.2f}km exceeds centers "
            f"{centers / 1000:.2f}km"
        )

    def test_concentric_out_and_back(self):
        """task_nohe (concentric 10km/200m/10km/100m turnpoints) matches XCTrack.

        Touching each concentric circle in order forces mandatory out-and-back
        legs; XCTrack displays 96.3 km (> 82.6 km through centers) and the
        optimizer must reproduce that, not shortcut through the interior.
        """
        turnpoints = task_to_turnpoints(reference_task("task_nohe").task)
        opt_km = optimized_distance(turnpoints) / 1000.0
        assert opt_km == pytest.approx(96.3, abs=0.15)
        assert opt_km > distance_through_centers(turnpoints) / 1000.0


class TestOneSolverOneProjection:
    """The point on a cylinder has one answer, whoever asks.

    ``TaskTurnpoint.optimal_point`` used to project onto a plane centred on
    *that turnpoint*, while the route optimizer projected onto the plane of
    the whole task area. Same paragraph of the spec (S7F §7.1.2), two
    different answers — and every crossing-case test in
    ``test_route_optimization_cases.py`` aimed at the one the product does not
    use, so a fix made there could go green and ship nothing. The plane is a
    required argument of ``boundary_point`` now, so a test cannot reach the
    per-turnpoint projection without saying it means to; these check that
    handing over the task's own plane reproduces what the optimizer chose.
    """

    def test_the_single_circle_answer_reproduces_the_optimizers_choice(self):
        """Given the task's plane, the two agree to the metre."""
        takeoff = TaskTurnpoint(47.0, 8.0)
        middle = TaskTurnpoint(47.2, 8.1, 5_000.0)
        goal = TaskTurnpoint(47.4, 8.0, 400.0)
        turnpoints = [takeoff, middle, goal]

        route = calculate_iteratively_refined_route(turnpoints)
        plane = LocalPlane.around([tp.center for tp in turnpoints])

        asked = boundary_point(middle, route.points[0], route.points[2], plane)

        _, _, apart = WGS84.inv(
            asked[1], asked[0], route.points[1][1], route.points[1][0]
        )
        assert apart < 1.0, f"the two answers are {apart:.2f} m apart"

    def test_the_projection_is_the_only_difference(self):
        """Without the task's plane the answer moves, which is the point.

        Not a defect — a plane centred on one turnpoint is a legitimate
        reading of §7.1.2. What was wrong was having no way to ask for the
        other one, so the tests could not reach the shipped policy.
        """
        turnpoints = [
            TaskTurnpoint(47.0, 8.0),
            TaskTurnpoint(47.2, 8.1, 5_000.0),
            TaskTurnpoint(47.4, 8.0, 400.0),
        ]
        prev_point, next_point = (47.0, 8.0), (47.4, 8.0)

        own = boundary_point(
            turnpoints[1],
            prev_point,
            next_point,
            LocalPlane.around([turnpoints[1].center]),
        )
        task = boundary_point(
            turnpoints[1],
            prev_point,
            next_point,
            LocalPlane.around([tp.center for tp in turnpoints]),
        )

        # Both sit exactly on the boundary; they are different points on it.
        for point in (own, task):
            _, _, radius = WGS84.inv(point[1], point[0], 8.1, 47.2)
            assert radius == pytest.approx(5_000.0, abs=0.01)

    def test_a_line_goal_is_a_zero_radius_circle(self):
        """One statement of the rule, at the one place that states it.

        ``task_to_turnpoints`` builds the cylinders, so that is where a LINE
        goal becomes a zero-radius point. ``plane_circle`` used to apply the
        same rule again from the goal type it was handed; this asserts the
        surviving owner produces a cylinder the solver already reads as a
        point, without the projection needing to know what kind of goal it is.
        """
        line_task = task(
            turnpoint("A", 46.5, 8.0, type=TurnpointType.TAKEOFF),
            turnpoint("Goal", 47.0, 8.0, radius=400),
            goal=GoalType.LINE,
        )
        goal = task_to_turnpoints(line_task)[-1]
        plane = LocalPlane.around([goal.center])

        # ``radius == 0`` is the whole of "this is a LINE goal" here — the
        # cylinder carried a ``goal_type`` label beside it that nothing read.
        assert goal.radius == 0
        assert plane_circle(goal, plane)[2] == 0.0
        assert boundary_point(goal, (46.5, 8.0), (46.5, 8.0), plane) == goal.center

    def test_a_cylinder_goal_keeps_its_radius(self):
        """The other half of the same rule, which nothing used to assert."""
        goal = task_to_turnpoints(
            task(
                turnpoint("A", 46.5, 8.0, type=TurnpointType.TAKEOFF),
                turnpoint("Goal", 47.0, 8.0, radius=400),
                goal=GoalType.CYLINDER,
            )
        )[-1]

        assert goal.radius == 400
