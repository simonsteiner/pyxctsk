"""Tests over the elevated-goal fixtures in ``reference_tasks/elevated-goal/``.

Eight real tasks that set an elevated goal in a field the spec does not define:
a root ``"o": {"v": 2, "fa": 1220}`` rather than ``"g": {"fa": ...}``, and with
an absolute AMSL value where the spec's ``finishAltitude`` is metres AGL above
the last turnpoint. See the directory's README for the full picture.

They pin two things: that unknown fields survive a round-trip rather than being
silently dropped, and that pyxctsk does *not* guess at their meaning.
"""

import json
from typing import Any

import pytest

from pyxctsk import Task, parse_task
from tests.paths import ELEVATED_GOAL_DIR

FIXTURES = ELEVATED_GOAL_DIR

TASKS = [f"task{i}" for i in range(1, 9)]

#: The elevated goal altitude every fixture carries, and the altitude of the
#: goal waypoint it sits above.
FINISH_ALTITUDE_AMSL = 1220
GOAL_WAYPOINT_ALTITUDE = 1020


def payload(name: str) -> str:
    """Return the decoded ``XCTSK:`` string for a fixture."""
    return (FIXTURES / f"{name}_qr_code.txt").read_text().strip()


def source(name: str) -> dict[str, Any]:
    """Return the fixture's QR JSON as the producer wrote it."""
    data: dict[str, Any] = json.loads(payload(name)[len("XCTSK:") :])
    return data


def load(name: str) -> Task:
    """Parse a fixture into a Task."""
    return parse_task(payload(name))


@pytest.mark.parametrize("name", TASKS)
def test_fixture_parses_and_validates(name):
    """A non-spec extra field must not stop the task being read."""
    task = load(name)

    assert task.turnpoints
    assert task.validate() == []


@pytest.mark.parametrize("name", TASKS)
def test_root_unknown_field_is_preserved(name):
    """The elevated goal lives in a root "o"; it must survive parsing."""
    task = load(name)

    assert task.unknown == {"o": {"v": 2, "fa": FINISH_ALTITUDE_AMSL}}


@pytest.mark.parametrize("name", TASKS)
def test_turnpoint_unknown_field_is_preserved(name):
    """Every turnpoint carries its own non-spec "o"."""
    task = load(name)

    assert all(tp.unknown == {"o": {"a1": 180}} for tp in task.turnpoints)


@pytest.mark.parametrize("name", TASKS)
def test_unknown_fields_are_re_emitted_in_qr_format(name):
    """Round-tripping through the QR format must not drop them."""
    emitted = json.loads(load(name).to_qr_code_task().to_json())

    assert emitted["o"] == {"v": 2, "fa": FINISH_ALTITUDE_AMSL}
    assert all(tp["o"] == {"a1": 180} for tp in emitted["t"])


@pytest.mark.parametrize("name", TASKS)
def test_unknown_fields_are_re_emitted_in_full_json(name):
    """And through the full .xctsk format, surviving a reparse."""
    task = load(name)

    emitted = json.loads(task.to_json())
    assert emitted["o"] == {"v": 2, "fa": FINISH_ALTITUDE_AMSL}
    assert all(tp["o"] == {"a1": 180} for tp in emitted["turnpoints"])

    assert parse_task(task.to_json()).unknown == task.unknown


@pytest.mark.parametrize("name", TASKS)
def test_non_spec_finish_altitude_is_not_guessed(name):
    """``o.fa`` must not be mapped onto the spec's ``goal.finishAltitude``.

    The two use different datums: ``o.fa`` is 1220 m AMSL while the spec defines
    finishAltitude as metres AGL above the last turnpoint, which for these tasks
    would be 200. Copying the value across would turn a field we merely fail to
    understand into one we report wrongly, off by the 1020 m the goal waypoint
    already sits at.
    """
    task = load(name)

    assert task.goal is not None
    assert task.goal.finish_altitude is None

    goal_altitude = task.turnpoints[-1].waypoint.alt_smoothed
    assert goal_altitude == GOAL_WAYPOINT_ALTITUDE
    assert task.unknown["o"]["fa"] - goal_altitude == 200


