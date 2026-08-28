"""QR scheme and serialized-shape conformance regressions.

Derived from docs/arch-review/2026-08-16-competition-interfaces-audit.md.
Each test keeps the finding and specification provenance that it pins.
"""

import json

import pytest

from pyxctsk import (
    InvalidFormatError,
    Task,
    parse_task,
)
from tests.conformance._support import task_json
from tests.corpus import reference_task

# Polyline-encoded "z" literals below are opaque tokens, not words.
# cspell:ignore Fligr


class TestCompressedQRScheme:
    """Finding 3 — the ``XCTSKZ:`` zlib+base64 encoding.

    Spec: "The QR code can be also compressed using zlib format and converted
    using base64 encoding to ascii. This must be prefixed with a string
    'XCTSKZ:'. It is recommended that the software accepts both XCTSK and
    XCTSKZ and is able to produce QR code in both formats."
    """

    def test_compressed_output_carries_the_right_prefix(self):
        """Each scheme must announce itself correctly."""
        task = Task.from_json(task_json())

        assert task.to_qr_code_task().to_string(compressed=True).startswith("XCTSKZ:")
        assert task.to_qr_code_task().to_string().startswith("XCTSK:")

    def test_plain_remains_the_default(self):
        """Existing callers must see no change."""
        qr = Task.from_json(task_json()).to_qr_code_task()

        assert qr.to_string() == qr.to_string(compressed=False)
        assert not qr.to_string().startswith("XCTSKZ:")

    @pytest.mark.parametrize("stem", ["task_bevo", "task_noha_route"])
    def test_compressed_round_trips_to_the_same_task(self, stem):
        """Compression must be transparent: same task in, same task out."""
        reference = reference_task(stem)
        original = parse_task(reference.qr_string)
        waypoints = reference.is_waypoints_format

        qr = original.to_qr_code_task()
        compressed = (
            qr.to_waypoints_string(compressed=True)
            if waypoints
            else qr.to_string(compressed=True)
        )

        assert parse_task(compressed).to_json() == original.to_json()

    def test_compression_actually_shrinks_a_real_task(self):
        """The point of the format is fitting more task in a scannable code."""
        qr = parse_task(reference_task("task_bevo").qr_string).to_qr_code_task()

        assert len(qr.to_string(compressed=True)) < len(qr.to_string())

    def test_parser_accepts_both_schemes(self):
        """The spec makes reading both mandatory."""
        qr = Task.from_json(task_json()).to_qr_code_task()

        assert (
            parse_task(qr.to_string()).to_json()
            == parse_task(qr.to_string(compressed=True)).to_json()
        )

    def test_compressed_url_is_not_mistaken_for_a_file_path(self):
        """Base64 contains "/", which the path heuristic used to trip over."""
        from pyxctsk.parser import _looks_like_file_path

        payloads = [
            Task.from_json(
                task_json(sss={"type": "RACE", "timeGates": [f"1{n}:00:00Z"]})
            )
            .to_qr_code_task()
            .to_string(compressed=True)
            for n in range(10)
        ]
        assert any("/" in p for p in payloads), "no sample exercised the '/' case"
        assert not any(_looks_like_file_path(p) for p in payloads)

    @pytest.mark.parametrize(
        "payload", ["XCTSKZ:not valid base64!!", "XCTSKZ:aGVsbG8=", "XCTSKZ:"]
    )
    def test_malformed_compressed_payload_is_reported(self, payload):
        """A recognized prefix with a bad body must not fall through silently."""
        with pytest.raises(InvalidFormatError):
            parse_task(payload)

    def test_unknown_scheme_is_rejected(self):
        """A lookalike prefix is not silently treated as plain JSON."""
        from pyxctsk.qrcode.task import QRCodeTask

        with pytest.raises(ValueError, match="Invalid QR code scheme"):
            QRCodeTask.from_string("NOT-A-SCHEME:{}")


