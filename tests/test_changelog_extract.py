"""Tests for ``scripts/changelog_extract.py``, where a release's notes come from.

A section runs to the next *version* heading. It used to end at any ``## ``
heading (S7), so a ``## Migration`` inside a release cut its notes short and
made ``roll`` call a non-empty ``[Unreleased]`` empty.

``scripts/`` is repository-only, so the sdist ``scripts/verify.sh`` tests from
does not carry it; the module skips there.
"""

import datetime
import importlib.util
from types import ModuleType

import pytest

from tests.paths import TESTS_DIR

SCRIPT = TESTS_DIR.parent / "scripts" / "changelog_extract.py"

if not SCRIPT.is_file():
    pytest.skip("scripts/ is not in the sdist", allow_module_level=True)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("changelog_extract", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


changelog_extract = _load()

DATE = datetime.date(2026, 10, 2)


class TestASectionRunsToTheNextVersion:
    """Only a version heading ends a section."""

    def test_a_subsection_belongs_to_its_release(self):
        """S7: the notes stopped at ``## Migration``."""
        text = (
            "## [v1.1.0] - 2026-02-01\n- b\n\n## Migration\n- m\n\n"
            "## [v1.0.0] - 2026-01-01\n- a\n"
        )

        assert changelog_extract.extract(text, "1.1.0") == "- b\n\n## Migration\n- m"

    def test_the_last_section_runs_to_the_end_of_the_file(self):
        """With no version after it, anything below is its own."""
        text = "## [v1.0.0] - 2026-01-01\n- a\n\n## Links\n- l\n"

        assert changelog_extract.extract(text, "1.0.0") == "- a\n\n## Links\n- l"


class TestRolling:
    """``roll`` renames ``[Unreleased]`` to a dated version."""

    def test_unreleased_holding_only_a_subsection_is_not_empty(self):
        """S7: a ``## `` line ended the section before its content."""
        text = "## [Unreleased]\n\n## Migration\n- m\n\n## [v1.0.0] - 2026-01-01\n"

        rolled = changelog_extract.roll(text, "1.1.0", DATE)

        assert rolled.startswith(
            "## [Unreleased]\n\n## [v1.1.0] - 2026-10-02\n\n## Migration\n- m\n"
        )
        assert changelog_extract.extract(rolled, "1.1.0") == "## Migration\n- m"

    def test_an_empty_unreleased_section_is_refused(self):
        """Nothing to release is an error, not an empty release."""
        text = "## [Unreleased]\n\n## [v1.0.0] - 2026-01-01\n- a\n"

        with pytest.raises(SystemExit, match="empty"):
            changelog_extract.roll(text, "1.1.0", DATE)
