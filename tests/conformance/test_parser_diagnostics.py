"""Parser-diagnostic regressions discovered by the conformance audits.

Derived from the Competition Interfaces and FAI S7F conformance audits under
docs/arch-review/. Each test retains its original diagnostic provenance.
"""

import json
from typing import Any

import pytest

from pyxctsk import (
    DistanceReport,
    GoalType,
    InvalidFormatError,
    Task,
    load_task,
    parse_task,
    render_task,
)
from pyxctsk.qrcode import image
from pyxctsk.qrcode.encoding import encode_num, encode_waypoint_turnpoint
from tests.conformance._support import BASE_TASK, task_json
from tests.corpus import reference_task


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
            load_task("/no/such/task.xctsk")

    def test_a_directory_says_so(self, tmp_path):
        """A different OS error, reported as itself."""
        with pytest.raises(InvalidFormatError, match="Is a directory"):
            load_task(tmp_path)

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
            load_task(png)

    def test_an_unreadable_image_is_told_apart_from_a_blank_one(self, tmp_path):
        """The distinction the magic-byte guess could not make."""
        png = tmp_path / "truncated.png"
        png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)

        with pytest.raises(InvalidFormatError, match="could not be read"):
            load_task(png)

    def test_a_missing_dependency_is_not_reported_as_a_bad_file(
        self, tmp_path, monkeypatch
    ):
        """The failure that most needed telling apart, and could not be."""
        png = tmp_path / "task.png"
        png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
        monkeypatch.setattr(image, "QR_CODE_SUPPORT", False)

        with pytest.raises(InvalidFormatError, match=r"pyxctsk\[qr\]"):
            load_task(png)

    def test_inline_json_containing_a_slash_still_parses(self):
        """A slash used to make parse_task try to open the payload as a file."""
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

    def test_parse_task_never_opens_a_file(self, tmp_path):
        """A path string is a payload to parse_task — and says so."""
        path = tmp_path / "task.xctsk"
        path.write_text(reference_task("task_bevo").task.to_json())

        with pytest.raises(InvalidFormatError, match="load_task reads files"):
            parse_task(str(path))
        assert load_task(path).turnpoints

    def test_a_path_object_is_refused_by_name(self, tmp_path):
        """It used to be read as the bytes of its own name: "invalid format"."""
        with pytest.raises(TypeError, match="load_task"):
            parse_task(tmp_path / "task.xctsk")  # type: ignore[arg-type]

    def test_unrecognized_bytes_still_fall_back_to_the_plain_message(self):
        """Nothing to say beyond "not a format I know"."""
        with pytest.raises(InvalidFormatError, match="invalid format"):
            parse_task(b"\x00\x01\x02\x03")


def _mutated(doc: Any, path: tuple[Any, ...], value: Any) -> str:
    """Return ``doc`` as JSON with the value at ``path`` replaced."""
    data = json.loads(json.dumps(doc))
    target = data
    for step in path[:-1]:
        target = target[step]
    target[path[-1]] = value
    return json.dumps(data)


def _qr_payload() -> dict[str, Any]:
    """The base task in the compact format, as a decoded JSON object."""
    url = parse_task(task_json()).to_qr_code_task().to_string()
    payload: dict[str, Any] = json.loads(url[len("XCTSK:") :])
    return payload


#: Wire values of every kind a scalar row can be handed by mistake: a JSON
#: boolean, the non-finite numbers Python's ``json`` reads, a number spelled as
#: a string, a number where text belongs, text UTF-8 cannot carry, containers.
_JUNK = [
    True,
    "inf",
    "nan",
    float("inf"),
    float("nan"),
    "46",
    123,
    "\ud800",
    [],
    {},
    1e9,
    10**400,
    " 7 ",
    "\u0663",
]

_FULL_SCALAR_PATHS = [
    ("version",),
    ("taskType",),
    ("earthModel",),
    ("turnpoints", 0, "radius"),
    ("turnpoints", 0, "type"),
    ("turnpoints", 0, "waypoint", "name"),
    ("turnpoints", 0, "waypoint", "lat"),
    ("turnpoints", 0, "waypoint", "lon"),
    ("turnpoints", 0, "waypoint", "altSmoothed"),
    ("turnpoints", 0, "waypoint", "description"),
    ("goal", "finishAltitude"),
    ("goal", "type"),
    ("sss", "type"),
]

_QR_SCALAR_PATHS = [
    ("version",),
    ("taskType",),
    ("e",),
    ("t", 0, "n"),
    ("t", 0, "d"),
    ("t", 0, "t"),
    ("t", 0, "z"),
    ("g", "fa"),
    ("g", "t"),
    ("s", "t"),
    ("s", "d"),
]


def _survives_every_output(task: Task) -> None:
    """Render every text format and the distance report, as the CLI would."""
    for fmt in ("json", "qrcode-json", "kml", "geojson"):
        render_task(task, fmt)
    report = DistanceReport.from_task(task)
    report.as_text()
    json.dumps(report.as_dict(), allow_nan=False)


