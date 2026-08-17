"""Tests for the `pyxctsk` command-line interface.

The CLI is the library's other public surface: every output format it offers
(json, kml, png, qrcode-json), reading from a file or from stdin, and what it
does with input it cannot parse.
"""

import json
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from pyxctsk import Task, TaskType, Turnpoint, TurnpointType, Waypoint
from pyxctsk.cli import convert, main
from tests.qr_test_utils import QR_CODE_SUPPORT

# ============================================================================
# CLI Utility Function Tests
# ============================================================================


class TestCLIConvert:
    """Test the CLI convert command functionality."""

    def test_cli_convert_json_output(self):
        """Test CLI conversion to JSON format."""
        # Create a simple task
        task = Task(
            task_type=TaskType.CLASSIC,
            version=1,
            turnpoints=[
                Turnpoint(
                    radius=1000,
                    waypoint=Waypoint(
                        name="Test", lat=46.5, lon=8.0, alt_smoothed=1000
                    ),
                    type=TurnpointType.TAKEOFF,
                )
            ],
        )

        # Create a temporary task file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xctsk", delete=False
        ) as tmp:
            tmp.write(task.to_json())
            tmp_path = tmp.name

        try:
            runner = CliRunner()
            with open(tmp_path, "rb") as f:
                result = runner.invoke(convert, ["--format", "json"], input=f.read())

            assert result.exit_code == 0
            # The CLI includes debug output, so check if JSON is in output
            assert "taskType" in result.output or "task_type" in result.output

            # Extract JSON from output (it might contain debug info)
            lines = result.output.strip().split("\n")
            json_line = None
            for line in lines:
                if line.strip().startswith("{"):
                    json_line = line.strip()
                    break

            if json_line:
                parsed = json.loads(json_line)
                assert (
                    parsed["taskType"] == "CLASSIC"
                    or parsed.get("task_type") == "CLASSIC"
                )

        finally:
            Path(tmp_path).unlink()

    def test_cli_convert_kml_output(self):
        """Test CLI conversion to KML format."""
        # Create a simple task
        task = Task(
            task_type=TaskType.CLASSIC,
            version=1,
            turnpoints=[
                Turnpoint(
                    radius=1000,
                    waypoint=Waypoint(
                        name="Test", lat=46.5, lon=8.0, alt_smoothed=1000
                    ),
                    type=TurnpointType.TAKEOFF,
                )
            ],
        )

        # Create a temporary task file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xctsk", delete=False
        ) as tmp:
            tmp.write(task.to_json())
            tmp_path = tmp.name

        try:
            runner = CliRunner()
            with open(tmp_path, "rb") as f:
                result = runner.invoke(convert, ["--format", "kml"], input=f.read())

            assert result.exit_code == 0
            assert "<?xml version=" in result.output
            assert "<kml xmlns=" in result.output
            assert "8.0,46.5,0.0" in result.output

        finally:
            Path(tmp_path).unlink()

    def test_cli_convert_qrcode_json_output(self):
        """Test CLI conversion to QR code JSON format."""
        # Create a simple task
        task = Task(
            task_type=TaskType.CLASSIC,
            version=1,
            turnpoints=[
                Turnpoint(
                    radius=1000,
                    waypoint=Waypoint(
                        name="Test", lat=46.5, lon=8.0, alt_smoothed=1000
                    ),
                    type=TurnpointType.TAKEOFF,
                )
            ],
        )

        # Create a temporary task file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xctsk", delete=False
        ) as tmp:
            tmp.write(task.to_json())
            tmp_path = tmp.name

        try:
            runner = CliRunner()
            with open(tmp_path, "rb") as f:
                result = runner.invoke(
                    convert, ["--format", "qrcode-json"], input=f.read()
                )

            assert result.exit_code == 0
            # Look for XCTSK: in the output (might have debug info before it)
            assert "XCTSK:" in result.output

        finally:
            Path(tmp_path).unlink()

    @pytest.mark.skipif(
        not QR_CODE_SUPPORT, reason="QR code dependencies not available"
    )
    def test_cli_convert_png_output(self):
        """Test CLI conversion to PNG QR code format."""
        # Create a simple task
        task = Task(
            task_type=TaskType.CLASSIC,
            version=1,
            turnpoints=[
                Turnpoint(
                    radius=1000,
                    waypoint=Waypoint(
                        name="Test", lat=46.5, lon=8.0, alt_smoothed=1000
                    ),
                    type=TurnpointType.TAKEOFF,
                )
            ],
        )

        # Create temporary files
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xctsk", delete=False
        ) as tmp_input:
            tmp_input.write(task.to_json())
            input_path = tmp_input.name

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_output:
            output_path = tmp_output.name

        try:
            runner = CliRunner()
            result = runner.invoke(
                convert, ["--format", "png", "--output", output_path, input_path]
            )

            assert result.exit_code == 0

            # Verify PNG file was created and has content
            output_file = Path(output_path)
            assert output_file.exists()
            assert output_file.stat().st_size > 0

        finally:
            Path(input_path).unlink()
            Path(output_path).unlink(missing_ok=True)

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
