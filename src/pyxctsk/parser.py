"""Parser for XCTrack Task.

Parse, load, and convert XCTrack task data from various formats.
Handles optional QR code dependencies.

Supports:
- JSON string/bytes with task data
- XCTSK: URL string/bytes (compact QR code format)
- Image bytes containing a QR code (if QR code dependencies are available)
- File path (str) to any of the above (auto-detected)

The auto-detection works by trying an ordered list of focused format
adapters (one per supported format). Each adapter answers two questions
independently: does the input *look like* my format, and can I parse it?
This keeps every format's recognition and parsing logic in one place and
makes each adapter testable in isolation.

Functions:
    parse_task(data: bytes | str) -> Task: Auto-detect and parse task from supported formats.
"""

import json
from io import BytesIO

from .exceptions import EmptyInputError, InvalidFormatError, TaskValidationError
from .model.task import Task
from .qrcode.task import QR_CODE_SCHEME, QR_CODE_SCHEME_COMPRESSED, QRCodeTask

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
_PARSE_ERRORS = (json.JSONDecodeError, ValueError, KeyError, UnicodeDecodeError)

#: What an adapter hands back: the payload as it arrived, in whichever format
#: it arrived in. Both members answer ``validate()`` for themselves, and the
#: QR one answers ``to_task()``.
Arrived = Task | QRCodeTask


def _looks_like_file_path(data: str) -> bool:
    """Return True if a string should be treated as a path to read.

    QR code URLs are excluded because they may contain path-like characters
    but are never files. Base64 in an XCTSKZ: payload routinely contains "/".
    """
    if data.startswith(_QR_SCHEMES):
        return False
    return "/" in data or "\\" in data or data.endswith(_FILE_EXTENSIONS)


def _read_file(path: str) -> bytes | None:
    """Read a file path to bytes, or return None if it cannot be read."""
    try:
        with open(path, "rb") as f:
            return f.read()
    except (FileNotFoundError, IsADirectoryError, PermissionError, OSError):
        return None


def _qr_url_text(text: str | None, raw: bytes) -> str | None:
    """Return the input as text if it carries either QR scheme, else None."""
    if text is not None and text.startswith(_QR_SCHEMES):
        return text
    for scheme in _QR_SCHEMES:
        if raw.startswith(scheme.encode("utf-8")):
            return raw.decode("utf-8", errors="strict")
    return None


def _parse_xctsk_url(text: str | None, raw: bytes) -> "Arrived | None":
    """Parse the compact ``XCTSK:`` and ``XCTSKZ:`` URL formats.

    A string carrying either prefix can only be this format, so a malformed
    payload raises a descriptive error rather than silently falling through
    to other adapters.
    """
    url = _qr_url_text(text, raw)
    if url is None:
        return None

    try:
        return QRCodeTask.from_string(url)
    except _PARSE_ERRORS as exc:
        scheme = url.split(":", 1)[0]
        raise InvalidFormatError(
            f"recognized {scheme}: URL but its payload could not be parsed: {exc}"
        ) from exc


def _parse_task_json(text: str | None, raw: bytes) -> "Arrived | None":
    """Parse the full Task JSON format."""
    if text is None:
        return None
    try:
        return Task.from_json(text)
    except _PARSE_ERRORS:
        return None


def _parse_qrcode_json(text: str | None, raw: bytes) -> "Arrived | None":
    """Parse the QR-code Task JSON format (full or simplified waypoints)."""
    if text is None:
        return None
    try:
        return QRCodeTask.from_json(text)
    except _PARSE_ERRORS:
        return None


def _parse_qrcode_image(text: str | None, raw: bytes) -> "Arrived | None":
    """Parse an image containing a ``XCTSK:`` QR code, if support is available."""
    if not QR_CODE_SUPPORT:
        return None
    try:
        image = Image.open(BytesIO(raw))  # type: ignore
        qr_codes = zxingcpp.read_barcodes(  # type: ignore
            image,
            formats=zxingcpp.BarcodeFormat.QRCode,  # type: ignore
        )
    except Exception:
        return None

    for qr_code in qr_codes:
        payload = qr_code.text
        if payload.startswith(_QR_SCHEMES):
            try:
                return QRCodeTask.from_string(payload)
            except _PARSE_ERRORS:
                continue
    return None


# Ordered list of format adapters. Each takes (decoded_text_or_None, raw_bytes)
# and returns *what arrived* — a Task or a QRCodeTask — if it can parse the
# input, None if the input is not its format. Order matters: more specific /
# cheaper formats come first.
#
# Returning the arrived payload rather than a Task is what makes strict=True
# honest. Three of these four formats are the compact one, and converting
# inside the adapter left nothing to check but the conversion: a QR payload
# declaring version 99 became a Task with version 1, a CLASSIC task type and
# a CYLINDER goal it never carried, so `parse_task(payload, strict=True)`
# accepted it and could not report UNKNOWN_VERSION for any QR input at all.
# See model/validation.py, whose TaskStructure split exists for this.
_FORMAT_PARSERS = (
    _parse_xctsk_url,
    _parse_task_json,
    _parse_qrcode_json,
    _parse_qrcode_image,
)


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
        InvalidFormatError: If input format is invalid or cannot be parsed.
        TaskValidationError: If ``strict`` and the task is structurally invalid.
    """
    if not data:
        raise EmptyInputError("empty input")

    # A string that names a readable file is replaced by its contents.
    if isinstance(data, str) and _looks_like_file_path(data):
        file_data = _read_file(data)
        if file_data is not None:
            return parse_task(file_data, strict=strict)

    # Normalize to (decoded text, raw bytes). text is None when the bytes are
    # not valid UTF-8 (e.g. a binary image); text-based adapters then skip.
    if isinstance(data, str):
        text: str | None = data
        raw = data.encode("utf-8")
    else:
        raw = bytes(data)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = None

    # Format detection: the first adapter that recognizes the input wins.
    for parser in _FORMAT_PARSERS:
        arrived = parser(text, raw)
        if arrived is not None:
            break
    else:
        raise InvalidFormatError("invalid format")

    # Validate what arrived, before converting it. Each format answers for
    # itself — Task.validate() and QRCodeTask.validate() both present a
    # TaskStructure to the same rules — so a violation is reported against the
    # payload rather than against the converter's inventions.
    if strict:
        issues = arrived.validate()
        if issues:
            raise TaskValidationError(issues)

    return arrived if isinstance(arrived, Task) else arrived.to_task()
