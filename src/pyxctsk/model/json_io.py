"""JSON in and out of the model, and the check that a wire value is an object.

Every payload the library reads or writes passes through :func:`load_json` or
:func:`dump_json`, so a malformed document raises
:class:`~pyxctsk.exceptions.MalformedPayloadError` and a layout is named, never
spelled as ``json.dumps`` options at a call site.
"""

import json
import math
from typing import Any, Iterator, Literal, Mapping

from ..exceptions import MalformedPayloadError, NotJsonError


def json_type(value: Any) -> str:
    """Name a decoded JSON value's type the way the format would."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "a boolean"
    if isinstance(value, (int, float)):
        return "a number"
    if isinstance(value, str):
        return "a string"
    if isinstance(value, list):
        return "an array"
    if isinstance(value, Mapping):
        return "an object"
    return type(value).__name__


def require_object(data: Any) -> Mapping[str, Any]:
    """Return a wire value that must be a JSON object, or refuse it.

    Args:
        data: The decoded value.

    Returns:
        The same value, now known to be a mapping.

    Raises:
        MalformedPayloadError: If it is anything else.
    """
    if not isinstance(data, Mapping):
        raise MalformedPayloadError(f"expected an object, got {json_type(data)}")
    return data


#: How many arrays and objects may sit inside one another. RFC 8259 §9 lets a
#: parser refuse deeper documents; without a bound, a document of a few hundred
#: brackets loads and then overflows the stack in :func:`json.dumps`.
MAX_NESTING = 100


def _segment(key: object) -> str:
    """Spell a key for a path, escaping what the console could not print."""
    text = str(key)
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return text.encode("unicode_escape").decode("ascii")
    return text


def _children(
    value: Mapping[Any, Any] | list[Any] | tuple[Any, ...], path: str
) -> Iterator[tuple[Any, str, bool]]:
    """Yield a container's keys and items, each with the path it sits at.

    Each entry is (child, path, nested): a mapping yields each ``str`` key
    (not nested) and then its value (nested), both at the key's
    path; a list or tuple yields its items at ``[index]``, nested.
    """
    if isinstance(value, Mapping):
        for key, item in value.items():
            where = f"{path}.{_segment(key)}" if path else _segment(key)
            if isinstance(key, str):
                yield key, where, False
            yield item, where, True
    else:
        for index, item in enumerate(value):
            yield item, f"{path}[{index}]", True


def _refuse_unwritable(value: Any, path: str = "", depth: int = 1) -> None:
    """Raise if JSON cannot carry ``value`` and UTF-8 cannot write it.

    Raises:
        MalformedPayloadError: For a float that is not finite or a string UTF-8
            cannot encode, located by ``path``, or for nesting past
            :data:`MAX_NESTING`, which names no path: a path that deep would be
            the whole message.
    """
    if isinstance(value, float) and not math.isfinite(value):
        raise MalformedPayloadError("expected a finite number", path)
    if isinstance(value, str) and not _encodes(value):
        raise MalformedPayloadError("text UTF-8 cannot encode", path)
    if isinstance(value, (Mapping, list, tuple)):
        if depth > MAX_NESTING:
            raise MalformedPayloadError(f"nested deeper than {MAX_NESTING} levels")
        for child, where, nested in _children(value, path):
            _refuse_unwritable(child, where, depth + 1 if nested else depth)


def _encodes(text: str) -> bool:
    """Whether UTF-8 can encode ``text``, which a lone surrogate defeats."""
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def load_json(text: str | bytes) -> Any:
    """Decode a JSON document that :func:`dump_json` can write back.

    Args:
        text: The document.

    Returns:
        The decoded value, of whatever JSON type it is.

    Raises:
        MalformedPayloadError: If it does not decode, holds a number that is
            not finite (``NaN``, ``Infinity``, ``1e999``), a string UTF-8
            cannot encode, or nests deeper than :data:`MAX_NESTING`.
    """
    try:
        value = json.loads(text)
    except RecursionError:
        raise MalformedPayloadError(
            f"nested deeper than {MAX_NESTING} levels"
        ) from None
    except ValueError as exc:
        raise NotJsonError(f"not JSON: {exc}") from exc
    _refuse_unwritable(value)
    return value


#: The layouts a JSON output is written in, one per kind of output: ``compact``
#: for a wire payload (the task file, the QR string — no space after ``,`` or
#: ``:``), ``line`` for one line as :func:`json.dumps` spaces it by default
#: (GeoJSON), ``indented`` for a document a person reads (the distance report).
#: Named rather than spelled as ``separators=``/``indent=`` at each call site,
#: so a combination no output uses cannot be asked for.
JsonLayout = Literal["compact", "line", "indented"]

_LAYOUT_OPTIONS: dict[str, dict[str, Any]] = {
    "compact": {"separators": (",", ":")},
    "line": {},
    "indented": {"indent": 2},
}


def dump_json(value: Any, *, layout: JsonLayout) -> str:
    r"""Encode a value as a JSON document, the one way every output writes JSON.

    :func:`load_json`'s counterpart. What every output shares is decided here:
    a character outside ASCII is written as itself, never as a ``\u`` escape.
    The two spellings are one JSON value, but four call sites chose between
    them independently, so a waypoint named ``Château`` came out one way in the
    task and QR formats and the other in GeoJSON and the distance report — and
    the fix that reached two of them could not reach the other two. Only the
    layout is each output's own, and it is one of :data:`JsonLayout`'s.

    A value built in code is held to what :func:`load_json` accepts, since the
    model does not validate on construction.

    Args:
        value: What to encode.
        layout: How the document is laid out.

    Returns:
        The document.

    Raises:
        MalformedPayloadError: If the value holds a number that is not finite,
            a string UTF-8 cannot encode, or nesting past :data:`MAX_NESTING`.
    """
    _refuse_unwritable(value)
    return json.dumps(value, ensure_ascii=False, **_LAYOUT_OPTIONS[layout])
