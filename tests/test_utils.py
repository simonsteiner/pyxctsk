"""Tests for utility functions."""

from io import BytesIO
from unittest.mock import patch

import pytest
from pyxctsk import Task, TaskType, Turnpoint, TurnpointType, Waypoint
from pyxctsk.utils import generate_qr_code, task_to_kml

try:
    from PIL import Image
    from pyzbar import pyzbar

    QR_CODE_SUPPORT = True
except ImportError:
    Image = None  # type: ignore
    pyzbar = None  # type: ignore
    QR_CODE_SUPPORT = False


class TestGenerateQRCode:
    """Test QR code generation functionality."""

    @pytest.mark.skipif(
        not QR_CODE_SUPPORT, reason="QR code dependencies not available"
    )
    def test_generate_qr_code_basic(self):
        """Test basic QR code generation."""
        test_data = "Hello, World!"
        img = generate_qr_code(test_data)

        assert Image is not None  # Type guard
        assert isinstance(img, Image.Image)
        assert img.size == (1024, 1024)  # Default size

        # Verify the QR code can be read back
        img_buffer = BytesIO()
        img.save(img_buffer, format="PNG")
        img_buffer.seek(0)

        assert pyzbar is not None  # Type guard
        decoded_data = pyzbar.decode(Image.open(img_buffer))
        assert len(decoded_data) == 1
        assert decoded_data[0].data.decode("utf-8") == test_data

    @pytest.mark.skipif(
        not QR_CODE_SUPPORT, reason="QR code dependencies not available"
    )
    def test_generate_qr_code_custom_size(self):
        """Test QR code generation with custom size."""
        test_data = "Custom size test"
        custom_size = 512
        img = generate_qr_code(test_data, size=custom_size)

        assert Image is not None  # Type guard
        assert isinstance(img, Image.Image)
        assert img.size == (custom_size, custom_size)

    @pytest.mark.skipif(
        not QR_CODE_SUPPORT, reason="QR code dependencies not available"
    )
    @pytest.mark.parametrize("size", [256, 512, 1024, 2048])
    def test_generate_qr_code_various_sizes(self, size):
        """Test QR code generation with various sizes."""
        test_data = f"Size test {size}"
        img = generate_qr_code(test_data, size=size)

        assert Image is not None  # Type guard
        assert isinstance(img, Image.Image)
        assert img.size == (size, size)

    @pytest.mark.skipif(
        not QR_CODE_SUPPORT, reason="QR code dependencies not available"
    )
    def test_generate_qr_code_empty_string(self):
        """Test QR code generation with empty string."""
        img = generate_qr_code("")
        assert Image is not None  # Type guard
        assert isinstance(img, Image.Image)
        assert img.size == (1024, 1024)

    @pytest.mark.skipif(
        not QR_CODE_SUPPORT, reason="QR code dependencies not available"
    )
    def test_generate_qr_code_long_data(self):
        """Test QR code generation with long data."""
        test_data = "A" * 1000  # Long string
        img = generate_qr_code(test_data)

        assert Image is not None  # Type guard
        assert isinstance(img, Image.Image)
        assert img.size == (1024, 1024)

    @patch("pyxctsk.utils.QR_CODE_SUPPORT", False)
    def test_generate_qr_code_no_dependencies(self):
        """Test QR code generation raises ImportError when dependencies unavailable."""
        with pytest.raises(ImportError, match="QR code support requires"):
            generate_qr_code("test")


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

        # Verify KML structure
        assert kml_result.startswith('<?xml version="1.0" encoding="UTF-8"?>')
        assert '<kml xmlns="http://www.opengis.net/kml/2.2">' in kml_result
        assert "<Document>" in kml_result
        assert "<Folder>" in kml_result
        assert "<Placemark>" in kml_result
        assert "<LineString>" in kml_result
        assert "<coordinates>" in kml_result

        # Verify coordinate data
        assert "8.0,46.5,1000" in kml_result  # First turnpoint
        assert "8.1,46.6,1200" in kml_result  # Second turnpoint

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
        for i in range(5):
            expected_coord = f"{8.0 + i * 0.1},{46.0 + i * 0.1},{1000 + i * 100}"
            assert expected_coord in kml_result

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

        # Check that XML tags are properly closed
        assert kml_result.count("<kml") == kml_result.count("</kml>")
        assert kml_result.count("<Document>") == kml_result.count("</Document>")
        assert kml_result.count("<Folder>") == kml_result.count("</Folder>")
        assert kml_result.count("<Placemark>") == kml_result.count("</Placemark>")
        assert kml_result.count("<LineString>") == kml_result.count("</LineString>")
        assert kml_result.count("<coordinates>") == kml_result.count("</coordinates>")
