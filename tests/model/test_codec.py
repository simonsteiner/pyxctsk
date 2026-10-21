"""Tests for the wire-scalar codecs and the combinators built from them."""

import pytest

from pyxctsk import MalformedPayloadError
from pyxctsk.model.codec import (
    INTEGER,
    LATITUDE,
    LONGITUDE,
    NUMBER,
    TEXT,
    TIME_OF_DAY,
    WHOLE_METRES,
    enum_codec,
    list_codec,
)
from pyxctsk.model.shape import (
    Value,
)
from pyxctsk.model.task import TurnpointType


class TestWireScalars:
    """One rule per kind of scalar, and every scalar row reads through one.

    The table used to check containers and trust scalars, so a bad scalar
    parsed and failed where it was first used. The end-to-end reproductions
    are in ``tests/conformance/test_parser_diagnostics.py``; these pin the
    rules themselves.
    """

    @pytest.mark.parametrize("raw", ["2", 2])
    def test_an_integer_may_be_spelled_as_a_string(self, raw):
        """Producers have written the QR version and earth model as strings."""
        assert INTEGER.from_wire(raw) == 2

    @pytest.mark.parametrize("raw", [2.0, "2.0", "2e0"])
    def test_an_integral_float_is_the_integer_it_spells(self, raw):
        """A producer holding a double writes ``2.0``; it is read back as 2."""
        value = INTEGER.from_wire(raw)
        assert value == 2
        assert type(value) is int

    @pytest.mark.parametrize("raw", [True, 2.5, "2.5", None, [2]])
    def test_an_integer_is_nothing_else(self, raw):
        """``True == 1`` in Python, and ``2.5`` is not a whole number."""
        with pytest.raises(MalformedPayloadError, match="expected an integer"):
            INTEGER.from_wire(raw)

    @pytest.mark.parametrize("raw", ["700", "699.5", 700, 699.5])
    def test_whole_metres_accept_either_spelling(self, raw):
        """Burnair writes a turnpoint radius as a string."""
        assert WHOLE_METRES.from_wire(raw) == 700

    @pytest.mark.parametrize(
        "raw", [True, "inf", "nan", float("inf"), float("nan"), 10**400, "wide", []]
    )
    def test_a_number_is_finite_and_not_a_boolean(self, raw):
        """Each of these used to reach the model, or ``OverflowError`` out."""
        with pytest.raises(MalformedPayloadError, match="expected a"):
            NUMBER.from_wire(raw)
        with pytest.raises(MalformedPayloadError, match="expected a"):
            WHOLE_METRES.from_wire(raw)

    @pytest.mark.parametrize("raw", [1220, 1220.5])
    def test_a_number_keeps_its_json_type(self, raw):
        """What was read is what is written, so outputs stay byte-identical."""
        assert type(NUMBER.from_wire(raw)) is type(raw)

    @pytest.mark.parametrize("raw", [" 700 ", "1_000", "\u0663", "0x10", "+5", "07"])
    def test_a_numeric_string_is_in_json_number_grammar(self, raw):
        """Python's ``int`` reads all of these; JSON spells none of them."""
        with pytest.raises(MalformedPayloadError, match="expected a number"):
            NUMBER.from_wire(raw)

    def test_a_refused_value_is_not_echoed_in_full(self):
        """A 5 000-digit altitude made a 5 000-character message."""
        with pytest.raises(MalformedPayloadError) as caught:
            NUMBER.from_wire("9" * 5000)

        assert len(str(caught.value)) < 100

    def test_a_number_spelled_as_a_string_reads_as_the_number(self):
        """An integer string is an integer, anything else a float."""
        assert type(NUMBER.from_wire("46")) is int
        assert NUMBER.from_wire("46.5") == 46.5

    @pytest.mark.parametrize(
        ("codec", "raw"),
        [(LATITUDE, 90.0001), (LATITUDE, -95), (LONGITUDE, 180.5), (LONGITUDE, -181)],
    )
    def test_a_coordinate_is_on_the_earth(self, codec, raw):
        """Off the earth reached the solver's assert instead."""
        with pytest.raises(MalformedPayloadError, match="is outside"):
            codec.from_wire(raw)

    @pytest.mark.parametrize(("codec", "raw"), [(LATITUDE, -90), (LONGITUDE, 180)])
    def test_the_poles_and_the_antimeridian_are_on_the_earth(self, codec, raw):
        """The range is closed."""
        assert codec.from_wire(raw) == raw

    @pytest.mark.parametrize("raw", [123, True, None, ["A"]])
    def test_text_is_a_string(self, raw):
        """A numeric name broke the text report's format string."""
        with pytest.raises(MalformedPayloadError, match="expected a string"):
            TEXT.from_wire(raw)

    def test_text_is_what_utf8_can_carry(self):
        """A lone surrogate is valid JSON and cannot be written back out."""
        with pytest.raises(MalformedPayloadError, match="not valid text"):
            TEXT.from_wire("A\ud800")

    def test_text_is_kept_as_is(self):
        """Non-ASCII is text, not a problem."""
        assert TEXT.from_wire("Château") == "Château"

    def test_a_row_names_its_codec(self):
        """There is no pass-through default for a value to slip through.

        ``Value`` used to default to an identity codec, which is how ``name``,
        ``lat``, ``lon``, ``version`` and ``fa`` reached the model unchecked.
        """
        with pytest.raises(TypeError):
            Value("label", "l")  # type: ignore[call-arg]


class TestCodecs:
    """The value spellings both formats share."""

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
