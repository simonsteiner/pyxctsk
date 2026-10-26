"""Wire-scalar codecs: how one value is spelled on the wire.

Every scalar a table reads goes through one of the codecs below, and each
kind of scalar has exactly one rule. The table used to check containers and
trust scalars: ``name``, ``lat``, ``lon``, ``version`` and ``fa`` were read
as whatever JSON held, and "a number on the wire" was answered three
different ways by three codecs. So a bad scalar parsed and failed where it
was first *used* — an ``OverflowError`` for an infinite radius, a
``TypeError`` from the planar projection for a latitude spelled ``"46"``,
and for a JSON ``true`` latitude no error at all: it was 1°N.

The rules, once each:

- **A number is finite and not a boolean.** ``True == 1`` in Python; on the
  wire it is not a number. Python's ``json`` reads ``NaN`` and ``Infinity``,
  and an integer too large for a float, so finiteness is checked here.
- **A number may be spelled as a string** — in JSON's own number grammar,
  nothing looser. Burnair writes ``"radius": "700"``, and producers have
  written the QR version and earth model as strings; it is one rule for every
  number rather than a flag on some of them. It is written back as a number.
- **Text is a string UTF-8 can carry.** A lone surrogate is valid JSON and
  cannot be written back out.

Each raises :class:`~pyxctsk.exceptions.MalformedPayloadError`, which the
table locates — ``turnpoints[0].radius: expected a finite number, got 'inf'``.
"""

import math
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping, TypeVar

from ..exceptions import MalformedPayloadError, pyXCTSKError
from .json_io import json_type
from .rounding import round_half_up
from .time_of_day import TimeOfDay

T = TypeVar("T")

#: What a codec may raise when handed a wire value of the wrong type or
#: spelling. Codecs are applied to untrusted input, so this is the one place
#: these are expected rather than bugs: each is converted into a
#: :class:`~pyxctsk.exceptions.MalformedPayloadError` naming where it happened.
_READ_ERRORS = (KeyError, ValueError, TypeError, AttributeError, pyXCTSKError)


def read_at(segment: str, read: Callable[[Any], T], raw: Any) -> T:
    """Run one step of a read, attributing any failure to ``segment``.

    Args:
        segment: The key, or ``[i]`` index, being read.
        read: The step.
        raw: What the step reads.

    Returns:
        What the step returned.

    Raises:
        MalformedPayloadError: Whatever the step raised, located.
    """
    try:
        return read(raw)
    except MalformedPayloadError as exc:
        raise exc.inside(segment) from exc.__cause__
    except KeyError as exc:
        # A required key that is not there. The key itself is the location,
        # which is one level deeper than ``segment`` only when a row reads a
        # key it does not own — so name the key that was missing.
        raise MalformedPayloadError(
            "required key is missing", str(exc.args[0]) if exc.args else segment
        ) from exc
    except _READ_ERRORS as exc:
        raise MalformedPayloadError(str(exc), segment) from exc


@dataclass(frozen=True)
class Codec:
    """How one value is spelled on the wire.

    Attributes:
        to_wire: Model value to JSON value.
        from_wire: JSON value to model value.
    """

    to_wire: Callable[[Any], Any]
    from_wire: Callable[[Any], Any]


def _identity(value: Any) -> Any:
    return value


#: JSON's own number grammar — what "a number spelled as a string" means.
#: Python's ``int`` and ``float`` read far more: padding, ``1_000``, ``inf``,
#: and digits from every script, so ``"٣"`` would be a radius of 3 metres.
_JSON_NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?")

#: Longest refused value echoed into a message; a 5 000-digit altitude is not
#: worth repeating back in full.
_ECHO_LIMIT = 40


def _describe(raw: Any) -> str:
    """Name a refused wire value: strings and numbers by value, else by type."""
    if isinstance(raw, str) or (
        isinstance(raw, (int, float)) and not isinstance(raw, bool)
    ):
        text = repr(raw)
        return text if len(text) <= _ECHO_LIMIT else text[: _ECHO_LIMIT - 3] + "..."
    return json_type(raw)


def _wire_number(raw: Any) -> int | float | None:
    """The number a wire value is or spells, keeping JSON's int/float; else None.

    None for a boolean, a container, and a string outside JSON's grammar — and
    for an integer string too long for Python to convert, which no float could
    hold either.
    """
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return raw
    if not isinstance(raw, str):
        return None
    match = _JSON_NUMBER.fullmatch(raw)
    if match is None:
        return None
    try:
        return float(raw) if match.group(1) or match.group(2) else int(raw)
    except ValueError:  # more digits than int() will convert
        return None


def _read_number(raw: Any) -> int | float:
    """A finite number, or a string spelling one; JSON's int/float kept."""
    value = _wire_number(raw)
    if value is None:
        raise MalformedPayloadError(f"expected a number, got {_describe(raw)}")
    try:
        finite = math.isfinite(value)
    except OverflowError:  # an integer no float can hold
        finite = False
    if not finite:
        raise MalformedPayloadError(f"expected a finite number, got {_describe(raw)}")
    return value


