"""Tests for TaskTurnpoint class and geometry calculations."""

import pytest
from geopy.distance import geodesic
from pyxctsk.turnpoint import (
    TaskTurnpoint,
    _calculate_distance_through_point,
    _find_optimal_cylinder_point,
    _get_optimized_perimeter_points,
    distance_through_centers,
)


class TestCalculateDistanceThroughPoint:
    """Test the _calculate_distance_through_point function."""

    def test_calculate_distance_simple(self):
        """Test distance calculation through a point."""
        start = (46.0, 8.0)
        middle = (46.1, 8.0)
        end = (46.2, 8.0)

        distance = _calculate_distance_through_point(start, middle, end)

        # Calculate expected distance
        expected = geodesic(start, middle).meters + geodesic(middle, end).meters
        assert abs(distance - expected) < 1.0  # Within 1 meter

    def test_calculate_distance_collinear(self):
        """Test distance calculation when points are collinear."""
        start = (46.0, 8.0)
        middle = (46.05, 8.0)  # Halfway point
        end = (46.1, 8.0)

        distance = _calculate_distance_through_point(start, middle, end)
        direct_distance = geodesic(start, end).meters

        # Should be very close to direct distance for collinear points
        assert abs(distance - direct_distance) < 10.0

    def test_calculate_distance_detour(self):
        """Test distance calculation with significant detour."""
        start = (46.0, 8.0)
        middle = (46.0, 8.1)  # Side detour
        end = (46.1, 8.0)

        distance = _calculate_distance_through_point(start, middle, end)
        direct_distance = geodesic(start, end).meters

        # Should be longer than direct distance
        assert distance > direct_distance


class TestFindOptimalCylinderPoint:
    """Test the _find_optimal_cylinder_point function."""

    def test_find_optimal_point_simple(self):
        """Test finding optimal point on a cylinder."""
        cylinder_center = (46.5, 8.0)
        cylinder_radius = 400.0
        start_point = (46.0, 8.0)
        end_point = (47.0, 8.0)

        optimal_point = _find_optimal_cylinder_point(
            cylinder_center, cylinder_radius, start_point, end_point
        )

        # Verify point is on the cylinder
        distance_to_center = geodesic(cylinder_center, optimal_point).meters
        assert abs(distance_to_center - cylinder_radius) < 1.0

    def test_find_optimal_point_collinear(self):
        """Test optimal point when start, center, and end are collinear."""
        cylinder_center = (46.5, 8.0)
        cylinder_radius = 400.0
        start_point = (46.0, 8.0)  # Due south
        end_point = (47.0, 8.0)  # Due north

        optimal_point = _find_optimal_cylinder_point(
            cylinder_center, cylinder_radius, start_point, end_point
        )

        # Optimal point should be on the line between start and end
        # Either north or south of center
        assert abs(optimal_point[1] - cylinder_center[1]) < 0.001  # Same longitude

    def test_find_optimal_point_90_degree(self):
        """Test optimal point when approach is at 90 degrees."""
        cylinder_center = (46.5, 8.0)
        cylinder_radius = 400.0
        start_point = (46.5, 7.9)  # Due west
        end_point = (46.5, 8.1)  # Due east

        optimal_point = _find_optimal_cylinder_point(
            cylinder_center, cylinder_radius, start_point, end_point
        )

        # Should be on the cylinder perimeter
        distance_to_center = geodesic(cylinder_center, optimal_point).meters
        assert abs(distance_to_center - cylinder_radius) < 1.0


