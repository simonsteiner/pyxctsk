"""Custom exceptions for the pyxctsk package.

This module defines the exception hierarchy for pyxctsk, including errors for empty input, invalid formats, and time parsing issues.
"""

from collections.abc import Sequence


class pyXCTSKError(Exception):
    """Base exception for all pyxctsk errors."""

    pass


class EmptyInputError(pyXCTSKError):
    """Raised when input data is empty."""

    pass


class InvalidFormatError(pyXCTSKError):
    """Raised when input format is invalid."""

    pass


class TaskValidationError(pyXCTSKError):
    """Raised when a task breaks the spec's structural rules.

    Distinct from :class:`InvalidFormatError`: the input parsed fine, but the
    turnpoints it describes are not a well-formed task.

    Attributes:
        issues (list): One :class:`~pyxctsk.model.validation.ValidationIssue` per
            violated rule, each naming the rule it broke. Typed loosely here
            because ``validation`` imports the exceptions, not the reverse.
    """

    def __init__(self, issues: Sequence[object]):
        """Initialize with the list of structural violations."""
        self.issues = list(issues)
        super().__init__("; ".join(str(issue) for issue in issues))


class InvalidTimeOfDayError(pyXCTSKError):
    """Raised when time of day format is invalid."""

    def __init__(self, time_str: str):
        """Initialize InvalidTimeOfDayError with the invalid time string."""
        self.time_str = time_str
        super().__init__(f"invalid time: {time_str!r}")
