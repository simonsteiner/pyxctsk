# 2026-08-17 — Package layout: 27 flat modules into four packages

<!-- Commit hashes below are hashes, not words. cspell:ignore caadbdb -->

**Status: applied.** Branch `refactor/package-layout-2026-08-17`, twelve commits.
Full suite green throughout (362 tests before, 357 after — the difference is tests
deleted for asserting nothing, items 7 and 12). This is a record of what changed and
why, not a proposal.

## The friction

`src/pyxctsk/` held 27 modules in one directory. That directory listing is the first
thing any reader — human or agent — sees, and it said nothing about which modules
belonged together. The prefixes were doing a directory's job:

```
qrcode_task.py  qrcode_models.py  qrcode_encoding.py  qrcode_enums.py
qrcode_image.py qrcode_conversion.py
task.py  task_enums.py  task_distances.py
distance.py  turnpoint.py  route_optimization.py  sss_calculations.py
optimization_config.py
kml.py  geojson.py  goal_line.py  visualization_common.py
passthrough.py  validation.py  rounding.py  time_of_day.py
cli.py  parser.py  exceptions.py  __init__.py  __main__.py
```

Three specific costs:

1. **No stated direction.** `distance.py`'s docstring already asked its submodules not
   to import back into it, and `CLAUDE.md` recorded four separate "must not import"
   rules in prose. Prose is the only thing that was enforcing them.
2. **`tests/` had the same problem**, 17 files deep, and no correspondence to the
   source. After changing `qrcode_encoding.py` you had to guess between
   `test_qrcode.py`, `test_spec_conformance.py` and `test_core.py`.
3. **Names carried the grouping**, so every module paid for the grouping in its own
   name: `qrcode/qrcode_task.py` is what the prefix would have become.

## What changed

```
src/pyxctsk/
  __init__.py  __main__.py  cli.py  parser.py  exceptions.py
  model/     task  enums  time_of_day  passthrough  validation  rounding
  qrcode/    task  models  encoding  enums  image  conversion
  distance/  turnpoint  route_optimization  task_distances  sss  goal_line  config
  export/    kml  geojson  common
```

Dependencies run one way:

```
model ──> qrcode
  └────> distance ──> export
```

Each package's `__init__.py` is its interface: it re-exports what callers outside the
package need and describes what the package holds. Modules *inside* a package import
sibling submodules directly, never through the package `__init__` — that rule is what
keeps a partially-initialized package from failing an import halfway.

`tests/` mirrors it — `model/`, `qrcode/`, `distance/`, `export/` — plus
`conformance/` for the spec-audit regressions that deliberately cut across packages,
and `test_cli.py` at the root.

### Two places the plan met reality

**Goal-line geometry went to `distance/`, not `export/`.** The obvious home for
`goal_line.py` is beside the KML and GeoJSON writers that draw it. But
`distance/task_distances.py` needs the rule that a goal line is twice the last
turnpoint's radius, because that is what sizes a LINE goal's cylinder. With
`goal_line.py` in `export/`, that one import made `distance → export → distance` a
real cycle the moment each package got an `__init__` that re-exports its own
submodules — and it failed loudly, on `import pyxctsk`:

```
ImportError: cannot import name 'task_to_turnpoints' from partially
initialized module 'pyxctsk.distance.task_distances'
```

Moving the file down one layer fixed it and is the more honest placement anyway: the
shapes of a task should not live in the package that knows about file formats.

