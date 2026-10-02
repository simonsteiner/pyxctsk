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


class MalformedPayloadError(pyXCTSKError, ValueError):
    """Raised when a payload is JSON of the wrong shape for the format.

    The one error reading a task raises, from either format, whatever went
    wrong inside it. The field tables used to trust wire types: a list where
    an object belongs reached ``.get`` and escaped as ``AttributeError``, a
    string where a list belongs was read one character at a time, and the
    parser kept a tuple of whichever built-in types had leaked out so far.
    Now the table checks, and every failure carries where it happened.

    Attributes:
        reason: What was wrong, without the location.
        path: Where, as keys and indices from the payload's root — e.g.
            ``turnpoints[0].waypoint`` — or empty for the root itself.
    """

    def __init__(self, reason: str, path: str = ""):
        """Initialize with a reason and the path it applies to."""
        self.reason = reason
        self.path = path
        super().__init__(f"{path}: {reason}" if path else reason)

    def inside(self, segment: str) -> "MalformedPayloadError":
        """The same error, seen from one level further out.

        Args:
            segment: The key, or ``[i]`` index, holding the value this error
                is about.

        Returns:
            A new error whose path starts with ``segment``.
        """
        if not self.path:
            path = segment
        elif self.path.startswith("["):
            path = segment + self.path
        else:
            path = f"{segment}.{self.path}"
        return MalformedPayloadError(self.reason, path)


class MismatchedRouteError(pyXCTSKError, ValueError):
    """Raised when a route is paired with a task it was not flown for.

    ``MeasuredTask`` exists to make that pairing unrepresentable, and its
    constructor is public, so it is where the check lives: one route point per
    turnpoint, each inside its turnpoint's cylinder, measured on the task's
    earth model. Handing it another task's route used to return a fully formed
    report — 47.8 km for a 94.0 km task — with no error. ``ValueError`` is kept
    for the reason :class:`TooFewTurnpointsError` states.
    """


class UnmeasurableRouteError(pyXCTSKError):
    """Raised when a task's geometry cannot be measured on its earth.

    Two owners raise it, each for the one thing it knows. S7F §7.1.2 solves a
    route in one Transverse Mercator plane centred on the task area, and
    :class:`~pyxctsk.distance.plane.LocalPlane` is the only way into or out of
    it: a point a quarter of the globe from the plane's central meridian has
    no finite planar image, and a planar point thousands of kilometres out has
    no finite way back. Those used to surface from the solver as an
    ``AssertionError`` about its own placements, as pyproj's ``CRSError``, or
    as a distance of ``NaN`` metres with exit 0. And a cylinder reaching past
    the far side of the earth has no boundary at all, which
    :func:`~pyxctsk.distance.earth.geodesic_destination` refuses wherever a
    point is placed on one — a route point snapped onto it, its outline, a
    goal line's end; that used to be a finite, wrong distance with exit 0.

    It is not a ``ValueError``: unlike :class:`TooFewTurnpointsError` it has
    no earlier type to stay compatible with.
    """


class InvalidTimeOfDayError(pyXCTSKError, ValueError):
    """Raised when a time of day is not one.

    Both of ``TimeOfDay``'s refusals raise it — a spelling that is not
    ``HH:MM:SSZ``, and a field out of range — in one wording. The second used
    to be a bare ``ValueError``, so ``ValueError`` is kept for the reason
    :class:`TooFewTurnpointsError` states.

    Attributes:
        time_str: The value that is not a time, as it arrived — usually a
            string, but whatever the wire carried for one that is not.
        reason: Why it is not one. Defaults to the spelling, the one reason
            the parser has.
    """

    def __init__(self, time_str: object, reason: str = "expected HH:MM:SSZ"):
        """Initialize with the value that is not a time, and why."""
        self.time_str = time_str
        self.reason = reason
        super().__init__(f"invalid time {time_str!r}: {reason}")
