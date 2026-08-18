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
from importlib.metadata import PackageNotFoundError, version
from io import BytesIO

import click

from .distance import (
    PROPOSED_READING,
    MeasuredTask,
    SpeedSection,
    center_distance,
    center_distance_readings,
)
from .export.kml import task_to_kml
from .parser import parse_task
from .qrcode.image import generate_qrcode_image

#: The S7F edition the distance calculations are audited against.
S7F_EDITION = "2026 V1.0"


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


def _pyxctsk_version() -> str:
    """Return the installed version, or "unknown" when running from a checkout."""
    try:
        return version("pyxctsk")
    except PackageNotFoundError:  # pragma: no cover - editable/source runs
        return "unknown"


def _distance_report(task) -> dict:
    """Build the S7F distance report for a task.

    Every number is labelled with the section that defines it, and the route
    points are included because a total only says two implementations disagree
    — the crossing coordinates say why. See ``docs/s7f-distance-reference.md``.

    Args:
        task: The parsed task to measure.

    Returns:
        A JSON-serializable report.
    """
    measured = MeasuredTask.from_task(task)
    cumulative = measured.cumulative_m()
    speed_section = SpeedSection.from_measured_task(measured)

    return {
        "pyxctsk_version": _pyxctsk_version(),
        "s7f_edition": S7F_EDITION,
        "earth_model": (
            task.earth_model.value if task.earth_model else "WGS84 (default)"
        ),
        "task_distance_m": measured.total_m,
        "speed_section_distance_m": (
            speed_section.distance_m if speed_section else None
        ),
        "speed_section_to_ess_m": (speed_section.to_ess_m if speed_section else None),
        "speed_section_pre_start_m": (
            speed_section.pre_start_m if speed_section else None
        ),
        "center_distance_m": center_distance(task),
        "center_distance_reading": PROPOSED_READING.value,
        "center_distance_readings_m": center_distance_readings(task),
        "route": [
            {
                "index": i,
                "name": tp.waypoint.name,
                "type": tp.type.value if tp.type else "",
                "radius_m": tp.radius,
                "center_lat": tp.waypoint.lat,
                "center_lon": tp.waypoint.lon,
                "route_lat": point[0],
                "route_lon": point[1],
                "cumulative_m": cumulative[i],
            }
            for i, (tp, point) in enumerate(zip(task.turnpoints, measured.route.points))
        ],
        "notes": {
            "task_distance_m": "FAI S7F 2026 §7.2, optimized launch to goal",
            "speed_section_distance_m": (
                "FAI S7F 2026 §7.2, a separate launch-to-ESS optimization minus "
                "its pre-start portion; null when the task has no SSS/ESS pair"
            ),
            "center_distance_m": (
                "NOT DEFINED BY S7F. A task-board convention; this is the "
                "reading pyxctsk proposes. See center_distance_readings_m for "
                "the alternatives and docs/s7f-distance-reference.md for why "
                "they differ by up to 39.9 km"
            ),
            "route": (
                "The optimized crossing point per turnpoint. Exchange these "
                "rather than totals: a total says two implementations disagree, "
                "these say where"
            ),
        },
    }


def _format_report_text(report: dict) -> str:
    """Render the report for a human rather than a diff.

    Args:
        report: The report from :func:`_distance_report`.

    Returns:
        A plain-text rendering.
    """
    lines = [
        f"pyxctsk {report['pyxctsk_version']}  |  FAI S7F {report['s7f_edition']}"
        f"  |  earth model: {report['earth_model']}",
        "",
        f"  task distance (§7.2)        {report['task_distance_m'] / 1000:10.3f} km",
    ]
    if report["speed_section_distance_m"] is None:
        lines.append("  speed section (§7.2)              no SSS/ESS pair")
    else:
        lines.append(
            f"  speed section (§7.2)        "
            f"{report['speed_section_distance_m'] / 1000:10.3f} km"
        )
    lines += [
        f"  through centres             {report['center_distance_m'] / 1000:10.3f} km"
        f"   [{report['center_distance_reading']}]",
        "",
        "  'through centres' is NOT defined by S7F. Other readings of it:",
    ]
    for name, value in report["center_distance_readings_m"].items():
        shown = f"{value / 1000:10.3f} km" if value is not None else "       n/a"
        lines.append(f"    {name:26s} {shown}")
    lines += ["", "  optimized route:"]
    for point in report["route"]:
        lines.append(
            f"    {point['index']:2d} {point['name']:<10s} {point['type']:<8s}"
            f" r={point['radius_m']:>6d} m"
            f"  {point['route_lat']:>10.6f} {point['route_lon']:>11.6f}"
            f"  {point['cumulative_m'] / 1000:8.3f} km"
        )
    return "\n".join(lines)


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

        task = parse_task(input_data, strict=strict)
        if len(task.turnpoints) < 2:
            click.echo(
                "Error: a task needs at least two turnpoints to have a distance.",
                err=True,
            )
            sys.exit(1)

        report = _distance_report(task)
        output = (
            json.dumps(report, indent=2)
            if output_format == "json"
            else _format_report_text(report)
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
