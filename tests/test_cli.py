"""Tests for the `pyxctsk` command-line interface.

The CLI is the library's other public surface: every output format `convert`
offers (json, kml, png, qrcode-json), the `distances` report another
implementation is meant to diff against, reading from a file or from stdin, and
what it does with input it cannot parse.
"""

import json

import pytest
from click.testing import CliRunner

from pyxctsk import (
    DistanceReport,
    parse_task,
)
from pyxctsk.cli import convert, distances, main
from tests.builders import TAKEOFF_ONLY_TASK
from tests.corpus import reference_task
from tests.qr_test_utils import QR_CODE_SUPPORT, Image, decode_qr


def convert_stdin(*options: str):
    """Run ``convert`` over TAKEOFF_ONLY_TASK on stdin, returning the click result."""
    return CliRunner().invoke(
        convert, list(options), input=TAKEOFF_ONLY_TASK.to_json().encode()
    )


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
        source.write_text(TAKEOFF_ONLY_TASK.to_json())
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

    def test_a_qr_scheme_that_is_not_utf8_is_an_error(self):
        r"""S2: ``printf 'XCTSK:\xff' | pyxctsk convert`` printed a traceback."""
        result = CliRunner().invoke(convert, [], input=b"XCTSK:\xff")

        assert result.exit_code == 1
        assert not isinstance(result.exception, UnicodeDecodeError)
        assert "Error:" in result.output

    def test_cli_main_command(self):
        """The main help preserves examples as separate readable lines."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "pyxctsk" in result.output
        assert "convert" in result.output
        assert r"\b" not in result.output
        assert "  pyxctsk convert task.xctsk --format json\n" in result.output
        assert "  pyxctsk distances task.xctsk --format text\n" in result.output

    @pytest.mark.parametrize("command", ["convert", "distances"])
    def test_command_help_does_not_leak_implementation_docs(self, command):
        """Click help is a user interface, not the callback's Python docs."""
        result = CliRunner().invoke(main, [command, "--help"])

        assert result.exit_code == 0
        assert r"\b" not in result.output
        assert "Args:" not in result.output
        assert "Returns:" not in result.output
        assert "Raises:" not in result.output
        assert f"  pyxctsk {command}" in result.output


class TestStrictValidation:
    """`--strict`, which the CLI's own docstring used to promise.

    `main`'s help advertised "strict error handling", and `convert` called
    `parse_task` with no `strict` and offered no flag to set it — so the one
    interface real users touch could never validate a task.
    """

    def _valid(self) -> bytes:
        """Return a real, spec-valid task.

        `TAKEOFF_ONLY_TASK` is not one: a single TAKEOFF turnpoint has neither an SSS nor
        an ESS.
        """
        return reference_task("task_bevo").xctsk_path.read_bytes()

    def _invalid(self) -> bytes:
        """The same task with a TAKEOFF where the spec forbids one."""
        data = json.loads(self._valid())
        data["turnpoints"][-1]["type"] = "TAKEOFF"
        return json.dumps(data).encode()

    def test_the_base_task_really_is_valid(self):
        """Otherwise the rejection below would prove nothing."""
        assert parse_task(self._valid()).validate() == []

    def test_an_invalid_task_still_converts_by_default(self):
        """Reading stays lenient, matching the library."""
        result = CliRunner().invoke(
            convert, ["--format", "json"], input=self._invalid()
        )

        assert result.exit_code == 0

    def test_strict_rejects_it_and_names_the_rule(self):
        """The message has to say which rule broke, not just "invalid"."""
        result = CliRunner().invoke(
            convert, ["--format", "json", "--strict"], input=self._invalid()
        )

        assert result.exit_code == 1
        assert "TAKEOFF is only allowed on the first turnpoint" in result.output

    def test_strict_passes_a_valid_task_through(self):
        """The flag must not reject what the spec allows."""
        result = CliRunner().invoke(
            convert, ["--format", "json", "--strict"], input=self._valid()
        )

        assert result.exit_code == 0

    def test_the_flag_is_documented(self):
        """A flag the help does not mention is one nobody finds."""
        result = CliRunner().invoke(main, ["convert", "--help"])

        assert "--strict" in result.output


