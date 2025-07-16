"""Comprehensive distance calculation tests using reference tasks.

This module provides comprehensive testing of distance calculation algorithms using
reference tasks with known expected results. It validates:
- Algorithm accuracy against reference JSON data
- Core optimization functionality with synthetic test cases
- Edge cases and robustness testing
- Integration testing of the complete distance calculation pipeline
- Precision validation with high-accuracy settings

The tests use real-world task data to ensure calculations match expected results
within acceptable tolerances, providing confidence in algorithm correctness.
"""

import json
import statistics
from pathlib import Path
from typing import Dict, List

import pytest
from pyxctsk.distance import (
    TaskTurnpoint,
    calculate_cumulative_distances,
    calculate_task_distances,
    distance_through_centers,
    optimized_distance,
)
from pyxctsk.parser import parse_task


class TestDistanceComprehensive:
    """Comprehensive test suite for distance calculation algorithms.

    This test class validates distance calculation accuracy, optimization algorithms,
    and edge cases using both reference tasks with known results and synthetic
    test data for controlled validation scenarios.
    """

    @pytest.fixture(scope="class")
    def reference_data(
        self, reference_tasks_dir: Path, reference_json_dir: Path
    ) -> Dict[str, Dict]:
        """Load reference task files and their expected JSON results."""
        if not reference_tasks_dir.exists() or not reference_json_dir.exists():
            pytest.skip("Reference task directories not found")

        reference_data = {}

        # Load all reference tasks that have both .xctsk and .json files
        for xctsk_file in reference_tasks_dir.glob("*.xctsk"):
            task_name = xctsk_file.stem
            json_file = f"{task_name}.json"
            json_path = reference_json_dir / json_file

            if not json_path.exists():
                continue

            try:
                # Load task
                task = parse_task(str(xctsk_file))

                # Load reference JSON
                with open(json_path, "r") as f:
                    json_data = json.load(f)

                reference_data[task_name] = {
                    "task": task,
                    "reference": json_data,
                    "xctsk_file": xctsk_file.name,
                }

            except Exception as e:
                print(f"Warning: Failed to load {task_name}: {e}")

        if not reference_data:
            pytest.skip("No valid reference task pairs found")

        return reference_data

    @pytest.fixture(scope="class")
    def test_turnpoints(self) -> List[TaskTurnpoint]:
        """Create synthetic test turnpoints for unit tests with significant optimization potential."""
        return [
            TaskTurnpoint(47.0, 8.0, 1000),  # Takeoff - 1km radius
            TaskTurnpoint(47.1, 8.0, 5000),  # Large radius target - 5km radius
            TaskTurnpoint(47.2, 8.1, 3000),  # Medium radius target - 3km radius
            TaskTurnpoint(47.25, 8.2, 1000),  # Goal - 1km radius
        ]

    def test_reference_task_validation(self, reference_data: Dict[str, Dict]):
        """Test distance calculations against reference JSON data.

        This test validates our optimization algorithms against known good results
        from reference tasks, ensuring accuracy within acceptable tolerances.
        """
        results = []
        tolerance_percent = 0.02  # 2% tolerance for optimization differences

        for task_name, data in reference_data.items():
            task = data["task"]
            ref_meta = data["reference"]["metadata"]

            # Skip tasks without reference distances
            if "distance_optimized_km" not in ref_meta:
                continue

            # Calculate distances with moderate precision for performance
            calc_results = calculate_task_distances(task, angle_step=10)

            ref_center_km = ref_meta.get("distance_through_centers_km", 0)
            ref_opt_km = ref_meta.get("distance_optimized_km", 0)
            calc_center_km = calc_results["center_distance_km"]
            calc_opt_km = calc_results["optimized_distance_km"]

            # Validate center distances (should be very close)
            if ref_center_km > 0:
                center_diff_pct = abs(calc_center_km - ref_center_km) / ref_center_km
                assert center_diff_pct < 0.005, (  # 0.5% tolerance for center distances
                    f"{task_name}: Center distance differs by {center_diff_pct:.1%} "
                    f"(calc: {calc_center_km:.1f}km, ref: {ref_center_km:.1f}km)"
                )

            # Validate optimized distances (allow more tolerance due to algorithm differences)
            if ref_opt_km > 0:
                opt_diff_pct = abs(calc_opt_km - ref_opt_km) / ref_opt_km
                assert opt_diff_pct < tolerance_percent, (
                    f"{task_name}: Optimized distance differs by {opt_diff_pct:.1%} "
                    f"(calc: {calc_opt_km:.1f}km, ref: {ref_opt_km:.1f}km)"
                )

                results.append(
                    {
                        "task": task_name,
                        "ref_opt": ref_opt_km,
                        "calc_opt": calc_opt_km,
                        "diff_pct": opt_diff_pct,
                    }
                )

        # Statistical validation across all tasks
        if results:
            avg_diff = statistics.mean([r["diff_pct"] for r in results])
            max_diff = max([r["diff_pct"] for r in results])

            print(f"\nReference validation results ({len(results)} tasks):")
            print(f"  Average difference: {avg_diff:.2%}")
            print(f"  Maximum difference: {max_diff:.2%}")
            print(f"  Tolerance: {tolerance_percent:.1%}")

            # Ensure average difference is well within tolerance
            assert (
                avg_diff < tolerance_percent / 2
            ), f"Average difference {avg_diff:.2%} exceeds half tolerance {tolerance_percent/2:.2%}"

    def test_algorithm_core_functionality(self, test_turnpoints: List[TaskTurnpoint]):
        """Test core algorithm functionality with synthetic data.

        Validates fundamental algorithm behavior, edge cases, and consistency
        using controlled synthetic turnpoint data.
        """
        # Test basic optimization effectiveness
        center_dist = distance_through_centers(test_turnpoints)
        opt_dist = optimized_distance(test_turnpoints, angle_step=15)

        assert center_dist > 0, "Center distance should be positive"
        assert opt_dist > 0, "Optimized distance should be positive"
        assert opt_dist < center_dist, "Optimization should reduce distance"

        # Validate reasonable optimization savings (larger radii should give better optimization)
        savings_pct = (center_dist - opt_dist) / center_dist
        assert (
            0.02 < savings_pct < 0.8
        ), f"Savings {savings_pct:.1%} outside reasonable range [2%-80%]"

    def test_cumulative_distance_calculations(
        self, test_turnpoints: List[TaskTurnpoint]
    ):
        """Test cumulative distance calculations through turnpoint sequence."""
        # Test cumulative calculations for different endpoints
        for target_idx in range(1, len(test_turnpoints)):
            center_cum, opt_cum = calculate_cumulative_distances(
                test_turnpoints, target_idx
            )

            assert (
                center_cum > 0
            ), f"Cumulative center distance to {target_idx} should be positive"
            assert (
                opt_cum > 0
            ), f"Cumulative optimized distance to {target_idx} should be positive"
            assert (
                opt_cum <= center_cum
            ), "Cumulative optimization should not exceed center distance"

            # Cumulative distances should increase with more turnpoints
            if target_idx > 1:
                prev_center, prev_opt = calculate_cumulative_distances(
                    test_turnpoints, target_idx - 1
                )
                assert center_cum > prev_center, "Center cumulative should increase"
                assert opt_cum > prev_opt, "Optimized cumulative should increase"

    def test_edge_cases_and_robustness(self):
        """Test algorithm robustness with edge cases."""
        # Empty list
        assert optimized_distance([]) == 0.0
        assert distance_through_centers([]) == 0.0

        # Single turnpoint
        single_tp = [TaskTurnpoint(47.0, 8.0, 400)]
        assert optimized_distance(single_tp) == 0.0
        assert distance_through_centers(single_tp) == 0.0

        # Identical turnpoints
        identical_tps = [TaskTurnpoint(47.0, 8.0, 400), TaskTurnpoint(47.0, 8.0, 400)]
        center_dist = distance_through_centers(identical_tps)
        opt_dist = optimized_distance(identical_tps)
        assert center_dist == 0.0, "Distance between identical points should be zero"
        assert (
            opt_dist <= center_dist
        ), "Optimization shouldn't increase distance from zero"

        # Zero radius turnpoints (exact points)
        zero_radius_tps = [
            TaskTurnpoint(47.0, 8.0, 0),
            TaskTurnpoint(47.1, 8.1, 0),
            TaskTurnpoint(47.2, 8.2, 0),
        ]
        center_dist = distance_through_centers(zero_radius_tps)
        opt_dist = optimized_distance(zero_radius_tps)
        # With zero radius, optimization should have minimal effect
        assert (
            abs(center_dist - opt_dist) < 1.0
        ), "Zero radius should have minimal optimization difference"

    @pytest.mark.parametrize("angle_step", [5, 10, 15, 30])
    def test_angle_step_consistency(
        self, test_turnpoints: List[TaskTurnpoint], angle_step: int
    ):
        """Test that different angle steps produce consistent optimization behavior."""
        center_dist = distance_through_centers(test_turnpoints)
        opt_dist = optimized_distance(test_turnpoints, angle_step=angle_step)

        # All angle steps should optimize
        assert (
            opt_dist < center_dist
        ), f"Angle step {angle_step}° should optimize distance"

        # Results should be reasonable regardless of angle step
        savings_pct = (center_dist - opt_dist) / center_dist
        assert (
            0.01 < savings_pct < 0.9
        ), f"Angle step {angle_step}°: savings {savings_pct:.1%} unreasonable"

    def test_task_distances_integration(self, reference_data: Dict[str, Dict]):
        """Test the full task distance calculation pipeline.

        This integration test validates the complete workflow from task parsing
        through distance optimization using a representative reference task.
        """
        # Use a known task with good optimization potential
        test_tasks = ["task_mega", "task_duna", "task_wovi"]

        for task_name in test_tasks:
            if task_name not in reference_data:
                continue

            task = reference_data[task_name]["task"]

            # Test full pipeline with different precision levels
            for angle_step, precision_name in [(15, "fast"), (5, "precise")]:
                results = calculate_task_distances(task, angle_step=angle_step)

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
                assert (
                    opt_km < center_km
                ), f"{task_name}: Optimization should reduce distance"

                # Validate turnpoint data
                for i, tp_result in enumerate(results["turnpoints"]):
                    assert "cumulative_center_km" in tp_result
                    assert "cumulative_optimized_km" in tp_result

                    # Cumulative distances should be non-decreasing
                    if i > 0:
                        prev_tp = results["turnpoints"][i - 1]
                        assert (
                            tp_result["cumulative_center_km"]
                            >= prev_tp["cumulative_center_km"]
                        )
                        assert (
                            tp_result["cumulative_optimized_km"]
                            >= prev_tp["cumulative_optimized_km"]
                        )

            # Only test first found task to keep test time reasonable
            break

    @pytest.mark.slow
    def test_algorithm_precision_validation(self, reference_data: Dict[str, Dict]):
        """Comprehensive precision validation with high-accuracy settings.

        This test uses high precision settings to validate algorithm accuracy
        and is marked as slow since it takes longer to run.
        """
        precision_tasks = ["task_mega", "task_duna"]  # Known complex tasks

        for task_name in precision_tasks:
            if task_name not in reference_data:
                continue

            task = reference_data[task_name]["task"]
            ref_meta = reference_data[task_name]["reference"]["metadata"]

            if "distance_optimized_km" not in ref_meta:
                continue

            # High precision calculation
            results = calculate_task_distances(task, angle_step=2)

            ref_opt_km = ref_meta["distance_optimized_km"]
            calc_opt_km = results["optimized_distance_km"]

            # With high precision, we should be very close to reference
            if ref_opt_km > 0:
                diff_pct = abs(calc_opt_km - ref_opt_km) / ref_opt_km
                assert diff_pct < 0.01, (  # 1% tolerance for high precision
                    f"{task_name} high precision: {diff_pct:.2%} difference "
                    f"(calc: {calc_opt_km:.2f}km, ref: {ref_opt_km:.2f}km)"
                )

                print(f"{task_name} high precision: {diff_pct:.3%} difference")


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
