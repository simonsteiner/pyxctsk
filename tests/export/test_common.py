"""The value both writers render: `TaskDrawing`.

Covers what the drawing answers once — which turnpoints to draw, whether there
is a goal line, where the optimized route runs — and the property that made it
worth introducing: rendering one task in both formats optimizes the route once
and cannot produce two different pictures of the same task.
"""

from pyxctsk import Goal, GoalType, Task, TaskType, Turnpoint, TurnpointType, Waypoint
from pyxctsk.export import common
from pyxctsk.export.common import TaskDrawing
from pyxctsk.export.geojson import drawing_to_geojson, generate_task_geojson
from pyxctsk.export.kml import drawing_to_kml


def _task(goal_type: GoalType | None = None, prev_lat: float = 46.0) -> Task:
    """A three-turnpoint task, optionally with a goal of the given type."""
    return Task(
        task_type=TaskType.CLASSIC,
        version=1,
        turnpoints=[
            Turnpoint(
                radius=1000,
                waypoint=Waypoint(name="A", lat=45.5, lon=8.0, alt_smoothed=0),
                type=TurnpointType.TAKEOFF,
            ),
            Turnpoint(
                radius=1000,
                waypoint=Waypoint(name="B", lat=prev_lat, lon=8.0, alt_smoothed=0),
                type=TurnpointType.NONE,
            ),
            Turnpoint(
                radius=400,
                waypoint=Waypoint(name="Goal", lat=47.0, lon=8.0, alt_smoothed=0),
                type=TurnpointType.NONE,
            ),
        ],
        goal=None if goal_type is None else Goal(type=goal_type),
    )


class TestTaskDrawing:
    """What the drawing derives, and that it derives it once."""

    def test_cylinder_goal_draws_every_turnpoint(self):
        """With no goal line, every turnpoint is drawn and the goal is the last."""
        drawing = TaskDrawing.from_task(_task(GoalType.CYLINDER))

        assert drawing.goal_line is None
        assert len(drawing.turnpoints) == 3
        assert drawing.is_goal(drawing.turnpoints[-1])
        assert not drawing.is_goal(drawing.turnpoints[0])

    def test_goal_line_replaces_the_last_turnpoint(self):
        """A goal line is drawn instead of the goal cylinder, never as well as."""
        drawing = TaskDrawing.from_task(_task(GoalType.LINE))

        assert drawing.goal_line is not None
        assert len(drawing.turnpoints) == 2
        assert drawing.turnpoints == tuple(drawing.task.turnpoints[:-1])

    def test_the_render_list_and_the_goal_line_cannot_disagree(self):
        """Dropping the last turnpoint and having a line are one decision.

        A LINE goal needs some earlier turnpoint at different coordinates to
        give it an approach direction. With every earlier turnpoint sitting on
        the goal there is no line — and the goal turnpoint must stay drawn.
        (One coincident turnpoint is not enough: the search walks back past it.)
        """
        task = _task(GoalType.LINE)
        for turnpoint in task.turnpoints:
            turnpoint.waypoint.lat = 47.0
            turnpoint.waypoint.lon = 8.0

        drawing = TaskDrawing.from_task(task)

        assert drawing.goal_line is None
        assert len(drawing.turnpoints) == 3
        assert drawing.is_goal(drawing.turnpoints[-1])

    def test_one_coincident_turnpoint_still_yields_a_line(self):
        """The approach direction comes from the last turnpoint that differs."""
        drawing = TaskDrawing.from_task(_task(GoalType.LINE, prev_lat=47.0))

        assert drawing.goal_line is not None
        assert drawing.goal_line.approach_from == (45.5, 8.0)
        assert len(drawing.turnpoints) == 2

    def test_route_below_two_points_is_not_a_line(self):
        """One turnpoint is a point, not a line, so there is nothing to draw."""
        task = _task(GoalType.CYLINDER)
        task.turnpoints = task.turnpoints[:1]
        drawing = TaskDrawing.from_task(task)

        assert len(drawing.route.points) == 1
        assert drawing.route_coordinates() is None

    def test_route_coordinates_follow_the_route(self):
        """The drawn line is the optimized route, in order."""
        drawing = TaskDrawing.from_task(_task(GoalType.CYLINDER))

        assert drawing.route_coordinates() == list(drawing.route.points)
        assert len(drawing.route_coordinates()) == 3


class TestOneDrawingTwoFormats:
    """The reason the value exists: both writers render the same one."""

    def test_rendering_both_formats_optimizes_the_route_once(self, monkeypatch):
        """Two formats, one drawing, one optimizer run.

        Each writer used to derive its own route, so producing both formats for
        one task optimized it twice. Note the patch target: the name is looked
        up in ``export.common`` at call time, which is exactly what the four
        inert ``@patch`` decorators in test_geojson.py got wrong — they patched
        a name ``geojson.py`` had already bound into its own module.
        """
        calls = []
        real = common.calculate_iteratively_refined_route

        def counting(*args, **kwargs):
            calls.append(args)
            return real(*args, **kwargs)

        monkeypatch.setattr(common, "calculate_iteratively_refined_route", counting)

        drawing = TaskDrawing.from_task(_task(GoalType.LINE))
        kml = drawing_to_kml(drawing)
        geojson = drawing_to_geojson(drawing)

        assert len(calls) == 1, "the drawing is the shared route, not a per-format one"
        assert "Goal Line" in kml
        assert any(f["properties"]["type"] == "goal_line" for f in geojson["features"])

    def test_the_task_entry_point_agrees_with_the_drawing_one(self):
        """``generate_task_geojson(task)`` is ``drawing_to_geojson(from_task(task))``."""
        task = _task(GoalType.LINE)

        assert generate_task_geojson(task) == drawing_to_geojson(
            TaskDrawing.from_task(task)
        )

    def test_both_formats_draw_the_same_route(self):
        """The KML course line and the GeoJSON route come from one value."""
        drawing = TaskDrawing.from_task(_task(GoalType.CYLINDER))
        route = drawing.route_coordinates()
        assert route is not None

        geojson = drawing_to_geojson(drawing)
        (feature,) = [
            f
            for f in geojson["features"]
            if f["properties"]["type"] == "optimized_route"
        ]
        assert feature["geometry"]["coordinates"] == [[lon, lat] for lat, lon in route]

        kml = drawing_to_kml(drawing)
        for lat, lon in route:
            assert f"{lon},{lat}" in kml
