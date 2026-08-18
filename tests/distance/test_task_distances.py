"""The task-distance pipeline: `calculate_task_distances` and its parts.

This file covers the layer *above* the optimizer — that a task is turned into
turnpoints correctly, that cumulative distances accumulate, that the result
dict has the shape callers read, and that degenerate inputs (no turnpoints,
one turnpoint, zero radii, concentric circles) do something defined.

How close the optimizer gets to XCTrack's published numbers is not asserted
here; `test_xctrack_accuracy.py` owns that, and does it on every reference task
at a tighter tolerance. The one reference check kept below runs through
`calculate_task_distances`, so it is testing the wiring, not the algorithm.
"""

import statistics
from typing import List
from unittest.mock import patch

import pytest

from pyxctsk import Task, TaskType
from pyxctsk.distance import (
    MeasuredTask,  # noqa: F401
    TaskTurnpoint,
    calculate_task_distances,
    distance_through_centers,
    optimized_distance,
    task_distances_from,
)
from pyxctsk.export import common
from pyxctsk.export.common import TaskDrawing
from pyxctsk.export.geojson import drawing_to_geojson
from tests.corpus import reference_task, tasks_with_reference_distance

#: The reference tasks the producer recorded distances for, discovered once.
WITH_REFERENCE = tasks_with_reference_distance()

#: How far the pipeline's optimized distance may sit from the producer's.
#: Deliberately looser than ``test_xctrack_accuracy`` allows the optimizer
#: itself: what is under test here is the wiring above it.
TOLERANCE = 0.02


class TestDistanceComprehensive:
    """Comprehensive test suite for distance calculation algorithms.

    This test class validates distance calculation accuracy, optimization algorithms,
    and edge cases using both reference tasks with known results and synthetic
    test data for controlled validation scenarios.
    """

    @pytest.fixture(scope="class")
    def test_turnpoints(self) -> List[TaskTurnpoint]:
        """Create synthetic test turnpoints for unit tests with significant optimization potential."""
        return [
            TaskTurnpoint(47.0, 8.0, 1000),  # Takeoff - 1km radius
            TaskTurnpoint(47.1, 8.0, 5000),  # Large radius target - 5km radius
            TaskTurnpoint(47.2, 8.1, 3000),  # Medium radius target - 3km radius
            TaskTurnpoint(47.25, 8.2, 1000),  # Goal - 1km radius
        ]

    @pytest.mark.parametrize("reference", WITH_REFERENCE, ids=str)
    def test_center_distance_matches_reference(self, reference):
        """Distance through centers is geometry, so it must be very close."""
        ref_km = reference.metadata.get("distance_through_centers_km", 0)
        if not ref_km:
            pytest.skip("the producer recorded no center distance")

        calc_km = calculate_task_distances(reference.task)["center_distance_km"]
        difference = abs(calc_km - ref_km) / ref_km

        assert difference < 0.005, (
            f"{reference.stem}: center distance differs by {difference:.1%} "
            f"(calc: {calc_km:.1f}km, ref: {ref_km:.1f}km)"
        )

    @pytest.mark.parametrize("reference", WITH_REFERENCE, ids=str)
    def test_optimized_distance_matches_reference(self, reference):
        """The pipeline reproduces the producer's optimized distance.

        A looser bound than ``test_xctrack_accuracy`` uses on the optimizer
        itself: what is under test here is the wiring above it.
        """
        ref_km = reference.reference_optimized_km
        calc_km = calculate_task_distances(reference.task)["optimized_distance_km"]
        difference = abs(calc_km - ref_km) / ref_km

        assert difference < TOLERANCE, (
            f"{reference.stem}: optimized distance differs by {difference:.1%} "
            f"(calc: {calc_km:.1f}km, ref: {ref_km:.1f}km)"
        )

    def test_the_average_difference_is_well_inside_the_tolerance(self):
        """Every task passing individually still allows a systematic bias.

        A claim about the corpus rather than any one task, so this one stays a
        loop.
        """
        differences = [
            abs(
                calculate_task_distances(r.task)["optimized_distance_km"]
                - r.reference_optimized_km
            )
            / r.reference_optimized_km
            for r in WITH_REFERENCE
        ]

        assert statistics.mean(differences) < TOLERANCE / 2

    def test_algorithm_core_functionality(self, test_turnpoints: List[TaskTurnpoint]):
        """Test core algorithm functionality with synthetic data.

        Validates fundamental algorithm behavior, edge cases, and consistency
        using controlled synthetic turnpoint data.
        """
        # Test basic optimization effectiveness
        center_dist = distance_through_centers(test_turnpoints)
        opt_dist = optimized_distance(test_turnpoints)

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

        results = calculate_task_distances(task)
        route = MeasuredTask.from_task(task).route

        expected = [round(m / 1000.0, 1) for m in route.cumulative_m()]
        actual = [tp["cumulative_optimized_km"] for tp in results["turnpoints"]]
        assert actual == expected, f"{stem}: cumulative column left the route"

        # The last turnpoint's cumulative distance is the task distance.
        assert actual[-1] == results["optimized_distance_km"]

        # An optimized prefix never exceeds the same prefix through centers.
        for tp in results["turnpoints"]:
            assert tp["cumulative_optimized_km"] <= tp["cumulative_center_km"]

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

    def test_optimization_is_deterministic(self, test_turnpoints: List[TaskTurnpoint]):
        """Repeated runs must produce identical, converged results."""
        center_dist = distance_through_centers(test_turnpoints)
        results = [optimized_distance(test_turnpoints) for _ in range(3)]

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

        results = calculate_task_distances(task)

        # Validate structure
        assert "center_distance_km" in results
        assert "optimized_distance_km" in results
        assert "turnpoints" in results
        assert len(results["turnpoints"]) == len(task.turnpoints)

        # Validate optimization effectiveness
        center_km = results["center_distance_km"]
        opt_km = results["optimized_distance_km"]

        assert center_km > 0, f"{task_name}: Center distance should be positive"
        assert opt_km > 0, f"{task_name}: Optimized distance should be positive"
        assert opt_km < center_km, f"{task_name}: Optimization should reduce distance"

        # Validate turnpoint data
        for i, tp_result in enumerate(results["turnpoints"]):
            assert "cumulative_center_km" in tp_result
            assert "cumulative_optimized_km" in tp_result

            # Cumulative distances should be non-decreasing
            if i > 0:
                prev_tp = results["turnpoints"][i - 1]
                assert (
                    tp_result["cumulative_center_km"] >= prev_tp["cumulative_center_km"]
                )
                assert (
                    tp_result["cumulative_optimized_km"]
                    >= prev_tp["cumulative_optimized_km"]
                )


