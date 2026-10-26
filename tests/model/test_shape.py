"""Tests for the machinery the field tables are written in.

That is ``Shape``, ``Value``, ``Discriminator`` and ``Optionality``.

The tables themselves are exercised end-to-end by the reference round-trips —
25 byte-exact QR strings and the corpus's JSON. The wire-scalar codecs are
pinned in ``test_codec.py``, and the invariants over every real table in
``tests/conformance/test_field_tables.py``.
"""

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest

from pyxctsk import MalformedPayloadError, TaskType
from pyxctsk.exceptions import pyXCTSKError
from pyxctsk.model.codec import (
    INTEGER,
    TEXT,
    WHOLE_METRES,
    enum_codec,
    list_codec,
)
from pyxctsk.model.shape import (
    DEFAULTED,
    OPTIONAL_EMPTY,
    REQUIRED,
    Discriminator,
    Shape,
    Value,
    shape_codec,
)
from pyxctsk.model.task_parts import (
    GOAL_SHAPE,
    TURNPOINT_SHAPE,
)
from pyxctsk.qrcode.models import (
    QR_TURNPOINT_SHAPE,
)
from pyxctsk.qrcode.task import QR_TASK_SHAPE, QR_WAYPOINTS_TASK_SHAPE


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
        Value("name", "n", TEXT, REQUIRED),
        Value("count", "c", WHOLE_METRES, DEFAULTED),
        Value("label", "l", TEXT, OPTIONAL_EMPTY),
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
        """One error type for every malformed payload, naming the key."""
        with pytest.raises(MalformedPayloadError, match="^n: required key"):
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
        assert Value("label", "l", TEXT).read({"l": None}) == {}

    def test_optional_omits_none(self):
        """No value, no key.

        ``write`` mutates the dict it is handed and always returns None, so
        asserting on its return value held whatever it did — this used to read
        ``assert Value("label", "l", TEXT).write(Toy(name="A"), {}) is None`` and
        passed for a field that wrote the key too.
        """
        written: dict[str, object] = {}

        Value("label", "l", TEXT).write(Toy(name="A"), written)

        assert written == {}

    def test_optional_empty_treats_empty_as_absent(self):
        """An empty description says nothing a missing key does not."""
        assert TOY_SHAPE.read({"n": "A", "l": ""}).label is None
        assert "l" not in TOY_SHAPE.write(Toy(name="A", label=""))

    def test_defaulted_writes_even_a_falsy_value(self):
        """A count of zero and an empty list of gates are still written."""
        assert TOY_SHAPE.write(Toy(name="A", count=0))["c"] == 0

    def test_required_reads_a_falsy_value_rather_than_defaulting(self):
        """Zero is a value; only missing is missing."""
        assert Value("count", "c", INTEGER, REQUIRED).read({"c": 0}) == {"count": 0}


class TestNestedRows:
    """Nesting is a codec, not a kind of row.

    A ``Shape`` already is one — ``write`` is ``to_wire`` and ``read`` is
    ``from_wire`` — so a nested object is a ``Value`` with ``shape_codec`` and a
    nested list is one with ``list_codec(shape_codec(...))``. ``Nested`` and
    ``NestedList`` used to be two more ``Field`` subclasses restating ``Value``'s
    required/absent/omit dance.
    """

    CHILD = Shape(Toy, (Value("name", "n", TEXT, REQUIRED),))

    def test_nested_reads_and_writes_through_the_child(self):
        """A child object is its own table, reached by one row."""
        row = Value("child", "c", shape_codec(self.CHILD))

        assert row.read({"c": {"n": "A"}})["child"].name == "A"

        written: dict = {}
        row.write(SimpleNamespace(child=Toy(name="A")), written)
        assert written == {"c": {"n": "A"}}

    def test_nested_list_reads_every_element(self):
        """Turnpoints are the list every task has."""
        row = Value("children", "c", list_codec(shape_codec(self.CHILD)))

        assert [
            t.name for t in row.read({"c": [{"n": "A"}, {"n": "B"}]})["children"]
        ] == [
            "A",
            "B",
        ]

    def test_a_nested_row_obeys_the_same_optionality_as_any_other(self):
        """Which is the point: one dance, written once, in ``Value``."""
        row = Value("child", "c", shape_codec(self.CHILD))

        assert row.read({}) == {}
        assert row.read({"c": None}) == {}

        written: dict = {}
        row.write(SimpleNamespace(child=None), written)
        assert written == {}

    def test_a_discriminator_states_what_choosing_the_shape_meant(self):
        """The key was already read — choosing this table *was* reading it."""
        row = Discriminator("T", "W", "name", "WAYPOINTS")

        assert row.read({}) == {"name": "WAYPOINTS"}
        result: dict = {}
        row.write(Toy(name="A"), result)
        assert result == {"T": "W"}


#: Every shape in the package, with the attribute holding its carried keys.


class TestTheTableChecksWireTypes:
    """A payload of the wrong shape is refused where it is read, and located.

    The tables used to trust wire types, so a list where an object belongs
    reached ``.get`` and left as ``AttributeError``, and a string where a list
    belongs was read one character at a time. The parser kept a tuple of
    whichever built-in types had leaked so far.
    """

    CHILD = Shape(Toy, (Value("name", "n", TEXT, REQUIRED),))
    PARENT = Shape(
        Toy,
        (
            Value("name", "n", TEXT, REQUIRED),
            Value("children", "c", list_codec(shape_codec(CHILD))),
        ),
    )

    @pytest.mark.parametrize(
        "payload, kind", [([], "an array"), ("x", "a string"), (5, "a number")]
    )
    def test_a_shape_is_an_object(self, payload, kind):
        """The root itself: no path, and the type that arrived."""
        with pytest.raises(
            MalformedPayloadError, match=f"^expected an object, got {kind}$"
        ):
            TOY_SHAPE.read(payload)

    def test_a_list_is_a_list_not_any_iterable(self):
        """A string is iterable; that is how it was read character by character."""
        with pytest.raises(MalformedPayloadError, match="^c: expected an array"):
            self.PARENT.read({"n": "A", "c": "AB"})

    def test_the_path_reaches_into_lists_and_objects(self):
        """Where it went wrong, spelled from the root."""
        with pytest.raises(MalformedPayloadError) as caught:
            self.PARENT.read({"n": "A", "c": [{"n": "B"}, {}]})

        assert caught.value.path == "c[1].n"
        assert caught.value.reason == "required key is missing"

    def test_a_codec_failure_is_located_and_chained(self):
        """The original error is the cause, not lost."""
        shape = Shape(Toy, (Value("name", "n", enum_codec(TaskType)),))

        with pytest.raises(MalformedPayloadError, match="^n: ") as caught:
            shape.read({"n": "NOT_A_TYPE"})

        assert isinstance(caught.value.__cause__, ValueError)

    def test_it_is_in_the_hierarchy_and_a_value_error(self):
        """One ``except`` for a caller; old ``except ValueError`` still works."""
        assert issubclass(MalformedPayloadError, pyXCTSKError)
        assert issubclass(MalformedPayloadError, ValueError)
