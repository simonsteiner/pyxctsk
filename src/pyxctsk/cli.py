"""Command line interface for pyxctsk."""

import sys
from io import BytesIO

import click

from .parser import parse_task
from .utils import generate_qr_code, task_to_kml


@click.group()
def main():
    """pyxctsk XCTrack task analysis tools."""
    pass


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
def convert(input_file, output_format: str, output_file: str) -> None:
    """Convert XCTrack task formats."""
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
            qr_string = qr_task.to_string()
            qr_image = generate_qr_code(qr_string, size=1024)

            if output_file:
                qr_image.save(output_file, format="PNG")
            else:
                # Write PNG to stdout
                buffer = BytesIO()
                qr_image.save(buffer, format="PNG")
                sys.stdout.buffer.write(buffer.getvalue())

        elif output_format == "qrcode-json":
            qr_task = task.to_qr_code_task()
            qr_string = qr_task.to_string()
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