class TestProjectionFromARoute:
    """`task_distances_from`: the report as a projection of one route."""

    @pytest.mark.parametrize("stem", ["task_bevo", "task_gibe"])
    def test_agrees_with_optimizing_from_scratch(self, stem):
        """Projecting a measured task gives exactly the report as measuring one."""
        task = reference_task(stem).task

        assert task_distances_from(MeasuredTask.from_task(task)) == (
            calculate_task_distances(task)
        )

    def test_a_task_and_its_map_can_share_one_route(self):
        """The distance table and the drawn map cost one optimizer run together.

        This is the pairing the task viewer makes on every request: it used to
        optimize the task once for the table and again for the GeoJSON.
        """
        task = reference_task("task_bevo").task

        calls = []
        real = common.MeasuredTask.from_task

        def counting(measured_task, *args, **kwargs):
            calls.append(measured_task)
            return real(measured_task, *args, **kwargs)

        with patch.object(common.MeasuredTask, "from_task", counting):
            drawing = TaskDrawing.from_task(task)
            table = task_distances_from(drawing.measured)
            geojson = drawing_to_geojson(drawing)

        assert len(calls) == 1
        # The table's total and the drawn line describe the same route.
        assert table["optimized_distance_km"] == round(drawing.route.total_m / 1000, 1)
        (line,) = [
            f
            for f in geojson["features"]
            if f["properties"]["type"] == "optimized_route"
        ]
        assert len(line["geometry"]["coordinates"]) == len(drawing.route.points)

    def test_degenerate_task_projects_to_zeros(self):
        """A task with fewer than two turnpoints reports zeros, not an error."""
        task = Task(task_type=TaskType.CLASSIC, version=1, turnpoints=[])

        result = task_distances_from(MeasuredTask.from_task(task))

        assert result["center_distance_km"] == 0.0
        assert result["optimized_distance_km"] == 0.0
        assert result["turnpoints"] == []
