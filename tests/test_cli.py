"""Tests for the `pyxctsk` command-line interface.

The CLI is the library's other public surface: every output format `convert`
offers (json, kml, png, qrcode-json), the `distances` report another
implementation is meant to diff against, reading from a file or from stdin, and
what it does with input it cannot parse.
"""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from pyxctsk import (
    DistanceReport,
    MissingQRCodeSupportError,
    TurnpointType,
    parse_task,
)
from pyxctsk.cli import convert, distances, main
from pyxctsk.exceptions import pyXCTSKError
from pyxctsk.qrcode import image
from tests.builders import task, turnpoint
from tests.corpus import reference_task
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


class TestStrictValidation:
    """`--strict`, which the CLI's own docstring used to promise.

    `main`'s help advertised "strict error handling", and `convert` called
    `parse_task` with no `strict` and offered no flag to set it — so the one
    interface real users touch could never validate a task.
    """

    def _valid(self) -> bytes:
        """Return a real, spec-valid task.

        `SAMPLE` is not one: a single TAKEOFF turnpoint has neither an SSS nor
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
        payload = SAMPLE.to_json().encode()

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
            input=SAMPLE.to_json().encode(),
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
            input=SAMPLE.to_json().encode(),
        )

        assert result.exit_code == 1
        assert "Error:" in result.output


class TestOptionalDependenciesAreReportedNotRaised:
    """A missing optional dependency is an expected failure, not a crash.

    `generate_qrcode_image` raises when Pillow and qrcode are absent, and
    narrowing `convert`'s catch from a bare `except Exception` to
    `(pyXCTSKError, OSError)` let that escape — so `convert --format png` on an
    install without the extras produced a traceback where it used to produce a
    one-line error. `MissingQRCodeSupportError` inherits from both
    `pyXCTSKError` and `ImportError` so each catch keeps working.
    """

    def test_png_without_the_dependencies_reports_an_error(self, monkeypatch):
        """Exit 1 and a message, not a stack trace."""
        monkeypatch.setattr(image, "QR_CODE_SUPPORT", False)

        result = CliRunner().invoke(
            convert, ["--format", "png"], input=SAMPLE.to_json().encode()
        )

        assert result.exit_code == 1
        assert "pyxctsk[qr]" in result.output
        assert not isinstance(result.exception, MissingQRCodeSupportError)

    def test_the_error_is_both_a_library_error_and_an_import_error(self):
        """Both bases are load-bearing, so both are pinned."""
        assert issubclass(MissingQRCodeSupportError, pyXCTSKError)
        assert issubclass(MissingQRCodeSupportError, ImportError)

    def test_qrcode_json_needs_no_dependencies(self, monkeypatch):
        """Only the image formats do — the string one must stay unaffected."""
        monkeypatch.setattr(image, "QR_CODE_SUPPORT", False)

        result = CliRunner().invoke(
            convert, ["--format", "qrcode-json"], input=SAMPLE.to_json().encode()
        )

        assert result.exit_code == 0
        assert result.output.startswith("XCTSK:")


class TestTheLibraryErrorsAreOneHierarchy:
    """The CLI transcribed the exception set by hand, because it had to.

    `TooFewTurnpointsError` descended from `ValueError` alone and was raised
    from `distance/report.py`, so it was the one library error outside
    `pyXCTSKError` — and `convert` and `distances` caught two different tuples
    because of it. A sixth library error would have meant editing `cli.py`.
    """

    def test_every_library_error_descends_from_the_base(self):
        """`exceptions.py` is the answer to "what can pyxctsk raise"."""
        import pyxctsk
        from pyxctsk.exceptions import pyXCTSKError

        errors = [
            getattr(pyxctsk, name)
            for name in pyxctsk.__all__
            if isinstance(getattr(pyxctsk, name), type)
            and issubclass(getattr(pyxctsk, name), BaseException)
        ]

        assert errors, "no exceptions found at the front door"
        for error in errors:
            assert issubclass(error, pyXCTSKError), f"{error.__name__} is outside it"

    def test_the_base_is_reachable_from_the_front_door(self):
        """It is the one name a caller writes in `except`."""
        import pyxctsk

        assert "pyXCTSKError" in pyxctsk.__all__

    def test_too_few_turnpoints_is_still_a_value_error(self):
        """Both bases are load-bearing, as `MissingQRCodeSupportError` states."""
        from pyxctsk import TooFewTurnpointsError

        assert issubclass(TooFewTurnpointsError, ValueError)

    def test_both_commands_catch_the_same_set(self):
        """One tuple, so the CLI stops knowing the library's error list."""
        import re

        source = (
            Path(__file__).resolve().parents[1] / "src" / "pyxctsk" / "cli.py"
        ).read_text()
        tuples = set(re.findall(r"except \(([^)]*)\) as e:", source))

        assert tuples == {"pyXCTSKError, OSError"}


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
