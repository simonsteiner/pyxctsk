"""Fast basic tests for distance calculation module."""

import pytest

from pyxctsk.distance import (
    TaskTurnpoint,
    calculate_cumulative_distances,
    distance_through_centers,
    optimized_distance,
)


class TestTaskTurnpointClass:
    """Test the TaskTurnpoint class functionality."""

    def test_turnpoint_creation(self):
        """Test basic turnpoint creation."""
        tp = TaskTurnpoint(47.0, 8.0, 400)
        assert tp.center == (47.0, 8.0)
        assert tp.radius == 400

    def test_perimeter_points_zero_radius(self):
        """Test perimeter points for zero radius turnpoint."""
        tp = TaskTurnpoint(47.0, 8.0, 0)
        points = tp.perimeter_points()
        assert len(points) == 1
        assert points[0] == (47.0, 8.0)

    def test_perimeter_points_with_radius(self):
        """Test perimeter points generation for turnpoint with radius."""
        tp = TaskTurnpoint(47.0, 8.0, 1000)  # 1km radius
        points = tp.perimeter_points(angle_step=90)  # 90° steps

        assert len(points) == 4  # 0°, 90°, 180°, 270°

        # All points should be approximately 1km from center
        from geopy.distance import geodesic

        for point in points:
            distance = geodesic(tp.center, point).meters
            # Allow some tolerance due to WGS84 calculations
            assert (
                abs(distance - 1000) < 50
            ), f"Point {point} is {distance:.1f}m from center, expected ~1000m"

    def test_perimeter_points_angle_step(self):
        """Test different angle steps for perimeter points."""
        tp = TaskTurnpoint(47.0, 8.0, 1000)

        # Test various angle steps
        for angle_step in [5, 10, 15, 30, 45, 90]:
            points = tp.perimeter_points(angle_step)
            expected_count = 360 // angle_step
            assert (
                len(points) == expected_count
            ), f"Expected {expected_count} points for {angle_step}° step, got {len(points)}"


class TestDistanceFunctions:
    """Test individual distance calculation functions."""

    def test_distance_through_centers_simple(self):
        """Test simple distance through centers calculation."""
        turnpoints = [
            TaskTurnpoint(47.0, 8.0, 400),
            TaskTurnpoint(47.1, 8.0, 400),  # ~11km north
        ]

        distance = distance_through_centers(turnpoints)
        # Should be approximately 11km (0.1 degree latitude ≈ 11km)
        assert 10000 < distance < 12000, f"Expected ~11km, got {distance/1000:.1f}km"

    def test_optimized_distance_simple(self):
        """Test simple optimized distance calculation."""
        turnpoints = [
            TaskTurnpoint(47.0, 8.0, 1000),  # 1km radius
            TaskTurnpoint(47.1, 8.0, 1000),  # 1km radius, ~11km north
        ]

        center_dist = distance_through_centers(turnpoints)
        opt_dist = optimized_distance(
            turnpoints, angle_step=30
        )  # Use larger angle_step for speed

        # Optimized should be shorter (starting from takeoff center, saves ~1km)
        assert opt_dist < center_dist, "Optimization should reduce distance"
        savings = center_dist - opt_dist
        # With takeoff center start, savings should be approximately the target cylinder radius
        assert (
            800 < savings < 1200
        ), f"Expected ~1km savings (target radius), got {savings:.0f}m"

    def test_cumulative_distances(self):
        """Test cumulative distance calculation."""
        turnpoints = [
            TaskTurnpoint(47.0, 8.0, 400),
            TaskTurnpoint(47.1, 8.0, 400),
            TaskTurnpoint(47.2, 8.0, 400),
        ]

        # Test cumulative to index 1 (second turnpoint)
        center, opt = calculate_cumulative_distances(turnpoints, 1)
        assert center > 0 and opt > 0, "Cumulative distances should be positive"
        assert opt <= center, "Optimized cumulative should not exceed center cumulative"

        # Test cumulative to index 2 (third turnpoint)
        center2, opt2 = calculate_cumulative_distances(turnpoints, 2)
        assert center2 > center, "Cumulative should increase with more turnpoints"
        assert opt2 > opt, "Optimized cumulative should increase with more turnpoints"

    # def test_edge_cases(self):
    #     """Test edge cases for distance calculations."""
    #     # Test empty turnpoint list
    #     assert optimized_distance([]) == 0.0
    #     assert distance_through_centers([]) == 0.0

    #     # Test single turnpoint
    #     single_tp = [TaskTurnpoint(47.0, 8.0, 400)]
    #     assert optimized_distance(single_tp) == 0.0
    #     assert distance_through_centers(single_tp) == 0.0

    #     # Test two identical turnpoints
    #     identical_tps = [TaskTurnpoint(47.0, 8.0, 400), TaskTurnpoint(47.0, 8.0, 400)]
    #     center_dist = distance_through_centers(identical_tps)
    #     opt_dist = optimized_distance(identical_tps)

    #     assert center_dist == 0.0  # Same center points
    #     assert opt_dist <= center_dist  # Optimization shouldn't increase distance

    def test_zero_radius_turnpoints(self):
        """Test turnpoints with zero radius (exact points)."""
        turnpoints = [
            TaskTurnpoint(47.0, 8.0, 0),  # Zero radius
            TaskTurnpoint(47.1, 8.2, 0),  # Zero radius
            TaskTurnpoint(47.2, 8.4, 0),  # Zero radius
        ]

        center_dist = distance_through_centers(turnpoints)
        opt_dist = optimized_distance(turnpoints)

        # With zero radius, optimized should equal center distance
        assert abs(center_dist - opt_dist) < 1.0  # Should be very close


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
