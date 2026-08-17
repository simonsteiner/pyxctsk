"""Where the test data lives.

Test modules sit at varying depths under ``tests/`` — ``tests/model/``,
``tests/qrcode/``, ``tests/conformance/`` — so none of them should be counting
directory levels back to the fixtures. They import these constants instead.
"""

from pathlib import Path

#: The ``tests/`` directory itself.
TESTS_DIR = Path(__file__).parent

#: Everything the suite reads.
DATA_DIR = TESTS_DIR / "data"

#: Reference corpus, one directory per representation of the same tasks.
REFERENCE_TASKS_DIR = DATA_DIR / "reference_tasks"
REFERENCE_XCTSK_DIR = REFERENCE_TASKS_DIR / "xctsk"
REFERENCE_JSON_DIR = REFERENCE_TASKS_DIR / "json"
REFERENCE_QRCODE_DIR = REFERENCE_TASKS_DIR / "qrcode_string"

#: Fixture sets that fill shapes the exported corpus misses; each has a README.
ESS_GOAL_DIR = REFERENCE_TASKS_DIR / "ess-goal"
ELEVATED_GOAL_DIR = REFERENCE_TASKS_DIR / "elevated-goal"
