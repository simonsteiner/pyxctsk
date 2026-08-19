"""Comprehensive core functionality tests for pyxctsk.

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
from pyxctsk.exceptions import InvalidTimeOfDayError
from tests.corpus import reference_task


class TestTimeOfDay:
    """Comprehensive TimeOfDay functionality tests."""

    def test_basic_functionality(self):
        """Test basic TimeOfDay functionality."""
        time = TimeOfDay(hour=10, minute=30, second=45)

        # Test string representation
        assert str(time) == "10:30:45Z"

        # Test JSON serialization — the bare value, quoted later by json.dumps.
        json_str = time.to_json_string()
        assert json_str == "10:30:45Z"

        # Test JSON deserialization (accepts the bare value and a quoted one)
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

    def test_parse_real_task_file(self):
        """Test parsing real task files."""
        task = parse_task(reference_task("task_gibe").xctsk_path.read_text())
        assert task.task_type == TaskType.CLASSIC
        assert task.version == 1
        assert task.earth_model == EarthModel.WGS84
        assert len(task.turnpoints) == 17  # Based on the test file

    def test_parse_task_from_file_path(self):
        """Test parsing task directly from file path."""
        task = parse_task(str(reference_task("task_gibe").xctsk_path))
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


class TestTheGoalDefaultIsDerivedNotStored:
    """A task serializes to what it was read from, goal key included.

    ``__post_init__`` used to write the CYLINDER default onto :attr:`Task.goal`,
    which made it part of the object and therefore part of the output: a file
    with no ``goal`` key round-tripped into one carrying
    ``{"goal": {"type": "CYLINDER"}}``. The only place the library invented a
    field, in the module whose docstring says nothing derived is stored here.
    It went unnoticed because every reference task carries a goal.
    """

    NO_GOAL = (
        '{"taskType":"CLASSIC","version":1,"turnpoints":['
        '{"radius":400,"waypoint":{"name":"A","lat":47.0,"lon":8.0,"altSmoothed":500}},'
        '{"radius":1000,"waypoint":{"name":"B","lat":47.1,"lon":8.2,"altSmoothed":900}}'
        "]}"
    )

    def test_a_task_without_a_goal_key_writes_none(self):
        """The round trip is exact."""
        assert Task.from_json(self.NO_GOAL).to_json() == self.NO_GOAL

    def test_but_it_is_still_flown_to_a_cylinder(self):
        """The contract callers rely on, as a projection."""
        task = Task.from_json(self.NO_GOAL)

        assert task.goal is None
        assert task.effective_goal is not None
        assert task.effective_goal.type is GoalType.CYLINDER

    def test_an_unstated_goal_type_defaults_without_being_written_back(self):
        """A goal object with no type is a cylinder to fly, and unchanged on disk."""
        task = Task.from_json(
            self.NO_GOAL.replace("]}", '],"goal":{"deadline":"18:00:00Z"}}')
        )

        assert task.goal is not None and task.goal.type is None
        assert task.effective_goal is not None
        assert task.effective_goal.type is GoalType.CYLINDER
        # And the caller's own Goal was not mutated into the derived one.
        assert task.effective_goal is not task.goal
        assert '"type"' not in task.to_json().split('"goal"')[1]

    def test_a_task_with_no_turnpoints_has_nothing_to_be_a_goal(self):
        """No turnpoints, no default."""
        assert (
            Task(task_type=TaskType.CLASSIC, version=1, turnpoints=[]).effective_goal
            is None
        )