**`qrcode/__init__.py` could not re-export `conversion`** as first written.
`model/task.py` imported `qrcode/task.py` at module level so `Task.to_qr_code_task()`
could exist, and `qrcode/conversion.py` imports `model/task.py`; re-exporting
conversion from the package `__init__` closed that loop on the first `import pyxctsk`.
Resolved in the follow-up pass below by cutting the model's import — see
[Follow-ups](#follow-ups).

Both of these are the kind of thing the flat layout let stay implicit. Packages made
them assertions the interpreter checks.

### Two things that were not about layout

- **`_task_to_turnpoints` → `task_to_turnpoints`.** Private by name only: the export
  package, five test modules and a script all imported it. After the split it crosses
  a package seam, so the underscore was actively lying.
- **Eight tests deleted.** `test_utils.py` mixed CLI coverage with tests asserting that
  `tempfile` creates files, that `json.dumps` returns a string, that `Mock` records
  calls, and one that read `assert True`. They could not fail for any reason a reader
  would care about. The two that did carry weight — the QR support probe answers a
  bool consistent with whether the decoders imported — moved next to the image tests
  they gate.

### One packaging hazard found on the way

Building locally with a stale `build/` directory shipped ghost modules: the wheel
contained `pyxctsk/task.py`, `pyxctsk/distance.py` and even a `pyxctsk/utils.py` that
has not existed in `src/` for a long time, alongside the new packages. setuptools
reuses `build/lib` and never removes what is no longer in the source tree. CI publishes
from a fresh checkout so releases were never affected, but the manual fallback in
`RELEASING.md` now starts with `rm -rf build dist`.

## Progress

- [x] 1. `model/` — task, enums, time_of_day, passthrough, validation, rounding (`617a648`)
- [x] 2. `qrcode/` — task, models, encoding, enums, image, conversion (`b4a34e7`)
- [x] 3. `distance/` — the facade module became the package `__init__` (`e03ce77`)
- [x] 4. `export/` — kml, geojson, common; goal_line moved down to `distance/` (`250fe17`)
- [x] 5. `task_to_turnpoints` made public and named in the distance interface (`2fe8622`)
- [x] 6. `tests/` mirrored to the same shape; `tests/paths.py` added (`85a3ead`)
- [x] 7. Standard-library self-tests deleted; QR probe checks moved — 362 → 354 tests (`8ecb0ce`)
- [x] 8. Docs: CLAUDE.md, README, CHANGELOG, RELEASING, this review

Verified at each step: `uv run pytest`, `ruff check`, `ruff format`, `mypy` (strict),
plus `import pyxctsk.<pkg>` for all four packages in isolation — a package-level cycle
only shows up when a specific submodule is the entry point, which the test suite does
not exercise on its own.

## Follow-ups

All four were taken on in a second pass on the same branch.

- [x] 9. **The `model → qrcode` back edge is gone** (`017fa45`). It existed for one
  method: `Task.to_qr_code_task()`, whose return type and delegation pulled
  `qrcode/task.py` into the model at module level. The method now reaches
  `qrcode.conversion.task_to_qr_code_task` through a function-local import and the
  annotation through `TYPE_CHECKING`, so `model` imports nothing else in the package,
  `conversion` sits cleanly above both, and the qrcode facade can finally name it.
  Public API unchanged.
- [x] 10. **The layering is asserted, not described** (`caadbdb`).
  `tests/test_layering.py` parses every module and checks the layer rules, the
  sibling-import rule, and that the function-local imports inside the packages are
  exactly the two known cycle-breakers (only one of which crosses a package
  boundary — a distinction the first version of the test blurred, see #12). Each check was confirmed to fail when its rule is
  broken — the sibling-import check was rewritten after the first version passed a
  real violation (`from ..export.common import x` from inside `export/`).
- [x] 11. **`export/common.py` pruned, and a latent defect fixed** (`3521cfb`).
  `is_goal_turnpoint` searched the turnpoint list by value; `Turnpoint` is a plain
  dataclass, so a task that ends by flying the same turnpoint twice matched the
  earlier occurrence and drew its goal in the default blue. Now compared by identity,
  with a regression test that fails on the old implementation. The reference corpus
  never hit it: the ess-goal fixtures duplicate their final waypoint but differ in
  `type`. Also deleted `get_route_coordinates_with_fallback` (no callers), and the
  module docstring now says why the cylinder outline here is a planar approximation
  while everything a distance depends on is geodesic.
- [x] 12. **The three distance test files have distinct jobs** (`ba7ab11`).
  `test_distance.py` → `test_xctrack_accuracy.py` (our numbers vs XCTrack's),
  `test_reference.py` → `test_task_distances.py` (the pipeline above the optimizer),
  and `test_route_optimization.py` unchanged (internals). Two subsumed tests deleted:
  a precision check running 1% on two tasks where the accuracy file already asserts 1%
  on every task, and a smoke test bracketing one task's distance between 100 and
  200 km. 359 → 357 tests.

Still open, deliberately:

- **`export/common.py` remains one module** rather than being split into geometry and
  styling. After pruning, what is left is exactly the four questions both writers must
  answer identically plus the cylinder polygon — splitting that would create two
  shallow modules and a decision about which one a writer asks first.
- **Old reviews in this directory use pre-split import paths** in their code snippets.
  Only the 2026-07-07 findings doc, whose snippets are meant to be run, was updated;
  the rest are left as written.
