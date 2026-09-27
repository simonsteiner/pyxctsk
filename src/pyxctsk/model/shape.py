"""One field table per serializable shape.

A **serializable shape** is one object as it appears on the wire: a turnpoint in
the full JSON format, a goal in the compact QR one, the XC/Waypoints task. Each
declares its mapping once, as an ordered table of fields, and one traversal
reads that table while another writes it.

What this replaces is a hand-written ``to_dict`` sitting beside a hand-written
``from_dict``, with nothing making the two agree. Adding one turnpoint-level
spec field meant twelve edits across four files and the type checker enforced
none of them; the drift that followed was not hypothetical. The QR task's two
shapes shared a single key allow-list while each read half of it, and four of
the eleven shapes had no allow-list at all — both silent losses of data.

Three properties follow from **a field owning its keys**, rather than a class
owning a list of keys beside the code that reads them:

- **The allow-list is derived.** :attr:`Shape.keys` is the union of its fields'
  keys, so what a shape claims to understand cannot disagree with what it reads.
- **Read and write cannot drift.** They are two traversals of one table.
- **Row order is output order.** The QR format's key order matches
  tools.xcontest.org byte for byte; the table is written in that order, and
  that order is what comes out.

A row is an attribute, a key, a codec and an :class:`Optionality` — that is
:class:`Value`, and **nesting is a codec, not a kind of row**. A ``Shape`` is
already one (``write`` is ``to_wire``, ``read`` is ``from_wire``), so a nested
object is ``Value(..., shape_codec(CHILD))`` and a nested list is
``Value(..., list_codec(shape_codec(CHILD)))``. Two further ``Field``
subclasses used to exist for those, each restating ``Value``'s
required/absent/omit dance with one line changed.

Genuinely irregular fields are still one row each. ``z`` packs four numbers
into one key, the QR task flattens its takeoff into root ``to``/``tc``, and
``T`` names a shape rather than carrying data — each is a :class:`Field`
subclass declared beside the shape that needs it, so the irregularity stays
where it belongs instead of becoming a branch inside a method every other
field also goes through.

Absence is one decision, not two. A field's :class:`Optionality` says both when
an incoming value counts as absent and when an outgoing one is skipped, because
those two answers are the ones that used to be written in different places and
quietly stop matching.
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Generic, Mapping, MutableMapping, TypeVar

from ..exceptions import MalformedPayloadError, pyXCTSKError
from .passthrough import read_passthrough, write_passthrough
from .rounding import round_half_up
from .time_of_day import TimeOfDay

T = TypeVar("T")

#: What a codec may raise when handed a wire value of the wrong type or
#: spelling. Codecs are applied to untrusted input, so this is the one place
#: these are expected rather than bugs: each is converted into a
#: :class:`~pyxctsk.exceptions.MalformedPayloadError` naming where it happened.
_READ_ERRORS = (KeyError, ValueError, TypeError, AttributeError, pyXCTSKError)


def _json_type(value: Any) -> str:
    """Name a decoded JSON value's type the way the format would."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "a boolean"
    if isinstance(value, (int, float)):
        return "a number"
    if isinstance(value, str):
        return "a string"
    if isinstance(value, list):
        return "an array"
    if isinstance(value, Mapping):
        return "an object"
    return type(value).__name__


def require_object(data: Any) -> Mapping[str, Any]:
    """Return a wire value that must be a JSON object, or refuse it.

    Args:
        data: The decoded value.

    Returns:
        The same value, now known to be a mapping.

    Raises:
        MalformedPayloadError: If it is anything else.
    """
    if not isinstance(data, Mapping):
        raise MalformedPayloadError(f"expected an object, got {_json_type(data)}")
    return data


def load_json(text: str | bytes) -> Any:
    """Decode a JSON document, refusing one that is not JSON at all.

    Args:
        text: The document.

    Returns:
        The decoded value, of whatever JSON type it is.

    Raises:
        MalformedPayloadError: If it does not decode.
    """
    try:
        return json.loads(text)
    except ValueError as exc:
        raise MalformedPayloadError(f"not JSON: {exc}") from exc


def _read_at(segment: str, read: Callable[[Any], T], raw: Any) -> T:
    """Run one step of a read, attributing any failure to ``segment``.

    Args:
        segment: The key, or ``[i]`` index, being read.
        read: The step.
        raw: What the step reads.

    Returns:
        What the step returned.

    Raises:
        MalformedPayloadError: Whatever the step raised, located.
    """
    try:
        return read(raw)
    except MalformedPayloadError as exc:
        raise exc.inside(segment) from exc.__cause__
    except KeyError as exc:
        # A required key that is not there. The key itself is the location,
        # which is one level deeper than ``segment`` only when a row reads a
        # key it does not own — so name the key that was missing.
        raise MalformedPayloadError(
            "required key is missing", str(exc.args[0]) if exc.args else segment
        ) from exc
    except _READ_ERRORS as exc:
        raise MalformedPayloadError(str(exc), segment) from exc


