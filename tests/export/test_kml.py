"""Unit tests for KML export functionality in pyxctsk.

This module verifies:
- Correct KML structure and XML validity for exported tasks
- Accurate coordinate and altitude representation for turnpoints
- Handling of edge cases (single turnpoint, negative/zero coordinates, etc.)
- Compatibility with various Task and Turnpoint configurations
"""

import re

from pyxctsk import (
    Goal,
    GoalType,
    Task,
    TaskType,
    Turnpoint,
    TurnpointType,
    Waypoint,
)
from pyxctsk.export.kml import task_to_kml


class TestTaskToKML:
    """Test KML conversion functionality."""

    def test_task_to_kml_basic(self):
        """Test basic KML conversion."""
        task = Task(
            task_type=TaskType.CLASSIC,
            version=1,
            turnpoints=[
                Turnpoint(
                    radius=1000,
                    waypoint=Waypoint(
                        name="Start", lat=46.5, lon=8.0, alt_smoothed=1000
                    ),
                    type=TurnpointType.TAKEOFF,
                ),
                Turnpoint(
                    radius=400,
                    waypoint=Waypoint(name="TP1", lat=46.6, lon=8.1, alt_smoothed=1200),
                    type=TurnpointType.NONE,  # Using valid enum value
                ),
            ],
        )

        kml_result = task_to_kml(task)

        # Verify KML structure - updated for simplekml output
        assert kml_result.startswith('<?xml version="1.0" encoding="UTF-8"?>')
        assert '<kml xmlns="http://www.opengis.net/kml/2.2"' in kml_result
        assert "<Document" in kml_result  # simplekml adds id attributes
        assert (
            "<Placemark" in kml_result
        )  # Multiple placemarks for turnpoints and course line
        assert "<Polygon" in kml_result  # Turnpoints are polygons (circles)
        assert "<LineString" in kml_result  # Course line
        assert "<coordinates>" in kml_result
        assert "extrude>1</extrude>" in kml_result
        assert "altitudeMode>relativeToGround</altitudeMode>" in kml_result

        # Verify coordinate data (coordinates appear in both polygon circles and course line)
        # KML output uses 0.0 for altitude in coordinates, allow for float formatting
        assert (
            "8.0" in kml_result and "46.5" in kml_result and ",0.0" in kml_result
        )  # First turnpoint
        assert (
            "8.1" in kml_result and "46.6" in kml_result and ",0.0" in kml_result
        )  # Second turnpoint

        # Verify turnpoint names and descriptions
        assert "Start" in kml_result
        assert "TP1" in kml_result
        assert "Type: TAKEOFF" in kml_result
        # Not the enum's repr: this string is user-visible map text.
        assert "TurnpointType." not in kml_result
        assert "Radius: 1000m" in kml_result
        assert "Radius: 400m" in kml_result

        # Verify course line
        assert "Course Line" in kml_result
        assert "XCTrack task course with 2 turnpoints" in kml_result

    def test_task_to_kml_single_turnpoint(self):
        """Test KML conversion with single turnpoint."""
        task = Task(
            task_type=TaskType.CLASSIC,
            version=1,
            turnpoints=[
                Turnpoint(
                    radius=1000,
                    waypoint=Waypoint(
                        name="Single", lat=47.0, lon=9.0, alt_smoothed=800
                    ),
                    type=TurnpointType.TAKEOFF,
                )
            ],
        )

        kml_result = task_to_kml(task)
        # One turnpoint is not a course: no LineString at all. This used to emit
        # a one-coordinate <LineString>, which is degenerate geometry.
        assert "<LineString" not in kml_result
        assert "XCTrack task course" not in kml_result
        # The turnpoint itself is still drawn, cylinder and centre point.
        assert "9.0,47.0,5000" in kml_result
        assert "Single" in kml_result
        assert "Single Center" in kml_result
        assert "Radius: 1000m" in kml_result

    def test_task_to_kml_multiple_turnpoints(self):
        """Test KML conversion with multiple turnpoints."""
        turnpoints = []
        for i in range(5):
            turnpoints.append(
                Turnpoint(
                    radius=400,
                    waypoint=Waypoint(
                        name=f"TP{i}",
                        lat=46.0 + i * 0.1,
                        lon=8.0 + i * 0.1,
                        alt_smoothed=1000 + i * 100,
                    ),
                    type=TurnpointType.NONE,  # Using valid enum value
                )
            )

        task = Task(
            task_type=TaskType.CLASSIC,
            version=1,
            turnpoints=turnpoints,
        )

        kml_result = task_to_kml(task)

        # Verify all coordinates are present (allow for float formatting)
        for i in range(5):
            lon = 8.0 + i * 0.1
            lat = 46.0 + i * 0.1
            # Check that both lon and lat (rounded to 1 decimal) and ',0.0' appear in the KML
            assert f"{lon:.1f}" in kml_result
            assert f"{lat:.1f}" in kml_result
            assert ",0.0" in kml_result

        # Verify course line description
        assert "XCTrack task course with 5 turnpoints" in kml_result

    def test_task_to_kml_negative_coordinates(self):
        """Test KML conversion with negative coordinates."""
        task = Task(
            task_type=TaskType.CLASSIC,
            version=1,
            turnpoints=[
                Turnpoint(
                    radius=1000,
                    waypoint=Waypoint(
                        name="Negative", lat=-45.5, lon=-120.0, alt_smoothed=500
                    ),
                    type=TurnpointType.TAKEOFF,
                )
            ],
        )

        kml_result = task_to_kml(task)
        assert "-120.0,-45.5,500" in kml_result

    def test_task_to_kml_zero_altitude(self):
        """Test KML conversion with zero altitude."""
        task = Task(
            task_type=TaskType.CLASSIC,
            version=1,
            turnpoints=[
                Turnpoint(
                    radius=1000,
                    waypoint=Waypoint(
                        name="Sea Level", lat=0.0, lon=0.0, alt_smoothed=0
                    ),
                    type=TurnpointType.TAKEOFF,
                )
            ],
        )

        kml_result = task_to_kml(task)
        # The centre point sits at the task altitude; nothing is emitted at
        # 0°N 0°E by accident, which an empty course line used to do.
        assert "0.0,0.0,5000" in kml_result
        assert "<LineString" not in kml_result

    def test_task_to_kml_xml_structure(self):
        """Test that generated KML has proper XML structure."""
        task = Task(
            task_type=TaskType.CLASSIC,
            version=1,
            turnpoints=[
                Turnpoint(
                    radius=1000,
                    waypoint=Waypoint(
                        name="Test", lat=46.5, lon=8.0, alt_smoothed=1000
                    ),
                    type=TurnpointType.TAKEOFF,
                )
            ],
        )

        kml_result = task_to_kml(task)

        # Check that XML tags are properly closed - updated for simplekml structure
        assert kml_result.count("<kml") == kml_result.count("</kml>")
        assert kml_result.count("<Document") == kml_result.count("</Document>")
        assert kml_result.count("<Placemark") == kml_result.count("</Placemark>")
        assert kml_result.count("<Polygon") == kml_result.count("</Polygon>")
        assert kml_result.count("<LineString") == kml_result.count("</LineString>")
        assert kml_result.count("<coordinates>") == kml_result.count("</coordinates>")

        # Check for proper structure elements
        assert "<Style" in kml_result  # simplekml generates styles
        assert "<outerBoundaryIs>" in kml_result  # polygon boundary
        assert "<LinearRing" in kml_result  # polygon ring


