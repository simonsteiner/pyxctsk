"""Tests for the reference corpus adapter.

``tests/corpus.py`` is the only thing that knows how the three directories pair
up, so the pairing and its integrity check are pinned here rather than implied
by whichever consumer happens to notice.
"""

import pytest

from tests.corpus import (
    CorpusError,
    ReferenceTask,
    reference_task,
    reference_tasks,
    tasks_with_reference_distance,
)


class TestDiscovery:
    """One discovery, one order, one pairing rule."""

    def test_every_task_has_all_three_representations(self):
        """The pairing is the whole point of the adapter."""
        for reference in reference_tasks():
            assert reference.xctsk_path.exists()
            assert reference.json_path.exists()
            assert reference.qrcode_path.exists()

    def test_the_order_is_stable(self):
        """Two consumers used to sort differently; now there is one order."""
        stems = [r.stem for r in reference_tasks()]

        assert stems == sorted(stems)

    def test_a_task_can_be_asked_for_by_name(self):
        """Named lookups beat building a path in each test."""
        assert reference_task("task_bevo").stem == "task_bevo"

    def test_an_unknown_name_is_an_error_not_a_skip(self):
        """A typo in a stem must fail rather than quietly cover nothing."""
        with pytest.raises(CorpusError, match="no reference task"):
            reference_task("task_that_does_not_exist")

    def test_the_stem_is_the_pytest_id(self):
        """Parametrized failures name the task, not a memory address."""
        assert str(reference_task("task_bevo")) == "task_bevo"


class TestIntegrity:
    """An orphan is a collection error, not a quietly narrower test run."""

    def test_a_stem_missing_a_file_is_reported(self, tmp_path, monkeypatch):
        """The check names both the directory and the stem.

        ``qrcode_string/task_dami.txt`` was a byte-identical copy of
        ``task_dami_route.txt`` under a stem no task had. One consumer
        exercised it and three could not see it, and nothing anywhere asserted
        the three directories were in step.
        """
        import tests.corpus as corpus

        for name in ("xctsk", "json", "qrcode_string"):
            (tmp_path / name).mkdir()
        (tmp_path / "xctsk" / "task_one.xctsk").write_text("{}")
        (tmp_path / "json" / "task_one.json").write_text("{}")
        (tmp_path / "qrcode_string" / "task_one.txt").write_text("XCTSK:{}")
        (tmp_path / "qrcode_string" / "task_orphan.txt").write_text("XCTSK:{}")

        monkeypatch.setattr(corpus, "REFERENCE_XCTSK_DIR", tmp_path / "xctsk")
        monkeypatch.setattr(corpus, "REFERENCE_JSON_DIR", tmp_path / "json")
        monkeypatch.setattr(corpus, "REFERENCE_QRCODE_DIR", tmp_path / "qrcode_string")

        with pytest.raises(CorpusError, match="task_orphan"):
            corpus.reference_tasks()

    def test_the_real_corpus_is_in_step(self):
        """Which is what every other consumer relies on."""
        assert len(reference_tasks()) == 24


class TestRepresentations:
    """What each record can be asked for."""

    def test_the_task_parses(self):
        """The record hands back a parsed task, not a path to one."""
        assert reference_task("task_bevo").task.turnpoints

    def test_the_metadata_is_the_producers(self):
        """The reference JSON's metadata block, not our own computation."""
        assert reference_task("task_bevo").metadata["file_name"] == "bevo"

    def test_the_qr_string_is_stripped(self):
        """Consumers compare it to generated output, which has no newline."""
        qr_string = reference_task("task_bevo").qr_string

        assert qr_string.startswith("XCTSK:")
        assert qr_string == qr_string.strip()

    def test_the_shape_is_read_off_the_source_file(self):
        """A fact about how the producer wrote it, not about our parse."""
        assert reference_task("task_dami_route").is_waypoints_format
        assert not reference_task("task_bevo").is_waypoints_format

    def test_only_some_tasks_carry_a_reference_distance(self):
        """The waypoints ones have no course to optimize."""
        with_distance = tasks_with_reference_distance()

        assert len(with_distance) == 22
        assert all(not r.is_waypoints_format for r in with_distance)

    def test_a_record_is_hashable_and_comparable(self):
        """It is a frozen value, so it can be a parametrize argument."""
        assert isinstance(reference_task("task_bevo"), ReferenceTask)
        assert reference_task("task_bevo") == reference_task("task_bevo")
