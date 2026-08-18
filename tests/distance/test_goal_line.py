"""Tests for goal line functionality.

Unit tests for goal line generation and calculation logic in pyxctsk.

This module covers:
- Goal line endpoint calculations based on approach direction
- Semicircle arc generation for goal control zones
- Whether a task has a goal line at all, which is what decides whether the
  last turnpoint is drawn as a cylinder or replaced by the line
- Helper functions for finding previous turnpoints with valid coordinates
"""

import pytest

from pyxctsk import (
    EarthModel,
    Goal,
    GoalType,
    Task,
    TaskType,
    Turnpoint,
    TurnpointType,
    Waypoint,
)
from pyxctsk.distance import geodesic_distance
from pyxctsk.distance.goal_line import (
    GoalLine,
    _endpoints_from_coords,
    _generate_semicircle_arc,
    _last_distinct_point,
    goal_line_length_from_turnpoints,
)


def _line_goal_task(prev_radius: int = 400, goal_radius: int = 400) -> Task:
    """Build a two-turnpoint LINE-goal task for goal-line tests."""
    tp1 = Turnpoint(
        radius=prev_radius,
        waypoint=Waypoint(name="TP1", lat=46.0, lon=8.0, alt_smoothed=1000),
        type=TurnpointType.TAKEOFF,
    )
    tp2 = Turnpoint(
        radius=goal_radius,
        waypoint=Waypoint(name="Goal", lat=47.0, lon=8.0, alt_smoothed=500),
        type=TurnpointType.NONE,
    )
    goal = Goal(type=GoalType.LINE)
    return Task(task_type=TaskType.CLASSIC, version=1, turnpoints=[tp1, tp2], goal=goal)


class TestGoalLineLengthFromTurnpoints:
    """Test the single-source goal-line length rule."""

    def test_length_is_twice_last_radius(self):
        """Goal-line length is twice the final turnpoint radius."""
        task = _line_goal_task(goal_radius=250)
        assert goal_line_length_from_turnpoints(task.turnpoints) == 500.0

    def test_empty_turnpoints_returns_none(self):
        """No turnpoints yields no goal-line length."""
        assert goal_line_length_from_turnpoints([]) is None


class TestGoalLineClass:
    """Test the GoalLine deep module in isolation."""

    def test_from_task_builds_line_goal(self):
        """A line goal builds a GoalLine with the expected geometry."""
        gl = GoalLine.from_task(_line_goal_task(goal_radius=300))
        assert gl is not None
        # The goal-line length is twice the last turnpoint's radius.
        assert gl.length == 600.0
        assert gl.center == (47.0, 8.0)
        assert gl.approach_from == (46.0, 8.0)

    def test_from_task_returns_none_for_cylinder(self):
        """A cylinder goal produces no GoalLine."""
        task = _line_goal_task()
        task.goal.type = GoalType.CYLINDER
        assert GoalLine.from_task(task) is None

    def test_endpoints_are_perpendicular_to_due_north_approach(self):
        """Endpoints lie perpendicular to a due-north approach, centred on goal."""
        # Approaching from due south, the line runs east-west and is centred
        # on the goal, so the forward azimuth is ~0/360.
        gl = GoalLine.from_task(_line_goal_task())
        (lon1, lat1), (lon2, lat2), forward_azimuth = gl.endpoints()
        assert abs(forward_azimuth) < 1.0 or abs(forward_azimuth - 360) < 1.0
        # Endpoints straddle the goal longitude symmetrically.
        assert abs((lon1 + lon2) / 2 - 8.0) < 1e-6

    def test_control_zone_is_a_closed_polygon(self):
        """The control zone is a closed ring of more than three points."""
        gl = GoalLine.from_task(_line_goal_task())
        zone = gl.control_zone()
        assert zone[0] == zone[-1]  # closed ring
        assert len(zone) > 3