@dataclass(frozen=True)
class Codec:
    """How one value is spelled on the wire.

    Attributes:
        to_wire: Model value to JSON value.
        from_wire: JSON value to model value.
    """

    to_wire: Callable[[Any], Any]
    from_wire: Callable[[Any], Any]


def _identity(value: Any) -> Any:
    return value


#: A value the JSON format already carries as-is.
IDENTITY = Codec(_identity, _identity)

#: A number the spec types loosely but this library holds as ``int``. The QR
#: encoding can only carry whole metres, so a fractional radius or altitude is
#: rounded on the way in — see :mod:`pyxctsk.model.rounding` for which way.
ROUNDED_INT = Codec(_identity, round_half_up)

#: An integer a producer may have written as a string.
LENIENT_INT = Codec(
    _identity, lambda raw: raw if isinstance(raw, int) else int(str(raw))
)

#: ``HH:MM:SSZ``, the only time spelling either format uses.
TIME_OF_DAY = Codec(lambda value: value.to_json_string(), TimeOfDay.from_json_string)


def enum_codec(enum_cls: Callable[[Any], Any]) -> Codec:
    """Return a codec for a constrained value.

    Args:
        enum_cls: The enum. Called on the wire value, so an unrecognized one
            raises rather than moving through the library as a bare string.

    Returns:
        Codec: Spelling the enum as its ``value``.
    """
    return Codec(lambda member: member.value, enum_cls)


def wire_int_codec(table: Mapping[Any, int], lenient: bool = False) -> Codec:
    """Return a codec spelling constrained values as the integers a format uses.

    The QR format writes a goal type as ``1`` or ``2`` where the full format
    writes ``"LINE"`` or ``"CYLINDER"``. That is a spelling, not a second kind
    of value, so the QR models hold the same enums as the full ones and this
    codec is where the integers live. They used to be six ``IntEnum`` classes
    and twelve translation tables between them and the model's enums, with a
    default at every call site for whatever a table left out.

    Args:
        table: Each value's wire integer. Must be one-to-one.
        lenient: Also accept an integer written as a string.

    Returns:
        Codec: Writing ``table[value]``, and reading its inverse.
    """
    inverse = {number: value for value, number in table.items()}
    if len(inverse) != len(table):
        raise ValueError(f"wire integers are not one-to-one: {dict(table)!r}")

    def from_wire(raw: Any) -> Any:
        number = LENIENT_INT.from_wire(raw) if lenient else raw
        # ``True == 1`` in Python, and a JSON ``true`` is not the integer one.
        if isinstance(number, bool) or number not in inverse:
            raise ValueError(f"{raw!r} is not one of {sorted(inverse)}")
        return inverse[number]

    return Codec(lambda value: table[value], from_wire)


def list_codec(item: Codec) -> Codec:
    """Return a codec for a JSON array of values.

    Args:
        item: The codec for one element.

    Returns:
        Codec: Applying ``item`` element-wise.
    """

    def from_wire(raw: Any) -> list[Any]:
        # A list is required, not just an iterable: a string where an array
        # belongs used to be read one character at a time, so a single time
        # gate written as ``"12:00:00Z"`` reported "invalid time: '1'".
        if not isinstance(raw, list):
            raise MalformedPayloadError(f"expected an array, got {_json_type(raw)}")
        return [_read_at(f"[{i}]", item.from_wire, r) for i, r in enumerate(raw)]

    return Codec(lambda values: [item.to_wire(v) for v in values], from_wire)


@dataclass(frozen=True)
class Optionality:
    """When a field may be missing, on each side of the wire.

    The two questions are asked in one place because they are the two that
    drifted: a reader that accepted an explicit null beside a writer that
    emitted one, or a key read into an attribute nothing ever wrote back.

    Attributes:
        absent: Over the raw wire value — True means the shape's default
            applies rather than this value.
        omit: Over the model value — True means write no key at all.
        required: If True the key must be present; its absence is a
            ``KeyError`` naming it, not a default.
        carry_unreadable: If True, a *present, non-null* value this field
            declines to read is carried into ``unknown`` instead of being
            dropped — see :meth:`Field.unread`.
    """

    absent: Callable[[Any], bool]
    omit: Callable[[Any], bool]
    required: bool = False
    carry_unreadable: bool = False


