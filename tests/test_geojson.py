"""Tests for GeoJSON generation functionality."""

from unittest.mock import Mock, patch

from pyxctsk import Goal, GoalType, Task, TaskType, Turnpoint, TurnpointType, Waypoint
from pyxctsk.geojson import (
    _calculate_goal_line_endpoints,
    _create_goal_line_features,
    _create_optimized_route_feature,
    _create_turnpoint_feature,
    _find_previous_turnpoint,
    _generate_semicircle_arc,
    _should_skip_last_turnpoint,
    generate_task_geojson,
)


class TestCreateTurnpointFeature:
    """Test the _create_turnpoint_feature function."""

    def test_create_turnpoint_feature_takeoff(self):
        """Test creating turnpoint feature for takeoff."""
        waypoint = Waypoint(name="Takeoff", lat=46.5, lon=8.0, alt_smoothed=1000)
        turnpoint = Mock()
        turnpoint.waypoint = waypoint
        turnpoint.type = "takeoff"
        turnpoint.radius = 1000

        feature = _create_turnpoint_feature(turnpoint, 0)

        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "Point"
        assert feature["geometry"]["coordinates"] == [8.0, 46.5]
        assert feature["properties"]["name"] == "Takeoff"
        assert feature["properties"]["type"] == "cylinder"
        assert feature["properties"]["radius"] == 1000
        assert feature["properties"]["color"] == "#204d74"  # takeoff color

    def test_create_turnpoint_feature_sss(self):
        """Test creating turnpoint feature for SSS."""
        waypoint = Waypoint(name="Start", lat=46.5, lon=8.0, alt_smoothed=1000)
        turnpoint = Mock()
        turnpoint.waypoint = waypoint
        turnpoint.type = "SSS"
        turnpoint.radius = 400

        feature = _create_turnpoint_feature(turnpoint, 1)

        assert feature["properties"]["color"] == "#ac2925"  # SSS color
        assert feature["properties"]["name"] == "Start"

    def test_create_turnpoint_feature_ess(self):
        """Test creating turnpoint feature for ESS."""
        waypoint = Waypoint(name="End", lat=46.5, lon=8.0, alt_smoothed=1000)
        turnpoint = Mock()
        turnpoint.waypoint = waypoint
        turnpoint.type = "ESS"
        turnpoint.radius = 400

        feature = _create_turnpoint_feature(turnpoint, 2)

        assert feature["properties"]["color"] == "#ac2925"  # ESS color

    def test_create_turnpoint_feature_goal(self):
        """Test creating turnpoint feature for goal."""
        waypoint = Waypoint(name="Goal", lat=46.5, lon=8.0, alt_smoothed=1000)
        turnpoint = Mock()
        turnpoint.waypoint = waypoint
        turnpoint.type = "goal"
        turnpoint.radius = 400

        feature = _create_turnpoint_feature(turnpoint, 3)

        assert feature["properties"]["color"] == "#398439"  # goal color

    def test_create_turnpoint_feature_default(self):
        """Test creating turnpoint feature with default type."""
        waypoint = Waypoint(name="TP1", lat=46.5, lon=8.0, alt_smoothed=1000)
        turnpoint = Mock()
        turnpoint.waypoint = waypoint
        turnpoint.type = "unknown"
        turnpoint.radius = 400

        feature = _create_turnpoint_feature(turnpoint, 1)

        assert feature["properties"]["color"] == "#269abc"  # default color

    def test_create_turnpoint_feature_no_name(self):
        """Test creating turnpoint feature without name."""
        waypoint = Waypoint(name="", lat=46.5, lon=8.0, alt_smoothed=1000)  # Empty name
        turnpoint = Mock()
        turnpoint.waypoint = waypoint
        turnpoint.type = None
        turnpoint.radius = 400

        feature = _create_turnpoint_feature(turnpoint, 2)

        assert feature["properties"]["name"] == "TP3"  # Auto-generated name
        assert feature["properties"]["color"] == "#269abc"  # default color

    def test_create_turnpoint_feature_properties(self):
        """Test that turnpoint feature has all required properties."""
        waypoint = Waypoint(name="Test", lat=46.5, lon=8.0, alt_smoothed=1000)
        turnpoint = Mock()
        turnpoint.waypoint = waypoint
        turnpoint.type = "takeoff"
        turnpoint.radius = 500

        feature = _create_turnpoint_feature(turnpoint, 0)

        props = feature["properties"]
        assert "name" in props
        assert "type" in props
        assert "radius" in props
        assert "description" in props
        assert "turnpoint_index" in props
        assert "tp_type" in props
        assert "color" in props
        assert "fillColor" in props
        assert "fillOpacity" in props
        assert "weight" in props
        assert "opacity" in props

        assert props["description"] == "Radius: 500m"
        assert props["turnpoint_index"] == 0


