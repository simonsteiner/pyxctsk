"""Verbatim passthrough of extensions and unknown keys.

Both task formats carry data pyxctsk does not interpret, and both must hand it
back unchanged:

- **extensions** — the spec's manufacturer mechanism. An opaque list of dicts
  under ``extensions`` in the full JSON format and ``x`` in the QR one.
- **unknown keys** — anything else the spec does not define. Real producers do
  put data outside the ``extensions`` mechanism (SeeYou Navigator writes an
  elevated goal altitude as a root ``{"o": {"v": 2, "fa": 1220}}``), and
  dropping it would silently lose data on a round-trip.

Nothing here is interpreted: values are carried, not understood, and are never
mapped onto a spec field — a look-alike key need not share the spec's units.

Every serializable shape declares a ``KNOWN_KEYS`` allow-list of the keys it
reads itself; everything outside it is unknown. That includes the nested
objects — a waypoint, an sss, a goal — which the spec gives no extensions list:
they pass ``ext_key=None`` and use the unknown-key half of the rule alone. A
shape without one drops whatever it does not understand, which is the loss this
module exists to prevent.

The two functions below are the only places that rule is implemented, so a new
shape gets it by calling them rather than by re-deriving it.
"""

from typing import Any, MutableMapping

#: The extensions key in the full JSON task format.
EXTENSIONS_KEY = "extensions"
#: The extensions key in the compact QR format.
QR_EXTENSIONS_KEY = "x"


def read_passthrough(
    data: dict[str, Any], known_keys: frozenset[str], ext_key: str | None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Split a payload into its extensions list and its unknown-key remainder.

    Args:
        data: The parsed object for one model.
        known_keys: The keys that model reads itself, including ``ext_key``.
        ext_key: ``EXTENSIONS_KEY``, ``QR_EXTENSIONS_KEY``, or None for a shape
            the spec gives no extensions list — the nested objects, which
            still need the unknown-key half of the rule.

    Returns:
        Tuple of (extensions, unknown). Both are fresh containers, so mutating
        them cannot reach back into ``data``. A missing or null extensions key
        yields an empty list rather than None, as does ``ext_key=None``.
    """
    extensions = list(data.get(ext_key) or []) if ext_key is not None else []
    unknown = {k: v for k, v in data.items() if k not in known_keys}
    return extensions, unknown


def write_passthrough(
    result: MutableMapping[str, Any],
    extensions: list[dict[str, Any]],
    unknown: dict[str, Any],
    ext_key: str | None,
) -> None:
    """Append extensions and unknown keys to a serialized model, in place.

    Both are written last, matching the order the spec lists extensions in. An
    empty extensions list emits no key at all, so an optional field stays
    absent rather than becoming ``[]``.

    **An unknown key never shadows a spec field.** A key the model already
    wrote wins: pyxctsk understands that one, and letting carried-through data
    overwrite it would turn a value we merely failed to understand into one we
    report wrongly.

    ``ext_key`` is excluded outright rather than left to that rule, because the
    rule only protects keys already in ``result``: with an empty extensions
    list nothing is written, and an ``unknown[ext_key]`` would then land in the
    output as the extensions field — carrying a value of any shape into a key
    the spec says is a list.

    Args:
        result: The dict built by the model's ``to_dict``, modified in place.
        extensions: The model's opaque extensions list.
        unknown: The model's carried-through unknown keys.
        ext_key: ``EXTENSIONS_KEY``, ``QR_EXTENSIONS_KEY``, or None for a shape
            with no extensions list — nothing is then reserved, and there is
            nowhere to write extensions, which such a shape never has.
    """
    if ext_key is not None and extensions:
        result[ext_key] = extensions
    for key, value in unknown.items():
        if key != ext_key:
            result.setdefault(key, value)