#: The key must be there, and is always written.
REQUIRED = Optionality(lambda raw: False, lambda value: False, required=True)

#: Missing or null on the way in, no key on the way out.
OPTIONAL = Optionality(lambda raw: raw is None, lambda value: value is None)

#: As :data:`OPTIONAL`, but an empty value counts as absent too — an empty
#: description or an empty list of time gates says nothing a missing key does
#: not. Note this is what makes ``""`` and absent the same thing on read.
OPTIONAL_EMPTY = Optionality(lambda raw: not raw, lambda value: not value)

#: Optional coming in, always written going out: a field with a default the
#: format still expects to see, such as the obsolete ``direction``.
DEFAULTED = Optionality(lambda raw: raw is None, lambda value: False)


class Field(ABC):
    """One row of a shape's table.

    A row owns a slice of the object and the wire keys that slice occupies —
    keys, plural, because ``z`` is four attributes in one key and the QR
    takeoff is one attribute across two. That is what lets the table stay total
    while the irregular cases stay one row each, and what lets
    :attr:`Shape.keys` be derived rather than restated.
    """

    @property
    @abstractmethod
    def keys(self) -> tuple[str, ...]:
        """Every wire key this row is responsible for."""

    @abstractmethod
    def read(self, data: Mapping[str, Any]) -> dict[str, Any]:
        """Return the constructor arguments this row contributes.

        Args:
            data: The parsed object for the whole shape.

        Returns:
            dict[str, Any]: Keyword arguments, empty when the field is absent
            and the dataclass default should stand.
        """

    @abstractmethod
    def write(self, obj: Any, result: MutableMapping[str, Any]) -> None:
        """Append this row's keys to a payload being built.

        Args:
            obj: The model object being serialized.
            result: The payload so far, appended to in place.
        """

    def unread(self, data: Mapping[str, Any]) -> tuple[str, ...]:
        """Declared keys this row left alone for *this* payload.

        The third state a key can be in, and the one :attr:`Shape.keys` alone
        cannot express. A row's keys are its keys whatever a given payload
        holds, so a row that declares ``g`` and then declines to read a ``g``
        of the wrong shape leaves the value nowhere: the passthrough excludes
        every declared key by construction, so it is neither read nor carried.
        A malformed nested section was therefore *dropped* while the
        optionality declaring it said, in as many words, that it "lands in
        ``unknown`` and travels back out untouched".

        Returns:
            The keys to hand to the passthrough after all. Empty by default,
            which is right for every row that reads whatever it declares.
        """
        return ()


@dataclass(frozen=True)
class Value(Field):
    """One attribute under one key.

    Attributes:
        attr: The dataclass attribute.
        key: The wire key.
        codec: How the value is spelled there.
        optionality: When it may be missing, on each side.
    """

    attr: str
    key: str
    codec: Codec = IDENTITY
    optionality: Optionality = OPTIONAL

    @property
    def keys(self) -> tuple[str, ...]:
        """The single key this row owns."""
        return (self.key,)

    def read(self, data: Mapping[str, Any]) -> dict[str, Any]:
        """Read the key, or nothing if it counts as absent."""
        if self.optionality.required:
            if self.key not in data:
                raise MalformedPayloadError("required key is missing")
            return {self.attr: self.codec.from_wire(data[self.key])}
        raw: Any = data.get(self.key)
        if self.optionality.absent(raw):
            return {}
        return {self.attr: self.codec.from_wire(raw)}

    def write(self, obj: Any, result: MutableMapping[str, Any]) -> None:
        """Write the key, unless the value is one this shape omits."""
        value = getattr(obj, self.attr)
        if self.optionality.omit(value):
            return
        result[self.key] = self.codec.to_wire(value)

    def unread(self, data: Mapping[str, Any]) -> tuple[str, ...]:
        """This key, when it holds a value present but unreadable.

        Null is not unreadable — for an optional section it is exactly how the
        format says "not there" — so only a present, non-null value the
        optionality calls absent is carried.
        """
        if not self.optionality.carry_unreadable or self.key not in data:
            return ()
        raw = data[self.key]
        if raw is None or not self.optionality.absent(raw):
            return ()
        return (self.key,)


