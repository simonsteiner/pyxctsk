"""Numeric rounding shared by the domain model and the QR codec.

Kept separate from both so neither has to import the other for it: the rule is
a property of the values themselves — radii and altitudes are whole metres —
not of the format they happen to be written in.
"""

import math


def round_half_up(value: float) -> int:
    """Round to the nearest integer, breaking ties upward (toward +infinity).

    XCTrack's reference implementation uses Java's ``Math.round``, which is
    ``floor(x + 0.5)``. Python's built-in ``round`` is banker's rounding, so the
    two disagree on exact ties: ``round(612344.5)`` is 612344 where Java gives
    612345. That is ~1.1 m of longitude — inside the FAI 5 m tolerance, but
    there is no reason to differ from the reference.

    Note this rounds -2.5 to -2, toward +infinity rather than away from zero,
    which is what Java does.

    Args:
        value: The number to round.

    Returns:
        int: The nearest integer, with exact halves rounded up.
    """
    return math.floor(value + 0.5)
