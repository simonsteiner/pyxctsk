"""Basic tests for XCTrack task functionality without QR code dependencies."""

import pytest

from pyxctsk import (
    SSS,
    Direction,
    EarthModel,
    EmptyInputError,
    Goal,
    GoalType,
    InvalidFormatError,
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


def test_time_of_day():
    """Test TimeOfDay functionality."""
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


def test_waypoint():
    """Test Waypoint functionality."""
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


def test_task_json_roundtrip():
    """Test Task JSON serialization and deserialization."""
    # Create a test task
    task = Task(
        task_type=TaskType.CLASSIC,
        version=1,
        earth_model=EarthModel.WGS84,
        turnpoints=[
            Turnpoint(
                radius=1000,
                waypoint=Waypoint(name="TP01", lat=46.5, lon=8.0, alt_smoothed=1000),
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


def test_parse_task_json():
    """Test parsing task from JSON."""
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


def test_parse_real_task_file():
    """Test parsing the real task file."""
    with open("tests/task_2020-07-07.xctsk", "r") as f:
        task_data = f.read()

    task = parse_task(task_data)
    assert task.task_type == TaskType.CLASSIC
    assert task.version == 1
    assert task.earth_model == EarthModel.WGS84
    assert len(task.turnpoints) == 17  # Based on the test file
    assert task.turnpoints[0].waypoint.name == "TP01"
    assert task.sss is not None
    assert task.goal is not None


def test_parse_task_empty_input():
    """Test parsing with empty input."""
    with pytest.raises(EmptyInputError):
        parse_task("")

    with pytest.raises(EmptyInputError):
        parse_task(b"")


def test_parse_task_invalid_format():
    """Test parsing with invalid format."""
    with pytest.raises(InvalidFormatError):
        parse_task("invalid data")


if __name__ == "__main__":
    pytest.main([__file__])
