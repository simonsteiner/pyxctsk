"""Tests for the field tables every serializable shape is declared as.

The tables themselves are exercised end-to-end by the reference round-trips —
25 byte-exact QR strings and the corpus's JSON — so what is pinned here is the
machinery those tables are written in, plus the one structural invariant the
whole design rests on: that a shape's declared keys are the keys it actually
uses, because every key belongs to a row.
"""

import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from pyxctsk import Task
from pyxctsk.model.shape import (
    DEFAULTED,
    IDENTITY,
    LENIENT_INT,
    OPTIONAL_EMPTY,
    REQUIRED,
    ROUNDED_INT,
    TIME_OF_DAY,
    Discriminator,
    Nested,
    NestedList,
    Shape,
    Value,
    enum_codec,
    list_codec,
)
from pyxctsk.model.task import (
    GOAL_SHAPE,
    SSS_SHAPE,
    TAKEOFF_SHAPE,
    TASK_SHAPE,
    TURNPOINT_SHAPE,
    WAYPOINT_SHAPE,
    TurnpointType,
)
from pyxctsk.model.time_of_day import TimeOfDay
from pyxctsk.qrcode.models import (
    QR_GOAL_SHAPE,
    QR_SSS_SHAPE,
    QR_TAKEOFF_SHAPE,
    QR_TURNPOINT_SHAPE,
    QR_WAYPOINT_TURNPOINT_SHAPE,
)
from pyxctsk.qrcode.task import QR_TASK_SHAPE, QR_WAYPOINTS_TASK_SHAPE
from tests.corpus import reference_tasks


@dataclass
class Toy:
    """A shape of every regular kind, for testing the machinery on."""

    name: str
    count: int = 0
    label: str | None = None
    extras: list[Any] = field(default_factory=list)
    unknown: dict[str, Any] = field(default_factory=dict)


TOY_SHAPE = Shape(
    Toy,
    (
        Value("name", "n", optionality=REQUIRED),
        Value("count", "c", ROUNDED_INT, DEFAULTED),
        Value("label", "l", optionality=OPTIONAL_EMPTY),
    ),
)


class TestKeysAreDerived:
    """The allow-list comes from the table, not from a second declaration."""

    def test_keys_are_the_union_of_the_rows(self):
        """Nothing to keep in step, because there is only one statement."""
        assert TOY_SHAPE.keys == frozenset({"n", "c", "l"})

    def test_the_extensions_key_joins_them(self):
        """A shape with an extensions list understands that key too."""
        assert "extensions" in TURNPOINT_SHAPE.keys
        assert "x" in QR_TURNPOINT_SHAPE.keys

    def test_ignored_keys_join_them(self):
        """Read and discarded still counts as understood."""
        assert "lineLength" in GOAL_SHAPE.keys

    def test_a_row_owning_two_keys_declares_both(self):
        """The QR takeoff is one attribute across ``to`` and ``tc``."""
        assert {"to", "tc"} <= QR_TASK_SHAPE.keys

    def test_a_row_owning_four_attributes_declares_one_key(self):
        """``z`` is the whole of a turnpoint's geometry."""
        assert "z" in QR_TURNPOINT_SHAPE.keys

    def test_the_two_qr_task_shapes_do_not_share_a_key_set(self):
        """The union of both is what swallowed a whole format's keys."""
        assert "e" in QR_TASK_SHAPE.keys
        assert "e" not in QR_WAYPOINTS_TASK_SHAPE.keys
        assert "T" in QR_WAYPOINTS_TASK_SHAPE.keys
        assert "T" not in QR_TASK_SHAPE.keys


class TestReadAndWrite:
    """Two traversals of one table."""

    def test_a_required_key_is_read_and_written(self):
        """The simplest row there is."""
        toy = TOY_SHAPE.read({"n": "A"})

        assert toy.name == "A"
        assert TOY_SHAPE.write(toy)["n"] == "A"

    def test_a_missing_required_key_names_itself(self):
        """A KeyError, which the parser treats as "not my format"."""
        with pytest.raises(KeyError, match="n"):
            TOY_SHAPE.read({"c": 1})

    def test_row_order_is_output_order(self):
        """The QR key orders are byte-exact, so this is load-bearing."""
        written = TOY_SHAPE.write(Toy(name="A", count=1, label="x"))

        assert list(written) == ["n", "c", "l"]

    def test_unknown_keys_come_last(self):
        """Matching the order the spec lists extensions in."""
        toy = TOY_SHAPE.read({"n": "A", "zz": 1})

        assert list(TOY_SHAPE.write(toy)) == ["n", "c", "zz"]

    def test_a_codec_runs_in_both_directions(self):
        """``altSmoothed`` is a number in, an int out."""
        toy = TOY_SHAPE.read({"n": "A", "c": 2.5})

        assert toy.count == 3
        assert TOY_SHAPE.write(toy)["c"] == 3


