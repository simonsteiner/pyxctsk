"""Both writers agree: KML and GeoJSON render one drawing the same way.

The palette is shared and each writer renders it in its own format, so these
tests read the colours, names and descriptions back out of both outputs and
compare them: that is the only way the drift the KML writer used to introduce
could have been caught.
"""

import json
import re
from pathlib import Path

import pytest

from pyxctsk import Goal, GoalType, Task, TaskType, Turnpoint, TurnpointType, Waypoint
from pyxctsk.export import common
from pyxctsk.export.common import (
    CONTROL_ZONE_EDGE_COLOR,
    CONTROL_ZONE_FILL_COLOR,
    GOAL_LINE_COLOR,
    ROUTE_COLOR,
    TaskDrawing,
)
from pyxctsk.export.geojson import drawing_to_geojson
from pyxctsk.export.kml import FILL_ALPHA, ROUTE_ALPHA, drawing_to_kml
from tests.builders import three_turnpoint_task


def _placemark_style(kml: str, name: str) -> str:
    """The named placemark's style block, followed through its styleUrl.

    simplekml hoists styles into the document and references them by id, so
    reading a placemark's colour means resolving that reference rather than
    counting occurrences.

    Args:
        kml: The rendered document.
        name: The placemark's ``<name>``.

    Returns:
        The `<Style>` element the placemark points at.
    """
    placemark = re.search(
        rf"<Placemark[^>]*>\s*<name>{re.escape(name)}</name>.*?</Placemark>",
        kml,
        re.S,
    )
    assert placemark, f"no placemark named {name!r}"
    reference = re.search(r"<styleUrl>#(\d+)</styleUrl>", placemark.group(0))
    assert reference, f"placemark {name!r} has no styleUrl"
    style = re.search(rf'<Style id="{reference.group(1)}">.*?</Style>', kml, re.S)
    assert style, f"style #{reference.group(1)} is not in the document"
    return style.group(0)


def _placemark_color(kml: str, name: str, element: str = "LineStyle") -> str:
    """One colour out of the named placemark's style.

    Args:
        kml: The rendered document.
        name: The placemark's ``<name>``.
        element: The style element to read, ``LineStyle`` or ``PolyStyle``.

    Returns:
        That element's colour as KML's ``aabbggrr``.
    """
    style = _placemark_style(kml, name)
    color = re.search(
        rf"<{element}[^>]*>\s*<color>([0-9a-f]{{8}})</color>", style, re.S
    )
    assert color, f"{name!r} has no {element} colour:\n{style}"
    return color.group(1)


def _task_of_every_role() -> Task:
    """A task showing every palette entry once, goal last."""
    return Task(
        task_type=TaskType.CLASSIC,
        version=1,
        goal=Goal(type=GoalType.CYLINDER),
        turnpoints=[
            Turnpoint(
                radius=1000,
                waypoint=Waypoint(
                    name=f"TP{i}", lat=46.0 + i / 10, lon=8.0, alt_smoothed=0
                ),
                type=turnpoint_type,
            )
            for i, turnpoint_type in enumerate([*TurnpointType, TurnpointType.NONE])
        ],
    )


