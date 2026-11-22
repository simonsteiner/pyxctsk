"""The task-distance pipeline: `DistanceReport` and its parts.

This file covers the layer *above* the optimizer — that a task is turned into
turnpoints correctly, that cumulative distances accumulate, that the report
reads the one route, and that degenerate inputs (no turnpoints,
one turnpoint, zero radii, concentric circles) do something defined.

How close the optimizer gets to XCTrack's published numbers is not asserted
here; `test_xctrack_accuracy.py` owns that, and does it on every reference task
at a tighter tolerance, but on `optimized_distance` directly. The two reference
checks kept below (the centre and the optimized distance) run through
`DistanceReport.from_task`, so they test the wiring, not the algorithm.
"""

from unittest.mock import patch

import pytest

from pyxctsk.distance import (
    DistanceReport,
    MeasuredTask,
    TaskTurnpoint,
    distance_through_centers,
    optimized_distance,
)
from pyxctsk.export import common
from pyxctsk.export.common import TaskDrawing
from pyxctsk.export.geojson import drawing_to_geojson
from tests.corpus import reference_task, tasks_with_reference_distance

#: The reference tasks the producer recorded distances for, discovered once.
WITH_REFERENCE = tasks_with_reference_distance()

#: How far the report's optimized distance may sit from the producer's.
#: Looser than `test_xctrack_accuracy` allows the optimizer itself: what is
#: under test here is the wiring above it.
TOLERANCE = 0.02

#: Synthetic route with enough cylinder radius for optimization to matter.
TEST_TURNPOINTS = [
    TaskTurnpoint(47.0, 8.0, 1000),
    TaskTurnpoint(47.1, 8.0, 5000),
    TaskTurnpoint(47.2, 8.1, 3000),
    TaskTurnpoint(47.25, 8.2, 1000),
]


class TestDistanceComprehensive:
    """Comprehensive test suite for distance calculation algorithms.

    This test class validates distance calculation accuracy, optimization algorithms,
    and edge cases using both reference tasks with known results and synthetic
    test data for controlled validation scenarios.
    """

    @pytest.mark.parametrize("reference", WITH_REFERENCE, ids=str)
    def test_center_distance_matches_reference(self, reference):
        """Distance through centers is geometry, so it must be very close."""
        ref_km = reference.metadata.get("distance_through_centers_km", 0)
        if not ref_km:
            pytest.skip("the producer recorded no center distance")

        center_m = DistanceReport.from_task(reference.task).center_distance_m
        assert center_m is not None
        calc_km = center_m / 1000
        difference = abs(calc_km - ref_km) / ref_km

        assert difference < 0.005, (
            f"{reference.stem}: center distance differs by {difference:.1%} "
            f"(calc: {calc_km:.1f}km, ref: {ref_km:.1f}km)"
        )

    @pytest.mark.parametrize("reference", WITH_REFERENCE, ids=str)
    def test_optimized_distance_matches_reference(self, reference):
        """The report's task distance reproduces the producer's optimized one."""
        ref_km = reference.reference_optimized_km
        calc_km = DistanceReport.from_task(reference.task).task_distance_m / 1000
        difference = abs(calc_km - ref_km) / ref_km

        assert difference < TOLERANCE, (
            f"{reference.stem}: optimized distance differs by {difference:.1%} "
            f"(calc: {calc_km:.1f}km, ref: {ref_km:.1f}km)"
        )

    def test_algorithm_core_functionality(self):
        """Test core algorithm functionality with synthetic data.

        Validates fundamental algorithm behavior, edge cases, and consistency
        using controlled synthetic turnpoint data.
        """
        # Test basic optimization effectiveness
        center_dist = distance_through_centers(TEST_TURNPOINTS)
        opt_dist = optimized_distance(TEST_TURNPOINTS)

        assert center_dist > 0, "Center distance should be positive"
        assert opt_dist > 0, "Optimized distance should be positive"
        assert opt_dist < center_dist, "Optimization should reduce distance"

        # Validate reasonable optimization savings (larger radii should give better optimization)
        savings_pct = (center_dist - opt_dist) / center_dist
        assert 0.02 < savings_pct < 0.8, (
            f"Savings {savings_pct:.1%} outside reasonable range [2%-80%]"
        )

    @pytest.mark.parametrize("stem", ["task_bevo", "task_gibe", "task_duna"])
    def test_cumulative_optimized_is_a_prefix_of_the_route(self, stem):
        """The cumulative column must be measured along the task's own route.

        Regression: the column was recomputed per turnpoint by re-optimizing
        ``turnpoints[:i + 1]``. The optimizer treats the last circle it is
        handed as the finish, so each of those runs bent the route towards
        turnpoint i instead of passing through it — the numbers were optima of
        truncated tasks, not distances along the route drawn beside them.
        On task_bevo turnpoint 7 the two were 5.09 km apart, both derived from
        the same Task. Only the non-decreasing property was asserted before,
        which both readings satisfy.
        """
        task = reference_task(stem).task

        report = DistanceReport.from_task(task)
        route = MeasuredTask.from_task(task).route

        rows = report.route()
        actual = [row.cumulative_m for row in rows]
        assert actual == route.cumulative_m(), (
            f"{stem}: cumulative column left the route"
        )

        # The last turnpoint's cumulative distance is the task distance. To
        # within a millionth of a metre, not bit for bit: from Python 3.12 ``sum()``
        # compensates, so a total and a running prefix differ in the last bit.
        assert actual[-1] == pytest.approx(report.task_distance_m, abs=1e-6)

        # An optimized prefix never exceeds the same prefix through centers.
        for row in rows:
            assert row.cumulative_m <= row.cumulative_center_m

    def test_edge_cases_and_robustness(self):
        """Test algorithm robustness with edge cases."""
        # Empty list
        assert optimized_distance([]) == 0.0
        assert distance_through_centers([]) == 0.0

        # Single turnpoint
        single_tp = [TaskTurnpoint(47.0, 8.0, 400)]
        assert optimized_distance(single_tp) == 0.0
        assert distance_through_centers(single_tp) == 0.0

        # Identical (concentric) turnpoints: the center distance is zero, but
        # touching semantics require reaching the second circle's boundary
        # from the start at the shared center — 400 m. XCTrack behaves the
        # same way for concentric turnpoints (see task_nohe reference data).
        identical_tps = [TaskTurnpoint(47.0, 8.0, 400), TaskTurnpoint(47.0, 8.0, 400)]
        center_dist = distance_through_centers(identical_tps)
        opt_dist = optimized_distance(identical_tps)
        assert center_dist == 0.0, "Distance between identical points should be zero"
        assert opt_dist == pytest.approx(400.0, abs=1.0), (
            "Touching a concentric circle from its center costs the radius"
        )

        # Zero radius turnpoints (exact points)
        zero_radius_tps = [
            TaskTurnpoint(47.0, 8.0, 0),
            TaskTurnpoint(47.1, 8.1, 0),
            TaskTurnpoint(47.2, 8.2, 0),
        ]
        center_dist = distance_through_centers(zero_radius_tps)
        opt_dist = optimized_distance(zero_radius_tps)
        # With zero radius, optimization should have minimal effect
        assert abs(center_dist - opt_dist) < 1.0, (
            "Zero radius should have minimal optimization difference"
        )

    def test_optimization_is_deterministic(self):
        """Repeated runs must produce identical, converged results."""
        center_dist = distance_through_centers(TEST_TURNPOINTS)
        results = [optimized_distance(TEST_TURNPOINTS) for _ in range(3)]

        assert all(r == results[0] for r in results), "Optimization must be stable"
        assert results[0] < center_dist, "Optimization should reduce distance"

        savings_pct = (center_dist - results[0]) / center_dist
        assert 0.01 < savings_pct < 0.9, f"Savings {savings_pct:.1%} unreasonable"

    @pytest.mark.parametrize("task_name", ["task_mega", "task_duna", "task_wovi"])
    def test_task_distances_integration(self, task_name):
        """Test the full task distance calculation pipeline.

        This integration test validates the complete workflow from task parsing
        through distance optimization using a representative reference task.
        """
        task = reference_task(task_name).task

        report = DistanceReport.from_task(task)
        rows = report.route()

        # Validate structure
        assert len(rows) == len(task.turnpoints)

        # Validate optimization effectiveness
        center_m = report.center_distance_m
        opt_m = report.task_distance_m

        assert center_m is not None
        assert center_m > 0, f"{task_name}: Center distance should be positive"
        assert opt_m > 0, f"{task_name}: Optimized distance should be positive"
        assert opt_m < center_m, f"{task_name}: Optimization should reduce distance"

        # Cumulative distances should be non-decreasing
        for prev, row in zip(rows, rows[1:]):
            assert row.cumulative_center_m >= prev.cumulative_center_m
            assert row.cumulative_m >= prev.cumulative_m