@dataclass(frozen=True)
class Discriminator(Field):
    """A key whose presence names the shape rather than carrying data.

    The XC/Waypoints task's ``"T": "W"`` is the whole of it: reading the key is
    how the shape was chosen in the first place, so this row's job on the way
    in is only to state the value that choice implies, and on the way out to
    spell the key that will let a reader make it again.

    Attributes:
        key: The wire key.
        wire_value: What is written there, always.
        attr: The attribute the choice determines.
        model_value: What that attribute is, given this shape was chosen.
    """

    key: str
    wire_value: Any
    attr: str
    model_value: Any

    @property
    def keys(self) -> tuple[str, ...]:
        """The discriminating key."""
        return (self.key,)

    def read(self, data: Mapping[str, Any]) -> dict[str, Any]:
        """State what choosing this shape means, whatever the key held."""
        return {self.attr: self.model_value}

    def write(self, obj: Any, result: MutableMapping[str, Any]) -> None:
        """Write the key that names this shape."""
        result[self.key] = self.wire_value


@dataclass(frozen=True)
class Shape(Generic[T]):
    """The whole mapping between one class and one wire object.

    Attributes:
        cls: What :meth:`read` builds.
        fields: The table, in the order the format writes its keys.
        ext_key: ``extensions`` or ``x`` for the two shapes the spec gives an
            extensions list, None for the rest.
        ignored_keys: Keys read and deliberately discarded rather than carried
            — a key on the allow-list with no row and no attribute. There is
            one, the goal's ``lineLength``, and naming it here is what keeps
            the drop a decision rather than an omission.
        carries_unknown: Whether the class has an ``unknown`` field. False only
            for the one shape that is never handed a payload of its own.
    """

    cls: type[T]
    fields: tuple[Field, ...]
    ext_key: str | None = None
    ignored_keys: frozenset[str] = frozenset()
    carries_unknown: bool = True

    @property
    def keys(self) -> frozenset[str]:
        """Every key this shape understands, derived from its table.

        This is the passthrough allow-list, so it cannot fall out of step with
        what the shape actually reads — the drift that let a whole format's
        keys be swallowed by the shape beside it.
        """
        declared = {key for field in self.fields for key in field.keys}
        if self.ext_key is not None:
            declared.add(self.ext_key)
        return frozenset(declared) | self.ignored_keys

    def read(self, data: Mapping[str, Any]) -> T:
        """Build the object this shape describes.

        Args:
            data: The parsed object for this shape.

        Returns:
            An instance of :attr:`cls`.

        Raises:
            MalformedPayloadError: If ``data`` is not an object, a required
                key is missing, or a value cannot be read — whichever it is,
                naming the path to it.
        """
        data = require_object(data)
        kwargs: dict[str, Any] = {}
        unread: set[str] = set()
        for field in self.fields:
            kwargs.update(_read_at(field.keys[0], field.read, data))
            unread.update(field.unread(data))
        if self.carries_unknown:
            # The allow-list is what this shape read *from this payload*, not
            # what it declares: a row that declined a value of the wrong shape
            # hands its key back so the value is carried rather than eaten.
            extensions, unknown = read_passthrough(
                dict(data), self.keys - unread, self.ext_key
            )
            if self.ext_key is not None:
                kwargs["extensions"] = extensions
            kwargs["unknown"] = unknown
        return self.cls(**kwargs)

    def write(self, obj: T) -> dict[str, Any]:
        """Serialize an object of this shape.

        Keys come out in table order, with extensions and unknown keys last.

        Args:
            obj: The object to serialize.

        Returns:
            dict[str, Any]: The wire object.
        """
        result: dict[str, Any] = {}
        for field in self.fields:
            field.write(obj, result)
        if self.carries_unknown:
            write_passthrough(
                result,
                getattr(obj, "extensions", []),
                obj.unknown,  # type: ignore[attr-defined]
                self.ext_key,
            )
        return result


def shape_codec(shape: "Shape[Any]") -> Codec:
    """Return a nested shape as the codec for one value.

    A ``Shape`` already *is* a codec — :meth:`Shape.write` is ``to_wire`` and
    :meth:`Shape.read` is ``from_wire`` — so a nested object is a :class:`Value`
    with this codec, and a nested list is one with ``list_codec(shape_codec(…))``.

    That is what this replaces. ``Nested`` and ``NestedList`` were two more
    :class:`Field` subclasses whose ``read`` was the same eight lines as
    :class:`Value`'s, differing only in how the raw value was converted, and
    whose ``write`` differed the same way — so the same required/absent/omit
    dance was written three times and a fix to one could miss the others.
    Verified byte-identical over the reference corpus before the two classes
    were deleted.

    Args:
        shape: The child's table.

    Returns:
        Codec: Reading and writing one object of that shape.
    """
    return Codec(shape.write, shape.read)
