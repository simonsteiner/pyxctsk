"""Writing a task out — the counterpart to `parse_task`, and its table.

Reading was one deep module and writing was five spellings with no module: the
mapping *format name → renderer* lived only in an `if/elif` chain inside
`cli.py`, with no `else`, so an unmatched format wrote nothing and exited 0.
The second consumer, `scripts/task_viewer`, re-derived it — including the
six-line PNG incantation and its own media types — which is what made the seam
real rather than hypothetical.
"""

import re

import pytest

from pyxctsk import OUTPUT_FORMATS, parse_task, render_task
from tests.corpus import reference_task
from tests.paths import TESTS_DIR
from tests.qr_test_utils import QR_CODE_SUPPORT


class TestEveryRowRenders:
    """One row per format, and each of them answers for itself."""

    @pytest.mark.parametrize(
        "name",
        [
            pytest.param(
                name,
                marks=pytest.mark.skipif(
                    name == "png" and not QR_CODE_SUPPORT,
                    reason="QR code dependencies not available",
                ),
            )
            for name in sorted(OUTPUT_FORMATS)
        ],
    )
    def test_the_payload_matches_the_rows_declared_kind(self, name):
        """`binary` is what a caller needs before it can open a file."""
        task = reference_task("task_bevo").task
        payload = render_task(task, name)

        expected = bytes if OUTPUT_FORMATS[name].binary else str
        assert isinstance(payload, expected)

    @pytest.mark.parametrize("name", sorted(OUTPUT_FORMATS))
    def test_every_row_declares_a_media_type_and_an_extension(self, name):
        """Both were spelled at each delivery site instead."""
        fmt = OUTPUT_FORMATS[name]

        assert "/" in fmt.media_type
        assert fmt.extension.startswith(".")
        assert fmt.name == name

    def test_an_unknown_format_is_refused(self):
        """It used to be an `elif` chain with no `else`: nothing, exit 0."""
        with pytest.raises(ValueError, match="not an output format"):
            render_task(reference_task("task_bevo").task, "pdf")


class TestTheTableIsTheOnlyStatementOfTheFormats:
    """A format is one row, not a row plus a Choice plus a branch."""

    def test_the_cli_offers_exactly_the_table(self):
        """`click.Choice` used to list the same names a second time."""
        from pyxctsk.cli import convert

        (option,) = [p for p in convert.params if p.name == "output_format"]
        choices = getattr(option.type, "choices", None)

        assert list(choices or []) == list(OUTPUT_FORMATS)

    def test_the_readmes_list_is_the_table(self):
        """S6: the README, CLAUDE.md and `cli.py` each listed four, not five.

        `geojson` was in the table and in `--help` and in none of the prose.
        The README is the list a user reads, so it stays — held to the table.
        """
        readme = (TESTS_DIR.parent / "README.md").read_text(encoding="utf-8")
        (listed,) = re.findall(r"`--format \[([^\]]*)\]`", readme)

        assert listed.split("|") == list(OUTPUT_FORMATS)

    def test_the_task_files_extension_is_the_json_rows(self):
        """The one place the extension is named."""
        assert OUTPUT_FORMATS["json"].extension == ".xctsk"


class TestTheOptionsAndTheReadBack:
    """What a rendering carries through the table: `compressed`, and a read-back."""

    def test_compressed_reaches_the_two_rows_that_read_it(self):
        """And is ignored by the three that do not, without the caller asking."""
        task = reference_task("task_bevo").task

        assert str(render_task(task, "qrcode-json", compressed=True)).startswith(
            "XCTSKZ:"
        )
        assert render_task(task, "json", compressed=True) == task.to_json()

    def test_a_rendered_task_reads_back(self):
        """Round trip through the seam, in every text format that is a task."""
        task = reference_task("task_bevo").task

        for name in ("json", "qrcode-json"):
            assert parse_task(render_task(task, name)).turnpoints
