"""Essential distance calculation tests.

This file contains only the most important and fast-running tests.
For more comprehensive testing, see:
- test_distance_basic.py: Basic functionality and edge cases
- test_distance_integration.py: Integration tests with real task files
- test_distance_slow.py: Thorough but slow algorithm tests (marked with @pytest.mark.slow)
"""

import os

import pytest

from pyxctsk import parse_task
from pyxctsk.distance import calculate_task_distances


class TestEssentialDistance:
    """Essential distance calculation tests that should always pass quickly."""

    @pytest.fixture
    def test_data_dir(self):
        """Return the path to test data directory."""
        return os.path.join(os.path.dirname(__file__))

    def test_single_task_smoke_test(self, test_data_dir):
        """Quick smoke test to ensure basic distance calculation works."""
        file_path = os.path.join(test_data_dir, "task_fuvu.xctsk")
        task = parse_task(file_path)

        # Use fast settings for smoke test
        results = calculate_task_distances(task, angle_step=30)

        # Basic sanity checks
        assert results["center_distance_km"] > 0, "Center distance should be positive"
        assert (
            results["optimized_distance_km"] > 0
        ), "Optimized distance should be positive"
        assert (
            results["center_distance_km"] > results["optimized_distance_km"]
        ), "Optimization should reduce distance"
        assert len(results["turnpoints"]) == len(
            task.turnpoints
        ), "Should have same number of turnpoints"

        # Reasonable range checks
        assert (
            100 <= results["center_distance_km"] <= 200
        ), f"Center distance {results['center_distance_km']:.1f}km seems unreasonable"
        assert (
            50 <= results["optimized_distance_km"] <= 150
        ), f"Optimized distance {results['optimized_distance_km']:.1f}km seems unreasonable"

        print(
            f"Smoke test passed: {results['center_distance_km']:.1f}km -> {results['optimized_distance_km']:.1f}km"
        )


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
