"""Custom exceptions for the pyxctsk package.

This module defines the exception hierarchy for pyxctsk, including errors for empty input, invalid formats, and time parsing issues.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .model.validation import ValidationIssue

#: What to install for QR *image* handling, named once. Two modules tell a user
#: this — :mod:`pyxctsk.parser` when an image cannot be read and
#: :mod:`pyxctsk.qrcode.image` when one cannot be written — and it lives here
#: beside :class:`MissingQRCodeSupportError`, the error that reports it, rather
#: than being spelled out at each site. The spelling matters: the message used
#: to name the ``web`` extra, which is flask.
QR_EXTRA_INSTALL = "pyxctsk[qr]"


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

    The whole point of a named rule is that a caller can react to a specific
    violation without matching on the English message, so this is typed:
    ``except TaskValidationError as e: e.issues[0].rule`` used to fail the type
    checker with *"object" has no attribute "rule"*. The import is under
    ``TYPE_CHECKING`` because the cycle it avoids is a runtime one, through
    ``model/__init__`` — ``validation`` itself imports only ``model.enums``,
    and never these exceptions.

    Attributes:
        issues: One :class:`~pyxctsk.model.validation.ValidationIssue` per
            violated rule, each naming the rule it broke.
    """

    def __init__(self, issues: Sequence["ValidationIssue"]):
        """Initialize with the list of structural violations."""
        self.issues: list[ValidationIssue] = list(issues)
        super().__init__("; ".join(str(issue) for issue in issues))


class MissingQRCodeSupportError(pyXCTSKError, ImportError):
    """Raised when QR code image handling is asked for without its dependencies.

    Both bases are load-bearing. ``pyXCTSKError`` puts it in this library's
    hierarchy, so the CLI's ``except (pyXCTSKError, OSError)`` reports it as a
    user-facing error rather than letting a traceback out — which it did once
    that catch was narrowed from a bare ``except Exception``. ``ImportError``
    keeps every existing ``except ImportError`` around
    :func:`~pyxctsk.generate_qrcode_image` working, since that is the type it
    has always raised.

    Reading a QR image without the dependencies already reported itself
    properly, through :class:`InvalidFormatError`; this is the writing half.
    """


class TooFewTurnpointsError(pyXCTSKError, ValueError):
    """Raised when a task has too few turnpoints to have a distance at all.

    Both bases are load-bearing, for the reason
    :class:`MissingQRCodeSupportError` states: ``pyXCTSKError`` puts it in this
    library's hierarchy, and ``ValueError`` keeps every existing
    ``except ValueError`` working, since that is the type it has always raised.

    It was raised from ``distance/report.py`` and descended from ``ValueError``
    alone, so it was the one library error outside the hierarchy — and the CLI
    paid for it directly, in two commands with two different catch tuples
    (``except (pyXCTSKError, OSError)`` for ``convert``, the same plus this for
    ``distances``). A sixth library error would have meant editing ``cli.py``.
    """


class InvalidTimeOfDayError(pyXCTSKError):
    """Raised when time of day format is invalid."""

    def __init__(self, time_str: str):
        """Initialize InvalidTimeOfDayError with the invalid time string."""
        self.time_str = time_str
        super().__init__(f"invalid time: {time_str!r}")