class TestEachQRShapeIsMeasuredAgainstItsOwnKeys:
    """A key one QR shape defines is unknown to the other, not understood.

    ``QRCodeTask`` used to carry a single allow-list spanning both shapes, so a
    competition key in a waypoints payload passed for a key this class reads.
    It was neither read into an attribute nor captured as unknown: ``from_dict``
    dropped it and ``to_dict`` had nothing to write back.
    """

    SOURCE = {
        "T": "W",
        "V": 2,
        "t": [{"n": "WPT1", "z": "|dz~FligrB?"}],
        "e": 1,
        "to": "09:00:00Z",
        "g": {"t": 2},
    }

    def _parsed(self):
        from pyxctsk.qrcode.task import QRCodeTask

        return QRCodeTask.from_dict(json.loads(json.dumps(self.SOURCE)))

    def test_competition_keys_are_unknown_to_the_waypoints_shape(self):
        """This shape reads none of them, so all three are carried."""
        assert self._parsed().unknown == {"e": 1, "to": "09:00:00Z", "g": {"t": 2}}

    def test_they_are_not_read_into_attributes(self):
        """Being unknown is the point — nothing may interpret them either."""
        parsed = self._parsed()

        assert (parsed.earth_model, parsed.takeoff, parsed.goal) == (None, None, None)

    def test_the_waypoints_roundtrip_keeps_them(self):
        """The whole payload comes back, which it did not before."""
        emitted = json.loads(self._parsed().to_waypoints_json())

        assert emitted == self.SOURCE

    def test_the_waypoints_keys_stay_unknown_to_the_competition_shape(self):
        """The rule runs the other way too: ``V`` is not the competition key."""
        from pyxctsk.qrcode.task import QRCodeTask

        source = {"taskType": "CLASSIC", "version": 2, "t": [], "V": 9}
        parsed = QRCodeTask.from_dict(source)

        assert parsed.version == 2
        assert parsed.unknown == {"V": 9}


class TestWaypointsTaskEncoding:
    """Findings 7 and 8 — the XC/Waypoints ``z`` carries three numbers.

    Spec: the XC/Waypoints task is a "simple route from waypoints without
    cylinders", and its ``z`` is "polyline encoded coordinates with altitude"
    — longitude, latitude, altitude. No radius.
    """

    def test_altitudes_survive_reading(self):
        """A three-number z must yield its altitude, not zero."""
        task = parse_task(reference_task("task_noha_route").qr_string)

        altitudes = [tp.waypoint.alt_smoothed for tp in task.turnpoints[:4]]
        assert altitudes == [1149, 175, 606, 1450]

    def test_no_cylinder_is_invented(self):
        """A route "without cylinders" must not acquire a radius on read."""
        task = parse_task(reference_task("task_noha_route").qr_string)

        assert all(tp.radius == 0 for tp in task.turnpoints)

    @pytest.mark.parametrize("stem", ["task_noha_route", "task_dami_route"])
    def test_roundtrip_is_byte_identical_to_xctrack(self, stem):
        """Re-encoding an XCTrack waypoints QR must reproduce it exactly.

        These fixtures were decoded from QR codes generated by
        tools.xcontest.org, so they are ground truth rather than our own output.
        """
        reference = reference_task(stem)
        task = parse_task(reference.qr_string)

        assert task.to_qr_code_task().to_waypoints_string() == reference.qr_string

    def test_competition_z_keeps_its_radius(self):
        """The four-number competition encoding must be left alone."""
        reference = reference_task("task_bevo")
        task = parse_task(reference.qr_string)

        assert task.to_qr_code_task().to_string() == reference.qr_string
        assert task.turnpoints[0].radius == 400

    def test_z_length_selects_the_format(self):
        """Three numbers means waypoints, four means competition."""
        from pyxctsk.qrcode.encoding import (
            encode_competition_turnpoint,
            encode_waypoint_turnpoint,
        )
        from pyxctsk.qrcode.models import QRCodeTurnpoint

        waypoint_z = encode_waypoint_turnpoint(8.1, 46.5, 1234)
        competition_z = encode_competition_turnpoint(8.1, 46.5, 1234, 400)

        waypoint = QRCodeTurnpoint.from_dict({"n": "X", "z": waypoint_z})
        competition = QRCodeTurnpoint.from_dict({"n": "X", "z": competition_z})

        assert (waypoint.alt_smoothed, waypoint.radius) == (1234, 0)
        assert (competition.alt_smoothed, competition.radius) == (1234, 400)
        assert competition_z.startswith(waypoint_z)
