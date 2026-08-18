# 2026-08-18 — Deepening candidates after the S7F audit

**Status: all seven candidates and all eight smaller findings applied** — see
[Outcome](#outcome) for what each landed as and where the fix departed from the card.

**Companion:** [`2026-08-18-deepening-candidates-after-s7f.html`](./2026-08-18-deepening-candidates-after-s7f.html) (visual report)

Reviewed at `8a64894`, the merge of PR #17 (the S7F 2026 conformance audit). Vocabulary
follows the *deep module* framing: a **module** has an **interface** (everything a caller
must know) and an **implementation**; **depth** is leverage at the interface; a **seam** is
where behaviour can be altered without editing in place; the **deletion test** asks whether
removing a module makes complexity vanish (it was a pass-through) or reappear across
callers (it was earning its keep). Domain terms are `CONTEXT.md`'s.

Every number, error message and code path below was reproduced by running the library at
this commit. Baseline: 840 tests pass, 18 documented skips; `ruff` and
`mypy --config-file mypy.ini src/` clean.

Scope was chosen by churn since the package split. Touches per file in `src/`, last 60
commits: `distance/__init__.py` (13), `export/common.py` (8),
`distance/route_optimization.py` (7), `distance/turnpoint.py` (6),
`distance/task_distances.py` (4), `distance/goal_line.py` (4).

---

## The signal behind most of what follows

`distance/__init__.py` is the single hottest file in `src/`, and it churns because the
package interface widens with every S7F number rather than absorbing one. Names in its
`__all__`, commit by commit:

| commit | date | names |
| --- | --- | ---: |
| `e03ce77` | 2026-08-17 | 13 |
| `250fe17` | 2026-08-17 | 17 |
| `cf48f0b` | 2026-08-17 | 18 |
| `7af325d` | 2026-08-17 | 16 |
| `2800429` | 2026-08-18 | 17 |
| `5ec661a` | 2026-08-18 | 18 |
| `60ee50a` | 2026-08-18 | **22** |

The speed section, the centre-distance readings and the task-area centre each arrived as
new public names. The last commit added four at once. A caller who wants "the S7F reading
of this task" must learn and correctly sequence five of them, three of which the front door
does not export.

**Already deep, and argued *from* rather than against:** `model/shape.py` (one field table
per serializable shape), `model/validation.py`'s `TaskStructure` plus its two format
adapters, `distance/speed_section.py`, and `export/`'s `TaskDrawing` with two renderers.

---

## A. Name the measured task — **Strong** · *applied `9c40d60`*

**Files:** `distance/task_distances.py:158`, `distance/goal_line.py:242`,
`distance/speed_section.py:100`, `export/common.py:60`, `cli.py:208`

**Problem.** A **task** and the **optimized route** flown for it are always used together
and nothing binds them. Every caller re-derives the route, and two public interfaces carry
the pairing as a sentence of prose no caller or type checker can check:
`task_distances_from_route(task, route)` — *"Must be the task `route` was optimized for"*
(`task_distances.py:165`) — and `GoalLine.from_task(task, ..., route=None)` — *"it must be
the route for `task`"* (`goal_line.py:251`).

**The incantation has no name.** `calculate_iteratively_refined_route(task_to_turnpoints(task))`
appears verbatim at **12 call sites** — 2 in `src/`, 10 in `tests/` — plus `cli.py:208-209`,
which spells it across two lines.

**A mismatched pair is silent, in both directions.**

```
task_distances_from_route(task_bevo, route_of_task_duna)      # no error
  optimized_distance_km = 81.2     # task_bevo's true value: 94.0
  savings_km            = 47.5     # savings_percent: 36.9
  turnpoints            = 10 rows  # fully formed, entirely wrong

task_distances_from_route(task_gibe, route_of_task_bevo)      # 17 tps, 10 points
  cumulative column = [0.0, 12.7, …, 94.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
```

That tail of zeros comes from `if i < len(cumulative) else 0.0` (`task_distances.py:134`,
twinned at `cli.py:240`) — unreachable for a correctly-paired call, and a wrong-number
generator for an incorrect one.

**Two further symptoms of the missing value.** `scripts/task_viewer/api.py:188` builds a
`TaskDrawing` — an `export` concept — purely to obtain an `OptimizedRoute` for its distance
table, because the front door exports no way to make one. And `goal_line.py` and
`speed_section.py` both import `task_distances` for `task_to_turnpoints` and nothing else;
the goal line depending on the *report* module is an accident of where that adapter was
parked, and `distance/__init__.py:40` has to explain the edge away.

**Deepening.** One module in `distance/` holding a task, the turnpoints derived from it,
and the route optimized for those turnpoints, built by `from_task(task)`. `GoalLine.from_task`,
`TaskDrawing.from_task`, the distance report and the CLI take *that* instead of a task plus
an optional route, so the mismatch stops being representable rather than staying documented.
`task_to_turnpoints` moves out of the report module into it, deleting the two stray edges.

**Tests.** `tests/distance/test_task_distances.py:263-286` currently proves "one optimizer
run" by monkeypatching `common.calculate_iteratively_refined_route` and counting calls; with
a value that is an assertion about identity. The mismatch above has no test because there is
nothing honest to assert — the interface promises nothing.

**Precedent in this repo.** `TaskStructure` (`model/validation.py:108`) did exactly this for
the validation rules one commit ago — one value, two format adapters — and `SpeedSection` is
already the shape proposed here.

---

## B. The S7F report is trapped in the CLI — **Strong** · *applied `a0192bd`*

**Files:** `cli.py:195-262` (`_distance_report`), `cli.py:265-306` (`_format_report_text`),
`tests/test_cli.py:185-275`, `docs/s7f-distance-reference.md:243`

**Problem.** `CLAUDE.md` calls the `distances` JSON keys and its `notes` block "part of the
public surface" and the command "another implementation is meant to diff against". The
module producing it is a leading-underscore function in `cli.py`, in neither
`pyxctsk.__all__` nor `pyxctsk.distance.__all__`, and reachable only by invoking the CLI.
It is 110 of `cli.py`'s 402 lines.

**The same eleven numbers are assembled three times.**

1. `_distance_report` builds the dict. `grep -rn "_distance_report" tests/` returns **zero
   hits**; 7 of the 13 `TestCLIDistances` tests assert on report *content* — which S7F
   section defines which number, that `NOT DEFINED BY S7F` travels with the centre distance,
   that a task with no speed section reports `null` not `0` — and each must build a
   `CliRunner`, invoke a click command, assert an exit code and `json.loads` stdout to see a
   dict a pure function produced.
2. `_format_report_text` reads it back out by string key nine times. The two already
   disagree about absence: `:238` writes `cumulative_m: None` defensively, `:300` does
   `point['cumulative_m'] / 1000` unguarded.
3. `docs/s7f-distance-reference.md:243` tells a library user to hand-roll the report from
   four `pyxctsk.distance` imports. That snippet omits the route points — the doc's own
   headline recommendation — and **crashes on a task with no speed section**:
   `SpeedSection.from_task(t).distance_m` → `AttributeError: 'NoneType' object has no
   attribute 'distance_m'`, verified on `task_dami_route`.

`README.md`'s usage examples show **no distance interface at all**; the library's headline
capability is documented only as a CLI.

**Deepening.** A report value in `distance/`, beside `SpeedSection` and
`CenterDistanceReading` whose shape it already mirrors, holding the numbers plus their
provenance (library version, S7F edition, earth model, which reading of the centre distance),
with `as_dict()` and `as_text()` as two renderings of one value. The CLI shrinks to parse →
build → render → write. The "at least two turnpoints" rule (`cli.py:374`) moves with it:
today that is the only place in the library that knows a one-turnpoint task has no distance,
and a library caller silently gets `0.0`.

**Deletion test:** passes clearly. Delete `_distance_report` and the knowledge reappears in
three places that already exist.

**Tests.** The seven content tests become assertions on a value — no runner, no exit code,
no `json.loads`. Newly testable: that `as_text()` and `as_dict()` report the same numbers
(today only spot-checked by `"92.002 km" in result.output`), and that the `notes` block
covers every number the report publishes.

---

## C. `--strict` validates the conversion, not the payload — **Strong** · *applied `9363cc9`*

**Files:** `parser.py:83-142` (the three QR adapters), `parser.py:148` (`_FORMAT_PARSERS`),
`parser.py:202` (the strict block), `qrcode/conversion.py:270`, `model/validation.py:16-22`

**Problem.** Three of the four format adapters call `QRCodeTask...to_task()` *inside* the
adapter, so by the strict gate at line 202 the payload is gone and `Task.validate()` reports
on the converted `Task`. That is precisely the failure `validation.py:18-22` says the
`TaskStructure` split exists to prevent — *"converting it to a `Task` first invents a
version, a task type and a goal it never carried… validating inventions reports on the
converter"*.

```
qr.version = 99
QRCodeTask.validate()            → ['this format defines version 2, the task declares 99']
parse_task(payload).version      → 1          # the converter invented it
parse_task(payload).validate()   → []
parse_task(payload, strict=True) → ACCEPTED   ← the violation is unreportable
```

So `pyxctsk convert --strict` and `pyxctsk distances --strict` — the only way a user can ask
for validation at all — cannot report `UNKNOWN_VERSION` for any `XCTSK:` string, `XCTSKZ:`
string, QR-code JSON or QR image. `QRCodeTask.validate()` is tested
(`tests/qrcode/test_conversion.py:160-207`) but nothing routes arrival through it. The
2026-08-17 card H is recorded as "validation on arrival for both formats, wired to
`--strict`"; it is wired for one.

**Deepening.** An adapter's job today is "recognise, and hand back a `Task`". Make it
"recognise, and hand back the thing that arrived, which knows how to validate itself" — the
adapter returns the `QRCodeTask` or the `Task`, and `parse_task` asks *that* before
converting. The seam already exists: both formats present a `TaskStructure`. What is missing
is that the parser drops the object holding the format's own answer one line before it would
be useful.

**Tests.** One table test — for each corpus task in each format, `parse_task(payload,
strict=True)` reports exactly what the arrived object's own `validate()` reports — kills the
whole class. Today nothing exercises `--strict` on QR input; `tests/test_cli.py:178` only
asserts the flag appears in `--help`.

---

## D. The earth model is threaded, not owned — **Strong** · *applied `810ca9a`, `62243ef`*

**Files:** `distance/turnpoint.py:37-84`, `:370-391` (`TurnpointGeometry`), `:394-435`
(`LocalPlane`), `:519-556` (`optimal_point`), `route_optimization.py:436`, and 16
`earth_model: object` parameters across `turnpoint.py`, `route_optimization.py`,
`goal_line.py`, `center_distance.py`

**Problem.** `CONTEXT.md` says the **earth model** is "a property of the task, so every
length in a task agrees". `model/task.py:415` types the field `EarthModel | None`. The
`distance` package widens it to bare `object` in 16 signatures, stores it on every
`TaskTurnpoint` (`turnpoint.py:517`), and reads it back off element 0 by `getattr`. Four
docstrings repeat the same sentence — "an `EarthModel` member, its string value, or None".
`tests/test_layering.py:36-42` already permits `distance → model`, so the enum is reachable.

**Three ways to be silently wrong, all reproduced.**

```
geodesic_distance(a, b, "FAI_SPHERE") → 134989.615 m
geodesic_distance(a, b, "FAI-SPHERE") → 135087.210 m   ← typo, 97.6 m out, no error
geodesic_distance(a, b, 42)           → 135087.210 m   ← passes mypy
```

The whole implementation behind those 16 parameters is one predicate —
`str(value).upper() == "FAI_SPHERE"` (`turnpoint.py:50`) — so everything unrecognised is
WGS84.

The `TurnpointGeometry` protocol declares `center`, `radius`, `goal_type`, and its docstring
says "route optimization needs only three things from a turnpoint";
`route_optimization.py:436` then reaches for a fourth by
`getattr(turnpoints[0], "earth_model", None)`. A fake that passes
`isinstance(x, TurnpointGeometry)` gets a different distance for identical geometry,
depending on an attribute the protocol does not mention.

`LocalPlane.around(centers, earth_model)` uses the model to build its transformers and then
throws it away, so `_corrected_path` has to carry both and nothing checks they agree.
`TaskTurnpoint.optimal_point(prev, next, plane=None)` solves in whatever plane it is given
but snaps with `self.earth_model` (`:554`). Worst corpus divergence between its default
plane and the task's: **42.36 cm** (`task_nubu`, tp 3).

**Deepening.** Give ADR 0003's selector a name (`EarthModel | str | None`) and a module: one
value owning the two engines and the selection rule, exposing distance, plane and snap, so
it stops being a trailing argument threaded through 16 signatures. Either put `earth_model`
on `TurnpointGeometry` — it is load-bearing, so the protocol is lying without it — or take
it off the turnpoints entirely and let the caller that knows the task pass it once.

> ⚠ **Touches ADR 0003 without contradicting it.** ADR 0003 fixes *which* values the selector
> accepts; this only names that set so the type checker can enforce it, and stops the model
> being stored per-turnpoint when `CONTEXT.md` calls it a property of the task. Worth opening
> the ADR alongside.

**Smallest independent slice:** give `LocalPlane` a fourth field for the model it was built
from. `_corrected_path` then loses a parameter and `optimal_point` takes the model from the
plane. Mechanical, and it lands on its own.

**Tests.** Nothing today can assert that a bogus selector is rejected, because nothing
rejects it; `tests/distance/test_xctrack_accuracy.py:327-362` covers only the two good
values. A typed selector makes "unknown earth model raises" a one-line test, and makes the
mixed-list case expressible.

---

## E. One task, two answers about itself — **Worth exploring** · *applied `9851263`*

**Files:** `distance/speed_section.py:36-50` and `:84-93`,
`distance/center_distance.py:106-120`, `distance/task_distances.py:182`, `cli.py:227`

**Problem.** "Does this task have a **speed section**", "where does its **goal** actually
end", and "what is the published **distance through centres**" are each answered in two
places, and a fix applied to one reader has already failed to reach the other.

**The roles rule, live.** Commit `9749a93` added a `TaskType.WAYPOINTS` guard to
`SpeedSection.from_task`, because an XC/Waypoints task's SSS/ESS annotations go unvalidated
and must not be read. `center_distance`'s `START_TO_GOAL` reading scans for the same
annotation with no such guard, so one CLI JSON document now says both things at once:

```
taskType = W (XC/Waypoints), turnpoints annotated TAKEOFF / SSS / ESS

speed_section_distance_m                    : None       ← roles ignored
center_distance_readings_m['START_TO_GOAL'] : 112416.5   ← roles obeyed
```

**The goal's shape, stated twice.** `LAUNCH_TO_GOAL_BOUNDARY` subtracts
`turnpoints[-1].radius`, justified in its docstring as making the number "end where the
*optimized* distance ends". For a LINE goal the optimized route ends at the goal **centre** —
`task_to_turnpoints:45-55` and `plane_circle:489` both encode "a LINE goal is a zero-radius
circle" — so the subtraction is unearned. On `task_fobe_line`: `218181.4 → 218081.4`, 100 m
short of its own definition. `tests/distance/test_center_distance.py` contains no LINE-goal
and no WAYPOINTS case.

**The centre-distance convention, spelled twice.** `center_distance.py` exists because S7F
defines no such number, and `distance_through_centers` is documented as "the primitive, not
the published number" (`turnpoint.py:562-571`). The CLI honours that (`cli.py:227`);
`task_distances_from_route:182` calls the primitive directly and publishes it as
`center_distance_km` with no caveat. They agree on every corpus task today, and would
diverge the moment `PROPOSED_READING` changed:

| task | `task_distances` `center_distance_km` | `center_distance` (PROPOSED) | if `…_BOUNDARY` |
| --- | ---: | ---: | ---: |
| `task_bevo` | 128.7 | 128.706 | 128.506 |
| `task_duna` | 115.9 | 115.897 | 115.697 |
| `task_gibe` | 190.7 | 190.651 | **189.651** |

That is the drift shape this repo has already fixed twice — the export palette, and
`KNOWN_KEYS` — both times by deriving the second copy from the first.

**Deepening.** One query for a task's roles and its goal's *effective* geometry that both
readers consult, and a report that asks `center_distance(task)` for the published number
instead of re-deriving it. Half of this collapses into candidate A, since one report has one
centre-distance reading.

---

## F. The CLI has no read/write seam — **Worth exploring** · *applied `b8f99c0`*

**Files:** `cli.py:128-138` and `:361-371` (byte-identical read blocks), `:146`, `:154`,
`:176`, `:388` (four write blocks), `:182`, `:394` (error handling)

**Problem.** Reading input and writing output are spelled out six times, so four decisions —
encoding, trailing newline, text vs bytes, stdout vs file — are each made independently, and
two are already made inconsistently.

| write block | encoding | trailing newline | stdout path |
| --- | --- | --- | --- |
| `convert` json `:146` | locale | none (`7d`) | `click.echo` |
| `convert` kml `:154` | locale | none | `click.echo` |
| `convert` png `:176` | bytes | — | `stdout.buffer` |
| `distances` `:388` | locale | yes (`0a`) | `click.echo` |

**None of the four writes passes `encoding=`,** while the data is UTF-8 and the KML declares
`<?xml version="1.0" encoding="UTF-8"?>`:

```
$ LC_ALL=C PYTHONCOERCECLOCALE=0 PYTHONUTF8=0 \
    pyxctsk distances task_bevo.xctsk --format text -o out.txt
Error: 'ascii' codec can't encode character '\xa7' in position 77
exit=1
```

The text report contains `§`, so on a non-UTF-8 locale the `-o` path fails for *every* task.
Linux usually escapes this via PEP 538 locale coercion — which is why the suite is green —
but Windows defaults to cp1252, where this **silently writes a mis-encoded file** rather than
failing. The `-o` path is the one `docs/s7f-distance-reference.md:238` recommends for running
a corpus. No corpus task contains non-ASCII text (`grep -lP "[^\x00-\x7F]"` → nothing), which
is why nothing caught it.

**Same absence, third symptom.** `except Exception as e: click.echo(f"Error: {e}")` makes a
library `TypeError` indistinguishable from unparseable input, and `tests/test_cli.py:298`
asserts only that `"Error:"` appears — so an internal crash passes that test.
`except SystemExit: raise` at `:394` is dead code (`SystemExit` is not an `Exception`), and
its absence in `convert` shows the uncertainty.

**Deepening.** One `read_input(input_file)` and one `write_output(output_file, payload)`
where the payload knows whether it is text or bytes. That single module becomes the only
place that has to know the output is UTF-8, that stdout is `click.echo`, that a PNG goes to
`sys.stdout.buffer`, and whether a trailing newline is added. Narrow the catch to
`pyXCTSKError` plus `OSError` so an unexpected exception surfaces as a traceback.

---

## G. The drawing answers colour, but not label or description — **Worth exploring** · *applied `14bef08`*

**Files:** `export/common.py:107-126` (`color_of`, the precedent), `export/kml.py:67`, `:68`,
`:80`, `export/geojson.py:44`, `:47`, `:49`

**Problem.** Applied candidate D (2026-08-17) moved *colour* onto `TaskDrawing` because "a
question both writers must answer identically is a method on the drawing, not something each
of them assembles". Label and description were left behind, and the two writers now disagree
— with the KML one visibly wrong. On `task_bevo`:

```
KML     <description>Type: TurnpointType.TAKEOFF, Radius: 400m</description>
KML     <description>Type: None, Radius: 4500m</description>
GeoJSON description "Radius: 400m"   tp_type <TurnpointType.TAKEOFF: 'TAKEOFF'>
```

The KML description leaks a Python enum repr into user-visible map text and prints
`Type: None` for an ordinary turnpoint. `geojson.py:49` uses
`getattr(turnpoint, "type", None)` — a defensive `getattr` on a dataclass field that always
exists — and skips the `or TurnpointType.NONE` normalisation `color_of` (`common.py:125`)
performs, which is the exact asymmetry `color_of`'s docstring says it was created to remove.
The fallback name `f"TP{i + 1}"` is written three times.

> ⚠ **A test currently pins the bug:** `tests/export/test_kml.py:76` asserts
> `"Type: TurnpointType.TAKEOFF" in kml_result` as expected output. Fixing the label means
> changing that assertion — worth confirming it was never a deliberate choice.

**Deepening.** `label_of(turnpoint, index)` and `description_of(turnpoint)` as methods on
`TaskDrawing`, beside `color_of`. The interesting new test is the cross-format one, beside
`test_both_writers_draw_the_turnpoints_in_the_palette_colours`
(`tests/export/test_common.py:361`): "both writers name the same turnpoint the same way",
which cannot be written at all right now.

*Minor, same file:* `generate_circle_coordinates_2d` (`common.py:231`) is public, has exactly
one caller one line below, and zero tests; GeoJSON draws no polygons. It fails the deletion
test.

---

## Smaller findings

Verified, but fixes rather than redesigns.

1. **The mypy strictness is dead config.** `pyproject.toml:94-104` sets
   `disallow_untyped_defs`/`disallow_incomplete_defs`, but `mypy.ini` takes precedence and
   sets `disable_error_code = no-untyped-def, no-untyped-call`. Both `uv run mypy src/` and
   the lefthook hook read `mypy.ini`. Under the flags `pyproject.toml` thinks are on, `src/`
   has **9 untyped defs** — 4 in `cli.py` (`:42`, `:102`, `:195`, `:329`), plus
   `export/geojson.py:24,160`, `distance/task_distances.py:96`, `distance/goal_line.py:76`,
   `qrcode/image.py:15`. `CLAUDE.md` states "mypy runs in strict mode
   (`disallow_untyped_defs`, `strict_optional`)" and "type hints are required on all function
   params and returns"; neither is enforced. Two config files, one of them inert.
2. **The front door offers the primitive and hides the published number.** `pyxctsk.__all__`
   carries 7 of `pyxctsk.distance.__all__`'s 22 names, and exports
   `distance_through_centers` — whose own docstring says a caller producing a task-board
   figure wants `center_distance(task)` — while `center_distance`, `center_distance_readings`,
   `CenterDistanceReading`, `PROPOSED_READING`, `GoalLine`, `task_to_turnpoints` and
   `calculate_iteratively_refined_route` are absent. It exports `OptimizedRoute` and
   `task_distances_from_route(task, route)` but **no way to construct a route**, which is why
   `docs/s7f-distance-reference.md:245` reaches past the front door for four names.
   `tests/test_layering.py` already parses the import graph and is the natural home for "every
   name a doc tells a user to import is reachable from the front door"; nothing today asserts
   anything about `__all__`.
3. **`import pyxctsk` costs 486 ms** and eagerly loads scipy (86% of it, via
   `distance.turnpoint`), pyproj and simplekml, because `__init__.py:11-28` imports all four
   packages. There is no cheaper path — `import pyxctsk.model.task` costs the same, since the
   package `__init__` runs first. The CLI pays it on `--help` (0.57 s wall). A lazy
   `__getattr__` on the package would make the eager scipy load optional without changing a
   caller's import.
4. **`TaskValidationError.issues` is typed `Sequence[object]`** (`exceptions.py:29-44`), so
   the documented way to react to a rule (`issue.rule`) fails mypy for a downstream caller
   with `"object" has no attribute "rule"`. The docstring blames a cycle with `validation`,
   but `validation.py` does not import `exceptions` at all — it imports only `.enums`. An
   `if TYPE_CHECKING:` import fixes it, the same escape hatch `validation.py:31` already uses
   and `tests/test_layering.py` explicitly allows.
5. **`InvalidFormatError("invalid format")` is the single diagnostic for every unrecognised
   input** (`parser.py:200`) — a nonexistent path, a directory, truncated JSON, a PNG with no
   readable QR, *and a valid QR image when the optional zxing/Pillow deps are missing*
   (`parser.py:122-123` returns `None`) all produce the identical message, so a missing
   dependency is indistinguishable from a corrupt file. `_looks_like_file_path` →
   `_read_file` swallowing the `OSError` (`parser.py:62-67`) is where the path case is lost.
6. **Two stale references.** `validation.py:17` cross-references `validate_turnpoint_roles`,
   which no longer exists — it is `validate_structure`, and it reads eight fields rather than
   the "exactly two things" the docstring claims. Stale in `CHANGELOG.md:11` too. Separately,
   `num_iterations` is threaded through `task_distances`, `route_optimization` and
   `optimized_distance` with exactly one caller: `tests/distance/test_xctrack_accuracy.py:320`.
7. **No `tests/model/test_validation.py` exists** for a 352-line module — its tests live in
   `tests/conformance/` and `tests/qrcode/`, and nothing ever names `TaskStructure` or
   `validate_structure` directly, so a third format has no worked example. One latent hazard:
   `finish_altitude` (`validation.py:142`) is the only field with a default and was the most
   recently added, so a future defaulted field silently skips whichever adapter forgets it.
8. **`pyxctsk --version` is not a thing** (prints a usage error) even though
   `_pyxctsk_version()` exists at `cli.py:186` for the report.

---

## Top recommendation

**A — name the measured task.** It is the candidate whose deletion test answers loudest:
remove the value and the complexity reappears across 12 call sites, two prose-only
invariants, two dead `else 0.0` clauses, and a viewer reaching through `export` for a
`distance` concept. It also has a demonstrated wrong answer behind it — a mismatched pair
returns a fully formed report 12.8 km out, reporting 36.9% savings, with no error.

**B follows almost for free** once A exists, since the S7F report becomes a rendering of the
measured task, and **half of E collapses into it**, since one report has one centre-distance
reading.

**Do C in parallel.** It is independent of A, it is the one finding where the library accepts
input it documents itself as rejecting, and its seam is already built.

Suggested order:

- A → B → E
- C in parallel — independent
- D: start with `LocalPlane`'s fourth field, the slice that lands on its own
- F, G: standalone fixes

---

## Outcome

All seven applied, in the suggested order — A → B → E, C in parallel, then D, F, G.
The suite went from 840 passing to 927; `cli.py` from 402 lines to 266.

| # | commit | landed as |
| --- | --- | --- |
| A | `9c40d60` | `MeasuredTask` in `distance/measured_task.py`, holding the task, its cylinders and the route. `task_distances_from_route(task, route)` → `task_distances_from(measured)`; `GoalLine`'s optional `route=` → `GoalLine.from_measured_task`; `SpeedSection.from_measured_task` added. `task_to_turnpoints` moved out of `task_distances`, which removed the edge making the goal line depend on the distance *report*. Corpus output byte-identical. |
| B | `a0192bd` | `DistanceReport` in `distance/report.py`, with `as_dict()` and `as_text()` as two renderings of one set of fields. `TooFewTurnpointsError` moved the two-turnpoint rule out of the CLI. All eight renderings byte-identical. |
| C | `9363cc9` | Adapters return the arrived payload; `parse_task` validates *that* before converting. `UNKNOWN_VERSION` is now reportable for all four formats; 96 strict parses over the corpus, 0 false rejections. |
| D | `810ca9a`, `62243ef` | `LocalPlane` carries its earth model (the slice that lands alone), then `EarthModelLike` replaces `object` in 16 signatures and an unrecognised value raises instead of silently meaning WGS84. `TurnpointGeometry` declares `earth_model`. Corpus output byte-identical. |
| E | `9851263` | `speed_section_indices` is the one answer to "does this task have a speed section"; `LAUNCH_TO_GOAL_BOUNDARY` reads the goal's effective radius; the table asks `center_distance` rather than the primitive. Exactly the five LINE-goal tasks move, by their goal radius. |
| F | `b8f99c0` | `_read_input` / `_write_output`. UTF-8 on every locale, one newline rule, `pyXCTSKError`/`OSError` instead of bare `Exception`. |
| G | `14bef08` | `label_of`, `description_of`, `role_of` on `TaskDrawing`. The enum repr leaves the map. |

Departures from the card worth recording:

- **The mismatch is unrepresentable at the *call site*, not at construction.** `MeasuredTask(...)`
  can still be built by hand with a route that does not belong to its task — the test
  seams in `test_geojson.py` do exactly that, deliberately. What the value removes is the
  two-argument interface every caller had to get right; it is not a proof.
- **`GoalLine` and `SpeedSection` kept their `from_task` constructors.** The card implies
  replacing them. Under the 2024 goal-line orientation no route is needed at all, so
  forcing a `MeasuredTask` would have made `from_task` optimize where it previously did
  not — a performance regression in the name of tidiness.
- **F chose a newline rule rather than preserving both.** `convert -o` gained a trailing
  newline it did not have. The card called the inconsistency accidental; fixing it means
  picking one, and stdout was already newline-terminated by `click.echo`.
- **The `route()` rows stayed `dict[str, Any]`.** Making them a value type was tempting and
  is not done: they are the published JSON shape, and a dataclass between the fields and
  `json.dumps` would be a layer with one caller.
### Outcome of the smaller findings

All eight applied, in four commits.

| # | commit | landed as |
| --- | --- | --- |
| 1 | `3eb0b29` | `mypy.ini` deleted, its overrides merged into `pyproject.toml`, whose strict flags were inert because every caller passed `--config-file mypy.ini`. Eight untyped functions in `src/` annotated. Four live references that would have broken — two CI workflows, `README.md`, `UPDATE_INSTRUCTIONS.md` — fixed. |
| 4 | `1cb965e` | `TaskValidationError.issues` typed via `if TYPE_CHECKING:`. The docstring's stated reason was wrong: `validation.py` imports only `model.enums` and never these exceptions. |
| 2, 3 | `8533520` | Ten answers added to the front door, including `center_distance` beside the primitive it is meant to replace. `scipy.optimize` deferred to the one function that needs it: `import pyxctsk` 400 ms → 95 ms, `pyxctsk --help` 0.57 s → 0.15 s. Both guarded in `tests/test_layering.py`. |
| 5 | `c743a4b` | `InvalidFormatError` names the case — an unreadable path with the OS's reason, an image with no QR code, an image with the QR dependencies missing, JSON that is not a task. |
| 6, 7, 8 | `3c7899c` | The stale `validate_turnpoint_roles` reference and "exactly two things" claim corrected; `num_iterations` dropped from the two layers that only forwarded it; `pyxctsk --version` added; `tests/model/test_validation.py` written. |

Two things worth recording from doing them:

- **Bringing `tests/` under the type checker found a vacuous test.**
  `test_optional_omits_none` read `assert Value("label", "l").write(Toy(name="A"), {}) is
  None`, but `write` mutates the dict it is handed and always returns `None` — so the
  assertion held whatever the field did, including writing the key it was meant to prove
  absent. 537 of the 565 errors were test functions missing `-> None`, which `tests.*`
  now exempts; the other 28 were un-narrowed `Optional`s.
- **`num_iterations` was not dead, so it was not deleted.** ADR 0004's precedent is about
  *no-ops*; this is a real knob. It stays on the optimizer and lost only the two
  pass-through layers no caller used.

---

## Reproducing this review

All commands from the repo root at `8a64894`.

```bash
# The framing chart — names in distance/__init__.py's __all__ per commit
for c in $(git log --format=%h -60 -- src/pyxctsk/distance/__init__.py | tac); do
  git show $c:src/pyxctsk/distance/__init__.py | sed -n '/^__all__/,/^]/p' | grep -c '^    "'
done

# A — the unnamed incantation, and the silent mismatch
grep -rn "calculate_iteratively_refined_route(task_to_turnpoints(" src/ tests/ scripts/
uv run python -c "
from pyxctsk import parse_task, task_distances_from_route
from pyxctsk.distance import calculate_iteratively_refined_route, task_to_turnpoints
a = parse_task('tests/data/reference_tasks/xctsk/task_bevo.xctsk')
b = parse_task('tests/data/reference_tasks/xctsk/task_duna.xctsk')
print(task_distances_from_route(a, calculate_iteratively_refined_route(task_to_turnpoints(b))))"

# C — a QR payload's own verdict never reaches --strict
uv run python -c "
from pyxctsk import parse_task
t = parse_task('tests/data/reference_tasks/xctsk/task_bevo.xctsk')
q = t.to_qr_code_task(); q.version = 99; s = q.to_string()
print('QR says :', [str(i) for i in q.validate()])
print('strict  :', parse_task(s, strict=True).version)"

# D — the typo that is silently WGS84
uv run python -c "
from pyxctsk.distance.turnpoint import geodesic_distance
a, b = (46.0, 8.0), (47.0, 9.0)
for m in ('FAI_SPHERE', 'FAI-SPHERE', 42): print(m, geodesic_distance(a, b, m))"

# E — one JSON document, two answers
uv run python -c "
from pyxctsk import parse_task, Task
from pyxctsk.cli import _distance_report
t = parse_task('tests/data/reference_tasks/xctsk/task_bevo.xctsk')
d = t.to_dict(); d['taskType'] = 'W'
r = _distance_report(Task.from_dict(d))
print(r['speed_section_distance_m'], r['center_distance_readings_m']['START_TO_GOAL'])"

# F — the -o encoding failure
LC_ALL=C PYTHONCOERCECLOCALE=0 PYTHONUTF8=0 \
  uv run python -m pyxctsk distances tests/data/reference_tasks/xctsk/task_bevo.xctsk \
  --format text -o /tmp/out.txt

# G — the enum repr in the KML description
uv run python -c "
from pyxctsk import parse_task, task_to_kml
import re
print(re.findall(r'<description>(.*?)</description>',
  task_to_kml(parse_task('tests/data/reference_tasks/xctsk/task_bevo.xctsk')))[:3])"

# Smaller finding 1 — the suppressed untyped defs
uv run mypy --config-file mypy.ini --disallow-untyped-defs \
  --enable-error-code no-untyped-def src/
```
