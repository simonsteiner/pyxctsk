"""Custom exceptions for the xctrack package."""


class XCTrackError(Exception):
    """Base exception for all xctrack errors."""

    pass


class EmptyInputError(XCTrackError):
    """Raised when input data is empty."""

    pass


class InvalidFormatError(XCTrackError):
    """Raised when input format is invalid."""

    pass


class InvalidTimeOfDayError(XCTrackError):
    """Raised when time of day format is invalid."""

    def __init__(self, time_str: str):
        self.time_str = time_str
        super().__init__(f"invalid time: {time_str!r}")