class TestLastDistinctPoint:
    """The walk-backwards rule both orientations share."""

    def test_returns_the_last_point_that_differs(self):
        """The nearest preceding point with its own position wins."""
        goal = (47.0, 8.0)
        points = [(46.0, 8.0), (46.5, 8.1)]

        assert _last_distinct_point(points, goal) == (46.5, 8.1)

    def test_skips_points_coincident_with_the_goal(self):
        """A candidate on the goal gives no approach direction, so keep walking."""
        goal = (47.0, 8.0)
        points = [(46.0, 8.0), (47.0, 8.0)]

        assert _last_distinct_point(points, goal) == (46.0, 8.0)

    def test_all_coincident_yields_none(self):
        """With nothing to approach from there is no line to draw."""
        assert _last_distinct_point([(47.0, 8.0)], (47.0, 8.0)) is None

    def test_empty_yields_none(self):
        """No candidates, no approach."""
        assert _last_distinct_point([], (47.0, 8.0)) is None

    def test_a_difference_under_tolerance_is_no_difference(self):
        """Coordinates within COORD_TOLERANCE are the same place.

        The optimized-route candidates come back through a projection round
        trip, so they are never bit-exact even when they are the same point.
        """
        assert _last_distinct_point([(47.0 + 1e-10, 8.0)], (47.0, 8.0)) is None


class TestEndpointsFromCoords:
    """The endpoint math, on raw coordinates.

    These used to build Mock turnpoints to reach it through a back-compat
    adapter (`calculate_goal_line_endpoints`); the core takes coordinates.
    """

    def test_approach_from_the_south_runs_the_line_east_west(self):
        """Approaching due north, the forward azimuth is 0 and the line is E-W."""
        (lon1, lat1), (lon2, lat2), forward_azimuth = _endpoints_from_coords(
            47.0, 8.0, 46.0, 8.0, 400.0
        )

        assert abs(forward_azimuth) < 1.0 or abs(forward_azimuth - 360) < 1.0
        # The endpoints straddle the goal in longitude, at the goal's latitude.
        assert lon1 > 8.0 > lon2
        assert abs(lat1 - 47.0) < 1e-4 and abs(lat2 - 47.0) < 1e-4

    def test_approach_from_the_west_runs_the_line_north_south(self):
        """Approaching due east, the forward azimuth is 90."""
        _, _, forward_azimuth = _endpoints_from_coords(47.0, 8.0, 47.0, 7.0, 400.0)

        assert abs(forward_azimuth - 90) < 1.0

    def test_zero_length_puts_both_endpoints_on_the_goal(self):
        """A zero-length line degenerates to the goal center."""
        (lon1, lat1), (lon2, lat2), _ = _endpoints_from_coords(
            47.0, 8.0, 46.0, 8.0, 0.0
        )

        assert abs(lon1 - 8.0) < 1e-10
        assert abs(lat1 - 47.0) < 1e-10
        assert abs(lon2 - 8.0) < 1e-10
        assert abs(lat2 - 47.0) < 1e-10


class TestGenerateSemicircleArc:
    """Test the semicircle arc generator."""

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
        from pyxctsk.distance.goal_line import GOAL_LINE_NUM_POINTS

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