class TestWritingOutput:
    """The read/write seam: one place that knows encoding, newlines and bytes.

    Reading and writing were spelled out six times across the two commands, so
    encoding, trailing newline, text-vs-bytes and stdout-vs-file were each
    decided independently — and two of them had been decided inconsistently.
    """

    #: A task whose waypoint names are outside ASCII. No corpus task has any,
    #: which is why the encoding defect survived: `grep -lP "[^\x00-\x7F]"`
    #: over the reference tasks matches nothing.
    def _non_ascii_task(self):
        built = parse_task(reference_task("task_bevo").xctsk_path.read_bytes())
        built.turnpoints[0].waypoint.name = "Küçük"
        return built

    @pytest.mark.parametrize("fmt", ["json", "kml"])
    def test_a_non_ascii_task_survives_a_round_trip_through_a_file(self, fmt, tmp_path):
        """None of the four writes passed `encoding=`, so all used the locale's."""
        out = tmp_path / f"out.{fmt}"
        payload = self._non_ascii_task().to_json().encode()

        result = CliRunner().invoke(
            convert, ["--format", fmt, "-o", str(out)], input=payload
        )

        assert result.exit_code == 0, result.output
        assert out.read_bytes().decode("utf-8")
        if fmt == "json":
            assert parse_task(out.read_bytes()).turnpoints[0].waypoint.name == "Küçük"
        else:
            assert "Küçük" in out.read_text(encoding="utf-8")

    @pytest.mark.parametrize(
        "command, options",
        [
            (convert, ["--format", "json"]),
            (convert, ["--format", "qrcode-json"]),
            (convert, ["--format", "kml"]),
            (convert, ["--format", "geojson"]),
            (distances, ["--format", "json"]),
        ],
        ids=["json", "qrcode-json", "kml", "geojson", "distances"],
    )
    def test_every_output_writes_a_non_ascii_name_as_itself(self, command, options):
        r"""Four JSON writers chose their own options, and two escaped ``â``.

        ``json`` and ``qrcode-json`` wrote ``Château``; ``geojson`` and the
        ``distances`` report wrote its ``â`` as ``\u00e2`` — the same JSON value,
        two spellings, depending on which call site produced it. KML, which is not
        JSON, is here because it is the other text output a name reaches.
        """
        built = parse_task(reference_task("task_bevo").xctsk_path.read_bytes())
        built.turnpoints[0].waypoint.name = "Château"

        result = CliRunner().invoke(command, options, input=built.to_json().encode())

        assert result.exit_code == 0, result.output
        assert "Château" in result.output
        assert "\\u00e2" not in result.output

    def test_the_distance_report_is_writable_as_a_file(self, tmp_path):
        """Its text rendering contains §, so a non-UTF-8 locale used to refuse."""
        out = tmp_path / "report.txt"

        result = CliRunner().invoke(
            distances,
            [
                str(reference_task("task_bevo").xctsk_path),
                "--format",
                "text",
                "-o",
                str(out),
            ],
        )

        assert result.exit_code == 0, result.output
        assert "§7.2" in out.read_text(encoding="utf-8")

    @pytest.mark.parametrize(
        "command, options",
        [
            ("convert", ["--format", "json"]),
            ("convert", ["--format", "kml"]),
            ("convert", ["--format", "qrcode-json"]),
            ("distances", []),
            ("distances", ["--format", "text"]),
        ],
    )
    def test_every_text_file_ends_with_a_newline(self, command, options, tmp_path):
        """`convert` wrote none and `distances` wrote one — nobody chose that."""
        out = tmp_path / "out"
        cmd = convert if command == "convert" else distances

        result = CliRunner().invoke(
            cmd, [str(reference_task("task_bevo").xctsk_path), *options, "-o", str(out)]
        )

        assert result.exit_code == 0, result.output
        assert out.read_bytes().endswith(b"\n")

    def test_a_png_is_written_as_bytes_not_text(self, tmp_path):
        """The one format whose payload is binary, through the same seam."""
        out = tmp_path / "qr.png"

        result = CliRunner().invoke(
            convert,
            ["--format", "png", "-o", str(out)],
            input=TAKEOFF_ONLY_TASK.to_json().encode(),
        )

        assert result.exit_code == 0, result.output
        assert out.read_bytes().startswith(b"\x89PNG")

    def test_an_unwritable_path_is_reported_not_raised(self, tmp_path):
        """OSError is caught alongside the library's own errors."""
        result = CliRunner().invoke(
            convert,
            [
                "--format",
                "json",
                "-o",
                str(tmp_path / "no" / "such" / "dir" / "o.json"),
            ],
            input=TAKEOFF_ONLY_TASK.to_json().encode(),
        )

        assert result.exit_code == 1
        assert "Error:" in result.output


class TestOneAnswerToWhatVersionThisIs:
    """Two spellings that failed differently, in two modules.

    `__init__` called `importlib.metadata.version` directly and raised on a
    source checkout; `distance/report.py` caught that and returned "unknown".
    `pyxctsk --version` was served by the second — a general "what version am
    I" utility parked in the S7F report module, reached from the CLI by a
    private-path import, and the only reason `cli.py` imported `distance` at
    all.
    """

    def test_the_three_places_agree(self):
        """The report's provenance line, `--version`, and `__version__`."""
        import pyxctsk
        from pyxctsk.metadata import pyxctsk_version

        report = DistanceReport.from_task(reference_task("task_bevo").task)

        assert pyxctsk.__version__ == pyxctsk_version()
        assert report.as_dict()["pyxctsk_version"] == pyxctsk_version()

    def test_the_command_prints_it(self):
        """`--version` shipped with no test at all."""
        result = CliRunner().invoke(main, ["--version"])

        from pyxctsk.metadata import pyxctsk_version

        assert result.exit_code == 0
        assert result.output.strip() == f"pyxctsk {pyxctsk_version()}"
