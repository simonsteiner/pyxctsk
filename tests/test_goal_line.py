"""Tests for goal line functionality.

Unit tests for goal line generation and calculation logic in pyxctsk.

This module covers:
- Goal line endpoint calculations based on approach direction
- Semicircle arc generation for goal control zones
- Goal line feature creation for GeoJSON output
- Logic for determining when to skip last turnpoint for LINE goals
- Helper functions for finding previous turnpoints with valid coordinates
"""

from unittest.mock import Mock

from pyxctsk import Goal, GoalType, Task, TaskType, Turnpoint, TurnpointType, Waypoint
from pyxctsk.geojson import _create_goal_line_features
from pyxctsk.goal_line import (
    _find_previous_turnpoint,
    calculate_goal_line_endpoints,
    generate_semicircle_arc,
    should_skip_last_turnpoint,
)


class TestFindPreviousTurnpoint:
    """Test the _find_previous_turnpoint function."""

    def test_find_previous_turnpoint_different_coords(self):
        """Test finding previous turnpoint with different coordinates."""
        last_tp = Mock()
        last_tp.waypoint = Mock()
        last_tp.waypoint.lat = 47.0
        last_tp.waypoint.lon = 8.0

        tp1 = Mock()
        tp1.waypoint = Mock()
        tp1.waypoint.lat = 46.0
        tp1.waypoint.lon = 8.0

        tp2 = Mock()
        tp2.waypoint = Mock()
        tp2.waypoint.lat = 46.5
        tp2.waypoint.lon = 8.1

        turnpoints = [tp1, tp2, last_tp]

        result = _find_previous_turnpoint(turnpoints, last_tp)

        assert result == tp2

    def test_find_previous_turnpoint_same_coords(self):
        """Test finding previous turnpoint when some have same coordinates."""
        last_tp = Mock()
        last_tp.waypoint = Mock()
        last_tp.waypoint.lat = 47.0
        last_tp.waypoint.lon = 8.0

        tp1 = Mock()
        tp1.waypoint = Mock()
        tp1.waypoint.lat = 46.0
        tp1.waypoint.lon = 8.0

        tp2 = Mock()  # Same coordinates as last_tp
        tp2.waypoint = Mock()
        tp2.waypoint.lat = 47.0
        tp2.waypoint.lon = 8.0

        turnpoints = [tp1, tp2, last_tp]

        result = _find_previous_turnpoint(turnpoints, last_tp)

        assert result == tp1  # Should skip tp2 and return tp1

    def test_find_previous_turnpoint_all_same_coords(self):
        """Test finding previous turnpoint when all have same coordinates."""
        last_tp = Mock()
        last_tp.waypoint = Mock()
        last_tp.waypoint.lat = 47.0
        last_tp.waypoint.lon = 8.0

        tp1 = Mock()
        tp1.waypoint = Mock()
        tp1.waypoint.lat = 47.0
        tp1.waypoint.lon = 8.0

        turnpoints = [tp1, last_tp]

        result = _find_previous_turnpoint(turnpoints, last_tp)

        assert result is None

    def test_find_previous_turnpoint_tolerance(self):
        """Test coordinate tolerance in finding previous turnpoint."""
        last_tp = Mock()
        last_tp.waypoint = Mock()
        last_tp.waypoint.lat = 47.0
        last_tp.waypoint.lon = 8.0

        tp1 = Mock()  # Within tolerance
        tp1.waypoint = Mock()
        tp1.waypoint.lat = 47.0 + 1e-10  # Very small difference
        tp1.waypoint.lon = 8.0

        turnpoints = [tp1, last_tp]

        result = _find_previous_turnpoint(turnpoints, last_tp)

        assert result is None  # Should be treated as same coordinates


