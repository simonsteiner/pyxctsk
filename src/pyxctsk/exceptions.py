"""
Custom exceptions for the pyxctsk package.

This module defines the exception hierarchy for pyxctsk, including errors for empty input, invalid formats, and time parsing issues.
"""


class pyXCTSKError(Exception):
    """Base exception for all pyxctsk errors."""

    pass


class EmptyInputError(pyXCTSKError):
    """Raised when input data is empty."""

    pass


class InvalidFormatError(pyXCTSKError):
    """Raised when input format is invalid."""

    pass


class InvalidTimeOfDayError(pyXCTSKError):
    """Raised when time of day format is invalid."""

    def __init__(self, time_str: str):
        """Initialize InvalidTimeOfDayError with the invalid time string."""
        self.time_str = time_str
        super().__init__(f"invalid time: {time_str!r}")