class TestCreateOptimizedRouteFeature:
    """Test the _create_optimized_route_feature function."""

    def test_create_optimized_route_feature_valid(self):
        """Test creating optimized route feature with valid coordinates."""
        coords = [(46.0, 8.0), (46.1, 8.1), (46.2, 8.2)]

        feature = _create_optimized_route_feature(coords)

        assert feature is not None
        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "LineString"
        assert len(feature["geometry"]["coordinates"]) == 3
        # Check coordinate conversion (lat, lon) -> [lon, lat]
        assert feature["geometry"]["coordinates"][0] == [8.0, 46.0]
        assert feature["geometry"]["coordinates"][1] == [8.1, 46.1]
        assert feature["geometry"]["coordinates"][2] == [8.2, 46.2]

        props = feature["properties"]
        assert props["name"] == "Optimized Route"
        assert props["type"] == "optimized_route"
        assert props["color"] == "#ff4136"

    def test_create_optimized_route_feature_single_point(self):
        """Test creating optimized route feature with single point."""
        coords = [(46.0, 8.0)]

        feature = _create_optimized_route_feature(coords)

        assert feature is None

    def test_create_optimized_route_feature_empty(self):
        """Test creating optimized route feature with empty coordinates."""
        coords = []

        feature = _create_optimized_route_feature(coords)

        assert feature is None

    def test_create_optimized_route_feature_two_points(self):
        """Test creating optimized route feature with minimum valid points."""
        coords = [(46.0, 8.0), (46.1, 8.1)]

        feature = _create_optimized_route_feature(coords)

        assert feature is not None
        assert len(feature["geometry"]["coordinates"]) == 2

    def test_create_optimized_route_feature_properties(self):
        """Test that optimized route feature has all required properties."""
        coords = [(46.0, 8.0), (46.1, 8.1)]

        feature = _create_optimized_route_feature(coords)

        assert (
            feature is not None
        )  # Ensure feature is not None before accessing properties
        props = feature["properties"]
        expected_props = [
            "name",
            "type",
            "color",
            "weight",
            "opacity",
            "arrowheads",
            "arrow_color",
            "arrow_size",
            "arrow_spacing",
        ]
        for prop in expected_props:
            assert prop in props


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
    """Test the _calculate_goal_line_endpoints function."""

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

        (lon1, lat1), (lon2, lat2), forward_azimuth = _calculate_goal_line_endpoints(
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

        (lon1, lat1), (lon2, lat2), forward_azimuth = _calculate_goal_line_endpoints(
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

        (lon1, lat1), (lon2, lat2), forward_azimuth = _calculate_goal_line_endpoints(
            last_tp, prev_tp, goal_line_length
        )

        # Both endpoints should be at the goal center
        assert abs(lon1 - 8.0) < 1e-10
        assert abs(lat1 - 47.0) < 1e-10
        assert abs(lon2 - 8.0) < 1e-10
        assert abs(lat2 - 47.0) < 1e-10


class TestGenerateSemicircleArc:
    """Test the _generate_semicircle_arc function."""

    def test_generate_semicircle_arc_basic(self):
        """Test basic semicircle arc generation."""
        center_lon = 8.0
        center_lat = 47.0
        start_azimuth = 270.0  # West
        end_azimuth = 90.0  # East
        through_azimuth = 0.0  # North
        radius = 200.0

        arc_points = _generate_semicircle_arc(
            center_lon, center_lat, start_azimuth, end_azimuth, through_azimuth, radius
        )

        # Should have GOAL_LINE_NUM_POINTS + 1 points
        from pyxctsk.geojson import GOAL_LINE_NUM_POINTS

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

        arc_points = _generate_semicircle_arc(
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
    """Test the _should_skip_last_turnpoint function."""

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

        result = _should_skip_last_turnpoint(task)

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

        result = _should_skip_last_turnpoint(task)

        assert result is False

    def test_should_skip_last_turnpoint_no_goal(self):
        """Test not skipping last turnpoint when no goal."""
        waypoint1 = Waypoint(name="TP1", lat=46.0, lon=8.0, alt_smoothed=1000)
        tp1 = Turnpoint(radius=400, waypoint=waypoint1, type=TurnpointType.TAKEOFF)

        task = Task(task_type=TaskType.CLASSIC, version=1, turnpoints=[tp1], goal=None)

        result = _should_skip_last_turnpoint(task)

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

        result = _should_skip_last_turnpoint(task)

        assert result is False


class TestGenerateTaskGeoJSON:
    """Test the generate_task_geojson function."""

    @patch("pyxctsk.geojson.optimized_route_coordinates")
    @patch("pyxctsk.geojson._task_to_turnpoints")
    def test_generate_task_geojson_basic(
        self, mock_task_to_turnpoints, mock_opt_coords
    ):
        """Test basic GeoJSON generation."""
        # Mock the dependencies
        mock_task_to_turnpoints.return_value = []
        mock_opt_coords.return_value = [(46.0, 8.0), (47.0, 8.0)]

        waypoint1 = Waypoint(name="TP1", lat=46.0, lon=8.0, alt_smoothed=1000)
        waypoint2 = Waypoint(name="TP2", lat=47.0, lon=8.0, alt_smoothed=500)

        tp1 = Turnpoint(radius=400, waypoint=waypoint1, type=TurnpointType.TAKEOFF)
        tp2 = Turnpoint(radius=400, waypoint=waypoint2, type=TurnpointType.NONE)

        task = Task(task_type=TaskType.CLASSIC, version=1, turnpoints=[tp1, tp2])

        result = generate_task_geojson(task)

        assert result["type"] == "FeatureCollection"
        assert "features" in result
        assert len(result["features"]) >= 2  # At least turnpoints

    @patch("pyxctsk.geojson.optimized_route_coordinates")
    @patch("pyxctsk.geojson._task_to_turnpoints")
    def test_generate_task_geojson_line_goal(
        self, mock_task_to_turnpoints, mock_opt_coords
    ):
        """Test GeoJSON generation with LINE goal."""
        mock_task_to_turnpoints.return_value = []
        mock_opt_coords.return_value = [(46.0, 8.0), (47.0, 8.0)]

        waypoint1 = Waypoint(name="TP1", lat=46.0, lon=8.0, alt_smoothed=1000)
        waypoint2 = Waypoint(name="Goal", lat=47.0, lon=8.0, alt_smoothed=500)

        tp1 = Turnpoint(radius=400, waypoint=waypoint1, type=TurnpointType.TAKEOFF)
        tp2 = Turnpoint(radius=400, waypoint=waypoint2, type=TurnpointType.NONE)

        goal = Goal(type=GoalType.LINE, line_length=500.0)
        task = Task(
            task_type=TaskType.CLASSIC, version=1, turnpoints=[tp1, tp2], goal=goal
        )

        result = generate_task_geojson(task)

        assert result["type"] == "FeatureCollection"
        features = result["features"]

        # Should have fewer turnpoint features (last one skipped) + goal line features
        turnpoint_features = [
            f for f in features if f["properties"].get("type") == "cylinder"
        ]
        goal_line_features = [
            f for f in features if f["properties"].get("type") == "goal_line"
        ]

        assert len(turnpoint_features) == 1  # Only first turnpoint
        assert len(goal_line_features) >= 1  # At least goal line

    @patch("pyxctsk.geojson.optimized_route_coordinates")
    @patch("pyxctsk.geojson._task_to_turnpoints")
    def test_generate_task_geojson_no_optimized_route(
        self, mock_task_to_turnpoints, mock_opt_coords
    ):
        """Test GeoJSON generation without optimized route."""
        mock_task_to_turnpoints.return_value = []
        mock_opt_coords.return_value = []  # No optimized route

        waypoint1 = Waypoint(name="TP1", lat=46.0, lon=8.0, alt_smoothed=1000)
        tp1 = Turnpoint(radius=400, waypoint=waypoint1, type=TurnpointType.TAKEOFF)

        task = Task(task_type=TaskType.CLASSIC, version=1, turnpoints=[tp1])

        result = generate_task_geojson(task)

        features = result["features"]
        route_features = [
            f for f in features if f["properties"].get("type") == "optimized_route"
        ]

        assert len(route_features) == 0  # No route feature

    @patch("pyxctsk.geojson.optimized_route_coordinates")
    @patch("pyxctsk.geojson._task_to_turnpoints")
    def test_generate_task_geojson_empty_task(
        self, mock_task_to_turnpoints, mock_opt_coords
    ):
        """Test GeoJSON generation with empty task."""
        mock_task_to_turnpoints.return_value = []
        mock_opt_coords.return_value = []

        task = Task(task_type=TaskType.CLASSIC, version=1, turnpoints=[])

        result = generate_task_geojson(task)

        assert result["type"] == "FeatureCollection"
        assert len(result["features"]) == 0
