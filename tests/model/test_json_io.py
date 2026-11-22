"""``load_json`` reads only what ``dump_json`` can write, and the reverse."""

import math

import pytest

from pyxctsk.exceptions import MalformedPayloadError
from pyxctsk.model.json_io import MAX_NESTING, dump_json, load_json

_LAYOUTS = ["compact", "line", "indented"]


def _nested(depth: int) -> str:
    return "[" * depth + "]" * depth


class TestLoadRefuses:
    """Each refusal is a ``MalformedPayloadError`` at the value's path."""

    @pytest.mark.parametrize(
        ("text", "path"),
        [
            ('{"x": NaN}', "x"),
            ('{"x": [1, Infinity]}', "x[1]"),
            ('{"x": -Infinity}', "x"),
            ('{"x": 1e999}', "x"),
            ('{"a": {"b": [{"c": NaN}]}}', "a.b[0].c"),
            ("[NaN]", "[0]"),
        ],
    )
    def test_a_number_json_cannot_write(self, text, path):
        """A number json cannot write."""
        with pytest.raises(MalformedPayloadError) as caught:
            load_json(text)
        assert caught.value.path == path

    @pytest.mark.parametrize(
        ("text", "path"),
        [
            ('{"x": "\\ud800"}', "x"),
            ('{"x": ["ok", "\\udc00"]}', "x[1]"),
            ('{"\\ud800": 1}', "\\ud800"),
            ('"\\ud800"', ""),
        ],
    )
    def test_a_string_utf8_cannot_carry(self, text, path):
        """A string utf8 cannot carry."""
        with pytest.raises(MalformedPayloadError) as caught:
            load_json(text)
        assert caught.value.path == path

    def test_nesting_past_the_bound(self):
        """Nesting past the bound."""
        with pytest.raises(MalformedPayloadError, match="nested"):
            load_json(_nested(MAX_NESTING + 1))

    def test_nesting_too_deep_for_the_decoder(self):
        """Nesting too deep for the decoder."""
        with pytest.raises(MalformedPayloadError, match="nested"):
            load_json(_nested(100_000))

    def test_not_json_at_all(self):
        """Not json at all."""
        with pytest.raises(MalformedPayloadError, match="not JSON"):
            load_json("{")


class TestDumpRefuses:
    """A value built in code is held to the same limits."""

    @pytest.mark.parametrize("layout", _LAYOUTS)
    @pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
    def test_a_non_finite_number(self, bad, layout):
        """A non finite number."""
        with pytest.raises(MalformedPayloadError) as caught:
            dump_json({"a": [1.0, bad]}, layout=layout)
        assert caught.value.path == "a[1]"

    def test_a_lone_surrogate_in_a_value_or_a_key(self):
        """A lone surrogate in a value or a key."""
        with pytest.raises(MalformedPayloadError) as caught:
            dump_json({"a": "\ud800"}, layout="compact")
        assert caught.value.path == "a"
        with pytest.raises(MalformedPayloadError):
            dump_json({"\ud800": 1}, layout="compact")

    def test_nesting_past_the_bound(self):
        """Nesting past the bound."""
        value: object = []
        for _ in range(MAX_NESTING):
            value = [value]
        with pytest.raises(MalformedPayloadError, match="nested"):
            dump_json(value, layout="compact")


class TestAcceptedValuesRoundTrip:
    """What both directions accept survives the trip."""

    @pytest.mark.parametrize("layout", _LAYOUTS)
    def test_what_load_returns_dump_writes_and_load_reads_again(self, layout):
        """What load returns dump writes and load reads again."""
        text = '{"a": [1, 2.5, -0.0, "caf\\u00e9", null, true], "b": {"c": {}}}'
        value = load_json(text)

        assert load_json(dump_json(value, layout=layout)) == value

    def test_nesting_at_the_bound_is_accepted(self):
        """Nesting at the bound is accepted."""
        value = load_json(_nested(MAX_NESTING))

        assert dump_json(value, layout="compact") == _nested(MAX_NESTING)

    def test_a_big_integer_below_float_overflow(self):
        """A big integer below float overflow."""
        assert (
            load_json("123456789012345678901234567890")
            == 123456789012345678901234567890
        )
