# Reference tasks

Real competition tasks from tools.xcontest.org, each in three representations
keyed by the task's stem:

- `xctsk/`: the task file (`.xctsk`), the input.
- `json/`: the reference metadata, with the distances XCTrack published for it.
- `qrcode_string/`: the expected `XCTSK:` string.

Tests reach these only through [`tests/corpus.py`](../../corpus.py), which pairs
the three directories and fails collection when one is missing a task; the
paths themselves are in [`tests/paths.py`](../../paths.py). Never glob them.

Two fixture sets cover what the corpus doesn't, each with its own README:

- [`ess-goal/`](ess-goal/README.md): how the ESS relates to the goal.
- [`elevated-goal/`](elevated-goal/README.md): a goal above the ground.

The expected values were scraped from each task's tools.xcontest.org page
([`scripts/extract_task_data.py`](../../../scripts/extract_task_data.py)), and
no test regenerates them: never hand-edit them to make a test pass. A mismatch
is a finding to report.
