"""JSON in and out of the model, and the check that a wire value is an object.

Every payload the library reads or writes passes through :func:`load_json` or
:func:`dump_json`, so a malformed document raises
:class:`~pyxctsk.exceptions.MalformedPayloadError` and a layout is named, never
spelled as ``json.dumps`` options at a call site.
"""

import json
from typing import Any, Literal, Mapping

from ..exceptions import MalformedPayloadError


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


def load_json(text: str | bytes) -> Any:
    """Decode a JSON document, refusing one that is not JSON at all.

    Args:
        text: The document.

    Returns:
        The decoded value, of whatever JSON type it is.

    Raises:
        MalformedPayloadError: If it does not decode.
    """
    try:
        return json.loads(text)
    except ValueError as exc:
        raise MalformedPayloadError(f"not JSON: {exc}") from exc


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

    A lone surrogate cannot arrive from a parsed task — the ``TEXT`` codec
    refuses one at read. A model built in code can still hold one, and then the
    document cannot be encoded as UTF-8; the model does not validate on
    construction, and this writer does not either.

    Args:
        value: What to encode.
        layout: How the document is laid out.

    Returns:
        The document.
    """
    return json.dumps(value, ensure_ascii=False, **_LAYOUT_OPTIONS[layout])