def _read_integer(raw: Any) -> int:
    """An integer, or a string spelling one; ``2.0`` reads as 2, ``true`` never.

    A producer holding a double writes ``1.0``; it is read as the integer it
    is, and so written back as ``1``.
    """
    value = _wire_number(raw)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if not isinstance(value, int):
        raise MalformedPayloadError(f"expected an integer, got {_describe(raw)}")
    return value


def _coordinate(name: str, limit: int) -> Callable[[Any], int | float]:
    """Return the reader for a coordinate within ``[-limit, limit]`` degrees."""

    def read(raw: Any) -> int | float:
        value = _read_number(raw)
        if not -limit <= value <= limit:
            raise MalformedPayloadError(
                f"{name} {value!r} is outside [-{limit}, {limit}]"
            )
        return value

    return read


def _read_text(raw: Any) -> str:
    """A string that UTF-8, and so every output format, can carry."""
    if not isinstance(raw, str):
        raise MalformedPayloadError(f"expected a string, got {_describe(raw)}")
    try:
        raw.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise MalformedPayloadError(
            f"not valid text: {exc.reason} at index {exc.start}"
        ) from None
    return raw


#: Any finite number — the elevated goal's height above the last turnpoint.
#: An integer stays an integer, so what was read is what is written.
NUMBER = Codec(_identity, _read_number)

#: A number this library holds as whole metres — a radius or an altitude. The
#: QR encoding can only carry whole metres, so a fractional value is rounded on
#: the way in; see :mod:`pyxctsk.model.rounding` for which way.
WHOLE_METRES = Codec(_identity, lambda raw: round_half_up(_read_number(raw)))

#: A whole number: a format version, or one of the QR format's wire integers.
INTEGER = Codec(_identity, _read_integer)

#: Degrees north, in ``[-90, 90]``.
LATITUDE = Codec(_identity, _coordinate("latitude", 90))

#: Degrees east, in ``[-180, 180]``.
LONGITUDE = Codec(_identity, _coordinate("longitude", 180))

#: A name or a description.
TEXT = Codec(_identity, _read_text)

#: ``HH:MM:SSZ``, the only time spelling either format uses.
TIME_OF_DAY = Codec(lambda value: value.to_json_string(), TimeOfDay.from_json_string)


def enum_codec(enum_cls: Callable[[Any], Any]) -> Codec:
    """Return a codec for a constrained value.

    Args:
        enum_cls: The enum. Called on the wire value, so an unrecognized one
            raises rather than moving through the library as a bare string.

    Returns:
        Codec: Spelling the enum as its ``value``.
    """
    return Codec(lambda member: member.value, enum_cls)


def wire_int_codec(table: Mapping[Any, int]) -> Codec:
    """Return a codec spelling constrained values as the integers a format uses.

    The QR format writes a goal type as ``1`` or ``2`` where the full format
    writes ``"LINE"`` or ``"CYLINDER"``. That is a spelling, not a second kind
    of value, so the QR models hold the same enums as the full ones and this
    codec is where the integers live. They used to be six ``IntEnum`` classes
    and twelve translation tables between them and the model's enums, with a
    default at every call site for whatever a table left out.

    Args:
        table: Each value's wire integer. Must be one-to-one. The integer is
            read by :data:`INTEGER`, so a string spelling one is accepted and a
            JSON ``true`` — which Python calls ``1`` — is not.

    Returns:
        Codec: Writing ``table[value]``, and reading its inverse.
    """
    inverse = {number: value for value, number in table.items()}
    if len(inverse) != len(table):
        raise ValueError(f"wire integers are not one-to-one: {dict(table)!r}")

    def from_wire(raw: Any) -> Any:
        number = INTEGER.from_wire(raw)
        if number not in inverse:
            raise MalformedPayloadError(f"{raw!r} is not one of {sorted(inverse)}")
        return inverse[number]

    return Codec(lambda value: table[value], from_wire)


def list_codec(item: Codec) -> Codec:
    """Return a codec for a JSON array of values.

    Args:
        item: The codec for one element.

    Returns:
        Codec: Applying ``item`` element-wise.
    """

    def from_wire(raw: Any) -> list[Any]:
        # A list is required, not just an iterable: a string where an array
        # belongs used to be read one character at a time, so a single time
        # gate written as ``"12:00:00Z"`` reported "invalid time: '1'".
        if not isinstance(raw, list):
            raise MalformedPayloadError(f"expected an array, got {json_type(raw)}")
        return [read_at(f"[{i}]", item.from_wire, r) for i, r in enumerate(raw)]

    return Codec(lambda values: [item.to_wire(v) for v in values], from_wire)
