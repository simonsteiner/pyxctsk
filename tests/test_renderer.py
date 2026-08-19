"""Writing a task out — the counterpart to `parse_task`, and its table.

Reading was one deep module and writing was five spellings with no module: the
mapping *format name → renderer* lived only in an `if/elif` chain inside
`cli.py`, with no `else`, so an unmatched format wrote nothing and exited 0.
The second consumer, `scripts/task_viewer`, re-derived it — including the
six-line PNG incantation and its own media types — which is what made the seam
real rather than hypothetical.
"""

import json
import re

import pytest

from pyxctsk import OUTPUT_FORMATS, parse_task, render_task
from tests.corpus import reference_task, reference_tasks


class TestEveryRowRenders:
    """One row per format, and each of them answers for itself."""

    @pytest.mark.parametrize("name", sorted(OUTPUT_FORMATS))
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

    def test_the_task_files_extension_and_media_type_are_the_json_row(self):
        """Two literals at the front door, exported and read by nothing."""
        import pyxctsk

        assert pyxctsk.EXTENSION == OUTPUT_FORMATS["json"].extension
        assert pyxctsk.MIME_TYPE == OUTPUT_FORMATS["json"].media_type


class TestTheRenderingsAreWhatTheyAlwaysWere:
    """The table is a seam, not a change of output."""

    @staticmethod
    def _without_element_ids(kml: str) -> str:
        """Element ids come from a process-global counter in simplekml.

        So two renders of one task differ in every `id="N"` and the
        `<styleUrl>#N</styleUrl>` pointing at it, and in nothing else. Not this
        seam's doing, and not worth asserting about.
        """
        return re.sub(r"(?<=id=\")\d+|(?<=>#)\d+", "N", kml)

    @pytest.mark.parametrize("reference", reference_tasks(), ids=str)
    def test_each_row_agrees_with_the_call_it_replaced(self, reference):
        """Byte-for-byte, across the whole corpus."""
        from pyxctsk import generate_task_geojson, task_to_kml

        task = reference.task

        assert render_task(task, "json") == task.to_json()
        assert self._without_element_ids(
            str(render_task(task, "kml"))
        ) == self._without_element_ids(task_to_kml(task))
        assert json.loads(str(render_task(task, "geojson"))) == generate_task_geojson(
            task
        )
        assert render_task(task, "qrcode-json") == task.to_qr_code_task().to_string()

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
