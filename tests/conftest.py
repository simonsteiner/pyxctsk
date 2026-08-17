"""Fixtures shared across the suite.

Almost everything the suite needs from the reference corpus it now asks
``tests/corpus.py`` for directly — one discovery, one pairing rule, one sort
order. What is left here is the one fixture that has to *search* the corpus
rather than name a task in it.

Twelve fixtures used to live here, five of them dead and two of them
(``bevo_task``, ``temp_xctsk_file``) the very duplication the tests were
suffering from. A fixture file is also a poor home for a function: this one
exported ``find_xctsk_files`` as a plain alias, which ``test_codec`` imported
directly, so it served two interfaces at once.
"""

import pytest

from pyxctsk import Task, TurnpointType
from tests.corpus import reference_tasks


@pytest.fixture
def sss_task() -> Task:
    """Return a reference task that has an SSS turnpoint.

    Searched rather than named, so the fixture keeps working if the corpus
    changes which of its tasks start a speed section.
    """
    for reference in reference_tasks():
        if any(tp.type == TurnpointType.SSS for tp in reference.task.turnpoints):
            return reference.task
    pytest.skip("no reference task defines an SSS turnpoint")
    raise AssertionError("unreachable")
