"""Tests for the GeoJSON goal-line features.

Covers `_create_goal_line_features` and the LINE goal that cannot produce a
line, which still has to be drawn.
"""

from pyxctsk import Goal, GoalType, Task, TaskType, Turnpoint, TurnpointType, Waypoint
from pyxctsk.export.common import TaskDrawing
from pyxctsk.export.geojson import _create_goal_line_features, generate_task_geojson


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
