"""Tests for GeoJSON generation functionality.

Unit tests for GeoJSON generation and geometry logic in pyxctsk.

This module covers:
- Creation of GeoJSON features for turnpoints and optimized routes
- Validation of feature properties, geometry, and color coding
- Task-level GeoJSON output for various goal types and task structures
"""

from unittest.mock import Mock, patch

from pyxctsk import Goal, GoalType, Task, TaskType, Turnpoint, TurnpointType, Waypoint
from pyxctsk.geojson import (
    _create_optimized_route_feature,
    _create_turnpoint_feature,
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

        # Should have fewer turnpoint features (last one skipped) for LINE goal
        turnpoint_features = [
            f for f in features if f["properties"].get("type") == "cylinder"
        ]

        assert len(turnpoint_features) == 1  # Only first turnpoint

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
