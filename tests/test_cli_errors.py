"""Tests for what the CLI does with the library's errors and missing optional dependencies."""

from pathlib import Path

from click.testing import CliRunner

from pyxctsk import (
    MissingQRCodeSupportError,
)
from pyxctsk.cli import convert
from pyxctsk.exceptions import pyXCTSKError
from pyxctsk.qrcode import image
from tests.builders import TAKEOFF_ONLY_TASK


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
            convert, ["--format", "png"], input=TAKEOFF_ONLY_TASK.to_json().encode()
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
            convert,
            ["--format", "qrcode-json"],
            input=TAKEOFF_ONLY_TASK.to_json().encode(),
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