@pytest.mark.parametrize("name", TASKS)
def test_roundtrip_matches_the_source(name):
    """Re-encoding reproduces the payload, bar two documented behaviours.

    An empty description is dropped (empty and absent mean the same, and the QR
    format exists to save bytes), and a task that omits ``goal`` gains the
    documented CYLINDER default.
    """
    original = source(name)
    emitted = json.loads(load(name).to_qr_code_task().to_json())

    emitted = {
        k: v for k, v in emitted.items() if not (k in ("tc", "to") and v is None)
    }
    if "g" not in original:
        assert emitted.pop("g") == {"t": 2}
    for turnpoint in original["t"]:
        if turnpoint.get("d") == "":
            del turnpoint["d"]
    if original.get("s", {}).get("g") == []:
        del original["s"]["g"]

    assert emitted == original


@pytest.mark.parametrize("name", TASKS)
def test_jpg_and_text_payloads_agree(name):
    """The decoded .txt must stay in step with the photo it came from."""
    zxingcpp = pytest.importorskip("zxingcpp")
    pytest.importorskip("PIL")
    from PIL import Image

    codes = zxingcpp.read_barcodes(
        Image.open(FIXTURES / f"{name}_qr_code.jpg"),
        formats=zxingcpp.BarcodeFormat.QRCode,
    )

    assert codes, "QR code could not be decoded"
    assert codes[0].text == payload(name)


def test_unknown_fields_never_shadow_spec_fields():
    """A rogue producer must not be able to overwrite a real field."""
    task = load("task1")
    task.unknown = {"taskType": "NONSENSE", "o": {"keep": 1}}

    emitted = json.loads(task.to_json())

    assert emitted["taskType"] == "CLASSIC"
    assert emitted["o"] == {"keep": 1}


class TestSeeYouSemantics:
    """What SeeYou Navigator's own UI says the ``o`` field means.

    Two tasks captured with their on-screen values (``seeyou-reference.json``),
    which settle two things the QR payloads alone could only suggest: the app
    labels the value *"Minimum altitude at finish point (MSL)"*, so ``o.fa`` is
    absolute; and setting the field to Auto omits ``fa`` entirely.
    """

    REFERENCE = json.loads((FIXTURES / "seeyou-reference.json").read_text())

    def test_explicit_finish_altitude_is_written_as_msl(self):
        """The UI shows "1220 m" against an MSL label, and fa is 1220."""
        task = parse_task((FIXTURES / "seeyou-finish-1220_qr_code.txt").read_text())
        displayed = self.REFERENCE["seeyou-finish-1220"]

        assert task.unknown["o"] == {"v": 2, "fa": 1220}
        assert displayed["finish_altitude_displayed"] == "1220 m"
        assert "(MSL)" in displayed["finish_altitude_label"]
        # MSL, so it exceeds the goal waypoint's own altitude rather than
        # being an offset from it.
        assert task.unknown["o"]["fa"] > task.turnpoints[-1].waypoint.alt_smoothed

    def test_auto_finish_altitude_omits_fa(self):
        """On Auto the app writes "o" without an fa key at all."""
        task = parse_task((FIXTURES / "seeyou-finish-auto_qr_code.txt").read_text())
        displayed = self.REFERENCE["seeyou-finish-auto"]

        assert task.unknown["o"] == {"v": 2}
        assert "fa" not in task.unknown["o"]
        assert displayed["finish_altitude_displayed"].startswith("Auto")

    @pytest.mark.parametrize("name", ["seeyou-finish-1220", "seeyou-finish-auto"])
    def test_centers_distance_matches_seeyou_exactly(self, name):
        """Through-centers distance is unambiguous, and we agree to 0.1 km."""
        from pyxctsk.distance import calculate_task_distances

        task = parse_task((FIXTURES / f"{name}_qr_code.txt").read_text())
        result = calculate_task_distances(task)

        assert result.center_distance_km == self.REFERENCE[name]["total_km"]

    @pytest.mark.parametrize("name", ["seeyou-finish-1220", "seeyou-finish-auto"])
    def test_optimized_legs_match_seeyou_except_the_first(self, name):
        """Every leg after the first matches; the first differs by convention.

        SeeYou measures the opening leg from the takeoff *cylinder boundary*,
        we from the takeoff *center* — the convention ADR 0002 chose to match
        XCTrack. On the 2-leg task the gap is exactly the 400 m takeoff radius.
        Legs beyond the first are independent validation of the optimizer
        against a second implementation.
        """
        from pyxctsk.distance.measured_task import MeasuredTask
        from pyxctsk.distance.turnpoint import geodesic_distance

        task = parse_task((FIXTURES / f"{name}_qr_code.txt").read_text())
        route = MeasuredTask.from_task(task).route.points
        ours = [
            geodesic_distance(route[i - 1], route[i], None) / 1000
            for i in range(1, len(route))
        ]
        theirs = self.REFERENCE[name]["leg_km"]

        assert len(ours) == len(theirs)
        for i, (mine, seeyou) in enumerate(zip(ours[1:], theirs[1:]), start=2):
            assert mine == pytest.approx(seeyou, abs=0.05), f"leg {i}"

        # The first leg is longer by at most the takeoff radius, never shorter.
        takeoff_radius_km = task.turnpoints[0].radius / 1000
        assert 0 <= ours[0] - theirs[0] <= takeoff_radius_km + 0.05