class TestGoalLinePresence:
    """Whether a task has a goal line — the one question, asked once.

    ``GoalLine.from_task`` used to be shadowed by ``should_skip_last_turnpoint``,
    which answered the same question with one clause fewer. The renderers asked
    both, so the two could disagree; the last case below is where they did.
    """

    def test_line_goal_has_a_goal_line(self):
        """A LINE goal with a distinct previous turnpoint has a goal line."""
        assert GoalLine.from_task(_line_goal_task()) is not None

    def test_cylinder_goal_has_none(self):
        """A CYLINDER goal has no goal line."""
        task = _line_goal_task()
        task.goal = Goal(type=GoalType.CYLINDER)
        assert GoalLine.from_task(task) is None

    def test_no_goal_has_none(self):
        """A task with no goal has no goal line."""
        waypoint1 = Waypoint(name="TP1", lat=46.0, lon=8.0, alt_smoothed=1000)
        tp1 = Turnpoint(radius=400, waypoint=waypoint1, type=TurnpointType.TAKEOFF)
        task = Task(task_type=TaskType.CLASSIC, version=1, turnpoints=[tp1], goal=None)
        assert GoalLine.from_task(task) is None

    def test_single_turnpoint_has_none(self):
        """One turnpoint cannot define an approach direction."""
        waypoint1 = Waypoint(name="TP1", lat=46.0, lon=8.0, alt_smoothed=1000)
        tp1 = Turnpoint(radius=400, waypoint=waypoint1, type=TurnpointType.TAKEOFF)
        task = Task(
            task_type=TaskType.CLASSIC,
            version=1,
            turnpoints=[tp1],
            goal=Goal(type=GoalType.LINE),
        )
        assert GoalLine.from_task(task) is None

    def test_coincident_previous_turnpoint_has_none(self):
        """A previous turnpoint at the goal's own coordinates gives no line.

        This is the case the two predicates disagreed on: there is no approach
        azimuth to be perpendicular to, so no line can be drawn — and the goal
        turnpoint must therefore stay in the rendered output. See
        ``tests/export/test_geojson.py`` for the writer-side regression.
        """
        task = _line_goal_task()
        task.turnpoints[0].waypoint.lat = task.turnpoints[-1].waypoint.lat
        task.turnpoints[0].waypoint.lon = task.turnpoints[-1].waypoint.lon
        assert GoalLine.from_task(task) is None


class TestGoalLineEarthModel:
    """The goal line is measured on the task's declared earth model (ADR 0003).

    It used to be measured on a hardcoded WGS84 ellipsoid, so a task declaring
    the FAI sphere had its route and distances on the sphere while the goal line
    and its control zone sat on the ellipsoid — two earth models in one
    exported document.
    """

    @staticmethod
    def _task(earth_model) -> Task:
        """A LINE-goal task with a 40 km goal line on the given earth model."""
        task = _line_goal_task(goal_radius=20_000)
        task.earth_model = earth_model
        return task

    def test_from_task_carries_the_model(self):
        """The model travels with the goal line, not with the caller."""
        assert GoalLine.from_task(self._task(EarthModel.FAI_SPHERE)).earth_model == (
            EarthModel.FAI_SPHERE
        )
        assert GoalLine.from_task(self._task(None)).earth_model is None

    def test_endpoints_are_half_the_length_from_the_center_on_that_model(self):
        """Each endpoint sits length / 2 from the goal, measured on the model.

        This is what a hardcoded ellipsoid broke: half of 40 km along the
        ellipsoid is not half of 40 km along the FAI sphere.
        """
        for earth_model in (None, EarthModel.FAI_SPHERE):
            goal_line = GoalLine.from_task(self._task(earth_model))
            (lon1, lat1), (lon2, lat2), _ = goal_line.endpoints()
            for lon, lat in ((lon1, lat1), (lon2, lat2)):
                measured = geodesic_distance(goal_line.center, (lat, lon), earth_model)
                assert measured == pytest.approx(goal_line.length / 2, abs=0.01), (
                    f"{earth_model}: endpoint is not half the line from the goal"
                )

    def test_the_two_models_disagree_enough_to_matter(self):
        """The models place the endpoints tens of metres apart on a long line."""
        wgs84 = GoalLine.from_task(self._task(None)).endpoints()[0]
        sphere = GoalLine.from_task(self._task(EarthModel.FAI_SPHERE)).endpoints()[0]

        apart = geodesic_distance((wgs84[1], wgs84[0]), (sphere[1], sphere[0]))
        assert apart > 10.0, "otherwise this test could not detect the wrong model"
