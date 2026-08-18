"""Tests for GeoJSON generation functionality.

Unit tests for GeoJSON generation and geometry logic in pyxctsk.

This module covers:
- Creation of GeoJSON features for turnpoints and optimized routes
- Validation of feature properties, geometry, and color coding
- Task-level GeoJSON output for various goal types and task structures

The hex colours asserted below are written out on purpose rather than read from
`export.common`'s palette: they are golden values, and pinning the actual bytes
is what makes a change to a palette constant show up as a failing test instead
of a test that agrees with whatever the constant now says. `test_common.py`
holds the complementary check — that both formats render the same palette — so
between them a colour cannot change silently or drift between writers.
"""

import pytest

from pyxctsk import Goal, GoalType, Task, TaskType, Turnpoint, TurnpointType, Waypoint
from pyxctsk.distance import MeasuredTask, OptimizedRoute
from pyxctsk.export.common import TaskDrawing
from pyxctsk.export.geojson import (
    _create_goal_line_features,
    _create_optimized_route_feature,
    _create_turnpoint_feature,
    generate_task_geojson,
)
from tests.builders import turnpoint


def _route(points) -> OptimizedRoute:
    """An OptimizedRoute through exactly these (lat, lon) points."""
    return OptimizedRoute(
        points=tuple(points), legs=(0.0,) * max(0, len(tuple(points)) - 1)
    )


def _measured(task: Task, points) -> MeasuredTask:
    """A measured task whose route is exactly these (lat, lon) points.

    The writers never look at the cylinders, only the route, so this leaves
    them empty rather than deriving them — the point of the seam is to render
    without running the optimizer.
    """
    return MeasuredTask(task=task, turnpoints=(), route=_route(points))


def _drawing_of(turnpoints: list, goal: Goal | None = None) -> TaskDrawing:
    """A drawing for a task of these turnpoints, with no route computed.

    Building the value directly is the seam the writers' tests need: a feature
    can be rendered without running the optimizer, and a route can be chosen
    outright. Four ``@patch("...get_optimized_route_coordinates")`` decorators
    used to stand in for this and never applied — geojson.py bound the name at
    import time, so those tests silently ran the real optimizer instead.
    """
    task = Task(task_type=TaskType.CLASSIC, version=1, turnpoints=turnpoints, goal=goal)
    return TaskDrawing(
        task=task,
        turnpoints=tuple(turnpoints),
        goal_line=None,
        measured=_measured(task, ()),
    )


class TestCreateTurnpointFeature:
    """One turnpoint rendered as a GeoJSON point feature."""

    @pytest.mark.parametrize(
        "tp_type, colour",
        [
            (TurnpointType.TAKEOFF, "#204d74"),
            (TurnpointType.SSS, "#ac2925"),
            (TurnpointType.ESS, "#ff8c00"),
            (TurnpointType.NONE, "#269abc"),
        ],
        ids=["takeoff", "sss", "ess", "ordinary"],
    )
    def test_the_colour_follows_the_turnpoint_role(self, tp_type, colour):
        """Four roles, four palette entries, one task shape."""
        first = turnpoint("First", 46.5, 8.0, radius=400, type=tp_type)
        drawing = _drawing_of([first, turnpoint("Goal", 47.0, 8.5, radius=400)])

        feature = _create_turnpoint_feature(drawing, first, 0)

        assert feature["properties"]["color"] == colour

    def test_the_goal_is_red(self):
        """The last turnpoint of a task that has a goal."""
        first = turnpoint("Start", 46.5, 8.0, radius=400)
        goal = turnpoint("Goal", 47.5, 9.0, radius=400)
        drawing = _drawing_of([first, goal], Goal(type=GoalType.CYLINDER))

        feature = _create_turnpoint_feature(drawing, goal, 1)

        assert feature["properties"]["color"] == "#ff0000"

    def test_the_geometry_is_the_waypoint(self):
        """A turnpoint feature is a point at its waypoint's position."""
        first = turnpoint("Takeoff", 46.5, 8.0, radius=1000, type=TurnpointType.TAKEOFF)
        drawing = _drawing_of([first, turnpoint("Goal", 47.0, 8.5, radius=400)])

        feature = _create_turnpoint_feature(drawing, first, 0)

        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "Point"
        assert feature["geometry"]["coordinates"] == [8.0, 46.5]
        assert feature["properties"]["name"] == "Takeoff"
        assert feature["properties"]["type"] == "cylinder"
        assert feature["properties"]["radius"] == 1000

    def test_an_unnamed_turnpoint_is_numbered(self):
        """A waypoint with no name still has to be labelled on the map."""
        unnamed = turnpoint("", 46.5, 8.0, radius=400)
        drawing = _drawing_of([unnamed, turnpoint("Goal", 47.0, 8.5, radius=400)])

        feature = _create_turnpoint_feature(drawing, unnamed, 0)

        assert feature["properties"]["name"] == "TP1"

    def test_the_feature_carries_every_property_the_map_reads(self):
        """The styling keys are the interface to the rendering library."""
        first = turnpoint("Test", 46.5, 8.0, radius=500, type=TurnpointType.TAKEOFF)
        drawing = _drawing_of([first, turnpoint("Goal", 47.0, 8.5, radius=400)])

        props = _create_turnpoint_feature(drawing, first, 0)["properties"]

        assert set(props) >= {
            "name",
            "type",
            "radius",
            "description",
            "turnpoint_index",
            "tp_type",
            "color",
            "fillColor",
            "fillOpacity",
            "weight",
            "opacity",
        }
        assert props["description"] == "Type: TAKEOFF, Radius: 500m"
        assert props["turnpoint_index"] == 0