class TestOptionality:
    """When a field may be missing, on each side of the wire."""

    def test_optional_treats_null_as_absent(self):
        """The default stands rather than a None reaching the codec."""
        assert Value("label", "l").read({"l": None}) == {}

    def test_optional_omits_none(self):
        """No value, no key."""
        assert Value("label", "l").write(Toy(name="A"), {}) is None

    def test_optional_empty_treats_empty_as_absent(self):
        """An empty description says nothing a missing key does not."""
        assert TOY_SHAPE.read({"n": "A", "l": ""}).label is None
        assert "l" not in TOY_SHAPE.write(Toy(name="A", label=""))

    def test_defaulted_writes_even_a_falsy_value(self):
        """A count of zero and an empty list of gates are still written."""
        assert TOY_SHAPE.write(Toy(name="A", count=0))["c"] == 0

    def test_required_reads_a_falsy_value_rather_than_defaulting(self):
        """Zero is a value; only missing is missing."""
        assert Value("count", "c", optionality=REQUIRED).read({"c": 0}) == {"count": 0}

    @pytest.mark.parametrize("raw", ["2", 2])
    def test_lenient_int_accepts_either_spelling(self, raw):
        """Producers have written the QR version and earth model as strings."""
        assert LENIENT_INT.from_wire(raw) == 2


class TestCodecs:
    """The value spellings both formats share."""

    def test_identity_is_a_round_trip(self):
        """The values JSON already carries as-is."""
        assert IDENTITY.to_wire(IDENTITY.from_wire(1.5)) == 1.5

    def test_time_of_day_round_trips(self):
        """``HH:MM:SSZ``, the one time spelling both formats use."""
        assert TIME_OF_DAY.to_wire(TIME_OF_DAY.from_wire("12:30:00Z")) == "12:30:00Z"

    def test_an_enum_is_spelled_as_its_value(self):
        """A constrained value travels as the string the spec names."""
        codec = enum_codec(TurnpointType)

        assert codec.to_wire(TurnpointType.SSS) == "SSS"
        assert codec.from_wire("SSS") is TurnpointType.SSS

    def test_an_unknown_enum_value_raises(self):
        """A constrained value fails at parse time, as it did before."""
        with pytest.raises(ValueError):
            enum_codec(TurnpointType).from_wire("NONSENSE")

    def test_a_list_codec_applies_element_wise(self):
        """Time gates are the only array of values either format has."""
        codec = list_codec(TIME_OF_DAY)

        assert codec.to_wire(codec.from_wire(["09:00:00Z"])) == ["09:00:00Z"]


class TestNestedRows:
    """Rows that hand off to another shape."""

    def test_nested_reads_and_writes_through_the_child(self):
        """A child object is its own table, reached by one row."""
        parent = Shape(Toy, (Value("name", "n", optionality=REQUIRED),))
        row = Nested("child", "c", parent)

        assert row.read({"c": {"n": "A"}})["child"].name == "A"

    def test_nested_list_reads_every_element(self):
        """Turnpoints are the list every task has."""
        parent = Shape(Toy, (Value("name", "n", optionality=REQUIRED),))
        row = NestedList("children", "c", parent)

        assert [
            t.name for t in row.read({"c": [{"n": "A"}, {"n": "B"}]})["children"]
        ] == [
            "A",
            "B",
        ]

    def test_a_discriminator_states_what_choosing_the_shape_meant(self):
        """The key was already read — choosing this table *was* reading it."""
        row = Discriminator("T", "W", "name", "WAYPOINTS")

        assert row.read({}) == {"name": "WAYPOINTS"}
        result: dict = {}
        row.write(Toy(name="A"), result)
        assert result == {"T": "W"}


#: Every shape in the package, with the attribute holding its carried keys.
ALL_SHAPES = [
    ("Task", TASK_SHAPE),
    ("Turnpoint", TURNPOINT_SHAPE),
    ("Waypoint", WAYPOINT_SHAPE),
    ("Takeoff", TAKEOFF_SHAPE),
    ("SSS", SSS_SHAPE),
    ("Goal", GOAL_SHAPE),
    ("QRCodeTask", QR_TASK_SHAPE),
    ("QRCodeTask/waypoints", QR_WAYPOINTS_TASK_SHAPE),
    ("QRCodeTurnpoint", QR_TURNPOINT_SHAPE),
    ("QRCodeTurnpoint/waypoints", QR_WAYPOINT_TURNPOINT_SHAPE),
    ("QRCodeTakeoff", QR_TAKEOFF_SHAPE),
    ("QRCodeSSS", QR_SSS_SHAPE),
    ("QRCodeGoal", QR_GOAL_SHAPE),
]