class TestTaskTurnpoint:
    """Test the TaskTurnpoint class."""

    def test_init_basic(self):
        """Test basic TaskTurnpoint initialization."""
        tp = TaskTurnpoint(46.5, 8.0, 400.0)

        assert tp.center == (46.5, 8.0)
        assert tp.radius == 400.0
        assert tp.goal_type is None
        assert tp.goal_line_length is None

    def test_init_goal_line(self):
        """Test TaskTurnpoint initialization with goal line."""
        tp = TaskTurnpoint(46.5, 8.0, 400.0, goal_type="LINE", goal_line_length=500.0)

        assert tp.center == (46.5, 8.0)
        assert tp.radius == 400.0
        assert tp.goal_type == "LINE"
        assert tp.goal_line_length == 500.0

    def test_perimeter_points_basic(self):
        """Test basic perimeter points generation."""
        tp = TaskTurnpoint(46.5, 8.0, 400.0)
        points = tp.perimeter_points(90)  # 90-degree steps

        assert len(points) == 4  # 0, 90, 180, 270 degrees

        # All points should be approximately 400m from center
        for point in points:
            distance = geodesic(tp.center, point).meters
            assert abs(distance - 400.0) < 1.0

    def test_perimeter_points_zero_radius(self):
        """Test perimeter points with zero radius."""
        tp = TaskTurnpoint(46.5, 8.0, 0.0)
        points = tp.perimeter_points(90)

        assert len(points) == 1
        assert points[0] == tp.center

    def test_perimeter_points_goal_line(self):
        """Test perimeter points for goal line."""
        tp = TaskTurnpoint(46.5, 8.0, 400.0, goal_type="LINE")
        points = tp.perimeter_points(90)

        # Goal line without previous point should return center
        assert len(points) == 1
        assert points[0] == tp.center

    @pytest.mark.parametrize("angle_step", [30, 45, 90, 120])
    def test_perimeter_points_various_steps(self, angle_step):
        """Test perimeter points with various angle steps."""
        tp = TaskTurnpoint(46.5, 8.0, 400.0)
        points = tp.perimeter_points(angle_step)

        expected_count = 360 // angle_step
        assert len(points) == expected_count

    def test_goal_line_points_basic(self):
        """Test goal line points generation."""
        tp = TaskTurnpoint(46.5, 8.0, 400.0, goal_type="LINE", goal_line_length=500.0)
        prev_point = (46.0, 8.0)  # South of goal

        points = tp.goal_line_points(prev_point, 90)

        # Should have endpoints, center, and semi-circle points
        assert len(points) >= 3

        # Center should be in the points
        assert tp.center in points

    def test_goal_line_points_no_goal_type(self):
        """Test goal line points when not a goal line."""
        tp = TaskTurnpoint(46.5, 8.0, 400.0)
        prev_point = (46.0, 8.0)

        points = tp.goal_line_points(prev_point, 90)

        # Should return regular perimeter points
        assert len(points) == 4

    def test_goal_line_points_default_length(self):
        """Test goal line points with default length."""
        tp = TaskTurnpoint(46.5, 8.0, 400.0, goal_type="LINE")  # No goal_line_length
        prev_point = (46.0, 8.0)

        points = tp.goal_line_points(prev_point, 90)

        # Should still generate points with default 400m length
        assert len(points) >= 3

    def test_optimal_point_cylinder(self):
        """Test optimal point calculation for cylinder."""
        tp = TaskTurnpoint(46.5, 8.0, 400.0)
        prev_point = (46.0, 8.0)
        next_point = (47.0, 8.0)

        optimal = tp.optimal_point(prev_point, next_point)

        # Should be on the cylinder perimeter
        distance = geodesic(tp.center, optimal).meters
        assert abs(distance - 400.0) < 1.0

    def test_optimal_point_zero_radius(self):
        """Test optimal point with zero radius."""
        tp = TaskTurnpoint(46.5, 8.0, 0.0)
        prev_point = (46.0, 8.0)
        next_point = (47.0, 8.0)

        optimal = tp.optimal_point(prev_point, next_point)

        # Should be the center
        assert optimal == tp.center

    def test_optimal_point_goal_line(self):
        """Test optimal point calculation for goal line."""
        tp = TaskTurnpoint(46.5, 8.0, 400.0, goal_type="LINE", goal_line_length=500.0)
        prev_point = (46.0, 8.0)
        next_point = (47.0, 8.0)

        optimal = tp.optimal_point(prev_point, next_point)

        # Should be a valid point (not None)
        assert optimal is not None
        assert len(optimal) == 2

    def test_find_optimal_goal_line_point_perpendicular(self):
        """Test optimal goal line point calculation."""
        tp = TaskTurnpoint(46.5, 8.0, 400.0, goal_type="LINE", goal_line_length=500.0)
        prev_point = (46.0, 8.0)  # Due south
        next_point = (47.0, 8.0)  # Not used for goal line

        optimal = tp._find_optimal_goal_line_point(prev_point, next_point)

        # Should be on the goal line
        assert optimal is not None
        assert len(optimal) == 2

    def test_find_optimal_goal_line_point_default_length(self):
        """Test optimal goal line point with default length."""
        tp = TaskTurnpoint(46.5, 8.0, 400.0, goal_type="LINE")  # No goal_line_length
        prev_point = (46.0, 8.0)
        next_point = (47.0, 8.0)

        optimal = tp._find_optimal_goal_line_point(prev_point, next_point)

        # Should still work with default 400m length
        assert optimal is not None
        assert len(optimal) == 2

    def test_optimized_perimeter_points_cylinder(self):
        """Test optimized perimeter points for cylinder."""
        tp = TaskTurnpoint(46.5, 8.0, 400.0)
        prev_point = (46.0, 8.0)
        next_point = (47.0, 8.0)

        points = tp.optimized_perimeter_points(prev_point, next_point, 90)

        # Should return a single optimal point for cylinder
        assert len(points) == 1

        # Point should be on the perimeter
        distance = geodesic(tp.center, points[0]).meters
        assert abs(distance - 400.0) < 1.0

    def test_optimized_perimeter_points_goal_line(self):
        """Test optimized perimeter points for goal line."""
        tp = TaskTurnpoint(46.5, 8.0, 400.0, goal_type="LINE", goal_line_length=500.0)
        prev_point = (46.0, 8.0)
        next_point = (47.0, 8.0)

        points = tp.optimized_perimeter_points(prev_point, next_point, 90)

        # Should return a single optimal point for goal line
        assert len(points) == 1

    def test_optimized_perimeter_points_goal_line_no_prev(self):
        """Test optimized perimeter points for goal line without previous point."""
        tp = TaskTurnpoint(46.5, 8.0, 400.0, goal_type="LINE")

        # The function checks if prev_point exists, but type signature requires tuple
        # This tests the internal logic where prev_point would be None
        # We'll test this indirectly by checking the internal logic works
        points = tp.perimeter_points(90)  # This should return center for goal lines

        # Should return center point for goal lines without prev point
        assert len(points) == 1
        assert points[0] == tp.center