def _route_drawing(points) -> TaskDrawing:
    """A drawing whose route is exactly these (lat, lon) points."""
    task = Task(task_type=TaskType.CLASSIC, version=1, turnpoints=[])
    return TaskDrawing(
        task=task, turnpoints=(), goal_line=None, measured=_measured(task, points)
    )


class TestCreateOptimizedRouteFeature:
    """Test the _create_optimized_route_feature function."""

    def test_create_optimized_route_feature_valid(self):
        """Test creating optimized route feature with valid coordinates."""
        coords = [(46.0, 8.0), (46.1, 8.1), (46.2, 8.2)]

        feature = _create_optimized_route_feature(_route_drawing(coords))

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

        feature = _create_optimized_route_feature(_route_drawing(coords))

        assert feature is None

    def test_create_optimized_route_feature_empty(self):
        """Test creating optimized route feature with empty coordinates."""
        coords: list[tuple[float, float]] = []

        feature = _create_optimized_route_feature(_route_drawing(coords))

        assert feature is None

    def test_create_optimized_route_feature_two_points(self):
        """Test creating optimized route feature with minimum valid points."""
        coords = [(46.0, 8.0), (46.1, 8.1)]

        feature = _create_optimized_route_feature(_route_drawing(coords))

        assert feature is not None
        assert len(feature["geometry"]["coordinates"]) == 2

    def test_create_optimized_route_feature_properties(self):
        """Test that optimized route feature has all required properties."""
        coords = [(46.0, 8.0), (46.1, 8.1)]

        feature = _create_optimized_route_feature(_route_drawing(coords))

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

    def test_generate_task_geojson_basic(self):
        """Test basic GeoJSON generation."""
        waypoint1 = Waypoint(name="TP1", lat=46.0, lon=8.0, alt_smoothed=1000)
        waypoint2 = Waypoint(name="TP2", lat=47.0, lon=8.0, alt_smoothed=500)

        tp1 = Turnpoint(radius=400, waypoint=waypoint1, type=TurnpointType.TAKEOFF)
        tp2 = Turnpoint(radius=400, waypoint=waypoint2, type=TurnpointType.NONE)

        task = Task(task_type=TaskType.CLASSIC, version=1, turnpoints=[tp1, tp2])

        result = generate_task_geojson(task)

        assert result["type"] == "FeatureCollection"
        assert "features" in result
        assert len(result["features"]) >= 2  # At least turnpoints

    def test_generate_task_geojson_line_goal(self):
        """Test GeoJSON generation with LINE goal."""
        waypoint1 = Waypoint(name="TP1", lat=46.0, lon=8.0, alt_smoothed=1000)
        waypoint2 = Waypoint(name="Goal", lat=47.0, lon=8.0, alt_smoothed=500)

        tp1 = Turnpoint(radius=400, waypoint=waypoint1, type=TurnpointType.TAKEOFF)
        tp2 = Turnpoint(radius=400, waypoint=waypoint2, type=TurnpointType.NONE)

        goal = Goal(type=GoalType.LINE)
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

    def test_generate_task_geojson_no_optimized_route(self):
        """Test GeoJSON generation without optimized route."""
        waypoint1 = Waypoint(name="TP1", lat=46.0, lon=8.0, alt_smoothed=1000)
        tp1 = Turnpoint(radius=400, waypoint=waypoint1, type=TurnpointType.TAKEOFF)

        task = Task(task_type=TaskType.CLASSIC, version=1, turnpoints=[tp1])

        result = generate_task_geojson(task)

        features = result["features"]
        route_features = [
            f for f in features if f["properties"].get("type") == "optimized_route"
        ]

        assert len(route_features) == 0  # No route feature

    def test_generate_task_geojson_empty_task(self):
        """Test GeoJSON generation with empty task."""
        task = Task(task_type=TaskType.CLASSIC, version=1, turnpoints=[])

        result = generate_task_geojson(task)

        assert result["type"] == "FeatureCollection"
        assert len(result["features"]) == 0


