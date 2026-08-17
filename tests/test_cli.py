"""Tests for the `pyxctsk` command-line interface.

The CLI is the library's other public surface: every output format it offers
(json, kml, png, qrcode-json), reading from a file or from stdin, and what it
does with input it cannot parse.
"""

import json

import pytest
from click.testing import CliRunner

from pyxctsk import TurnpointType
from pyxctsk.cli import convert, main
from tests.builders import task, turnpoint
from tests.qr_test_utils import QR_CODE_SUPPORT, Image, decode_qr

#: One turnpoint at a known position, so every format test converts the same
#: task and differs only in what it asks the CLI to write.
SAMPLE = task(turnpoint("Test", 46.5, 8.0, radius=1000, type=TurnpointType.TAKEOFF))


def convert_stdin(*options: str):
    """Run ``convert`` over SAMPLE on stdin, returning the click result."""
    return CliRunner().invoke(convert, list(options), input=SAMPLE.to_json().encode())


class TestCLIConvert:
    """Every output format the CLI offers, over one task."""

    def test_json_output_is_the_task(self):
        """The default format round-trips the task through the CLI."""
        result = convert_stdin("--format", "json")

        assert result.exit_code == 0
        emitted = json.loads(
            next(line for line in result.output.splitlines() if line.startswith("{"))
        )
        assert emitted["taskType"] == "CLASSIC"
        assert emitted["turnpoints"][0]["waypoint"]["name"] == "Test"

    def test_kml_output_draws_the_turnpoint(self):
        """KML carries the turnpoint at the task altitude."""
        result = convert_stdin("--format", "kml")

        assert result.exit_code == 0
        assert "<?xml version=" in result.output
        assert "<kml xmlns=" in result.output
        # It used to be asserted at ",0.0" — the degenerate one-point course line.
        assert "8.0,46.5,5000" in result.output

    def test_qrcode_json_output_is_a_scannable_string(self):
        """The qrcode-json format emits the XCTSK: URL itself."""
        result = convert_stdin("--format", "qrcode-json")

        assert result.exit_code == 0
        assert "XCTSK:" in result.output

    def test_compressed_switches_the_scheme(self):
        """``-z`` asks for the XCTSKZ: encoding of the same task."""
        result = convert_stdin("--format", "qrcode-json", "--compressed")

        assert result.exit_code == 0
        assert "XCTSKZ:" in result.output

    @pytest.mark.skipif(
        not QR_CODE_SUPPORT, reason="QR code dependencies not available"
    )
    def test_png_output_decodes_back_to_the_task(self, tmp_path):
        """The written image is a QR code, not merely a non-empty file.

        This asserted ``st_size > 0``, which a truncated or blank PNG also
        satisfies — and the suite could already decode one.
        """
        source = tmp_path / "task.xctsk"
        source.write_text(SAMPLE.to_json())
        output = tmp_path / "task.png"

        result = CliRunner().invoke(
            convert, ["--format", "png", "--output", str(output), str(source)]
        )

        assert result.exit_code == 0
        decoded = decode_qr(Image.open(output))
        assert decoded, "the CLI wrote a PNG that carries no QR code"
        assert decoded[0].startswith("XCTSK:")

    def test_cli_convert_invalid_format(self):
        """Test CLI conversion with invalid format."""
        runner = CliRunner()
        result = runner.invoke(convert, ["--format", "invalid"], input="test")

        assert result.exit_code != 0
        assert "invalid" in result.output.lower() or "choice" in result.output.lower()

    def test_cli_convert_no_input(self):
        """Test CLI conversion with no input."""
        runner = CliRunner()
        result = runner.invoke(convert, ["--format", "json"])

        assert result.exit_code != 0
        assert (
            "empty input" in result.output.lower()
            or "no input" in result.output.lower()
        )

    def test_cli_convert_invalid_task(self):
        """Test CLI conversion with invalid task data."""
        runner = CliRunner()
        result = runner.invoke(convert, ["--format", "json"], input="invalid task data")

        assert result.exit_code != 0
        assert "error" in result.output.lower()

    def test_cli_main_command(self):
        """Test the main CLI command shows help."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "pyxctsk" in result.output
        assert "convert" in result.output
