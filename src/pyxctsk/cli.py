"""pyxctsk Command Line Interface (CLI).

Tools for parsing, converting, and measuring XCTrack task files
(paragliding/hang gliding competitions).

Features:
- Parse XCTrack task files from file or stdin
- Convert tasks to JSON, KML, PNG QR code, or compact QR string
- Report the FAI S7F distances, including the route points another
  implementation needs to diff against
- Output to file or stdout
- Optional strict validation (--strict), off by default so a malformed task
  can still be read and converted

See project README for usage examples and supported formats.
"""

import json
import sys
from typing import BinaryIO

import click

from .distance.report import DistanceReport
from .exceptions import pyXCTSKError
from .metadata import pyxctsk_version
from .parser import parse_task
from .renderer import OUTPUT_FORMATS, render_task

_MAIN_HELP = """pyxctsk: Convert task files between formats.

\b
Examples:
  pyxctsk convert task.xctsk --format json
  pyxctsk convert task.xctsk --format kml -o task.kml
  pyxctsk convert --format png < task.xctsk > task.png
  pyxctsk convert task.xctsk --format qrcode-json -z
  pyxctsk convert task.xctsk --strict
  pyxctsk distances task.xctsk --format text

\b
Formats:
  Input:  .xctsk files, XCTSK:/XCTSKZ: URLs, QR code images (PNG)
  Output: JSON, GeoJSON, KML, QR codes (PNG or XCTSK:/XCTSKZ: URL)

See README for more examples and details.
"""

_CONVERT_HELP = """Convert an XCTrack task between supported formats.

The input may be a task file, an XCTSK:/XCTSKZ: string, a QR image, or stdin.
Parsing is lenient by default; --strict rejects structural spec violations.

\b
Examples:
  pyxctsk convert task.xctsk --format json
  pyxctsk convert task.xctsk --format geojson -o task.geojson
  pyxctsk convert task.xctsk --format qrcode-json -z
  pyxctsk convert --format png < task.xctsk > task.png
"""

_DISTANCES_HELP = """Report a task's FAI S7F distances and optimized route.

The JSON form is the machine-readable reference surface for comparing another
implementation. The text form includes the same values for a human reader.

\b
Examples:
  pyxctsk distances task.xctsk
  pyxctsk distances task.xctsk --format text
  pyxctsk distances task.xctsk -o distances.json
  pyxctsk distances < task.xctsk
"""


@click.group(help=_MAIN_HELP)
@click.version_option(
    version=pyxctsk_version(),
    prog_name="pyxctsk",
    message="%(prog)s %(version)s",
)
def main() -> None:
    """Register the pyxctsk command group."""


def _read_input(input_file: BinaryIO | None) -> bytes:
    """Read the task payload from a file argument or stdin.

    Args:
        input_file: A binary file object from click, or None for stdin.

    Returns:
        The raw payload.

    Raises:
        SystemExit: If no input was given and stdin is a terminal.
    """
    if input_file:
        data: bytes = input_file.read()
        return data
    if sys.stdin.isatty():
        click.echo(
            "Error: No input provided. Please provide an input file or pipe input.",
            err=True,
        )
        sys.exit(1)
    return sys.stdin.buffer.read()


def _write_output(output_file: str | None, payload: str | bytes) -> None:
    """Write the converted payload to a file or stdout.

    The one place that knows output is UTF-8. None of the four write blocks
    this replaces passed ``encoding=``, so they used the locale's — while the
    data is UTF-8 and the KML even declares ``encoding="UTF-8"``. On a
    non-UTF-8 locale that raised (the text distance report contains ``§``, so
    it failed for every task); on Windows, whose default is cp1252, it wrote a
    mis-encoded file and said nothing.

    It is also the one place that knows a text file ends with a newline, which
    ``convert`` and ``distances`` had answered differently by accident, and
    that a PNG goes to ``sys.stdout.buffer`` rather than through ``click.echo``.

    Args:
        output_file: Path to write to, or None for stdout.
        payload: Text to write, or bytes for a binary format.
    """
    if isinstance(payload, bytes):
        if output_file:
            with open(output_file, "wb") as f:
                f.write(payload)
        else:
            sys.stdout.buffer.write(payload)
        return

    if output_file:
        with open(output_file, "w", encoding="utf-8", newline="\n") as f:
            f.write(payload if payload.endswith("\n") else payload + "\n")
    else:
        click.echo(payload)