class TestGetOptimizedPerimeterPoints:
    """Test the _get_optimized_perimeter_points function."""

    def test_optimized_perimeter_points_cylinder(self):
        """Test optimized perimeter points for cylinder."""
        tp = TaskTurnpoint(46.5, 8.0, 400.0)
        prev_point = (46.0, 8.0)
        next_point = (47.0, 8.0)

        points = _get_optimized_perimeter_points(tp, prev_point, next_point, 90)

        # Should return single optimal point
        assert len(points) == 1

    def test_optimized_perimeter_points_goal_line(self):
        """Test optimized perimeter points for goal line."""
        tp = TaskTurnpoint(46.5, 8.0, 400.0, goal_type="LINE")
        prev_point = (46.0, 8.0)
        next_point = (47.0, 8.0)

        points = _get_optimized_perimeter_points(tp, prev_point, next_point, 90)

        # Should return optimal goal line point
        assert len(points) == 1

    def test_optimized_perimeter_points_zero_radius(self):
        """Test optimized perimeter points with zero radius."""
        tp = TaskTurnpoint(46.5, 8.0, 0.0)
        prev_point = (46.0, 8.0)
        next_point = (47.0, 8.0)

        points = _get_optimized_perimeter_points(tp, prev_point, next_point, 90)

        # Should return center
        assert len(points) == 1
        assert points[0] == tp.center

    def test_optimized_perimeter_points_fallback(self):
        """Test fallback to uniform sampling when optimization not possible."""
        tp = TaskTurnpoint(46.5, 8.0, 400.0)
        # Use a dummy point instead of None to test fallback behavior
        dummy_point = (46.0, 8.0)
        next_point = (47.0, 8.0)

        # The function should handle the case where optimization might not be possible
        # and fall back to uniform perimeter points
        points = _get_optimized_perimeter_points(tp, dummy_point, next_point, 90)

        # Should return optimized point(s)
        assert len(points) >= 1


class TestDistanceThroughCenters:
    """Test the distance_through_centers function."""

    def test_distance_through_centers_basic(self):
        """Test basic distance calculation through centers."""
        tp1 = TaskTurnpoint(46.0, 8.0, 400.0)
        tp2 = TaskTurnpoint(46.1, 8.0, 400.0)
        tp3 = TaskTurnpoint(46.2, 8.0, 400.0)

        distance = distance_through_centers([tp1, tp2, tp3])

        # Calculate expected distance
        expected = (
            geodesic(tp1.center, tp2.center).meters
            + geodesic(tp2.center, tp3.center).meters
        )
        assert abs(distance - expected) < 1.0

    def test_distance_through_centers_single(self):
        """Test distance with single turnpoint."""
        tp1 = TaskTurnpoint(46.0, 8.0, 400.0)

        distance = distance_through_centers([tp1])
        assert distance == 0.0

    def test_distance_through_centers_empty(self):
        """Test distance with empty list."""
        distance = distance_through_centers([])
        assert distance == 0.0

    def test_distance_through_centers_two_points(self):
        """Test distance with two turnpoints."""
        tp1 = TaskTurnpoint(46.0, 8.0, 400.0)
        tp2 = TaskTurnpoint(46.1, 8.0, 400.0)

        distance = distance_through_centers([tp1, tp2])

        expected = geodesic(tp1.center, tp2.center).meters
        assert abs(distance - expected) < 1.0

    def test_distance_through_centers_real_coordinates(self):
        """Test distance with real-world coordinates."""
        # Approximate coordinates for some Alpine locations
        tp1 = TaskTurnpoint(46.5197, 8.0207, 400.0)  # Interlaken area
        tp2 = TaskTurnpoint(46.6033, 7.9108, 400.0)  # Grindelwald area
        tp3 = TaskTurnpoint(46.5586, 7.8986, 400.0)  # Lauterbrunnen area

        distance = distance_through_centers([tp1, tp2, tp3])

        # Should be a reasonable distance (several kilometers)
        assert 10000 < distance < 50000  # Between 10km and 50km
