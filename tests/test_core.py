"""
Comprehensive core functionality tests for pyxctsk.

This test suite covers:
- TimeOfDay: validation, serialization, and error handling
- Waypoint: dict conversion and parsing
- Task: JSON serialization/deserialization, minimal and complex cases
- Task parsing: from files, strings, and error conditions
- QRCodeTask: conversion, string roundtrip, and integration

"""

import pytest
from pyxctsk import (
    SSS,
    Direction,
    EarthModel,
    EmptyInputError,
    Goal,
    GoalType,
    InvalidFormatError,
    InvalidTimeOfDayError,
    QRCodeTask,
    SSSType,
    Takeoff,
    Task,
    TaskType,
    TimeOfDay,
    Turnpoint,
    TurnpointType,
    Waypoint,
    parse_task,
)


class TestTimeOfDay:
    """Comprehensive TimeOfDay functionality tests."""

    def test_basic_functionality(self):
        """Test basic TimeOfDay functionality."""
        time = TimeOfDay(hour=10, minute=30, second=45)

        # Test string representation
        assert str(time) == "10:30:45Z"

        # Test JSON serialization
        json_str = time.to_json_string()
        assert json_str == '"10:30:45Z"'

        # Test JSON deserialization
        parsed_time = TimeOfDay.from_json_string(json_str)
        assert parsed_time.hour == 10
        assert parsed_time.minute == 30
        assert parsed_time.second == 45

    def test_validation(self):
        """Test TimeOfDay validation."""
        # Test valid edge cases
        TimeOfDay(hour=0, minute=0, second=0)  # Midnight
        TimeOfDay(hour=23, minute=59, second=59)  # End of day

        # Test invalid hours
        with pytest.raises(ValueError):
            TimeOfDay(hour=24, minute=0, second=0)

        with pytest.raises(ValueError):
            TimeOfDay(hour=-1, minute=0, second=0)

        # Test invalid minutes
        with pytest.raises(ValueError):
            TimeOfDay(hour=0, minute=60, second=0)

        # Test invalid seconds
        with pytest.raises(ValueError):
            TimeOfDay(hour=0, minute=0, second=60)

    def test_invalid_format_parsing(self):
        """Test TimeOfDay parsing with invalid format."""
        with pytest.raises(InvalidTimeOfDayError):
            TimeOfDay.from_json_string('"invalid"')


class TestWaypoint:
    """Waypoint functionality tests."""

    def test_basic_functionality(self):
        """Test Waypoint basic operations."""
        waypoint = Waypoint(
            name="Test Point",
            lat=46.5,
            lon=8.0,
            alt_smoothed=1000,
            description="Test description",
        )

        # Test dict conversion
        data = waypoint.to_dict()
        assert data["name"] == "Test Point"
        assert data["lat"] == 46.5
        assert data["lon"] == 8.0
        assert data["altSmoothed"] == 1000
        assert data["description"] == "Test description"

        # Test from dict
        parsed_waypoint = Waypoint.from_dict(data)
        assert parsed_waypoint.name == waypoint.name
        assert parsed_waypoint.lat == waypoint.lat
        assert parsed_waypoint.lon == waypoint.lon
        assert parsed_waypoint.alt_smoothed == waypoint.alt_smoothed
        assert parsed_waypoint.description == waypoint.description


