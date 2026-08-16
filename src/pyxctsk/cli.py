"""pyxctsk Command Line Interface (CLI).

Tools for parsing, converting, and visualizing XCTrack task files (paragliding/hang gliding competitions).

Features:
- Parse XCTrack task files from file or stdin
- Convert tasks to JSON, KML, PNG QR code, or compact QR string
- Output to file or stdout
- Strict error handling and clear messaging

See project README for usage examples and supported formats.
"""

import sys
from io import BytesIO

import click

from .kml import task_to_kml
from .parser import parse_task
from .qrcode_image import generate_qrcode_image


@click.group()
def main():
    r"""pyxctsk: Convert task files between formats with strict error handling.

    \b
    Parameter Options:
      --format [json|kml|png|qrcode-json]  Output format (default: json)
      --output, -o FILE                    Output file (default: stdout)
      --compressed, -z                     Emit XCTSKZ: instead of XCTSK:
      INPUT_FILE                           Input file (optional, uses stdin)

    \b
    Examples:
      pyxctsk convert task.xctsk --format json
      pyxctsk convert task.xctsk --format kml -o task.kml
      pyxctsk convert --format png < task.xctsk > task.png
      pyxctsk convert task.xctsk --format qrcode-json
      pyxctsk convert task.xctsk --format qrcode-json -z

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
def convert(input_file, output_format: str, output_file: str, compressed: bool) -> None:
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
        task = parse_task(input_data)

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


if __name__ == "__main__":
    main()