class TestConformantElevatedGoal:
    """The spec-conformant counterpart, from tools.xcontest.org.

    Same feature, encoded the way the spec defines it: ``goal.finishAltitude``
    in the full format and ``g.fa`` in the QR one, both in metres AGL above the
    last turnpoint. Kept beside the SeeYou tasks so the two conventions can be
    compared directly.
    """

    #: Metres AGL above the last turnpoint, per the spec's definition.
    FINISH_ALTITUDE_AGL = 300
    #: Altitude of the goal waypoint the offset is measured from.
    GOAL_WAYPOINT_ALTITUDE = 428

    @pytest.mark.parametrize(
        "filename", ["xcontest-conformant.xctsk", "xcontest-conformant_qr_code.txt"]
    )
    def test_finish_altitude_is_read_from_the_spec_field(self, filename):
        """Both formats must yield the same finish altitude."""
        task = parse_task((FIXTURES / filename).read_text().strip())

        assert task.validate() == []
        assert task.goal is not None
        assert task.goal.finish_altitude == self.FINISH_ALTITUDE_AGL
        assert task.unknown == {}

    def test_the_value_is_agl_not_absolute(self):
        """300 m is below the goal waypoint's own 428 m, so it cannot be AMSL.

        This is what distinguishes the spec's datum from the SeeYou ``o.fa``
        convention in the tasks above, and why the two must not be conflated.
        """
        task = parse_task((FIXTURES / "xcontest-conformant.xctsk").read_text())
        goal_altitude = task.turnpoints[-1].waypoint.alt_smoothed

        assert goal_altitude == self.GOAL_WAYPOINT_ALTITUDE
        assert self.FINISH_ALTITUDE_AGL < goal_altitude

    def test_qr_roundtrip_is_byte_identical(self):
        """Our QR output must match the reference producer exactly."""
        expected = (FIXTURES / "xcontest-conformant_qr_code.txt").read_text().strip()
        task = parse_task(expected)

        emitted = json.loads(task.to_qr_code_task().to_json())
        emitted = {
            k: v for k, v in emitted.items() if not (k in ("tc", "to") and v is None)
        }
        rebuilt = "XCTSK:" + json.dumps(
            emitted, separators=(",", ":"), ensure_ascii=False
        )

        assert rebuilt == expected

    def test_full_json_roundtrip_preserves_finish_altitude(self):
        """And the .xctsk format survives a reparse."""
        task = parse_task((FIXTURES / "xcontest-conformant.xctsk").read_text())

        assert json.loads(task.to_json())["goal"]["finishAltitude"] == (
            self.FINISH_ALTITUDE_AGL
        )
        round_tripped = parse_task(task.to_json())
        assert round_tripped.goal is not None
        assert round_tripped.goal.finish_altitude == (self.FINISH_ALTITUDE_AGL)

    def test_concentric_sss_and_goal_keep_their_out_and_back(self):
        """SSS r=61.6 km and goal r=400 m share a center, so the route flies out.

        Guards the duplicate-collapse fix: these two circles are concentric but
        differ in radius, so they must not be merged (ADR 0002).
        """
        from pyxctsk.distance import calculate_task_distances

        task = parse_task((FIXTURES / "xcontest-conformant.xctsk").read_text())
        result = calculate_task_distances(task)

        assert task.turnpoints[-2].radius == 61600
        assert task.turnpoints[-1].radius == 400
        assert result.optimized_distance_km > result.center_distance_km