class TestAMalformedScalarIsRefusedWhereItIsRead:
    """A bad scalar is a ``MalformedPayloadError`` naming its path, at read.

    The field table checked containers and trusted scalars, so a value of the
    wrong kind parsed and failed wherever it was first used: a traceback from
    the planar solver, the text report or the UTF-8 writer, or — for a JSON
    ``true`` read as the number one — a silent wrong distance. Each test below
    is one of the reproductions recorded in the 2026-10-02 review's C1 card.
    """

    @pytest.mark.parametrize("raw", ["inf", float("inf"), float("nan")])
    def test_a_non_finite_radius_names_where(self, raw):
        """It used to escape every command as ``OverflowError``."""
        with pytest.raises(InvalidFormatError, match=r"turnpoints\[0\]\.radius"):
            parse_task(_mutated(BASE_TASK, ("turnpoints", 0, "radius"), raw))

    def test_a_boolean_latitude_is_not_one_degree(self):
        """``true`` was read as 1°N and measured, 4 996 km, exit 0."""
        doc = _mutated(BASE_TASK, ("turnpoints", 1, "waypoint", "lat"), True)

        with pytest.raises(InvalidFormatError, match=r"turnpoints\[1\]\.waypoint"):
            parse_task(doc)

    def test_a_latitude_spelled_as_a_string_is_a_number(self):
        """The spelling Burnair uses for a radius, read the same way.

        It used to parse, keep the string, and raise ``TypeError`` from the
        planar projection the first time a distance was asked for.
        """
        doc = _mutated(BASE_TASK, ("turnpoints", 1, "waypoint", "lat"), "46.6")

        task = parse_task(doc)

        assert task.turnpoints[1].waypoint.lat == 46.6
        _survives_every_output(task)

    @pytest.mark.parametrize("raw", [95, -90.5])
    def test_a_latitude_off_the_earth_is_refused(self, raw):
        """It reached the solver's ``assert`` instead (C4's reproduction)."""
        doc = _mutated(BASE_TASK, ("turnpoints", 1, "waypoint", "lat"), raw)

        with pytest.raises(InvalidFormatError, match="latitude"):
            parse_task(doc)

    def test_a_numeric_name_is_refused(self):
        """``distances --format text`` raised ``Unknown format code 's'``."""
        doc = _mutated(BASE_TASK, ("turnpoints", 1, "waypoint", "name"), 123)

        with pytest.raises(InvalidFormatError, match="expected a string"):
            parse_task(doc)

    def test_a_name_utf8_cannot_carry_is_refused(self):
        """A lone surrogate parsed and broke ``convert`` with UnicodeEncodeError."""
        doc = _mutated(BASE_TASK, ("turnpoints", 1, "waypoint", "name"), "\ud800")

        with pytest.raises(InvalidFormatError, match=r"waypoint\.name"):
            parse_task(doc)

    def test_a_version_spelled_as_a_string_is_the_version(self):
        """``--strict`` said "defines version 1, the task declares 1"."""
        task = parse_task(task_json(version="1"), strict=True)

        assert task.version == 1

    def test_a_version_written_as_a_double_is_the_version(self):
        """A producer holding a double writes ``1.0``; it read before C1."""
        task = parse_task(task_json(version=1.0), strict=True)

        assert task.version == 1
        assert '"version":1,' in task.to_json()

    def test_a_qr_wire_integer_written_as_a_double_is_read(self):
        """The QR goal ``t`` accepted ``2.0`` before C1, as ``CYLINDER``."""
        payload = _qr_payload()
        payload["g"] = {"t": 2.0}

        task = parse_task("XCTSK:" + json.dumps(payload))

        assert task.goal is not None
        assert task.goal.type is GoalType.CYLINDER

    def test_an_unknown_qr_task_type_is_refused(self):
        """S1: ``"taskType": "FOO"`` was re-written as ``CLASSIC``, value lost.

        The full format refuses the same value as not a valid ``TaskType``.
        """
        payload = _qr_payload()
        payload["taskType"] = "FOO"

        with pytest.raises(InvalidFormatError, match="'FOO' is not a valid TaskType"):
            parse_task("XCTSK:" + json.dumps(payload))

    @pytest.mark.parametrize(
        ("lat", "radius"), [(95, 400), (46.5, 10**400), (46.5, -(10**400))]
    )
    def test_a_qr_coordinate_string_is_held_to_the_same_rules(self, lat, radius):
        """``z`` decodes four numbers, and they are the full format's four.

        A polyline can carry an integer of any size, so a radius of 10**400
        parsed and raised ``OverflowError`` from ``distances``.
        """
        payload = _qr_payload()
        payload["t"][0]["z"] = encode_waypoint_turnpoint(8.0, lat, 1000) + encode_num(
            radius
        )

        with pytest.raises(InvalidFormatError, match=r"t\[0\]\.z"):
            parse_task("XCTSK:" + json.dumps(payload))

    @pytest.mark.parametrize("path", _FULL_SCALAR_PATHS, ids=str)
    @pytest.mark.parametrize("raw", _JUNK, ids=repr)
    def test_every_full_format_scalar_is_refused_or_safe(self, path, raw):
        """No scalar the full format reads can fail after it was read."""
        try:
            task = parse_task(_mutated(BASE_TASK, path, raw))
        except InvalidFormatError:
            return
        _survives_every_output(task)

    @pytest.mark.parametrize("path", _QR_SCALAR_PATHS, ids=str)
    @pytest.mark.parametrize("raw", _JUNK, ids=repr)
    def test_every_qr_scalar_is_refused_or_safe(self, path, raw):
        """No scalar the compact format reads can fail after it was read."""
        try:
            task = parse_task("XCTSK:" + _mutated(_qr_payload(), path, raw))
        except InvalidFormatError:
            return
        _survives_every_output(task)
