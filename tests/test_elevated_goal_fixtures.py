"""Tests over the elevated-goal fixtures in ``reference_tasks/elevated-goal/``.

Eight real tasks that set an elevated goal in a field the spec does not define:
a root ``"o": {"v": 2, "fa": 1220}`` rather than ``"g": {"fa": ...}``, and with
an absolute AMSL value where the spec's ``finishAltitude`` is metres AGL above
the last turnpoint. See the directory's README for the full picture.

They pin two things: that unknown fields survive a round-trip rather than being
silently dropped, and that pyxctsk does *not* guess at their meaning.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from pyxctsk import Task, parse_task

FIXTURES = Path(__file__).parent / "data" / "reference_tasks" / "elevated-goal"

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
