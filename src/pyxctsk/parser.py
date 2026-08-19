"""Parser for XCTrack Task.

Parse, load, and convert XCTrack task data from various formats.
Handles optional QR code dependencies.

Supports:
- JSON string/bytes with task data
- XCTSK: URL string/bytes (compact QR code format)
- Image bytes containing a QR code (if QR code dependencies are available)
- File path (str) to any of the above (auto-detected)

The auto-detection works by trying an ordered list of focused format adapters,
one per supported format. **Each adapter answers two questions independently:
does the input look like my format, and can I read it?** That is what
:class:`FormatAdapter` is — a name, a ``recognizes`` and a ``read`` — and it is
what keeps every format's recognition beside its parsing.

The recognition question is not decoration. Without it, "not my format" could
only be said by failing to parse, and the QR-JSON adapter cannot fail: it
accepted *any* JSON object, so ``{}`` read as a task and a ten-turnpoint
``.xctsk`` document read as a task with **zero** turnpoints and its whole
content in ``unknown``. Only this tuple's order kept that from happening, and
the error path re-derived each adapter's predicate a second time, in
``_unrecognized``, where it could drift unseen — and where, for a JSON object,
it could never run at all.

Two rules follow, and each was a defect before:

- **The key sets are derived from the shapes** (:data:`FULL_FORMAT_ONLY_KEYS`,
  :data:`QR_FORMAT_ONLY_KEYS`), not listed here, so they cannot disagree with
  what the shapes actually read — the same reason ``KNOWN_KEYS`` is derived.
- **A recognized input that cannot be read raises**, naming the reason, rather
  than falling through to an adapter whose format it is not. Only the file-path
  heuristic still falls through, because it genuinely is a heuristic.

Functions:
    parse_task(data: bytes | str) -> Task: Auto-detect and parse task from supported formats.
"""

import json
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Callable

from .exceptions import (
    QR_EXTRA_INSTALL,
    EmptyInputError,
    InvalidFormatError,
    TaskValidationError,
)
from .model.task import TASK_SHAPE, Task
from .qrcode.task import (
    QR_CODE_SCHEME,
    QR_CODE_SCHEME_COMPRESSED,
    QR_TASK_SHAPE,
    QR_WAYPOINTS_TASK_SHAPE,
    QRCodeTask,
)

# Both QR schemes the spec defines. XCTSKZ: is checked first because XCTSK: is
# not a prefix of it, but keeping them ordered makes the intent obvious.
_QR_SCHEMES = (QR_CODE_SCHEME_COMPRESSED, QR_CODE_SCHEME)

# Optional QR code dependencies
try:
    import zxingcpp
    from PIL import Image

    QR_CODE_SUPPORT = True
except ImportError:
    Image = None  # type: ignore
    zxingcpp = None  # type: ignore
    QR_CODE_SUPPORT = False


# File extensions that mark a string as a path to read rather than inline data.
_FILE_EXTENSIONS = (".xctsk", ".json", ".png", ".jpg", ".jpeg")

# JSON decoding failures share these exception types across every adapter.
# ``TypeError`` is here because a JSON *array* or scalar reaches the shapes as
# something that does not answer ``.get``: ``parse_task("[]")`` used to leave
# the library as a bare ``TypeError``, past the CLI's error handling and into
# the user's terminal as a traceback.
_PARSE_ERRORS = (
    json.JSONDecodeError,
    ValueError,
    KeyError,
    TypeError,
    UnicodeDecodeError,
)

#: What an adapter hands back: the payload as it arrived, in whichever format
#: it arrived in. Both members answer ``validate()`` for themselves, and the
#: QR one answers ``to_task()``.
Arrived = Task | QRCodeTask

#: The top-level keys only the full format has. Derived from the shapes rather
#: than listed, so an adapter cannot recognize a key its shape does not read.
FULL_FORMAT_ONLY_KEYS = (
    TASK_SHAPE.keys - QR_TASK_SHAPE.keys - QR_WAYPOINTS_TASK_SHAPE.keys
)