class TestProjectionFromARoute:
    """`DistanceReport.from_measured_task`: the report as a projection of one route."""

    def test_a_task_and_its_map_can_share_one_route(self):
        """The distance report and the drawn map cost one optimizer run together.

        This is the pairing the task viewer makes on every request: it used to
        optimize the task once for the report and again for the GeoJSON.
        """
        task = reference_task("task_bevo").task

        calls = []
        real = common.MeasuredTask.from_task

        def counting(measured_task, *args, **kwargs):
            calls.append(measured_task)
            return real(measured_task, *args, **kwargs)

        with patch.object(common.MeasuredTask, "from_task", counting):
            drawing = TaskDrawing.from_task(task)
            report = DistanceReport.from_measured_task(drawing.measured)
            geojson = drawing_to_geojson(drawing)

        assert len(calls) == 1
        # The report's total and the drawn line describe the same route.
        assert report.task_distance_m == drawing.route.total_m
        (line,) = [
            f
            for f in geojson["features"]
            if f["properties"]["type"] == "optimized_route"
        ]
        assert len(line["geometry"]["coordinates"]) == len(drawing.route.points)


class TestTheCentreColumn:
    """The centre column and the centre total are one polyline."""

    @pytest.mark.parametrize("stem", ["task_bevo", "task_pepi"])
    def test_the_centre_column_ends_at_the_centre_total(self, stem):
        """The prefix and the total are one polyline, so they must agree.

        They are both ``PROPOSED_READING``. Deriving the column from a
        different reading than the total would put the report in disagreement with
        its own last row — which is why
        ``cumulative_center_m`` lives in ``center_distance``.
        """
        report = DistanceReport.from_task(reference_task(stem).task)

        # A millionth of a metre, not bit for bit: from Python 3.12 ``sum()`` compensates,
        # so the total and the running prefix differ in the last bit.
        assert report.route()[-1].cumulative_center_m == pytest.approx(
            report.center_distance_m, abs=1e-6
        )


def test_the_report_does_not_optimize_the_speed_section():
    """§7.2's second distance is derived on first use, not at construction.

    ``DistanceReport`` used to optimize ``taskToESS`` at construction — a
    second route per drawing, which the task viewer's "one drawing, one route"
    comments said did not happen.
    """
    report = DistanceReport.from_measured_task(
        MeasuredTask.from_task(reference_task("task_bevo").task)
    )
    assert "speed_section" not in report.__dict__
    assert report.speed_section is not None  # still there when asked for
