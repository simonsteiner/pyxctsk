"""What both writers share: the `TaskDrawing` value.

Covers what the drawing answers once — which turnpoints to draw, whether there
is a goal line, where the optimized route runs — and the property that made it
worth introducing: rendering one task in both formats optimizes the route once
and cannot produce two different pictures of the same task.

The palette is in `test_common_palette.py` and the check that both writers
render it alike is in `test_writers_agree.py`.
"""

import pytest

from pyxctsk import EarthModel, GoalType, UnmeasurableRouteError
from pyxctsk.distance import GoalLine, GoalLineOrientation
from pyxctsk.distance.earth import geodesic_distance
from pyxctsk.export import common
from pyxctsk.export.common import TaskDrawing
from pyxctsk.export.geojson import drawing_to_geojson, generate_task_geojson
from pyxctsk.export.kml import drawing_to_kml
from tests.builders import three_turnpoint_task


class TestTaskDrawing:
    """What the drawing derives, and that it derives it once."""

    def test_cylinder_goal_draws_every_turnpoint(self):
        """With no goal line, every turnpoint is drawn and the goal is the last."""
        drawing = TaskDrawing.from_task(three_turnpoint_task(GoalType.CYLINDER))

        assert drawing.goal_line is None
        assert len(drawing.turnpoints) == 3
        assert drawing.is_goal(drawing.turnpoints[-1])
        assert not drawing.is_goal(drawing.turnpoints[0])

    def test_the_task_is_the_measured_ones(self):
        """One task per drawing: the one its route was measured for."""
        drawing = TaskDrawing.from_task(three_turnpoint_task(GoalType.CYLINDER))

        assert drawing.task is drawing.measured.task
        assert "task" not in TaskDrawing.__dataclass_fields__

    def test_goal_line_replaces_the_last_turnpoint(self):
        """A goal line is drawn instead of the goal cylinder, never as well as."""
        drawing = TaskDrawing.from_task(three_turnpoint_task(GoalType.LINE))

        assert drawing.goal_line is not None
        assert len(drawing.turnpoints) == 2
        assert drawing.turnpoints == tuple(drawing.task.turnpoints[:-1])

    def test_the_render_list_and_the_goal_line_cannot_disagree(self):
        """Dropping the last turnpoint and having a line are one decision.

        A LINE goal needs an approach direction. With every point of the
        optimized route sitting on the goal there is none, so there is no line
        — and the goal turnpoint must stay drawn.
        """
        task = three_turnpoint_task(GoalType.LINE)
        for turnpoint in task.turnpoints:
            turnpoint.waypoint.lat = 47.0
            turnpoint.waypoint.lon = 8.0
            # Zero radius: with a cylinder the route would still reach a
            # boundary point away from the goal, which *is* a direction.
            turnpoint.radius = 0

        drawing = TaskDrawing.from_task(task)

        assert drawing.goal_line is None
        assert len(drawing.turnpoints) == 3
        assert drawing.is_goal(drawing.turnpoints[-1])

    def test_coincident_centres_still_yield_a_line(self):
        """Concentric cylinders have an approach direction even so.

        Under S7F 2025+ the line is oriented against the optimized route
        point, and the route touches the previous cylinder's *boundary*. The
        pilot really does arrive from there, so there is a direction to face —
        where the 2024 rule, comparing centres, saw none.
        """
        drawing = TaskDrawing.from_task(
            three_turnpoint_task(GoalType.LINE, middle_lat=47.0)
        )

        assert drawing.goal_line is not None
        assert drawing.goal_line.approach_from != (47.0, 8.0)
        assert len(drawing.turnpoints) == 2

    def test_the_line_faces_the_route_not_the_turnpoint_centre(self):
        """S7F 2025+ §6.2.3.1, and the 2024 rule is still reachable."""
        task = three_turnpoint_task(GoalType.LINE, middle_lat=47.0)
        drawing = TaskDrawing.from_task(task)

        assert drawing.goal_line is not None
        assert drawing.goal_line.approach_from == drawing.route.points[-2]

        legacy = GoalLine.from_task(task, GoalLineOrientation.TURNPOINT_CENTERS)
        assert legacy is not None
        assert legacy.approach_from == (45.5, 8.0)

    def test_route_below_two_points_is_not_a_line(self):
        """One turnpoint is a point, not a line, so there is nothing to draw."""
        task = three_turnpoint_task(GoalType.CYLINDER)
        task.turnpoints = task.turnpoints[:1]
        drawing = TaskDrawing.from_task(task)

        assert len(drawing.route.points) == 1
        assert drawing.route_coordinates() is None

    def test_route_coordinates_follow_the_route(self):
        """The drawn line is the optimized route, in order."""
        drawing = TaskDrawing.from_task(three_turnpoint_task(GoalType.CYLINDER))

        assert drawing.route_coordinates() == list(drawing.route.points)
        coordinates = drawing.route_coordinates()
        assert coordinates is not None
        assert len(coordinates) == 3