#: The top-level keys only the QR format has, across both of its shapes.
QR_FORMAT_ONLY_KEYS = (
    QR_TASK_SHAPE.keys | QR_WAYPOINTS_TASK_SHAPE.keys
) - TASK_SHAPE.keys

#: Magic bytes for the image formats the QR adapter can read. This is the one
#: list of them: it is what the image adapter recognizes *and* what tells a
#: caller their PNG failed for want of a dependency rather than for being
#: unreadable. The two used to be separate lists that could disagree.
_IMAGE_MAGIC = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff")


def _looks_like_file_path(data: str) -> bool:
    """Return True if a string should be treated as a path to read.

    QR code URLs are excluded because they may contain path-like characters
    but are never files. Base64 in an XCTSKZ: payload routinely contains "/".
    """
    if data.startswith(_QR_SCHEMES):
        return False
    return "/" in data or "\\" in data or data.endswith(_FILE_EXTENSIONS)


def _read_file(path: str) -> tuple[bytes | None, str | None]:
    """Read a file path to bytes.

    Args:
        path: The path to read.

    Returns:
        ``(contents, None)`` on success, or ``(None, reason)`` where reason is
        the OS's own description. The reason is carried rather than discarded
        because a path that cannot be read still falls through to the inline
        adapters — ``_looks_like_file_path`` is a heuristic, and a JSON payload
        containing a "/" trips it — so the only place it can be reported is the
        error raised when everything else has also failed.
    """
    try:
        with open(path, "rb") as f:
            return f.read(), None
    except OSError as exc:
        return None, exc.strerror or str(exc)


#: What :attr:`Input.document` holds when the input is not JSON at all. A
#: sentinel rather than ``None``, because ``None`` is what a JSON ``null``
#: decodes to and the two are different answers.
_NOT_JSON = object()


@dataclass(frozen=True)
class Input:
    """The input as every adapter needs to see it, decoded once.

    One value rather than a ``(text, raw)`` pair: of the eight parameters the
    four adapters used to take, three were dead — ``raw`` in the two JSON
    adapters, ``text`` in the image one — because a uniform two-argument
    signature is a lowest common denominator, not an interface.

    Attributes:
        raw: The input bytes.
        text: The bytes decoded as UTF-8, or None if they are not UTF-8 (a
            binary image, say). Text-based adapters do not recognize such input.
        document: The text decoded as JSON, or :data:`_NOT_JSON`. Decoded here
            so recognition and reading share one decode; the two JSON adapters
            used to decode the same payload a second time each.
    """

    raw: bytes
    text: str | None
    document: Any

    @classmethod
    def of(cls, data: bytes | str) -> "Input":
        """Normalize a caller's bytes or string into one input value.

        Args:
            data: The payload as it was handed to :func:`parse_task`.

        Returns:
            The input, with its text and JSON decodings attempted once.
        """
        if isinstance(data, str):
            text: str | None = data
            raw = data.encode("utf-8")
        else:
            raw = bytes(data)
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = None

        document: Any = _NOT_JSON
        if text is not None:
            try:
                document = json.loads(text)
            except ValueError:
                document = _NOT_JSON

        return cls(raw=raw, text=text, document=document)

    @property
    def mapping(self) -> dict[str, Any] | None:
        """The input as a JSON object, or None if it is not one."""
        if isinstance(self.document, dict):
            return self.document
        return None

    @property
    def keys(self) -> frozenset[str]:
        """The top-level keys, if the input is a JSON object; empty otherwise."""
        mapping = self.mapping
        return frozenset(mapping) if mapping is not None else frozenset()

    @property
    def looks_like_json(self) -> bool:
        """Whether the input is JSON, or was trying to be.

        True for a document that decoded, and also for one that did not — a
        truncated payload starting with ``{`` parsed as far as being
        JSON-shaped, and saying so is more use than "invalid format".
        """
        return self.document is not _NOT_JSON or self.raw.lstrip()[:1] in (b"{", b"[")


