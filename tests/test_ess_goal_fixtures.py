"""Tests over the ESS/goal fixtures in ``tests/data/reference_tasks/ess-goal/``.

Those tasks cover how the End of Speed Section relates to the goal — either as
the last turnpoint, or duplicated as a separate goal turnpoint with identical
coordinates and radius. The main corpus barely exercises either shape. See the
directory's README for provenance and for what each file contributes.

The duplicated pair is a degenerate case for the route optimizer: two route
points constrained to the same circle. Before ``_collapse_duplicate_circles``,
the alternating sweep froze at a spurious local minimum there, costing 168 m on
``task2``.
"""

import json
from pathlib import Path

import pytest

from pyxctsk import Task, TurnpointType, parse_task
from pyxctsk.distance import optimized_distance, optimized_route_coordinates
from pyxctsk.distance.task_distances import _task_to_turnpoints
from pyxctsk.distance.turnpoint import geodesic_distance

FIXTURES = Path(__file__).parent / "data" / "reference_tasks" / "ess-goal"

#: Tasks whose last two turnpoints are the same waypoint, one marked ESS.
DUPLICATE_GOAL_TASKS = ["task2", "task3", "task4"]

#: Every task in the directory, as (name, path) pairs.
ALL_TASKS = [("do-t3", FIXTURES / "do-t3.xctsk")] + [
    (name, FIXTURES / f"{name}_qr_code.txt") for name in DUPLICATE_GOAL_TASKS
]


def load(path: Path) -> Task:
    """Parse a fixture from its path."""
    return parse_task(path.read_text().strip())


@pytest.mark.parametrize(("name", "path"), ALL_TASKS, ids=[n for n, _ in ALL_TASKS])
def test_fixture_parses_and_validates(name, path):
    """Every fixture is a structurally valid CLASSIC task."""
    task = load(path)

    assert task.turnpoints
    assert task.validate() == []


@pytest.mark.parametrize("name", DUPLICATE_GOAL_TASKS)
def test_last_two_turnpoints_are_an_identical_pair(name):
    """The shape these fixtures exist to cover: ESS duplicated as goal."""
    task = load(FIXTURES / f"{name}_qr_code.txt")
    ess, goal = task.turnpoints[-2], task.turnpoints[-1]

    assert ess.type == TurnpointType.ESS
    assert goal.type is None
    assert (ess.waypoint.lat, ess.waypoint.lon) == (
        goal.waypoint.lat,
        goal.waypoint.lon,
    )
    assert ess.radius == goal.radius
    assert ess.waypoint.alt_smoothed == goal.waypoint.alt_smoothed


@pytest.mark.parametrize("name", DUPLICATE_GOAL_TASKS)
def test_duplicate_turnpoint_costs_nothing(name):
    """Touching a circle twice is satisfied by touching it once.

    The regression: the duplicate used to drag its predecessor off the optimum,
    so the route through it came out *longer* than the route without it.
    """
    task = load(FIXTURES / f"{name}_qr_code.txt")
    turnpoints = _task_to_turnpoints(task)

    with_duplicate = optimized_distance(turnpoints)
    without_duplicate = optimized_distance(turnpoints[:-1])

    assert with_duplicate == pytest.approx(without_duplicate, abs=0.01)


@pytest.mark.parametrize("name", DUPLICATE_GOAL_TASKS)
def test_duplicate_route_points_coincide(name):
    """The two points of the pair must land on the same spot."""
    task = load(FIXTURES / f"{name}_qr_code.txt")
    route = optimized_route_coordinates(_task_to_turnpoints(task))

    assert geodesic_distance(route[-2], route[-1], None) == pytest.approx(0.0, abs=0.01)


@pytest.mark.parametrize("name", DUPLICATE_GOAL_TASKS)
def test_final_point_is_the_true_optimum(name):
    """The optimizer must not freeze the final point at an arbitrary bearing.

    Pins the actual defect rather than just its symptom: the route that ends at
    the duplicated pair must place its last point exactly where the route
    without the duplicate does. On task2 these were 257 m apart.
    """
    task = load(FIXTURES / f"{name}_qr_code.txt")
    turnpoints = _task_to_turnpoints(task)

    with_duplicate = optimized_route_coordinates(turnpoints)[-1]
    without_duplicate = optimized_route_coordinates(turnpoints[:-1])[-1]

    assert geodesic_distance(with_duplicate, without_duplicate, None) == pytest.approx(
        0.0, abs=0.5
    )


def test_ess_as_last_turnpoint_is_the_goal():
    """do-t3 marks its final turnpoint ESS, which the spec equates with goal."""
    task = load(FIXTURES / "do-t3.xctsk")

    assert task.turnpoints[-1].type == TurnpointType.ESS
    assert task.is_ess_goal()


@pytest.mark.parametrize("name", DUPLICATE_GOAL_TASKS)
def test_qr_payload_round_trips(name):
    """Re-encoding reproduces the source payload, key order aside.

    These came from a producer that orders keys differently from
    tools.xcontest.org and omits tc/to rather than emitting nulls, so compare
    the parsed structures rather than the bytes.
    """
    source = json.loads((FIXTURES / f"{name}_qr_code.txt").read_text().strip()[6:])
    task = load(FIXTURES / f"{name}_qr_code.txt")

    emitted = json.loads(task.to_qr_code_task().to_json())
    emitted = {
        k: v for k, v in emitted.items() if not (k in ("tc", "to") and v is None)
    }
    # The source leaves the goal type implicit; CYLINDER is the documented default.
    emitted["g"] = {k: v for k, v in emitted["g"].items() if not (k == "t" and v == 2)}

    assert emitted == source


@pytest.mark.parametrize("name", DUPLICATE_GOAL_TASKS)
def test_png_and_text_payloads_agree(name):
    """The decoded .txt must stay in step with the .png it came from."""
    zxingcpp = pytest.importorskip("zxingcpp")
    pytest.importorskip("PIL")
    from PIL import Image

    codes = zxingcpp.read_barcodes(
        Image.open(FIXTURES / f"{name}_qr_code.png"),
        formats=zxingcpp.BarcodeFormat.QRCode,
    )

    assert codes, "QR code could not be decoded"
    assert codes[0].text == (FIXTURES / f"{name}_qr_code.txt").read_text().strip()
