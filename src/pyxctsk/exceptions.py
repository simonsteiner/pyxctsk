"""Custom exceptions for the pyxctsk package."""


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
        self.time_str = time_str
        super().__init__(f"invalid time: {time_str!r}")