class TestTheCylinderOutline:
    """Drawn on the task's earth, at exactly the radius the route touches.

    It was a planar polygon from a fixed 111 320 m per degree, 129 m out at a
    50 km radius, so the KML route visibly missed the cylinder it touched.
    """

    @pytest.mark.parametrize("model", [None, EarthModel.FAI_SPHERE])
    @pytest.mark.parametrize("radius", [400, 5_000, 50_000])
    def test_every_point_is_on_the_boundary(self, model, radius):
        """On the earth the task declares, not a flat one."""
        task = three_turnpoint_task()
        task.earth_model = model
        task.turnpoints[1].radius = radius
        drawing = TaskDrawing.from_task(task)
        centre = (46.0, 8.0)

        ring = drawing.outline_of(task.turnpoints[1])

        assert ring[0] == ring[-1]
        for lon, lat in ring:
            assert geodesic_distance(centre, (lat, lon), model) == pytest.approx(
                radius, abs=1e-6
            )

    @pytest.mark.parametrize("model", [None, EarthModel.FAI_SPHERE])
    def test_a_cylinder_past_the_far_side_has_no_outline(self, model):
        """A takeoff the route never touches still has an outline to draw.

        Its radius cannot change the distance (ADR 0002), so nothing refuses it
        before the drawing — where 10^300 m used to come out as a KML ring of
        points thousands of kilometres from the centre. GeoJSON draws no ring:
        it carries the centre and the radius the task declares, which are true.
        """
        task = three_turnpoint_task()
        task.earth_model = model
        task.turnpoints[0].radius = 10**300
        drawing = TaskDrawing.from_task(task)

        with pytest.raises(UnmeasurableRouteError, match="far side of the earth"):
            drawing.outline_of(task.turnpoints[0])
        with pytest.raises(UnmeasurableRouteError, match="far side of the earth"):
            drawing_to_kml(drawing)
        takeoff = drawing_to_geojson(drawing)["features"][0]
        assert takeoff["properties"]["radius"] == 10**300

    @pytest.mark.parametrize("model", [None, EarthModel.FAI_SPHERE])
    def test_a_line_goal_past_the_far_side_is_drawn_in_neither_format(self, model):
        """Both formats draw a LINE goal's ends and control zone, so both refuse.

        The distance still stands — a LINE goal is a point to the optimizer —
        but GeoJSON, unlike for a cylinder, carries the line's geometry, and
        10^300 m of it used to come out as two ends nowhere near the goal.
        """
        task = three_turnpoint_task(GoalType.LINE)
        task.earth_model = model
        task.turnpoints[-1].radius = 10**300
        drawing = TaskDrawing.from_task(task)

        with pytest.raises(UnmeasurableRouteError, match="far side of the earth"):
            drawing_to_geojson(drawing)
        with pytest.raises(UnmeasurableRouteError, match="far side of the earth"):
            drawing_to_kml(drawing)

    def test_the_kml_polygon_is_the_outline(self):
        """The writer renders the drawing's answer rather than its own."""
        drawing = TaskDrawing.from_task(three_turnpoint_task(GoalType.CYLINDER))
        kml = drawing_to_kml(drawing)
        lon, lat = drawing.outline_of(drawing.turnpoints[1])[5]

        assert f"{lon},{lat}," in kml


class TestOneDrawingTwoFormats:
    """The reason the value exists: both writers render the same one."""

    def test_rendering_both_formats_optimizes_the_route_once(self, monkeypatch):
        """Two formats, one drawing, one measured task.

        Each writer used to derive its own route, so producing both formats for
        one task optimized it twice. Counting optimizer calls is no longer the
        way to say so: the drawing holds a ``MeasuredTask``, so the claim is
        that both renderings read that one value — an assertion about identity,
        which a call count could only approximate.
        """
        calls = []
        real = common.MeasuredTask.from_task

        def counting(task, *args, **kwargs):
            calls.append(task)
            return real(task, *args, **kwargs)

        monkeypatch.setattr(common.MeasuredTask, "from_task", counting)

        drawing = TaskDrawing.from_task(three_turnpoint_task(GoalType.LINE))
        kml = drawing_to_kml(drawing)
        geojson = drawing_to_geojson(drawing)

        assert len(calls) == 1, (
            "the drawing is the shared measurement, not a per-format one"
        )
        assert "Goal Line" in kml
        assert any(f["properties"]["type"] == "goal_line" for f in geojson["features"])

    def test_the_drawings_route_is_its_measured_tasks_route(self):
        """``drawing.route`` reads through to the measured task, not a copy."""
        drawing = TaskDrawing.from_task(three_turnpoint_task(GoalType.LINE))

        assert drawing.route is drawing.measured.route
        assert drawing.measured.task is drawing.task

    def test_the_task_entry_point_agrees_with_the_drawing_one(self):
        """``generate_task_geojson(task)`` is ``drawing_to_geojson(from_task(task))``."""
        task = three_turnpoint_task(GoalType.LINE)

        assert generate_task_geojson(task) == drawing_to_geojson(
            TaskDrawing.from_task(task)
        )

    def test_both_formats_draw_the_same_route(self):
        """The KML course line and the GeoJSON route come from one value."""
        drawing = TaskDrawing.from_task(three_turnpoint_task(GoalType.CYLINDER))
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