class TestEveryKeyBelongsToARow:
    """The invariant the whole design rests on.

    If a shape can write a key its table does not declare, the derived
    allow-list is wrong again and the passthrough will treat that key as
    unknown on the way back in — reading it into ``unknown`` *and* writing it
    from its own row, or worse, letting a carried key shadow it. Rendering the
    whole corpus and checking every emitted key against the shape that emitted
    it is what makes a bespoke row's undeclared key fail here rather than in a
    round-trip nobody runs.
    """

    def _emitted_keys(self, obj: Any, shape: Shape) -> set[str]:
        written = shape.write(obj)
        carried = set(getattr(obj, "unknown", {}))
        return set(written) - carried

    @pytest.mark.parametrize("name, shape", ALL_SHAPES, ids=[n for n, _ in ALL_SHAPES])
    def test_no_shape_declares_a_key_it_cannot_reach(self, name, shape):
        """Every declared key is one some row owns, by construction."""
        owned = {key for f in shape.fields for key in f.keys}
        extra = shape.keys - owned - shape.ignored_keys

        assert extra <= {shape.ext_key} - {None}, f"{name} declares stray {extra}"

    @pytest.mark.parametrize("reference", reference_tasks(), ids=str)
    def test_nothing_a_reference_task_emits_falls_outside_its_shape(self, reference):
        """Rendered both ways, every key at every level is a declared one."""
        task = reference.task

        assert self._emitted_keys(task, TASK_SHAPE) <= TASK_SHAPE.keys
        for turnpoint in task.turnpoints:
            assert (
                self._emitted_keys(turnpoint, TURNPOINT_SHAPE) <= TURNPOINT_SHAPE.keys
            )
            assert (
                self._emitted_keys(turnpoint.waypoint, WAYPOINT_SHAPE)
                <= WAYPOINT_SHAPE.keys
            )

        qr = task.to_qr_code_task()
        assert self._emitted_keys(qr, QR_TASK_SHAPE) <= QR_TASK_SHAPE.keys
        assert (
            self._emitted_keys(qr.as_waypoints(), QR_WAYPOINTS_TASK_SHAPE)
            <= QR_WAYPOINTS_TASK_SHAPE.keys
        )
        for qr_turnpoint in qr.turnpoints:
            assert (
                self._emitted_keys(qr_turnpoint, QR_TURNPOINT_SHAPE)
                <= QR_TURNPOINT_SHAPE.keys
            )
            assert (
                self._emitted_keys(qr_turnpoint, QR_WAYPOINT_TURNPOINT_SHAPE)
                <= QR_WAYPOINT_TURNPOINT_SHAPE.keys
            )

    def test_the_takeoff_row_declares_both_of_its_keys(self):
        """The regression this class is shaped to catch, stated directly."""
        from pyxctsk.qrcode.models import QRCodeTakeoff
        from pyxctsk.qrcode.task import QRCodeTask

        task = QRCodeTask(takeoff=QRCodeTakeoff(time_open=TimeOfDay(9, 0, 0)))

        assert set(QR_TASK_SHAPE.write(task)) <= QR_TASK_SHAPE.keys


class TestTablesAndModelsAgree:
    """A row names an attribute the class actually has.

    ``Shape.read`` ends in ``cls(**kwargs)``, so a misspelled ``attr`` is a
    ``TypeError`` at the moment something parses — which for a row the corpus
    does not exercise could be a long way from here.
    """

    @pytest.mark.parametrize("name, shape", ALL_SHAPES, ids=[n for n, _ in ALL_SHAPES])
    def test_every_row_names_a_field_of_its_class(self, name, shape):
        """Checked for the rows that declare one attribute.

        The handful spanning several write their own names, and the corpus
        covers those.
        """
        fields = set(shape.cls.__dataclass_fields__)

        for row in shape.fields:
            attr = getattr(row, "attr", None)
            if attr is not None:
                assert attr in fields, f"{name}: no attribute {attr!r}"

    @pytest.mark.parametrize("name, shape", ALL_SHAPES, ids=[n for n, _ in ALL_SHAPES])
    def test_a_shape_carries_unknown_only_if_its_class_can(self, name, shape):
        """The one shape that is not an object on the wire has no ``unknown``."""
        has_field = "unknown" in shape.cls.__dataclass_fields__

        assert shape.carries_unknown == has_field, name


def test_the_derived_key_sets_match_the_spec_fields():
    """A last check that deriving them changed none of them.

    The allow-lists were hand-written before the tables existed; these are the
    same sets, which is the evidence that the tables describe the format rather
    than a new reading of it.
    """
    assert Task.KNOWN_KEYS == frozenset(
        {
            "taskType",
            "version",
            "earthModel",
            "turnpoints",
            "takeoff",
            "sss",
            "goal",
            "extensions",
        }
    )
    assert json.loads(Task.from_json(_MINIMAL).to_json())["taskType"] == "CLASSIC"


_MINIMAL = json.dumps(
    {
        "taskType": "CLASSIC",
        "version": 1,
        "turnpoints": [
            {
                "radius": 400,
                "waypoint": {"name": "A", "lat": 46.5, "lon": 8.1, "altSmoothed": 100},
            }
        ],
    }
)