@main.command(help=_CONVERT_HELP)
@click.argument("input_file", type=click.File("rb"), required=False)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(list(OUTPUT_FORMATS)),
    default="json",
    help="Output format",
)
@click.option(
    "--output",
    "-o",
    "output_file",
    type=click.Path(),
    help="Output file (default: stdout)",
)
@click.option(
    "--compressed",
    "-z",
    is_flag=True,
    default=False,
    help="Emit the XCTSKZ: (zlib+base64) QR encoding; png and qrcode-json only",
)
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    help="Reject a task that breaks the spec's structural rules",
)
def convert(
    input_file: BinaryIO | None,
    output_format: str,
    output_file: str | None,
    compressed: bool,
    strict: bool,
) -> None:
    """Convert XCTrack task files between supported formats.

    Reads an XCTrack task from a file or stdin, parses it, and outputs the
    converted result in the specified format (JSON, KML, PNG QR code, or compact
    QR string) to a file or stdout. Both XCTSK: and XCTSKZ: inputs are accepted
    regardless of this flag.

    Args:
        input_file (file or None): Input file object opened in binary mode, or None to read from stdin.
        output_format (str): Output format ('json', 'kml', 'png', or 'qrcode-json').
        output_file (str): Output file path, or None to write to stdout.
        compressed (bool): Emit the XCTSKZ: encoding for QR output formats.
        strict (bool): Reject a structurally invalid task instead of converting
            it. Off by default, matching the library: reading is lenient so a
            malformed task can still be inspected and converted.

    Returns:
        None

    Raises:
        SystemExit: If input is missing or an error occurs during parsing or conversion.
    """
    try:
        task = parse_task(_read_input(input_file), strict=strict)
        _write_output(output_file, render_task(task, output_format, compressed))
    except (pyXCTSKError, OSError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command(help=_DISTANCES_HELP)
@click.argument("input_file", type=click.File("rb"), required=False)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "text"]),
    default="json",
    help="Output format",
)
@click.option(
    "--output",
    "-o",
    "output_file",
    type=click.Path(),
    help="Output file (default: stdout)",
)
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    help="Reject a task that breaks the spec's structural rules",
)
def distances(
    input_file: BinaryIO | None,
    output_format: str,
    output_file: str | None,
    strict: bool,
) -> None:
    """Report a task's FAI S7F distances, with the route that produced them.

    pyxctsk aims to be a reference implementation of the S7F distance
    calculations, so this is the command another implementation should diff
    against. It reports §7.2's two distances, the task-board "distance through
    centres" that S7F does *not* define — with every reading of it — and the
    optimized crossing point for each turnpoint.

    Args:
        input_file (file or None): Input file object opened in binary mode, or
            None to read from stdin.
        output_format (str): 'json' for a machine-readable report, 'text' for a
            human-readable one.
        output_file (str): Output file path, or None to write to stdout.
        strict (bool): Reject a structurally invalid task instead of measuring
            it.

    Returns:
        None

    Raises:
        SystemExit: If input is missing, the task cannot be parsed, or it has
            too few turnpoints to have a distance at all. All three are
            ``pyXCTSKError`` — this command used to name the last one
            separately, because it descended from ``ValueError`` alone.
    """
    try:
        input_data = _read_input(input_file)

        report = DistanceReport.from_task(parse_task(input_data, strict=strict))
        _write_output(
            output_file,
            json.dumps(report.as_dict(), indent=2)
            if output_format == "json"
            else report.as_text(),
        )

    except (pyXCTSKError, OSError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