class TestDegenerateAndStyledOutput:
    """Two defects Copilot found on PR #13, pinned so they stay fixed."""

    @staticmethod
    def _task(count: int) -> Task:
        """A task with ``count`` turnpoints along a meridian."""
        return Task(
            task_type=TaskType.CLASSIC,
            version=1,
            turnpoints=[
                Turnpoint(
                    radius=1000,
                    waypoint=Waypoint(
                        name=f"TP{i}", lat=46.0 + i, lon=8.0, alt_smoothed=0
                    ),
                    type=TurnpointType.NONE,
                )
                for i in range(count)
            ],
            goal=Goal(type=GoalType.CYLINDER) if count else None,
        )

    def test_no_line_string_below_two_points(self):
        """A LineString needs two points; an empty task must not invent one.

        simplekml writes an empty coordinate list as a single ``0.0,0.0,0.0``,
        so the empty task used to emit a course line at 0°N 0°E.
        """
        for count in (0, 1):
            kml_result = task_to_kml(self._task(count))
            assert "<LineString" not in kml_result, f"{count} turnpoints"
            assert "0.0, 0.0, 0.0" not in kml_result, f"{count} turnpoints"

    def test_two_points_do_get_a_course_line(self):
        """The line is omitted only when there is nothing to draw."""
        kml_result = task_to_kml(self._task(2))

        assert "<LineString" in kml_result
        assert "XCTrack task course with 2 turnpoints" in kml_result

    def test_icon_style_colour_is_a_colour(self):
        """``iconstyle.color`` held a whole nested <Style>, which is invalid KML."""
        kml_result = task_to_kml(self._task(3))

        icons = re.findall(r"<IconStyle[^>]*>(.*?)</IconStyle>", kml_result, re.S)
        assert icons, "expected an IconStyle per centre point"
        for icon in icons:
            assert "<Style" not in icon, "a Style nested inside IconStyle"
            (colour,) = re.findall(r"<color>([^<]*)</color>", icon)
            assert re.fullmatch(r"[0-9a-f]{8}", colour), colour

    def test_centre_point_matches_its_cylinder(self):
        """The centre point takes the colour of the cylinder it sits in."""
        kml_result = task_to_kml(self._task(3))

        # The goal's cylinder is red, so its centre point must be red too.
        assert kml_result.count("ff0000ff") >= 2
