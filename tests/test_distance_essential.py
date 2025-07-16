"""Essential smoke tests for distance calculation functionality.

This module contains lightweight smoke tests that quickly validate core distance
calculation functionality works correctly. These tests are designed to:
- Run fast as part of regular development workflows
- Catch basic regressions in distance calculation algorithms
- Validate essential functionality with minimal test data
- Provide quick feedback during development

For comprehensive testing with reference data validation, see test_distance_reference.py
which provides full coverage using real-world tasks and thorough algorithm validation.
"""

import pytest
from pyxctsk import Task
from pyxctsk.distance import calculate_task_distances


class TestEssentialDistance:
    """Essential distance calculation tests that should always pass quickly."""

    def test_smoke_test_basic_functionality(self, bevo_task: Task):
        """Quick smoke test to ensure basic distance calculation works.

        This test validates that the core distance calculation pipeline
        functions correctly with real task data and produces sensible results.
        """
        task = bevo_task

        # Use fast settings for smoke test
        results = calculate_task_distances(task, angle_step=30)

        # Basic sanity checks - all distances should be positive
        assert results["center_distance_km"] > 0, "Center distance should be positive"
        assert (
            results["optimized_distance_km"] > 0
        ), "Optimized distance should be positive"

        # Optimization should reduce distance
        assert (
            results["center_distance_km"] > results["optimized_distance_km"]
        ), "Optimization should reduce distance"

        # Should have same number of turnpoints as input task
        assert len(results["turnpoints"]) == len(
            task.turnpoints
        ), "Should have same number of turnpoints"

        # Reasonable range checks for this specific task
        center_km = results["center_distance_km"]
        opt_km = results["optimized_distance_km"]

        assert (
            100 <= center_km <= 200
        ), f"Center distance {center_km:.1f}km outside expected range [100-200km]"
        assert (
            50 <= opt_km <= 150
        ), f"Optimized distance {opt_km:.1f}km outside expected range [50-150km]"

        print(f"✅ Smoke test passed: {center_km:.1f}km → {opt_km:.1f}km")


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
