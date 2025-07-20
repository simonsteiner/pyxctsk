"""Common enums shared across pyxctsk modules to avoid circular imports."""

import re
from dataclasses import dataclass

from .exceptions import InvalidTimeOfDayError


@dataclass(frozen=True)
class TimeOfDay:
    """Represents a time of day (HH:MM:SS).

    Attributes:
        hour (int): Hour (0-23).
        minute (int): Minute (0-59).
        second (int): Second (0-59).
    """

    hour: int
    minute: int
    second: int

    def __post_init__(self) -> None:
        """Validate the time of day values."""
        if not (0 <= self.hour <= 23):
            raise ValueError("Hour must be between 0 and 23")
        if not (0 <= self.minute <= 59):
            raise ValueError("Minute must be between 0 and 59")
        if not (0 <= self.second <= 59):
            raise ValueError("Second must be between 0 and 59")

    def to_json_string(self) -> str:
        """Convert to JSON string format.

        Returns:
            str: JSON string representation of the time.
        """
        return f'"{self.hour:02d}:{self.minute:02d}:{self.second:02d}Z"'

    @classmethod
    def from_json_string(cls, time_str: str) -> "TimeOfDay":
        """Parse from JSON string format.

        Args:
            time_str (str): JSON string to parse.

        Returns:
            TimeOfDay: Parsed TimeOfDay object.

        Raises:
            InvalidTimeOfDayError: If the string is not a valid time.
        """
        # Handle both quoted and unquoted formats
        if time_str.startswith('"') and time_str.endswith('"'):
            time_str = time_str[1:-1]  # Remove quotes

        pattern = r"^(\d{2}):(\d{2}):(\d{2})Z$"
        match = re.match(pattern, time_str)
        if not match:
            raise InvalidTimeOfDayError(f"Invalid time string: {time_str}")

        hour = int(match.group(1))
        minute = int(match.group(2))
        second = int(match.group(3))

        return cls(hour=hour, minute=minute, second=second)

    def __str__(self) -> str:
        """Return string representation in HH:MM:SSZ format."""
        return f"{self.hour:02d}:{self.minute:02d}:{self.second:02d}Z"
