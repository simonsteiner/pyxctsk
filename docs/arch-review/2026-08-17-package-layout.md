# 2026-08-17 — Package layout: 27 flat modules into four packages

**Status: applied.** Branch `refactor/package-layout-2026-08-17`, eight commits.
Full suite green throughout (362 tests before, 354 after — see [Progress](#progress),
item 7). This is a record of what changed and why, not a proposal.

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

**`qrcode/__init__.py` deliberately does not re-export `conversion`.** `model/task.py`
imports `qrcode/task.py` at module level so `Task.to_qr_code_task()` can exist, and
`qrcode/conversion.py` imports `model/task.py`. Re-exporting conversion from the
package `__init__` would close that loop on the first `import pyxctsk`. The `__init__`
says so, in the file, so the next person to "tidy up the exports" finds out before CI
does.

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

## Follow-ups, not done here

- **`model → qrcode` is the one remaining back edge.** `Task.to_qr_code_task()` is why
  the domain model imports a serialization format. Cutting it means either a lazy
  import inside the method (the idiom the 2026-08-16 review removed from
  `qrcode_task.py`, in the other direction) or dropping the convenience method in
  favour of `pyxctsk.qrcode.conversion.task_to_qr_code_task(task)`. Worth deciding
  deliberately rather than by accident; it is currently held in place by a comment in
  `qrcode/__init__.py`.
- **`export/common.py` is a bag of helpers**, not a module with an interface: circle
  coordinates in 2-D and 3-D, colour hex, route coordinates with a fallback, "is this
  the goal turnpoint". Some of it is geometry that belongs beside `turnpoint.py`, some
  is styling that belongs to whichever writer uses it. Left alone here because
  splitting it is a design question, not a move.
- **`tests/distance/test_distance.py` and `test_reference.py` overlap** — both walk the
  reference corpus asserting distances. Worth reading side by side once.
- **Old reviews in this directory use pre-split import paths** in their code snippets.
  Only the 2026-07-07 findings doc, whose snippets are meant to be run, was updated;
  the rest are left as written.
