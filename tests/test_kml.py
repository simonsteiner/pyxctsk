"""
Unit tests for KML export functionality in pyxctsk.

This module verifies:
- Correct KML structure and XML validity for exported tasks
- Accurate coordinate and altitude representation for turnpoints
- Handling of edge cases (single turnpoint, negative/zero coordinates, etc.)
- Compatibility with various Task and Turnpoint configurations
"""

from pyxctsk import (
    Task,
    TaskType,
    Turnpoint,
    TurnpointType,
    Waypoint,
)
from pyxctsk.kml import task_to_kml


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
        # With unified altitude calculation: (1000 + 1200) // 2 = 1100
        assert "8.0,46.5,1100" in kml_result  # First turnpoint with unified altitude
        assert "8.1,46.6,1100" in kml_result  # Second turnpoint with unified altitude

        # Verify turnpoint names and descriptions
        assert "Start" in kml_result
        assert "TP1" in kml_result
        assert "Type: TurnpointType.TAKEOFF" in kml_result
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
        assert "9.0,47.0,800" in kml_result
        assert "XCTrack task course with 1 turnpoints" in kml_result
        assert "Single" in kml_result
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

        # Verify all coordinates are present
        # With unified altitude calculation: (1000 + 1100 + 1200 + 1300 + 1400) // 5 = 1200
        for i in range(5):
            expected_coord = (
                f"{8.0 + i * 0.1},{46.0 + i * 0.1},1200"  # Unified altitude
            )
            assert expected_coord in kml_result

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
        assert "0.0,0.0,0" in kml_result

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
