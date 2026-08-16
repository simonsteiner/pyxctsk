"""Tests for the extensions/unknown passthrough helpers.

These two functions are the only implementation of the passthrough rules that
every model relies on, so the rules are pinned here rather than re-tested once
per model. The model-level round-trips live in ``test_spec_conformance.py`` and
``test_elevated_goal_fixtures.py``.
"""

import pytest

from pyxctsk.passthrough import (
    EXTENSIONS_KEY,
    QR_EXTENSIONS_KEY,
    read_passthrough,
    write_passthrough,
)

KNOWN = frozenset({"radius", "waypoint", "extensions"})


class TestReadPassthrough:
    """Splitting a payload into extensions and the unknown remainder."""

    def test_splits_known_from_unknown(self):
        """Anything outside the allow-list is unknown; the rest is untouched."""
        extensions, unknown = read_passthrough(
            {"radius": 400, "extensions": [{"id": "ACME"}], "o": {"fa": 1220}},
            KNOWN,
            EXTENSIONS_KEY,
        )

        assert extensions == [{"id": "ACME"}]
        assert unknown == {"o": {"fa": 1220}}

    def test_absent_extensions_yield_an_empty_list(self):
        """A missing optional list must not become None."""
        extensions, unknown = read_passthrough({"radius": 400}, KNOWN, EXTENSIONS_KEY)

        assert extensions == []
        assert unknown == {}

    def test_null_extensions_yield_an_empty_list(self):
        """An explicit null is as good as absent."""
        extensions, _ = read_passthrough({"extensions": None}, KNOWN, EXTENSIONS_KEY)

        assert extensions == []

    def test_returns_fresh_containers(self):
        """Mutating the result must not reach back into the parsed payload."""
        data = {"extensions": [{"id": "ACME"}], "o": 1}
        extensions, unknown = read_passthrough(data, KNOWN, EXTENSIONS_KEY)

        extensions.append({"id": "OTHER"})
        unknown["p"] = 2

        assert data["extensions"] == [{"id": "ACME"}]
        assert "p" not in data

    def test_qr_format_uses_its_own_extensions_key(self):
        """The QR format spells extensions "x"; "extensions" is then unknown."""
        extensions, unknown = read_passthrough(
            {"n": "TP", "x": [{"id": "ACME"}]},
            frozenset({"n", "x"}),
            QR_EXTENSIONS_KEY,
        )

        assert extensions == [{"id": "ACME"}]
        assert unknown == {}


class TestWritePassthrough:
    """Appending extensions and unknown keys to a serialized model."""

    def test_appends_both_after_the_spec_fields(self):
        """Extensions come last, matching the order the spec lists them in."""
        result = {"radius": 400}
        write_passthrough(result, [{"id": "ACME"}], {"o": 1}, EXTENSIONS_KEY)

        assert list(result) == ["radius", "extensions", "o"]

    def test_empty_extensions_emit_no_key(self):
        """An optional list must stay absent rather than become []."""
        result = {"radius": 400}
        write_passthrough(result, [], {}, EXTENSIONS_KEY)

        assert result == {"radius": 400}

    def test_unknown_never_shadows_a_key_the_model_wrote(self):
        """A key pyxctsk understands wins over carried-through data.

        Letting a look-alike key overwrite a spec field would turn a value we
        merely failed to understand into one we report wrongly.
        """
        result = {"taskType": "CLASSIC"}
        write_passthrough(result, [], {"taskType": "NONSENSE", "o": 1}, EXTENSIONS_KEY)

        assert result["taskType"] == "CLASSIC"
        assert result["o"] == 1

    def test_unknown_cannot_shadow_extensions_either(self):
        """A real extensions list wins over an unknown key of the same name."""
        result: dict = {}
        write_passthrough(
            result, [{"id": "ACME"}], {"extensions": "rogue"}, EXTENSIONS_KEY
        )

        assert result["extensions"] == [{"id": "ACME"}]

    @pytest.mark.parametrize("ext_key", [EXTENSIONS_KEY, QR_EXTENSIONS_KEY])
    def test_unknown_cannot_become_the_extensions_key(self, ext_key):
        """With nothing to write, the shadowing rule alone is not enough.

        "A key the model already wrote wins" only protects keys that are
        *there*. An empty extensions list writes nothing, so an
        ``unknown[ext_key]`` used to sail through ``setdefault`` and land in
        the output as the extensions field — a value of any shape occupying a
        key the spec defines as a list.
        """
        result: dict = {}
        write_passthrough(result, [], {ext_key: "rogue", "o": 1}, ext_key)

        assert ext_key not in result
        assert result == {"o": 1}
