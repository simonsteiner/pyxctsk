"""The reference corpus, discovered once.

``tests/paths.py`` says *where* the corpus lives. This says *what it is*: three
parallel directories keyed by task stem — the input `.xctsk`, the reference
metadata with its pre-computed distances, and the expected ``XCTSK:`` string —
which together describe one task in three representations.

The pairing rule used to be re-implemented per consumer: the accuracy tests
globbed and sorted, ``test_task_distances`` globbed unsorted into a
differently-shaped dict, ``test_codec`` paired two directories inline twice, and
``test_spec_conformance`` parametrized over the QR strings alone. Four
discoveries, two sort orders, and nothing that could notice the corpus was not
in step with itself — which it was not: ``qrcode_string/task_dami.txt`` was a
byte-identical copy of ``task_dami_route.txt`` under a stem no task had, and
only one of the four consumers ever saw it.

Integrity is checked here, at discovery, so a half-added task is a collection
error naming the missing file rather than a test that quietly covers less.
"""

import json
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

from pyxctsk import Task, parse_task
from tests.paths import (
    REFERENCE_JSON_DIR,
    REFERENCE_QRCODE_DIR,
    REFERENCE_XCTSK_DIR,
)


class CorpusError(AssertionError):
    """The three directories are not in step."""


@dataclass(frozen=True)
class ReferenceTask:
    """One task in all three of its representations.

    Attributes:
        stem: The task name the three directories key on.
        xctsk_path: The input ``.xctsk`` file.
        json_path: The reference metadata, as the producer exported it.
        qrcode_path: The expected ``XCTSK:`` string.
    """

    stem: str
    xctsk_path: Path
    json_path: Path
    qrcode_path: Path

    def __str__(self) -> str:
        """Return the stem, so pytest ids read as task names."""
        return self.stem

    @cached_property
    def task(self) -> Task:
        """The parsed task."""
        return parse_task(str(self.xctsk_path))

    @cached_property
    def reference(self) -> dict[str, Any]:
        """The whole reference JSON document."""
        with open(self.json_path) as handle:
            data: dict[str, Any] = json.load(handle)
        return data

    @property
    def metadata(self) -> dict[str, Any]:
        """The reference JSON's ``metadata`` block."""
        block: dict[str, Any] = self.reference["metadata"]
        return block

    @cached_property
    def qr_string(self) -> str:
        """The expected ``XCTSK:`` string, whitespace stripped."""
        return self.qrcode_path.read_text().strip()

    @cached_property
    def is_waypoints_format(self) -> bool:
        """Whether the source file is an XC/Waypoints task.

        Read off the file rather than the parsed task, because it is a fact
        about how the producer wrote it: the simplified shape is identified by
        a root ``T``.
        """
        return "T" in json.loads(self.xctsk_path.read_text())

    @property
    def reference_optimized_km(self) -> float | None:
        """The producer's optimized distance, where it recorded one."""
        value: float | None = self.metadata.get("distance_optimized_km")
        return value


def _check_in_step() -> None:
    """Raise if any stem is missing one of its three files."""
    found = {
        "xctsk": {p.stem for p in REFERENCE_XCTSK_DIR.glob("*.xctsk")},
        "json": {p.stem for p in REFERENCE_JSON_DIR.glob("*.json")},
        "qrcode_string": {p.stem for p in REFERENCE_QRCODE_DIR.glob("*.txt")},
    }
    every_stem = set().union(*found.values())
    missing = {
        name: sorted(every_stem - stems)
        for name, stems in found.items()
        if every_stem - stems
    }
    if missing:
        raise CorpusError(
            f"reference corpus is not in step, stems missing a file: {missing}"
        )


def reference_tasks() -> list[ReferenceTask]:
    """Return every task in the corpus, in one stable order.

    Returns:
        list[ReferenceTask]: Sorted by stem, one entry per task.

    Raises:
        CorpusError: If the three directories disagree about which tasks exist.
    """
    _check_in_step()
    return [
        ReferenceTask(
            stem=path.stem,
            xctsk_path=path,
            json_path=REFERENCE_JSON_DIR / f"{path.stem}.json",
            qrcode_path=REFERENCE_QRCODE_DIR / f"{path.stem}.txt",
        )
        for path in sorted(REFERENCE_XCTSK_DIR.glob("*.xctsk"))
    ]


def reference_task(stem: str) -> ReferenceTask:
    """Return one task of the corpus by name.

    Args:
        stem: The task name the three directories key on, e.g. ``task_bevo``.

    Returns:
        ReferenceTask: That task in all three representations.

    Raises:
        CorpusError: If no task of that name is in the corpus.
    """
    for task in reference_tasks():
        if task.stem == stem:
            return task
    raise CorpusError(f"no reference task named {stem!r}")


def tasks_with_reference_distance() -> list[ReferenceTask]:
    """Return the tasks whose metadata carries an optimized distance.

    Not every reference task does — the XC/Waypoints ones have no course to
    optimize — so the accuracy tests take this subset rather than skipping
    inside the test body.

    Returns:
        list[ReferenceTask]: Those with a ``distance_optimized_km``.
    """
    return [t for t in reference_tasks() if t.reference_optimized_km]
