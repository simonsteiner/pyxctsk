"""Tests for the `pyxctsk distances` command: the S7F report as the CLI writes it."""

import json

import pytest
from click.testing import CliRunner

from pyxctsk import (
    DistanceReport,
    TurnpointType,
    parse_task,
)
from pyxctsk.cli import convert, distances, main
from tests.builders import TAKEOFF_ONLY_TASK, task, turnpoint
from tests.corpus import reference_task


class TestCLIDistances:
    """The command wiring: it renders `DistanceReport` and writes it out.

    What the report *says* is asserted on the value, in
    `tests/distance/test_report.py`. These cover only what the command adds —
    the two output formats, stdin, and the exit code for a task with no
    distance to report.
    """

    def _report(self, *options: str, stem: str = "task_pepi") -> dict:
        """Run ``distances`` over a reference task and parse its JSON."""
        result = CliRunner().invoke(
            distances, [str(reference_task(stem).xctsk_path), *options]
        )
        assert result.exit_code == 0, result.output
        report: dict = json.loads(result.output)
        return report

    def test_the_json_output_is_the_reports_dict(self):
        """The command renders the value rather than assembling its own."""
        task = reference_task("task_pepi").task

        assert self._report() == DistanceReport.from_task(task).as_dict()

    def test_the_text_output_is_the_reports_text(self):
        """Same value, the other rendering."""
        result = CliRunner().invoke(
            distances,
            [str(reference_task("task_pepi").xctsk_path), "--format", "text"],
        )

        assert result.exit_code == 0
        assert result.output.rstrip("\n") == (
            DistanceReport.from_task(reference_task("task_pepi").task).as_text()
        )

    def test_the_text_format_is_for_humans(self):
        """Same numbers, and the same disclaimer."""
        result = CliRunner().invoke(
            distances,
            [str(reference_task("task_pepi").xctsk_path), "--format", "text"],
        )

        assert result.exit_code == 0
        assert "92.002 km" in result.output
        assert "NOT defined by S7F" in result.output
        assert "optimized route:" in result.output

    def test_a_task_with_no_distance_exits_nonzero_and_says_why(self):
        """One turnpoint has no leg; the report refuses and the CLI reports it."""
        payload = TAKEOFF_ONLY_TASK.to_json().encode()

        result = CliRunner().invoke(distances, input=payload)

        assert result.exit_code == 1
        assert "at least two turnpoints" in result.output

    def test_it_reads_stdin(self):
        """So it composes with whatever produced the task."""
        payload = reference_task("task_bevo").xctsk_path.read_bytes()

        result = CliRunner().invoke(distances, input=payload)

        assert result.exit_code == 0
        assert json.loads(result.output)["task_distance_m"] == pytest.approx(
            94028.3, abs=1.0
        )

    def test_it_writes_to_a_file(self, tmp_path):
        """For piping a corpus through it."""
        out = tmp_path / "distances.json"

        result = CliRunner().invoke(
            distances, [str(reference_task("task_bevo").xctsk_path), "-o", str(out)]
        )

        assert result.exit_code == 0
        assert json.loads(out.read_text())["task_distance_m"] > 0

    def test_a_task_too_short_to_measure_is_an_error(self):
        """One turnpoint is a point, not a distance."""
        result = CliRunner().invoke(
            distances, input=task(turnpoint("Only", 46.0, 8.0)).to_json().encode()
        )

        assert result.exit_code == 1
        assert "at least two turnpoints" in result.output

    @pytest.mark.parametrize(
        ("command", "options"),
        [
            (distances, []),
            (distances, ["--format", "text"]),
            (convert, ["--format", "kml"]),
            (convert, ["--format", "geojson"]),
        ],
    )
    def test_a_task_the_plane_cannot_hold_is_an_error(self, command, options):
        """Two points half the globe apart: reported, not an AssertionError."""
        payload = task(
            turnpoint("A", 0.0, 0.0, radius=0, type=TurnpointType.SSS),
            turnpoint("B", 0.0, 180.0, radius=0, type=TurnpointType.ESS),
        ).to_json()

        result = CliRunner().invoke(command, options, input=payload.encode())

        assert result.exit_code == 1
        assert not isinstance(result.exception, AssertionError)
        assert "Error:" in result.output
        assert "Transverse Mercator" in result.output

    @pytest.mark.parametrize(
        ("command", "options"),
        [
            (distances, []),
            (distances, ["--format", "text"]),
            (convert, ["--format", "kml"]),
            (convert, ["--format", "geojson"]),
        ],
    )
    def test_a_cylinder_past_the_far_side_is_an_error(self, command, options):
        """A 10^300 m goal: reported, not measured as 2 941 637 m with exit 0."""
        payload = task(
            turnpoint("A", 46.0, 8.0, radius=400),
            turnpoint("B", 46.1, 8.0, radius=10**300),
        ).to_json()

        result = CliRunner().invoke(command, options, input=payload.encode())

        assert result.exit_code == 1
        assert "Error:" in result.output
        assert "far side of the earth" in result.output

    @pytest.mark.parametrize(
        ("command", "options"),
        [
            (distances, []),
            (distances, ["--format", "text"]),
            (convert, ["--format", "kml"]),
            (convert, ["--format", "geojson"]),
        ],
    )
    def test_a_negative_radius_is_named_not_blamed_on_the_route(self, command, options):
        """S9: it said "route point 0 is 11.0 m outside turnpoint 0's cylinder"."""
        payload = task(
            turnpoint("A", 46.0, 8.0, radius=-11, type=TurnpointType.TAKEOFF),
            turnpoint("B", 46.1, 8.0, radius=400),
        ).to_json()

        result = CliRunner().invoke(command, options, input=payload.encode())

        assert result.exit_code == 1
        assert "Error: turnpoint 0 has a negative radius (-11)" in result.output

    def test_a_negative_radius_still_converts_to_the_formats_that_carry_it(self):
        """Reading stays lenient: only measuring the cylinder refuses it."""
        payload = task(
            turnpoint("A", 46.0, 8.0, radius=-11, type=TurnpointType.TAKEOFF),
            turnpoint("B", 46.1, 8.0, radius=400),
        ).to_json()

        result = CliRunner().invoke(convert, [], input=payload.encode())

        assert result.exit_code == 0, result.output
        assert parse_task(result.output).turnpoints[0].radius == -11

    def test_input_that_cannot_be_parsed_is_an_error(self):
        """Not a traceback."""
        result = CliRunner().invoke(distances, input=b"not a task")

        assert result.exit_code == 1
        assert "Error:" in result.output

    def test_the_command_is_documented(self):
        """A command the help does not mention is one nobody finds."""
        top = CliRunner().invoke(main, ["--help"])
        own = CliRunner().invoke(main, ["distances", "--help"])

        assert "distances" in top.output
        assert "--format" in own.output and "--strict" in own.output
