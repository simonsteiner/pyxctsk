"""Slow comprehensive tests for distance calculation algorithms.

These tests are more thorough but take longer to run. They should be run
separately when doing comprehensive testing or before releases.
"""

import os

import pytest

from pyxctsk import parse_task
from pyxctsk.distance import calculate_task_distances


class TestDistanceAlgorithmThorough:
    """Thorough tests for distance algorithms that take longer to run."""

    @pytest.fixture
    def test_data_dir(self):
        """Return the path to test data directory."""
        return os.path.join(os.path.dirname(__file__))

    @pytest.mark.slow
    def test_optimization_effectiveness_all_tasks(self, test_data_dir):
        """Test that optimization actually reduces distance for all tasks."""
        task_files = ["task_fuvu.xctsk", "task_jedu.xctsk", "task_meta.xctsk"]

        for task_file in task_files:
            file_path = os.path.join(test_data_dir, task_file)
            task = parse_task(file_path)
            results = calculate_task_distances(task, angle_step=5)  # High accuracy

            # Optimization should always reduce distance
            assert (
                results["optimized_distance_km"] < results["center_distance_km"]
            ), f"Optimization failed to reduce distance for {task_file}"

            # Check savings percentage
            savings_percent = (
                (results["center_distance_km"] - results["optimized_distance_km"])
                / results["center_distance_km"]
                * 100
            )
            assert savings_percent > 0, f"No savings achieved for {task_file}"

            print(f"{task_file}: {savings_percent:.1f}% distance savings")

    @pytest.mark.slow
    def test_algorithm_consistency(self, test_data_dir):
        """Test that algorithm produces consistent results across multiple runs."""
        file_path = os.path.join(test_data_dir, "task_fuvu.xctsk")
        task = parse_task(file_path)

        # Run calculation multiple times
        results = []
        for _ in range(3):
            result = calculate_task_distances(task, angle_step=5)
            results.append(
                (result["center_distance_km"], result["optimized_distance_km"])
            )

        # All results should be identical
        first_result = results[0]
        for result in results[1:]:
            assert (
                abs(result[0] - first_result[0]) < 0.01
            ), "Center distance not consistent"
            assert (
                abs(result[1] - first_result[1]) < 0.01
            ), "Optimized distance not consistent"

    @pytest.mark.slow
    def test_angle_step_impact(self, test_data_dir):
        """Test impact of different angle steps on optimization accuracy."""
        file_path = os.path.join(test_data_dir, "task_fuvu.xctsk")
        task = parse_task(file_path)

        # Test different angle steps
        angle_steps = [5, 10, 15, 30]
        results = {}

        for step in angle_steps:
            result = calculate_task_distances(task, angle_step=step)
            results[step] = result["optimized_distance_km"]

        # Smaller angle steps should generally give better (shorter) optimization
        # But we test that they're all reasonable
        for step, distance in results.items():
            assert (
                80 <= distance <= 100
            ), f"Distance {distance:.1f}km seems unreasonable for angle step {step}°"

        print("\nAngle step impact on task_fuvu.xctsk:")
        for step in angle_steps:
            print(f"  {step}°: {results[step]:.1f}km")

    @pytest.mark.slow
    def test_high_precision_calculations(self, test_data_dir):
        """Test high precision calculations with very small angle steps."""
        file_path = os.path.join(test_data_dir, "task_fuvu.xctsk")
        task = parse_task(file_path)

        # Use very high precision (2° step)
        results = calculate_task_distances(task, angle_step=2)

        # Results should be reasonable
        assert (
            140 <= results["center_distance_km"] <= 160
        ), f"Center distance {results['center_distance_km']:.1f}km seems unreasonable"
        assert (
            80 <= results["optimized_distance_km"] <= 100
        ), f"Optimized distance {results['optimized_distance_km']:.1f}km seems unreasonable"

        # High precision should give good optimization
        savings_percent = (
            (results["center_distance_km"] - results["optimized_distance_km"])
            / results["center_distance_km"]
            * 100
        )
        assert (
            savings_percent > 30
        ), f"High precision should give >30% savings, got {savings_percent:.1f}%"

        print(
            f"High precision (2°): {results['optimized_distance_km']:.2f}km ({savings_percent:.1f}% savings)"
        )


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v", "-m", "slow"])