class TestTaskSerialization:
    """Task JSON serialization and parsing tests."""

    def test_json_roundtrip_comprehensive(self):
        """Test comprehensive Task JSON serialization and deserialization."""
        # Create a complex test task with all optional components
        task = Task(
            task_type=TaskType.CLASSIC,
            version=1,
            earth_model=EarthModel.WGS84,
            turnpoints=[
                Turnpoint(
                    radius=1000,
                    waypoint=Waypoint(
                        name="TP01", lat=46.5, lon=8.0, alt_smoothed=1000
                    ),
                    type=TurnpointType.TAKEOFF,
                )
            ],
            takeoff=Takeoff(
                time_open=TimeOfDay(hour=10, minute=0, second=0),
                time_close=TimeOfDay(hour=18, minute=0, second=0),
            ),
            sss=SSS(
                type=SSSType.RACE,
                direction=Direction.ENTER,
                time_gates=[TimeOfDay(hour=12, minute=0, second=0)],
            ),
            goal=Goal(
                type=GoalType.CYLINDER, deadline=TimeOfDay(hour=20, minute=0, second=0)
            ),
        )

        # Convert to JSON and back
        json_str = task.to_json()
        parsed_task = Task.from_json(json_str)

        # Verify the parsed task
        assert parsed_task.task_type == TaskType.CLASSIC
        assert parsed_task.version == 1
        assert parsed_task.earth_model == EarthModel.WGS84
        assert len(parsed_task.turnpoints) == 1
        assert parsed_task.turnpoints[0].waypoint.name == "TP01"
        assert parsed_task.takeoff is not None
        assert parsed_task.sss is not None
        assert parsed_task.goal is not None

    def test_minimal_task_json(self):
        """Test parsing minimal task from JSON."""
        json_data = """{
            "taskType": "CLASSIC",
            "version": 1,
            "earthModel": "WGS84",
            "turnpoints": [
                {
                    "radius": 1000,
                    "waypoint": {
                        "name": "TP01",
                        "lat": 46.5,
                        "lon": 8.0,
                        "altSmoothed": 1000
                    }
                }
            ]
        }"""

        task = parse_task(json_data)
        assert task.task_type == TaskType.CLASSIC
        assert task.version == 1
        assert len(task.turnpoints) == 1


class TestTaskParsing:
    """Task parsing from various input formats."""

    def test_parse_real_task_file(self, reference_tasks_dir):
        """Test parsing real task files."""
        # Use a known task file for consistent testing
        task_file = reference_tasks_dir / "task_gibe.xctsk"
        if not task_file.exists():
            pytest.skip(f"Reference task file not found: {task_file}")

        with open(task_file, "r") as f:
            task_data = f.read()

        task = parse_task(task_data)
        assert task.task_type == TaskType.CLASSIC
        assert task.version == 1
        assert task.earth_model == EarthModel.WGS84
        assert len(task.turnpoints) == 17  # Based on the test file

    def test_parse_task_from_file_path(self, reference_tasks_dir):
        """Test parsing task directly from file path."""
        task_file = reference_tasks_dir / "task_gibe.xctsk"
        if not task_file.exists():
            pytest.skip(f"Reference task file not found: {task_file}")

        task = parse_task(str(task_file))
        assert task.task_type == TaskType.CLASSIC
        assert len(task.turnpoints) > 0

    def test_parse_task_empty_input(self):
        """Test parsing with empty input."""
        with pytest.raises(EmptyInputError):
            parse_task("")

        with pytest.raises(EmptyInputError):
            parse_task(b"")

    def test_parse_task_invalid_format(self):
        """Test parsing with invalid format."""
        with pytest.raises(InvalidFormatError):
            parse_task("invalid data")


class TestQRCodeIntegration:
    """QR code task conversion and basic functionality."""

    def test_qr_code_task_conversion(self):
        """Test QR code task conversion."""
        # Create a simple task
        task = Task(
            task_type=TaskType.CLASSIC,
            version=1,
            turnpoints=[
                Turnpoint(
                    radius=1000,
                    waypoint=Waypoint(
                        name="TP01", lat=46.5, lon=8.0, alt_smoothed=1000
                    ),
                )
            ],
        )

        # Convert to QR code task and back
        qr_task = task.to_qr_code_task()
        converted_task = qr_task.to_task()

        # Verify conversion
        assert converted_task.task_type == TaskType.CLASSIC
        assert len(converted_task.turnpoints) == 1
        assert converted_task.turnpoints[0].waypoint.name == "TP01"

    def test_qr_code_task_string(self):
        """Test QR code task string generation."""
        qr_task = QRCodeTask(version=2)
        qr_string = qr_task.to_string()
        assert qr_string.startswith("XCTSK:")

        # Parse back from string
        parsed_qr_task = QRCodeTask.from_string(qr_string)
        assert parsed_qr_task.version == 2