class TestCalculateGoalLineEndpoints:
    """Test the calculate_goal_line_endpoints function."""

    def test_calculate_goal_line_endpoints_basic(self):
        """Test basic goal line endpoint calculation."""
        last_tp = Mock()
        last_tp.waypoint = Mock()
        last_tp.waypoint.lat = 47.0
        last_tp.waypoint.lon = 8.0

        prev_tp = Mock()
        prev_tp.waypoint = Mock()
        prev_tp.waypoint.lat = 46.0
        prev_tp.waypoint.lon = 8.0

        goal_line_length = 400.0

        (lon1, lat1), (lon2, lat2), forward_azimuth = calculate_goal_line_endpoints(
            last_tp, prev_tp, goal_line_length
        )

        # Both endpoints should be valid coordinates
        assert isinstance(lon1, float)
        assert isinstance(lat1, float)
        assert isinstance(lon2, float)
        assert isinstance(lat2, float)
        assert isinstance(forward_azimuth, float)

        # Forward azimuth should be approximately 0 (north) for this setup
        assert abs(forward_azimuth) < 1.0 or abs(forward_azimuth - 360) < 1.0

    def test_calculate_goal_line_endpoints_east_west(self):
        """Test goal line endpoints for east-west approach."""
        last_tp = Mock()
        last_tp.waypoint = Mock()
        last_tp.waypoint.lat = 47.0
        last_tp.waypoint.lon = 8.0

        prev_tp = Mock()
        prev_tp.waypoint = Mock()
        prev_tp.waypoint.lat = 47.0
        prev_tp.waypoint.lon = 7.0  # West of goal

        goal_line_length = 400.0

        (lon1, lat1), (lon2, lat2), forward_azimuth = calculate_goal_line_endpoints(
            last_tp, prev_tp, goal_line_length
        )

        # Forward azimuth should be approximately 90 (east)
        assert abs(forward_azimuth - 90) < 1.0

    def test_calculate_goal_line_endpoints_zero_length(self):
        """Test goal line endpoints with zero length."""
        last_tp = Mock()
        last_tp.waypoint = Mock()
        last_tp.waypoint.lat = 47.0
        last_tp.waypoint.lon = 8.0

        prev_tp = Mock()
        prev_tp.waypoint = Mock()
        prev_tp.waypoint.lat = 46.0
        prev_tp.waypoint.lon = 8.0

        goal_line_length = 0.0

        (lon1, lat1), (lon2, lat2), forward_azimuth = calculate_goal_line_endpoints(
            last_tp, prev_tp, goal_line_length
        )

        # Both endpoints should be at the goal center
        assert abs(lon1 - 8.0) < 1e-10
        assert abs(lat1 - 47.0) < 1e-10
        assert abs(lon2 - 8.0) < 1e-10
        assert abs(lat2 - 47.0) < 1e-10


class TestGenerateSemicircleArc:
    """Test the generate_semicircle_arc function."""

    def test_generate_semicircle_arc_basic(self):
        """Test basic semicircle arc generation."""
        center_lon = 8.0
        center_lat = 47.0
        start_azimuth = 270.0  # West
        end_azimuth = 90.0  # East
        through_azimuth = 0.0  # North
        radius = 200.0

        arc_points = generate_semicircle_arc(
            center_lon, center_lat, start_azimuth, end_azimuth, through_azimuth, radius
        )

        # Should have GOAL_LINE_NUM_POINTS + 1 points
        from pyxctsk.goal_line import GOAL_LINE_NUM_POINTS

        assert len(arc_points) == GOAL_LINE_NUM_POINTS + 1

        # Each point should be [lon, lat] format
        for point in arc_points:
            assert len(point) == 2
            assert isinstance(point[0], float)  # longitude
            assert isinstance(point[1], float)  # latitude

    def test_generate_semicircle_arc_zero_radius(self):
        """Test semicircle arc with zero radius."""
        center_lon = 8.0
        center_lat = 47.0
        start_azimuth = 270.0
        end_azimuth = 90.0
        through_azimuth = 0.0
        radius = 0.0

        arc_points = generate_semicircle_arc(
            center_lon, center_lat, start_azimuth, end_azimuth, through_azimuth, radius
        )

        # All points should be at the center
        for point in arc_points:
            assert abs(point[0] - center_lon) < 1e-10
            assert abs(point[1] - center_lat) < 1e-10