@dataclass(frozen=True)
class FormatAdapter:
    """One input format: how to tell it apart, and how to read it.

    Attributes:
        name: The format, for the error a failed read raises.
        recognizes: Whether this input is this format. Cheap, total, and never
            the same question as "does it parse" — see the module docstring.
        read: The payload as it arrived. Called only when ``recognizes`` said
            yes, and free to raise :class:`~pyxctsk.InvalidFormatError` with the
            reason rather than returning None.
    """

    name: str
    recognizes: Callable[["Input"], bool]
    read: Callable[["Input"], Arrived]


def _qr_url_text(inp: Input) -> str | None:
    """Return the input as text if it carries either QR scheme, else None."""
    if inp.text is not None and inp.text.startswith(_QR_SCHEMES):
        return inp.text
    for scheme in _QR_SCHEMES:
        if inp.raw.startswith(scheme.encode("utf-8")):
            return inp.raw.decode("utf-8", errors="strict")
    return None


def _is_xctsk_url(inp: Input) -> bool:
    """Whether the input carries the ``XCTSK:`` or ``XCTSKZ:`` scheme."""
    return _qr_url_text(inp) is not None


def _read_xctsk_url(inp: Input) -> Arrived:
    """Read the compact ``XCTSK:`` and ``XCTSKZ:`` URL formats.

    Raises:
        InvalidFormatError: If the scheme is right but the payload is not.
    """
    url = _qr_url_text(inp)
    assert url is not None  # recognizes() said so
    try:
        return QRCodeTask.from_string(url)
    except _PARSE_ERRORS as exc:
        scheme = url.split(":", 1)[0]
        raise InvalidFormatError(
            f"recognized {scheme}: URL but its payload could not be parsed: {exc}"
        ) from exc


def _is_task_json(inp: Input) -> bool:
    """Whether the input is a JSON object carrying a full-format-only key."""
    return bool(inp.keys & FULL_FORMAT_ONLY_KEYS)


def _read_task_json(inp: Input) -> Arrived:
    """Read the full Task JSON format.

    Raises:
        InvalidFormatError: If the document is the full format but malformed.
    """
    document = inp.mapping
    assert document is not None  # recognizes() said so
    try:
        return Task.from_dict(document)
    except _PARSE_ERRORS as exc:
        raise InvalidFormatError(
            f"recognized the task JSON format but could not read it: {exc}"
        ) from exc


def _is_qrcode_json(inp: Input) -> bool:
    """Whether the input is a JSON object carrying a QR-format-only key."""
    return bool(inp.keys & QR_FORMAT_ONLY_KEYS)


def _read_qrcode_json(inp: Input) -> Arrived:
    """Read the QR-code Task JSON format (competition or XC/Waypoints shape).

    Raises:
        InvalidFormatError: If the document is the QR format but malformed.
    """
    document = inp.mapping
    assert document is not None  # recognizes() said so
    try:
        return QRCodeTask.from_dict(document)
    except _PARSE_ERRORS as exc:
        raise InvalidFormatError(
            f"recognized the QR JSON format but could not read it: {exc}"
        ) from exc


def _is_qrcode_image(inp: Input) -> bool:
    """Whether the input begins with the magic bytes of an image we can read.

    Answered without the optional dependencies, so a machine without them still
    tells a caller their PNG failed for want of an install.
    """
    return inp.raw.startswith(_IMAGE_MAGIC)


def _read_qrcode_image(inp: Input) -> Arrived:
    """Read an image carrying an ``XCTSK:`` QR code.

    Raises:
        InvalidFormatError: If QR image support is not installed, if the image
            cannot be opened, or if it carries no XCTSK code. Each of these
            used to be the same "invalid format", so a missing install was
            indistinguishable from a corrupt file.
    """
    if not QR_CODE_SUPPORT:
        raise InvalidFormatError(
            "looks like an image, but QR image support is not installed "
            f"(pip install '{QR_EXTRA_INSTALL}')"
        )
    try:
        image = Image.open(BytesIO(inp.raw))  # type: ignore
        qr_codes = zxingcpp.read_barcodes(  # type: ignore
            image,
            formats=zxingcpp.BarcodeFormat.QRCode,  # type: ignore
        )
    except Exception as exc:
        raise InvalidFormatError(
            f"looks like an image, but it could not be read: {exc}"
        ) from exc

    for qr_code in qr_codes:
        payload = qr_code.text
        if payload.startswith(_QR_SCHEMES):
            try:
                return QRCodeTask.from_string(payload)
            except _PARSE_ERRORS:
                continue
    raise InvalidFormatError("looks like an image, but it carries no XCTSK: QR code")