class TestRepeatedTurnpoint:
    """A task may fly the same turnpoint twice, ending on it."""

    def test_repeated_final_turnpoint_is_still_the_goal(self):
        """The goal is identified by position, not by value.

        `Turnpoint` is a plain dataclass, so a task whose last turnpoint
        repeats an earlier one verbatim — same name, coordinates, radius and
        type — has two equal turnpoints. Searching the list by value finds the
        earlier one and styles the goal as an ordinary turnpoint.
        """

        def tp(name: str, lat: float, lon: float) -> Turnpoint:
            return Turnpoint(
                radius=1000,
                waypoint=Waypoint(name=name, lat=lat, lon=lon, alt_smoothed=0),
                type=TurnpointType.NONE,
            )

        turnpoints = [tp("A", 47.0, 8.0), tp("B", 47.1, 8.1), tp("B", 47.1, 8.1)]
        task = Task(
            task_type=TaskType.CLASSIC,
            version=1,
            turnpoints=turnpoints,
            goal=Goal(type=GoalType.CYLINDER),
        )

        assert turnpoints[-1] == turnpoints[-2], "precondition: the two are equal"

        drawing = _drawing_of(turnpoints, task.goal)
        goal_feature = _create_turnpoint_feature(drawing, turnpoints[-1], 2)
        middle_feature = _create_turnpoint_feature(drawing, turnpoints[1], 1)

        assert goal_feature["properties"]["color"] == "#ff0000"  # goal red
        assert middle_feature["properties"]["color"] == "#269abc"  # default blue


class TestLineGoalWithoutAnApproach:
    """A LINE goal that cannot produce a line still has to be drawn.

    The last turnpoint is dropped because a goal line replaces it. When the
    previous turnpoint sits at the goal's own coordinates there is no approach
    azimuth, so there is no line — and the goal used to be dropped anyway,
    leaving nothing in either output to represent it.
    """

    @staticmethod
    def _task(goal_lat: float) -> Task:
        """Build a LINE-goal task whose first turnpoint is at ``goal_lat``."""
        return Task(
            task_type=TaskType.CLASSIC,
            version=1,
            turnpoints=[
                Turnpoint(
                    radius=1000,
                    waypoint=Waypoint(name="A", lat=goal_lat, lon=8.0, alt_smoothed=0),
                    type=TurnpointType.TAKEOFF,
                ),
                Turnpoint(
                    radius=400,
                    waypoint=Waypoint(name="Goal", lat=47.0, lon=8.0, alt_smoothed=0),
                    type=TurnpointType.NONE,
                ),
            ],
            goal=Goal(type=GoalType.LINE),
        )

    def test_coincident_previous_turnpoint_keeps_the_goal(self):
        """No goal line means the goal turnpoint is rendered, in goal red."""
        geojson = generate_task_geojson(self._task(goal_lat=47.0))
        by_type = [f["properties"]["type"] for f in geojson["features"]]

        assert "goal_line" not in by_type, "precondition: no line can be drawn"
        goals = [
            f
            for f in geojson["features"]
            if f["properties"].get("name") == "Goal"
            and f["properties"]["type"] == "cylinder"
        ]
        assert len(goals) == 1, "the goal must survive in some form"
        assert goals[0]["properties"]["color"] == "#ff0000"

    def test_distinct_previous_turnpoint_replaces_the_goal_with_the_line(self):
        """With an approach direction, the line stands in for the turnpoint."""
        geojson = generate_task_geojson(self._task(goal_lat=46.0))
        by_type = [f["properties"]["type"] for f in geojson["features"]]

        assert "goal_line" in by_type
        assert "goal_control_zone" in by_type
        names = [f["properties"].get("name") for f in geojson["features"]]
        assert "Goal" not in names, "the goal line replaces the goal cylinder"