class TestCreateGoalLineFeatures:
    """Test the _create_goal_line_features function."""

    def test_create_goal_line_features_valid_line_goal(self):
        """Test creating goal line features for valid LINE goal."""
        # Create a task with LINE goal
        waypoint1 = Waypoint(name="TP1", lat=46.0, lon=8.0, alt_smoothed=1000)
        waypoint2 = Waypoint(name="Goal", lat=47.0, lon=8.0, alt_smoothed=500)

        tp1 = Turnpoint(radius=400, waypoint=waypoint1, type=TurnpointType.TAKEOFF)
        tp2 = Turnpoint(radius=400, waypoint=waypoint2, type=TurnpointType.NONE)

        goal = Goal(type=GoalType.LINE, line_length=500.0)
        task = Task(
            task_type=TaskType.CLASSIC, version=1, turnpoints=[tp1, tp2], goal=goal
        )

        features = _create_goal_line_features(task)

        assert len(features) == 2  # Goal line + control zone

        # Check goal line feature
        goal_line = features[0]
        assert goal_line["type"] == "Feature"
        assert goal_line["geometry"]["type"] == "LineString"
        assert goal_line["properties"]["type"] == "goal_line"
        # Task.__post_init__ sets line_length to 2 * radius (400 * 2 = 800)
        assert goal_line["properties"]["length"] == 800.0

        # Check control zone feature
        control_zone = features[1]
        assert control_zone["type"] == "Feature"
        assert control_zone["geometry"]["type"] == "Polygon"
        assert control_zone["properties"]["type"] == "goal_control_zone"

    def test_create_goal_line_features_no_line_length(self):
        """Test creating goal line features without explicit line length."""
        waypoint1 = Waypoint(name="TP1", lat=46.0, lon=8.0, alt_smoothed=1000)
        waypoint2 = Waypoint(name="Goal", lat=47.0, lon=8.0, alt_smoothed=500)

        tp1 = Turnpoint(radius=400, waypoint=waypoint1, type=TurnpointType.TAKEOFF)
        tp2 = Turnpoint(radius=200, waypoint=waypoint2, type=TurnpointType.NONE)

        goal = Goal(type=GoalType.LINE)  # No line_length specified
        task = Task(
            task_type=TaskType.CLASSIC, version=1, turnpoints=[tp1, tp2], goal=goal
        )

        features = _create_goal_line_features(task)

        assert len(features) == 2
        # Should use 2 * radius as line length
        assert features[0]["properties"]["length"] == 400.0  # 2 * 200

    def test_create_goal_line_features_cylinder_goal(self):
        """Test creating goal line features for CYLINDER goal."""
        waypoint1 = Waypoint(name="TP1", lat=46.0, lon=8.0, alt_smoothed=1000)
        waypoint2 = Waypoint(name="Goal", lat=47.0, lon=8.0, alt_smoothed=500)

        tp1 = Turnpoint(radius=400, waypoint=waypoint1, type=TurnpointType.TAKEOFF)
        tp2 = Turnpoint(radius=400, waypoint=waypoint2, type=TurnpointType.NONE)

        goal = Goal(type=GoalType.CYLINDER)  # Not LINE type
        task = Task(
            task_type=TaskType.CLASSIC, version=1, turnpoints=[tp1, tp2], goal=goal
        )

        features = _create_goal_line_features(task)

        assert len(features) == 0  # No features for CYLINDER goal

    def test_create_goal_line_features_no_goal(self):
        """Test creating goal line features when no goal."""
        waypoint1 = Waypoint(name="TP1", lat=46.0, lon=8.0, alt_smoothed=1000)
        tp1 = Turnpoint(radius=400, waypoint=waypoint1, type=TurnpointType.TAKEOFF)

        task = Task(task_type=TaskType.CLASSIC, version=1, turnpoints=[tp1], goal=None)

        features = _create_goal_line_features(task)

        assert len(features) == 0

    def test_create_goal_line_features_insufficient_turnpoints(self):
        """Test creating goal line features with insufficient turnpoints."""
        waypoint1 = Waypoint(name="TP1", lat=46.0, lon=8.0, alt_smoothed=1000)
        tp1 = Turnpoint(radius=400, waypoint=waypoint1, type=TurnpointType.TAKEOFF)

        goal = Goal(type=GoalType.LINE, line_length=500.0)
        task = Task(
            task_type=TaskType.CLASSIC,
            version=1,
            turnpoints=[tp1],  # Only one turnpoint
            goal=goal,
        )

        features = _create_goal_line_features(task)

        assert len(features) == 0

    def test_create_goal_line_features_no_previous_turnpoint(self):
        """Test creating goal line features when no valid previous turnpoint."""
        # Create turnpoints with same coordinates
        waypoint1 = Waypoint(name="TP1", lat=47.0, lon=8.0, alt_smoothed=1000)
        waypoint2 = Waypoint(name="Goal", lat=47.0, lon=8.0, alt_smoothed=500)

        tp1 = Turnpoint(radius=400, waypoint=waypoint1, type=TurnpointType.TAKEOFF)
        tp2 = Turnpoint(radius=400, waypoint=waypoint2, type=TurnpointType.NONE)

        goal = Goal(type=GoalType.LINE, line_length=500.0)
        task = Task(
            task_type=TaskType.CLASSIC, version=1, turnpoints=[tp1, tp2], goal=goal
        )

        features = _create_goal_line_features(task)

        assert len(features) == 0  # No features when no valid previous TP


