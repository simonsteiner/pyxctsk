"""Writing a task out, in each format this library can write.

The counterpart to :func:`~pyxctsk.parser.parse_task`. Reading was one deep
module — a caller learns one name and hands it anything — while writing was
five spellings and no module:

    task.to_json()
    task_to_kml(task)
    generate_task_geojson(task)
    task.to_qr_code_task().to_string(compressed=…)
    generate_qrcode_image(task.to_qr_code_task().to_string()).save(buf, "PNG")

The mapping *format name → renderer* existed in exactly one place, an
``if/elif`` chain inside ``cli.py`` with no ``else``, so an unmatched format
wrote nothing and exited 0 — prevented only by ``click.Choice`` listing the
same four names a second time. And because the chain was in the command layer,
the second consumer re-derived it: ``scripts/task_viewer`` spells out the
six-line PNG incantation and carries its own media types.

:data:`OUTPUT_FORMATS` is that mapping as a table, so a format is one row
rather than a ``click.Choice`` entry plus a branch plus whatever each other
caller does. Each row carries what a caller has to know to *deliver* the bytes
as well as make them — the media type, the file extension, and whether the
payload is text or binary — because those were spelled at each site too, and
``pyxctsk.EXTENSION`` and ``pyxctsk.MIME_TYPE`` were exported for the job and
read by nothing.

``export/common.py`` argues the policy this follows, for the palette: "spelled
out rather than defaulted… a lookup with a default is what the old KML writer
had, and it meant a palette entry it did not know about rendered as an ordinary
turnpoint with nothing failing". An unknown format name is a ``ValueError``
naming the ones that exist.
"""

from dataclasses import dataclass
from io import BytesIO
from typing import Callable

from .export.geojson import generate_task_geojson
from .export.kml import task_to_kml
from .model.task import Task
from .qrcode.image import generate_qrcode_image

#: Pixel size of the QR image ``png`` renders. The CLI's own number, kept here
#: with the row that uses it.
QR_IMAGE_SIZE = 1024


def _render_json(task: Task, compressed: bool) -> str:
    """The full task format — the ``.xctsk`` file itself."""
    return task.to_json()


def _render_kml(task: Task, compressed: bool) -> str:
    """A map of the task, cylinders and optimized route included."""
    return task_to_kml(task)


def _render_geojson(task: Task, compressed: bool) -> str:
    """The same map as a GeoJSON FeatureCollection."""
    import json

    return json.dumps(generate_task_geojson(task))


def _qr_string(task: Task, compressed: bool) -> str:
    """The compact payload both QR formats carry."""
    return task.to_qr_code_task().to_string(compressed=compressed)


def _render_png(task: Task, compressed: bool) -> bytes:
    """The QR payload as a scannable image.

    Six lines at each of the two call sites that wanted one, including the
    ``BytesIO`` dance, which is the whole reason this table exists.
    """
    buffer = BytesIO()
    generate_qrcode_image(_qr_string(task, compressed), size=QR_IMAGE_SIZE).save(
        buffer, format="PNG"
    )
    return buffer.getvalue()


@dataclass(frozen=True)
class OutputFormat:
    """One way a task can be written out.

    Attributes:
        name: What a caller asks for, and the key in :data:`OUTPUT_FORMATS`.
        media_type: The MIME type to serve it as.
        extension: The file extension to save it under, leading dot included.
        binary: True when :attr:`render` returns bytes rather than text. The
            one fact a caller needs before it can open a file or set a header,
            and the one every call site used to infer from the format name.
        render: The task and the ``compressed`` flag to the payload. The flag
            is accepted by every row and read by the two QR ones, so a caller
            passes it without asking which formats care.
    """

    name: str
    media_type: str
    extension: str
    binary: bool
    render: Callable[[Task, bool], str | bytes]


#: Every format this library writes, in the order the CLI offers them.
OUTPUT_FORMATS: dict[str, OutputFormat] = {
    fmt.name: fmt
    for fmt in (
        OutputFormat("json", "application/xctsk", ".xctsk", False, _render_json),
        OutputFormat(
            "kml", "application/vnd.google-earth.kml+xml", ".kml", False, _render_kml
        ),
        OutputFormat(
            "geojson", "application/geo+json", ".geojson", False, _render_geojson
        ),
        OutputFormat("png", "image/png", ".png", True, _render_png),
        OutputFormat("qrcode-json", "text/plain", ".txt", False, _qr_string),
    )
}


def render_task(
    task: Task, output_format: str, compressed: bool = False
) -> str | bytes:
    """Write a task out in one of the formats this library can write.

    Args:
        task: The task to render.
        output_format: One of :data:`OUTPUT_FORMATS`.
        compressed: Emit the ``XCTSKZ:`` (zlib+base64) QR encoding rather than
            ``XCTSK:``. Read by the ``png`` and ``qrcode-json`` formats and
            ignored by the rest, so a caller need not know which is which.

    Returns:
        The payload — ``bytes`` for a binary format, ``str`` otherwise. Ask
        ``OUTPUT_FORMATS[output_format].binary`` rather than guessing.

    Raises:
        ValueError: If no such format exists. It used to be a chain of ``elif``
            with no ``else``, which wrote nothing and reported success.
    """
    try:
        fmt = OUTPUT_FORMATS[output_format]
    except KeyError:
        raise ValueError(
            f"not an output format: {output_format!r} "
            f"(expected one of {sorted(OUTPUT_FORMATS)})"
        ) from None
    return fmt.render(task, compressed)