class TestCreateGoalLineFeatures:
    """Test the _create_goal_line_features function.

    These moved here from ``tests/distance/test_goal_line.py``: they assert on
    GeoJSON output, so a distance test had been importing an export private to
    run them.
    """

    def test_create_goal_line_features_valid_line_goal(self):
        """Test creating goal line features for valid LINE goal."""
        # Create a task with LINE goal
        waypoint1 = Waypoint(name="TP1", lat=46.0, lon=8.0, alt_smoothed=1000)
        waypoint2 = Waypoint(name="Goal", lat=47.0, lon=8.0, alt_smoothed=500)

        tp1 = Turnpoint(radius=400, waypoint=waypoint1, type=TurnpointType.TAKEOFF)
        tp2 = Turnpoint(radius=400, waypoint=waypoint2, type=TurnpointType.NONE)

        goal = Goal(type=GoalType.LINE)
        task = Task(
            task_type=TaskType.CLASSIC, version=1, turnpoints=[tp1, tp2], goal=goal
        )

        features = _create_goal_line_features(TaskDrawing.from_task(task))

        assert len(features) == 2  # Goal line + control zone

        # Check goal line feature
        goal_line = features[0]
        assert goal_line["type"] == "Feature"
        assert goal_line["geometry"]["type"] == "LineString"
        assert goal_line["properties"]["type"] == "goal_line"
        # The goal-line length is twice the last radius (400 * 2 = 800).
        assert goal_line["properties"]["length"] == 800.0

        # Check control zone feature
        control_zone = features[1]
        assert control_zone["type"] == "Feature"
        assert control_zone["geometry"]["type"] == "Polygon"
        assert control_zone["properties"]["type"] == "goal_control_zone"

    def test_create_goal_line_features_length_tracks_goal_radius(self):
        """The goal-line length follows the goal turnpoint's radius, not the previous one."""
        waypoint1 = Waypoint(name="TP1", lat=46.0, lon=8.0, alt_smoothed=1000)
        waypoint2 = Waypoint(name="Goal", lat=47.0, lon=8.0, alt_smoothed=500)

        tp1 = Turnpoint(radius=400, waypoint=waypoint1, type=TurnpointType.TAKEOFF)
        tp2 = Turnpoint(radius=200, waypoint=waypoint2, type=TurnpointType.NONE)

        goal = Goal(type=GoalType.LINE)
        task = Task(
            task_type=TaskType.CLASSIC, version=1, turnpoints=[tp1, tp2], goal=goal
        )

        features = _create_goal_line_features(TaskDrawing.from_task(task))

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

        features = _create_goal_line_features(TaskDrawing.from_task(task))

        assert len(features) == 0  # No features for CYLINDER goal

    def test_create_goal_line_features_no_goal(self):
        """Test creating goal line features when no goal."""
        waypoint1 = Waypoint(name="TP1", lat=46.0, lon=8.0, alt_smoothed=1000)
        tp1 = Turnpoint(radius=400, waypoint=waypoint1, type=TurnpointType.TAKEOFF)

        task = Task(task_type=TaskType.CLASSIC, version=1, turnpoints=[tp1], goal=None)

        features = _create_goal_line_features(TaskDrawing.from_task(task))

        assert len(features) == 0

    def test_create_goal_line_features_insufficient_turnpoints(self):
        """Test creating goal line features with insufficient turnpoints."""
        waypoint1 = Waypoint(name="TP1", lat=46.0, lon=8.0, alt_smoothed=1000)
        tp1 = Turnpoint(radius=400, waypoint=waypoint1, type=TurnpointType.TAKEOFF)

        goal = Goal(type=GoalType.LINE)
        task = Task(
            task_type=TaskType.CLASSIC,
            version=1,
            turnpoints=[tp1],  # Only one turnpoint
            goal=goal,
        )

        features = _create_goal_line_features(TaskDrawing.from_task(task))

        assert len(features) == 0

    def test_create_goal_line_features_no_previous_turnpoint(self):
        """Test creating goal line features when no valid previous turnpoint."""
        # Create turnpoints with same coordinates
        waypoint1 = Waypoint(name="TP1", lat=47.0, lon=8.0, alt_smoothed=1000)
        waypoint2 = Waypoint(name="Goal", lat=47.0, lon=8.0, alt_smoothed=500)

        tp1 = Turnpoint(radius=400, waypoint=waypoint1, type=TurnpointType.TAKEOFF)
        tp2 = Turnpoint(radius=400, waypoint=waypoint2, type=TurnpointType.NONE)

        goal = Goal(type=GoalType.LINE)
        task = Task(
            task_type=TaskType.CLASSIC, version=1, turnpoints=[tp1, tp2], goal=goal
        )

        features = _create_goal_line_features(TaskDrawing.from_task(task))

        assert len(features) == 0  # No features when no valid previous TP
