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
from io import BytesIO

import click

from .distance.report import DistanceReport
from .export.kml import task_to_kml
from .parser import parse_task
from .qrcode.image import generate_qrcode_image


@click.group()
def main():
    r"""pyxctsk: Convert task files between formats.

    \b
    Parameter Options:
      --format [json|kml|png|qrcode-json]  Output format (default: json)
      --output, -o FILE                    Output file (default: stdout)
      --compressed, -z                     Emit XCTSKZ: instead of XCTSK:
      --strict                             Reject a structurally invalid task
      INPUT_FILE                           Input file (optional, uses stdin)

    \b
    Examples:
      pyxctsk convert task.xctsk --format json
      pyxctsk convert task.xctsk --format kml -o task.kml
      pyxctsk convert --format png < task.xctsk > task.png
      pyxctsk convert task.xctsk --format qrcode-json
      pyxctsk convert task.xctsk --format qrcode-json -z
      pyxctsk convert task.xctsk --strict
      pyxctsk distances task.xctsk
      pyxctsk distances task.xctsk --format text

    \b
    Formats:
      Input:  .xctsk files, XCTSK:/XCTSKZ: URLs, QR code images (PNG)
      Output: JSON, KML, QR codes (PNG or XCTSK:/XCTSKZ: URL)

    See README for more examples and details.
    """


@main.command()
@click.argument("input_file", type=click.File("rb"), required=False)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "kml", "png", "qrcode-json"]),
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
    input_file, output_format: str, output_file: str, compressed: bool, strict: bool
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
        # Read input data
        if input_file:
            input_data = input_file.read()
        else:
            if sys.stdin.isatty():
                click.echo(
                    "Error: No input provided. Please provide an input file or pipe input.",
                    err=True,
                )
                sys.exit(1)
            input_data = sys.stdin.buffer.read()

        # Parse the task
        task = parse_task(input_data, strict=strict)

        # Convert to requested format
        if output_format == "json":
            output = task.to_json()
            if output_file:
                with open(output_file, "w") as f:
                    f.write(output)
            else:
                click.echo(output)

        elif output_format == "kml":
            output = task_to_kml(task)
            if output_file:
                with open(output_file, "w") as f:
                    f.write(output)
            else:
                click.echo(output)

        elif output_format == "png":
            qr_task = task.to_qr_code_task()
            qr_string = qr_task.to_string(compressed=compressed)
            qr_image = generate_qrcode_image(qr_string, size=1024)

            if output_file:
                qr_image.save(output_file, format="PNG")
            else:
                # Write PNG to stdout
                buffer = BytesIO()
                qr_image.save(buffer, format="PNG")
                sys.stdout.buffer.write(buffer.getvalue())

        elif output_format == "qrcode-json":
            qr_task = task.to_qr_code_task()
            qr_string = qr_task.to_string(compressed=compressed)
            if output_file:
                with open(output_file, "w") as f:
                    f.write(qr_string)
            else:
                click.echo(qr_string)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
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
def distances(input_file, output_format: str, output_file: str, strict: bool) -> None:
    r"""Report a task's FAI S7F distances, with the route that produced them.

    pyxctsk aims to be a reference implementation of the S7F distance
    calculations, so this is the command another implementation should diff
    against. It reports §7.2's two distances, the task-board "distance through
    centres" that S7F does *not* define — with every reading of it — and the
    optimized crossing point for each turnpoint.

    \b
    Examples:
      pyxctsk distances task.xctsk
      pyxctsk distances task.xctsk --format text
      pyxctsk distances task.xctsk -o distances.json
      pyxctsk distances < task.xctsk

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
            too few turnpoints to have a distance at all.
    """
    try:
        if input_file:
            input_data = input_file.read()
        else:
            if sys.stdin.isatty():
                click.echo(
                    "Error: No input provided. Please provide an input file or pipe input.",
                    err=True,
                )
                sys.exit(1)
            input_data = sys.stdin.buffer.read()

        report = DistanceReport.from_task(parse_task(input_data, strict=strict))
        output = (
            json.dumps(report.as_dict(), indent=2)
            if output_format == "json"
            else report.as_text()
        )

        if output_file:
            with open(output_file, "w") as f:
                f.write(output + "\n")
        else:
            click.echo(output)

    except SystemExit:
        raise
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
