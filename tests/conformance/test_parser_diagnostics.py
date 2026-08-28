"""Parser-diagnostic regressions discovered by the conformance audits.

Derived from the Competition Interfaces and FAI S7F conformance audits under
docs/arch-review/. Each test retains its original diagnostic provenance.
"""

import json

import pytest

from pyxctsk import (
    InvalidFormatError,
    parse_task,
    parser,
)


class TestUnrecognizedInputSaysWhy:
    """One message for every failure hid a missing install as a corrupt file.

    `InvalidFormatError("invalid format")` was raised for a nonexistent path, a
    directory, truncated JSON, a PNG carrying no QR code — and for a perfectly
    good QR image on a machine without Pillow and zxing-cpp, because the
    adapter returns None when the optional dependencies are absent.
    """

    def test_a_missing_file_says_so(self):
        """The path case was lost when _read_file swallowed the OSError."""
        with pytest.raises(InvalidFormatError, match="No such file or directory"):
            parse_task("/no/such/task.xctsk")

    def test_a_directory_says_so(self, tmp_path):
        """A different OS error, reported as itself."""
        with pytest.raises(InvalidFormatError, match="Is a directory"):
            parse_task(f"{tmp_path}/")

    def test_truncated_json_is_named_as_json(self):
        """It parsed as far as being JSON-shaped; that is worth saying."""
        with pytest.raises(InvalidFormatError, match="looks like JSON"):
            parse_task('{"taskType": "CLASSIC", "vers')

    def test_an_image_with_no_qr_code_says_so(self, tmp_path):
        """Not "invalid format": the file was read, it just carries no task.

        A *real* image, written by Pillow. This used to be eight magic bytes
        followed by 64 zeros, which no decoder can open — so the case it names
        was never the case it ran, and it passed only because the adapter
        answered "no QR code" for anything that started like an image.
        """
        from PIL import Image

        png = tmp_path / "blank.png"
        Image.new("RGB", (32, 32), "white").save(png)

        with pytest.raises(InvalidFormatError, match="no XCTSK: QR code"):
            parse_task(str(png))

    def test_an_unreadable_image_is_told_apart_from_a_blank_one(self, tmp_path):
        """The distinction the magic-byte guess could not make."""
        png = tmp_path / "truncated.png"
        png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)

        with pytest.raises(InvalidFormatError, match="could not be read"):
            parse_task(str(png))

    def test_a_missing_dependency_is_not_reported_as_a_bad_file(
        self, tmp_path, monkeypatch
    ):
        """The failure that most needed telling apart, and could not be."""
        png = tmp_path / "task.png"
        png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
        monkeypatch.setattr(parser, "QR_CODE_SUPPORT", False)

        with pytest.raises(InvalidFormatError, match=r"pyxctsk\[qr\]"):
            parse_task(str(png))

    def test_inline_json_containing_a_slash_still_parses(self):
        """The path heuristic matches it, so the fallthrough must survive.

        `_looks_like_file_path` is `"/" in data`, so a waypoint name with a
        slash trips it. Reading has to stay non-fatal.
        """
        task = parse_task(
            json.dumps(
                {
                    "taskType": "CLASSIC",
                    "version": 1,
                    "turnpoints": [
                        {
                            "radius": 400,
                            "waypoint": {
                                "name": "A/B",
                                "lat": 46.5,
                                "lon": 8.0,
                                "altSmoothed": 100,
                            },
                        }
                    ],
                }
            )
        )

        assert task.turnpoints[0].waypoint.name == "A/B"

    def test_unrecognized_bytes_still_fall_back_to_the_plain_message(self):
        """Nothing to say beyond "not a format I know"."""
        with pytest.raises(InvalidFormatError, match="invalid format"):
            parse_task(b"\x00\x01\x02\x03")