#: Ordered list of format adapters. At most one recognizes any given input, so
#: the order is a tie-break for a payload spelling keys from both formats, not
#: the thing keeping one adapter out of another's input. It used to be the
#: latter — see the module docstring.
FORMAT_ADAPTERS = (
    FormatAdapter("XCTSK: URL", _is_xctsk_url, _read_xctsk_url),
    FormatAdapter("task JSON", _is_task_json, _read_task_json),
    FormatAdapter("QR JSON", _is_qrcode_json, _read_qrcode_json),
    FormatAdapter("QR image", _is_qrcode_image, _read_qrcode_image),
)


def _unrecognized(inp: Input, path_error: str | None) -> InvalidFormatError:
    """Build the error for input no adapter recognized.

    Every failure used to raise ``InvalidFormatError("invalid format")`` — a
    missing file, a directory, truncated JSON, an unreadable QR image, and a
    perfectly good QR image on a machine without the optional dependencies all
    produced the identical message, so a missing install was indistinguishable
    from a corrupt file.

    The image cases now belong to the image adapter, which recognizes those
    bytes and says which of them it was. What is left here is what genuinely
    reached the end: a path that would not open, and JSON that is not a task.

    Args:
        inp: The input nothing recognized.
        path_error: Why the input failed to open as a path, if it looked like
            one and did not open.

    Returns:
        The error to raise.
    """
    if path_error is not None:
        return InvalidFormatError(f"could not read it as a file ({path_error})")
    if inp.looks_like_json:
        return InvalidFormatError("looks like JSON, but it is not a task in any format")
    return InvalidFormatError("invalid format")


def parse_task(data: bytes | str, strict: bool = False) -> Task:
    """Parse a XCTrack Task from a variety of input formats.

    Args:
        data: Input data as bytes, string, or file path.
        strict: If True, validate the payload *as it arrived* — through
            :meth:`Task.validate` for the full format or
            :meth:`QRCodeTask.validate` for the compact one — and reject
            anything that breaks the spec's structural rules. Off by default so
            that a malformed task can still be read, inspected and converted.

    Returns:
        Task: Parsed Task object.

    Raises:
        EmptyInputError: If input is empty.
        InvalidFormatError: If no adapter recognizes the input, or if the one
            that does cannot read it. The message names which failure it was —
            an unreadable path, an image with no QR code, an image with the
            optional QR dependencies missing, JSON that is not a task, or a
            recognized format whose payload is malformed.
        TaskValidationError: If ``strict`` and the task is structurally invalid.
    """
    if not data:
        raise EmptyInputError("empty input")

    # A string that names a readable file is replaced by its contents. A
    # failure here is not fatal — the heuristic also matches inline payloads —
    # so the reason is kept for the error at the end.
    path_error: str | None = None
    if isinstance(data, str) and _looks_like_file_path(data):
        file_data, path_error = _read_file(data)
        if file_data is not None:
            return parse_task(file_data, strict=strict)

    inp = Input.of(data)

    # Format detection: the adapter that recognizes the input reads it, and
    # says why if it cannot. Nothing falls through from here.
    for adapter in FORMAT_ADAPTERS:
        if adapter.recognizes(inp):
            arrived = adapter.read(inp)
            break
    else:
        raise _unrecognized(inp, path_error)

    # Validate what arrived, before converting it. Each format answers for
    # itself — Task.validate() and QRCodeTask.validate() both present a
    # TaskStructure to the same rules — so a violation is reported against the
    # payload rather than against the converter's inventions.
    if strict:
        issues = arrived.validate()
        if issues:
            raise TaskValidationError(issues)

    return arrived if isinstance(arrived, Task) else arrived.to_task()