class TestBothWritersAgree:
    """KML and GeoJSON say the same thing about one drawing."""

    def test_both_writers_draw_the_turnpoints_in_the_palette_colours(self):
        """The regression: KML's colours are the shared ones, not a remapping."""
        drawing = TaskDrawing.from_task(_task_of_every_role())
        expected = [drawing.color_of(tp) for tp in drawing.turnpoints]

        geojson = drawing_to_geojson(drawing)
        from_geojson = [
            f["properties"]["color"]
            for f in geojson["features"]
            if f["properties"]["type"] == "cylinder"
        ]
        assert from_geojson == [color.hex for color in expected]

        kml = drawing_to_kml(drawing)
        from_kml = [
            _placemark_color(kml, tp.waypoint.name) for tp in drawing.turnpoints
        ]
        assert from_kml == [color.kml() for color in expected]

    def test_both_writers_name_the_same_turnpoint_the_same_way(self):
        """The label was assembled twice, so it could differ; now it is asked for.

        The ``TP{i+1}`` fallback for an unnamed turnpoint was written three
        times across the two writers.
        """
        drawing = TaskDrawing.from_task(_task_of_every_role())
        expected = [drawing.label_of(tp, i) for i, tp in enumerate(drawing.turnpoints)]

        geojson = drawing_to_geojson(drawing)
        from_geojson = [
            f["properties"]["name"]
            for f in geojson["features"]
            if f["properties"]["type"] == "cylinder"
        ]

        assert from_geojson == expected
        kml = drawing_to_kml(drawing)
        for label in expected:
            assert f"<name>{label}</name>" in kml

    def test_both_writers_describe_the_same_turnpoint_the_same_way(self):
        """KML wrote `Type: TurnpointType.TAKEOFF`; GeoJSON wrote no role at all."""
        drawing = TaskDrawing.from_task(_task_of_every_role())
        expected = [drawing.description_of(tp) for tp in drawing.turnpoints]

        geojson = drawing_to_geojson(drawing)
        from_geojson = [
            f["properties"]["description"]
            for f in geojson["features"]
            if f["properties"]["type"] == "cylinder"
        ]

        assert from_geojson == expected
        kml = drawing_to_kml(drawing)
        for description in expected:
            assert f"<description>{description}</description>" in kml

    def test_both_writers_name_the_route_the_same_way(self):
        """KML wrote "Course Line" where GeoJSON wrote "Optimized Route".

        The same line, two user-visible names, each pinned as expected by a
        test in its own file — so the suite enforced the divergence rather
        than catching it. The name is the drawing's answer now, and it is the
        glossary's term.
        """
        drawing = TaskDrawing.from_task(three_turnpoint_task(GoalType.CYLINDER))
        expected = drawing.route_label()

        geojson = drawing_to_geojson(drawing)
        (route,) = [
            f
            for f in geojson["features"]
            if f["properties"]["type"] == "optimized_route"
        ]

        assert route["properties"]["name"] == expected
        assert f"<name>{expected}</name>" in drawing_to_kml(drawing)

    def test_both_writers_name_and_describe_the_goal_line_the_same_way(self):
        """Two byte-identical f-strings, one per writer, with nothing pairing them."""
        drawing = TaskDrawing.from_task(three_turnpoint_task(GoalType.LINE))
        assert drawing.goal_line is not None

        geojson = drawing_to_geojson(drawing)
        (line,) = [
            f for f in geojson["features"] if f["properties"]["type"] == "goal_line"
        ]
        kml = drawing_to_kml(drawing)

        assert line["properties"]["name"] == drawing.goal_line_label()
        assert line["properties"]["description"] == drawing.goal_line_description()
        assert f"<name>{drawing.goal_line_label()}</name>" in kml
        assert f"<description>{drawing.goal_line_description()}</description>" in kml

    def test_both_writers_describe_the_control_zone_the_same_way(self):
        """And its radius is the goal line's, not `length / 2` in three modules."""
        drawing = TaskDrawing.from_task(three_turnpoint_task(GoalType.LINE))
        assert drawing.goal_line is not None

        geojson = drawing_to_geojson(drawing)
        (zone,) = [
            f
            for f in geojson["features"]
            if f["properties"]["type"] == "goal_control_zone"
        ]
        kml = drawing_to_kml(drawing)

        assert zone["properties"]["name"] == drawing.control_zone_label()
        assert zone["properties"]["description"] == drawing.control_zone_description()
        assert zone["properties"]["radius"] == drawing.goal_line.control_zone_radius
        assert f"<name>{drawing.control_zone_label()}</name>" in kml
        assert f"<description>{drawing.control_zone_description()}</description>" in kml

    def test_the_control_zone_radius_is_half_the_line(self):
        """S7F §6.2.3.1, owned by the goal line rather than by its captions."""
        drawing = TaskDrawing.from_task(three_turnpoint_task(GoalType.LINE))
        assert drawing.goal_line is not None

        assert drawing.goal_line.control_zone_radius == drawing.goal_line.length / 2

    def test_both_writers_read_one_route_in_one_axis_order(self):
        """One flipped by unpacking, the other by positional index."""
        drawing = TaskDrawing.from_task(three_turnpoint_task(GoalType.CYLINDER))
        lon_lat = drawing.route_coordinates_lon_lat()
        assert lon_lat is not None

        geojson = drawing_to_geojson(drawing)
        (route,) = [
            f
            for f in geojson["features"]
            if f["properties"]["type"] == "optimized_route"
        ]

        assert route["geometry"]["coordinates"] == [list(p) for p in lon_lat]
        assert [(lat, lon) for lon, lat in lon_lat] == drawing.route_coordinates()

    def test_no_writer_puts_a_python_repr_in_user_visible_text(self):
        """`Type: TurnpointType.TAKEOFF` and `Type: None` reached the map."""
        drawing = TaskDrawing.from_task(_task_of_every_role())

        kml = drawing_to_kml(drawing)
        geojson = json.dumps(drawing_to_geojson(drawing), default=str)

        for rendered in (kml, geojson):
            assert "TurnpointType." not in rendered
            assert "Type: None" not in rendered

    @pytest.mark.parametrize("role", [None, TurnpointType.NONE])
    def test_an_ordinary_turnpoint_is_described_without_a_role(self, role):
        """It has none, and printing `Type: None` said otherwise.

        Both spellings of "no role" describe the same — the asymmetry
        ``color_of`` normalizes away, applied here too.
        """
        drawing = TaskDrawing.from_task(_task_of_every_role())
        ordinary = Turnpoint(
            radius=1500,
            waypoint=Waypoint(name="X", lat=46.0, lon=8.0, alt_smoothed=0),
            type=role,
        )

        assert drawing.description_of(ordinary) == "Radius: 1500m"

    def test_both_writers_draw_the_route_in_one_colour(self):
        """KML's course line was ``#ff3641`` where GeoJSON's route was ``#ff4136``."""
        drawing = TaskDrawing.from_task(three_turnpoint_task(GoalType.CYLINDER))

        geojson = drawing_to_geojson(drawing)
        (route,) = [
            f
            for f in geojson["features"]
            if f["properties"]["type"] == "optimized_route"
        ]
        assert route["properties"]["color"] == ROUTE_COLOR.hex
        assert route["properties"]["arrow_color"] == ROUTE_COLOR.hex

        kml = drawing_to_kml(drawing)
        assert _placemark_color(kml, drawing.route_label()) == ROUTE_COLOR.kml(
            ROUTE_ALPHA
        )

    def test_both_writers_draw_the_goal_line_in_one_colour(self):
        """It was red in KML and green in GeoJSON — the same shape, two colours."""
        drawing = TaskDrawing.from_task(three_turnpoint_task(GoalType.LINE))
        assert drawing.goal_line is not None, "this task has a goal line to draw"

        geojson = drawing_to_geojson(drawing)
        (goal_line,) = [
            f for f in geojson["features"] if f["properties"]["type"] == "goal_line"
        ]
        assert goal_line["properties"]["stroke"] == GOAL_LINE_COLOR.hex

        kml = drawing_to_kml(drawing)
        assert _placemark_color(kml, "Goal Line") == GOAL_LINE_COLOR.kml()

    def test_both_writers_draw_the_control_zone_in_one_pair_of_colours(self):
        """Edge and fill differ from each other, but not between formats."""
        drawing = TaskDrawing.from_task(three_turnpoint_task(GoalType.LINE))

        geojson = drawing_to_geojson(drawing)
        (zone,) = [
            f
            for f in geojson["features"]
            if f["properties"]["type"] == "goal_control_zone"
        ]
        assert zone["properties"]["stroke"] == CONTROL_ZONE_EDGE_COLOR.hex
        assert zone["properties"]["fill"] == CONTROL_ZONE_FILL_COLOR.hex

        kml = drawing_to_kml(drawing)
        name = "Goal Control Zone"
        assert _placemark_color(kml, name) == CONTROL_ZONE_EDGE_COLOR.kml(), (
            "the zone's edge"
        )
        assert _placemark_color(kml, name, "PolyStyle") == CONTROL_ZONE_FILL_COLOR.kml(
            FILL_ALPHA
        ), "the zone's fill"

    def test_neither_writer_declares_a_colour_of_its_own(self):
        """The structural half: a colour literal in a writer is the drift itself.

        Every defect this class covers was a colour spelled out in a writer —
        a `simplekml.Color` constant, a `#rrggbb` string, or an `aabbggrr` one
        typed by hand. The palette is the only place those may appear, so a new
        one appearing in a writer fails here rather than in a map three months
        from now.

        The `aabbggrr` rule is by shape, so any quoted 8-hex-digit literal in a
        writer trips it, colour or not. That is deliberate: nothing else in these
        two modules has wanted one, and the failure is a prompt to move a colour
        into the palette or to narrow this check on purpose — the same kind of
        review gate as `EXPECTED_DEFERRED_IMPORTS` in test_layering.py.
        """
        moved_to = "move it into common.py's palette, or narrow this check"
        package = Path(common.__file__).parent
        for writer in ("kml.py", "geojson.py"):
            source = (package / writer).read_text()
            assert not re.search(r"#[0-9a-fA-F]{6}\b", source), (
                f"{writer} spells out a #rrggbb colour: {moved_to}"
            )
            assert "simplekml.Color" not in source, (
                f"{writer} uses a simplekml.Color constant: {moved_to}"
            )
            assert not re.search(r"""["'][0-9a-fA-F]{8}["']""", source), (
                f"{writer} has a quoted 8-hex-digit literal, which is how a KML "
                f"colour gets hand-written: {moved_to}"
            )