class TestShouldSkipLastTurnpoint:
    """Test the should_skip_last_turnpoint function."""

    def test_should_skip_last_turnpoint_line_goal(self):
        """Test skipping last turnpoint for LINE goal."""
        waypoint1 = Waypoint(name="TP1", lat=46.0, lon=8.0, alt_smoothed=1000)
        waypoint2 = Waypoint(name="Goal", lat=47.0, lon=8.0, alt_smoothed=500)

        tp1 = Turnpoint(radius=400, waypoint=waypoint1, type=TurnpointType.TAKEOFF)
        tp2 = Turnpoint(radius=400, waypoint=waypoint2, type=TurnpointType.NONE)

        goal = Goal(type=GoalType.LINE)
        task = Task(
            task_type=TaskType.CLASSIC, version=1, turnpoints=[tp1, tp2], goal=goal
        )

        result = should_skip_last_turnpoint(task)

        assert result is True

    def test_should_skip_last_turnpoint_cylinder_goal(self):
        """Test not skipping last turnpoint for CYLINDER goal."""
        waypoint1 = Waypoint(name="TP1", lat=46.0, lon=8.0, alt_smoothed=1000)
        waypoint2 = Waypoint(name="Goal", lat=47.0, lon=8.0, alt_smoothed=500)

        tp1 = Turnpoint(radius=400, waypoint=waypoint1, type=TurnpointType.TAKEOFF)
        tp2 = Turnpoint(radius=400, waypoint=waypoint2, type=TurnpointType.NONE)

        goal = Goal(type=GoalType.CYLINDER)
        task = Task(
            task_type=TaskType.CLASSIC, version=1, turnpoints=[tp1, tp2], goal=goal
        )

        result = should_skip_last_turnpoint(task)

        assert result is False

    def test_should_skip_last_turnpoint_no_goal(self):
        """Test not skipping last turnpoint when no goal."""
        waypoint1 = Waypoint(name="TP1", lat=46.0, lon=8.0, alt_smoothed=1000)
        tp1 = Turnpoint(radius=400, waypoint=waypoint1, type=TurnpointType.TAKEOFF)

        task = Task(task_type=TaskType.CLASSIC, version=1, turnpoints=[tp1], goal=None)

        result = should_skip_last_turnpoint(task)

        assert result is False

    def test_should_skip_last_turnpoint_insufficient_turnpoints(self):
        """Test not skipping when insufficient turnpoints."""
        waypoint1 = Waypoint(name="TP1", lat=46.0, lon=8.0, alt_smoothed=1000)
        tp1 = Turnpoint(radius=400, waypoint=waypoint1, type=TurnpointType.TAKEOFF)

        goal = Goal(type=GoalType.LINE)
        task = Task(
            task_type=TaskType.CLASSIC,
            version=1,
            turnpoints=[tp1],  # Only one turnpoint
            goal=goal,
        )

        result = should_skip_last_turnpoint(task)

        assert result is False
