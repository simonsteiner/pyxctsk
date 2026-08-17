# 2026-08-17 — Deepening candidates after the package split

**Status: A, B, D and G applied** (see [Progress](#progress) and the outcome notes below);
the other four are proposed. Companion visual report was written to a temp file, not the
repo; this document is the record.

Reviewed at `5a3c207` (the four-package split, merged as PR #12). Vocabulary follows the
*deep module* framing: a **module** has an **interface** (everything a caller must know)
and an **implementation**; **depth** is leverage at the interface; a **seam** is where
behaviour can be altered without editing in place; the **deletion test** asks whether
removing a module makes complexity vanish (it was a pass-through) or reappear across
callers (it was earning its keep).

Every defect claimed below was reproduced by running the library at this commit. Where a
number is quoted, the command that produced it is described inline.

Scope was chosen by churn since June, mapped through the renames: `model/task.py` (17
touches), `qrcode/task.py` (13), `qrcode/models.py` (13), `distance/route_optimization.py`
(10), `parser.py` (10), `distance/task_distances.py` (10).

---

## A. Return the optimized route as a value, not a scalar — **Strong**

**Files:** `distance/route_optimization.py:232`, `distance/task_distances.py:104-262`,
`export/common.py:43`

**Problem.** `calculate_iteratively_refined_route` computes every leg of the route, sums
them, and returns `tuple[float, list[point]]` — the legs are discarded. So
`_create_turnpoint_details` (`task_distances.py:139`) rebuilds them by calling
`optimized_distance(turnpoints[:i+1])` inside a per-turnpoint loop: n full optimizer runs
per task, on top of the whole-task run at line 202.

Two consequences.

**It costs n×.** Measured per reference task (optimizer alone vs
`calculate_task_distances`):

```
task_gimi   n= 6   0.019s → 0.078s    4.1x
task_bevo   n=10   0.025s → 0.166s    6.7x
task_duna   n=11   0.023s → 0.202s    8.8x
task_gibe   n=17   0.022s → 0.311s   14.4x
```

The optimizer is flat in n at this size; the ratio is entirely the re-optimization loop.
Both export writers then run it again through
`export/common.get_optimized_route_coordinates`, so the dev viewer's single request runs
the optimizer n+2 times.

**And the numbers are wrong.** The n partial runs are not prefixes of the route:
`_optimize_plane_points:216` treats the *last* circle specially (nearest boundary point
rather than `plane_optimal_point`), so "optimized distance to turnpoint i" is the optimum
of a *truncated task*. Comparing the dict's `cumulative_optimized_km` against the actual
route prefix, both derived from the same `Task`:

```
task_bevo    i=1  route 12.683  dict 11.300   +1.383 km
             i=3  route 38.113  dict 36.500   +1.613 km
             i=7  route 83.092  dict 78.000   +5.092 km
task_gibe   worst delta 0.944 km
```

The table beside the map disagrees with the line on it by 5.09 km. The only test over
these values asserts they are non-decreasing
(`tests/distance/test_task_distances.py:284`), which both readings satisfy.

The interface makes this invisible: five stringly-typed keys plus a nested list of
eight-key dicts, and the values are pre-rounded to 0.1 km at `task_distances.py:153,234`
— a display artefact inside a computation.

**Solution.** Return a route value carrying `points`, `legs`, the earth model and the
total. Per-leg and cumulative distances become `accumulate` over `legs`: one optimizer
run, prefixes consistent by construction, no rounding baked in.
`calculate_task_distances` collapses to a projection of that value for the viewer, and
`calculate_cumulative_distances` (`task_distances.py:242`, no `src/` caller, a copy of the
loop body it was extracted from) disappears.

**Wins.**

- locality: one definition of "distance to here"
- leverage: one run serves the table, KML and GeoJSON
- interface shrinks: no `dict[str, Any]` keys to learn
- rounding leaves the computation
- prefix-vs-route consistency becomes impossible to break

---

## B. Make `GoalLine.from_task` total — **Strong**

**Files:** `distance/goal_line.py:185-216, 281-295`, `export/common.py:27-40, 125-150`,
`export/kml.py:218`, `export/geojson.py:164`

**Problem.** One question — "does this task have a goal line, and if so what is it" — is
answered by two predicates in two files, with different conditions:

```python
# goal_line.py:290 — should_skip_last_turnpoint
task.goal and task.goal.type == GoalType.LINE and task.turnpoints and len(task.turnpoints) >= 2

# goal_line.py:195 — GoalLine.from_task
... the same four clauses ... AND _find_previous_turnpoint(...) is not None
```

`get_turnpoints_to_render` drops the last turnpoint on the first; `get_goal_line_data`
returns `None` on the second. When the previous turnpoint coincides with the goal, both
fire and the goal disappears from the output entirely:

```
turnpoints: A(47.0, 8.0) TAKEOFF, Goal(47.0, 8.0)   goal=LINE
geojson: [('A','cylinder'), ('Optimized Route','optimized_route')]
kml "Goal Line" present: False
```

`tests/distance/test_goal_line.py:400-416` pins that absence as intended, with nothing
asserting that something still represents the goal.

Second consequence of the same split: **`is_goal_turnpoint` can never fire for a LINE
goal**, because it compares against `all_turnpoints[-1]` — the turnpoint the renderer just
removed. The red goal colour is unreachable:

```
LINE     [('A','#204d74'), ('B','#269abc')]                     red: False
CYLINDER [('A','#204d74'), ('B','#269abc'), ('Goal','#ff0000')] red: True
```

**Solution.** `GoalLine.from_task` is already the right locus — make it total. One call
returns either a goal line, whose presence *is* the reason to drop the last turnpoint, or
nothing, in which case the last turnpoint is an ordinary cylinder that still gets drawn.
"Which turnpoints to render" becomes a derived property of that one answer rather than an
independently computed second opinion, and `should_skip_last_turnpoint` goes away.

**Departs from ADR 0003 — fix it here.** `goal_line.py:21` hardcodes
`Geod(ellps="WGS84")` and the string `earth_model` never appears in the file. On an
`EarthModel.FAI_SPHERE` task the route and distances are measured on the sphere while the
goal line's endpoints and control-zone arc are measured on the ellipsoid — two earth models
inside one exported document. ADR 0003 says the selector is accepted everywhere; this
module is the exception, and nothing tests goal-line geometry under a non-default earth
model.

**Wins.**

- locality: the LINE-goal rule in one module
- the silent output hole closes; the goal colour becomes reachable
- the earth model reaches the goal line (ADR 0003)
- one test surface instead of two predicates the writers must order correctly

---

## C. One field table per serializable shape — **Strong (largest scope)**

**Files:** `model/task.py`, `model/passthrough.py`, `qrcode/models.py`, `qrcode/task.py`,
`qrcode/conversion.py`

**Problem.** Adding one turnpoint-level spec field means editing 12 places in 4 files:
the dataclass field, `to_dict`, `from_dict` and `KNOWN_KEYS` on `Turnpoint`; the same four
on `QRCodeTurnpoint` except `to_dict` is split into competition and simplified branches;
both directions in `conversion.py`; and the `as_waypoints()` reduction list. A root-level
field is 10 places; a goal-level field is 8. The type checker enforces none of them.

The drift is already measurable: **4 `read_passthrough` call sites against 6
`write_passthrough` call sites**, because each `to_dict` split into two format branches
while `from_dict` did not. That exact asymmetry shipped once as a bug —
`tests/conformance/test_spec_conformance.py:698` records it — and three more instances are
live:

**The QR simplified branch swallows keys it never writes.** `QRCodeTask.KNOWN_KEYS`
(`qrcode/task.py:128`) is the *union* of both formats' key sets, but each branch handles
only its half, so the passthrough sees nothing unknown:

```
in : {'T':'W','V':2,'t':[…],'e':1,'to':'09:00:00Z','g':{'t':2}}
unknown captured: {}
out: {'T':'W','V':2,'t':[…]}          LOST: {'e','to','g'}
```

**Passthrough covers 4 of 11 serializable shapes.** `Waypoint`, `SSS`, `Goal`, `Takeoff`
and their QR counterparts have no `KNOWN_KEYS` and no `unknown` field, so nested unknown
keys are dropped — the loss `passthrough.py:8-12` exists to prevent:

```
waypoint.zzz kept: False   sss extra: False   goal extra: False   takeoff extra: False
```

**`unknown` crosses the format seam still keyed in the other namespace.** `conversion.py`
copies it across verbatim, so a full-format key can land in a slot the QR format defines,
producing a payload this library cannot re-read:

```
model: turnpoints[0].unknown == {'t': 99}
QR   : {"t":[{"n":"A","z":"…","t":99}], …}
re-read: ValueError: 99 is not a valid QRCodeTurnpointType
```

`write_passthrough`'s "never shadow" rule cannot help here: `"t"` is only written for
SSS/ESS turnpoints, so for a plain one the slot is free and the foreign key wins. The
invariant that is missing is *an unknown key never occupies a key that any branch of any
format defines* — a check over the union of both key sets, not over what happened to be
written.

**Solution.** Declare each shape's mapping once as data — `(attr, wire_key, codec,
optionality)` — and let one traversal read and write it. `KNOWN_KEYS` becomes derived
rather than hand-declared, the two QR shapes get their own key sets instead of sharing a
union, `conversion.py` maps table to table, and `(KNOWN_KEYS, ext_key)` binds to a shape
instead of being passed loose at every call site.

**Wins.**

- leverage: a spec field is one row, not 12 edits
- locality: read/write drift becomes structurally impossible
- every shape gets passthrough instead of four of eleven
- `passthrough.py`'s unstated "known_keys must include ext_key" precondition discharges
- the 25 byte-exact QR golden strings are the guard rail for attempting it

---

## D. Carry colour across the export seam as a value, not a hex string — **Strong**

**Files:** `export/common.py:56-77`, `export/kml.py:20-53, 104-111`

**Problem.** `export/common.py:1-13` promises "four questions, each answered once so the
two writers cannot answer them differently." Colour is answered as a hex string, and
`kml.py:40` maps it back through a hand-written `color_map` that re-declares all five
palette entries — and loses their values. A TAKEOFF turnpoint is `#204d74` in GeoJSON and
`ff8b0000` (`#00008b`) in KML; three of the five entries drift this way. `.get(hex,
simplekml.Color.blue)` means a sixth entry degrades silently rather than failing.

**And `kml.py:110` assigns a `Style` to a colour field:**

```python
center_point.style.iconstyle.color = _create_turnpoint_style(turnpoint_type, is_goal)
```

Every centre-point placemark of every exported task therefore carries invalid KML:

```xml
<IconStyle id="33">
    <color>
        <Style id="35">
            <LineStyle id="36"><color>ff8b0000</color>
```

`tests/export/test_kml.py:203` asserts only `"<Style" in kml_result`, which this
satisfies. Note the shape of the failure: `get_turnpoint_color_hex` is pure and fully
covered by `tests/export/test_geojson.py:24-112`, while both defects live in the caller
that adapts its output. That is what a helper extracted without locality looks like.

**Solution.** Make the shared answer a colour value — an RGB triple, or a small enum of
turnpoint roles — that each writer renders with a total function, so simplekml conversion
stops being a hand-maintained dict keyed on a string and the style assignment has one
right-typed target.

**Wins.**

- locality: one palette, not two
- the invalid `<color><Style>` nesting becomes unrepresentable
- a new palette entry cannot degrade silently
- the module docstring's promise becomes true

---

## E. One solver for "the optimal point on a cylinder" — **Worth exploring**

**Files:** `distance/turnpoint.py:328-406`, `distance/route_optimization.py:57-229`,
`distance/sss.py`, `tests/distance/test_xctrack_accuracy.py:169-268`

**Problem.** Two implementations answer the same question in two different projection
planes. `TaskTurnpoint.optimal_point` projects into a Transverse Mercator plane centred on
*that turnpoint* (`turnpoint.py:373`); `route_optimization._plane_circles` projects into a
plane centred on the *mean of all centres* (`route_optimization.py:75`). Same spec
paragraph (§7.1.2), two different answers.

The one the product ships is the second. `TaskTurnpoint.optimal_point` has exactly one
`src/` caller — `sss.py:32` — and `sss.py`'s own public entry point `calculate_sss_info`
has no callers anywhere; its test body is `assert True`
(`tests/distance/test_sss.py:58-62`). Meanwhile the crossing-case tests at
`test_xctrack_accuracy.py:183, 196, 267` exercise `optimal_point`, i.e. the plane the
optimizer does not use. Anyone fixing a crossing-case bug will edit that function, watch
the tests go green, and ship nothing.

Attached surface, by deletion test:

| Name | Evidence |
| --- | --- |
| `TaskTurnpoint.optimal_point` | one `src/` caller, different projection plane from the shipped one |
| `calculate_sss_info` | zero callers; test body is `assert True` |
| `TaskTurnpoint.goal_line_length` | set at `task_distances.py:60`, never read in `src/` |
| `_find_optimal_goal_line_point` | 22-line docstring over `return self.center` |
| `turnpoint.py:36` `geod` | "retained for backwards compatibility"; zero references in `src/` or `tests/` |
| `show_progress` | never passed `True` anywhere: 5 signatures, 9 `print()` branches in a library |
| `distance/config.py` | `CONVERGENCE_EPSILON_M` reaches only a default on the *private* `_optimize_plane_points`; `calculate_iteratively_refined_route` never forwards it, so it is not a seam |

**Solution.** One planar solver with one projection policy; `TaskTurnpoint` keeps the data
and delegates. Crossing/reflection tests aim at `plane_optimal_point` (as
`test_route_optimization.py:41-99` already does) and at the whole-route entry point, with
nothing in between to be tested at the wrong altitude. If SSS entry points are wanted,
they become a query on the computed route rather than a second solver.

**Precedent, not conflict — ADR 0004** already chose "remove the dead surface in one
breaking change" over keeping documented no-ops, for exactly this kind of tuning surface.
Removing a public `__all__` name is the repo owner's call; the reasoning transfers.

**Wins.**

- locality: one answer to one question
- tests point at shipped code
- interface shrinks by seven names
- no `print()` left in a library

---

## F. Give the reference corpus an adapter — **Strong**

**Files:** `tests/paths.py`, `tests/conftest.py`,
`tests/distance/test_xctrack_accuracy.py:46`, `tests/distance/test_task_distances.py:39`,
`tests/qrcode/test_codec.py:52`, `tests/conformance/test_spec_conformance.py:219`

**Problem.** The corpus is three parallel directories keyed by task stem, and the pairing
rule is re-implemented per consumer: the accuracy tests glob and sort; `test_task_distances`
globs unsorted into a differently-shaped dict; `test_codec` pairs `xctsk/` against
`qrcode_string/` inline, twice; `test_spec_conformance` parametrizes over `qrcode_string/`
alone. Four discoveries, two sort orders.

The consequence is already on disk: `xctsk/` and `json/` hold 24 files, `qrcode_string/`
holds 25, and **`qrcode_string/task_dami.txt` has no `.xctsk` and no `.json`**. It is
exercised by one consumer and invisible to the other three. Nothing asserts the three
directories are in step — corpus integrity has no owner.

`tests/paths.py` is 27 lines of `Path` constants and no functions. It earns its keep (it
killed the `Path(__file__).parent.parent` counting at four directory depths) but stops one
level short: it names *where* the corpus lives, and nothing names *what it is*.

What the same card collapses:

- **~34 hand-built `Task`s** across six files (≈59 `Turnpoint`, ≈58 `Waypoint`). Largest
  cluster: the same two-turnpoint task seven times in `test_geojson.py:26-120`, differing
  only in `type=`/`radius=`; the same CLI task four times byte-identical in `test_cli.py`,
  differing only in `--format`. `test_goal_line.py:27` defines exactly the right builder
  and then rebuilds the shape by hand four times below it.
- **5 of 12 `conftest.py` fixtures are dead**, and two of them (`bevo_task`,
  `temp_xctsk_file`) are precisely the duplication the tests are suffering from.
  `test_spec_conformance.py:36-57` shows the pattern the other files need: one `BASE_TASK`
  dict plus `task_json(**overrides)`.
- **`conftest.py:173` exports a function** (`find_xctsk_files = _find_xctsk_files`) that
  `test_codec.py:34` imports directly — a fixture-injection file serving two interfaces.
- **The suite writes 24 tracked PNGs into the source tree** on every run
  (`test_codec.py:139`), where `tmp_path` is available; and the only assertion about the
  generated QR image is `st_size > 0` (`test_cli.py:194`), though
  `tests/qr_test_utils.py:60` can decode it.
- **4 inert `@patch` decorators** in `test_geojson.py:217-291` patch
  `pyxctsk.export.common.get_optimized_route_coordinates`, but `geojson.py:17` bound the
  name at import time — the mock is never called, those tests silently run the real
  optimizer, and the "optimizer returned fewer than 2 points" branch at `geojson.py:73` is
  untested. `geojson._create_optimized_route_feature` also keeps an
  `isinstance(task_or_coords, list)` dispatch commented `# Old API for testing`, used by
  five tests and no production caller.
- **Two tests are 77% of the 6.4 s suite**, both loop-and-accumulate over the whole
  corpus. `test_reference_task_validation` (3.96 s) runs all 24 tasks in one function, so
  one failure names one task and the other 23 go unreported. Parametrizing costs the same
  wall time and reports all of them.

Coverage worth naming while here: `distance/sss.py` is at 19%, `export/kml.py:165-195`
(the whole goal-line writer) is uncovered, `QRCodeTakeoff.to_dict`/`from_dict` have never
run, and no test ever sees `QR_CODE_SUPPORT is False` — the documented failure mode of the
only optional dependency, reachable with one `monkeypatch`.

**Solution.** One generator over the corpus yielding `(stem, xctsk, json meta, qr string)`,
plus a small task builder; delete the dead fixtures and move the conftest alias to
`tests/paths.py`.

**Wins.**

- leverage: one discovery, four consumers
- locality: corpus integrity gets an owner; an orphan becomes a collection error
- test setup stops being the bulk of the test
- the suite stops writing to tracked files

---

## G. The layering guard is weaker than its docstring — **Strong (one predicate)**

**Files:** `tests/test_layering.py:99-120`

**Problem.** `_module_level_imports` documents that it "skips anything inside a function or
class body, and anything guarded by `if TYPE_CHECKING:`" — but it implements that by
iterating `tree.body` only. "Not a direct child of the module" is not the same predicate as
"does not run at import time": a relative import inside a module-level `try:/except
ImportError:` or any module-level `if` runs at import time and escapes all three layer
checks silently. `_deferred_imports` has the mirror gap — it walks `FunctionDef` bodies but
not `ClassDef` bodies, and a class-body import also runs at import time.

This matters here specifically: `parser.py:34-42` and `qrcode/image.py:4-12` already use
that exact `try: import … except ImportError:` shape for optional dependencies. Those
imports are absolute, so nothing is hidden today — but the pattern is established, and the
next relative import wrapped in a `try:` gets a green suite.

Everything else about the file is right, and it is the deepest module in `tests/`: eight
lines of declaration (`ALLOWED`, `LEAVES`) govern all 30 source modules, and `SRC.rglob`
means adding a module needs no edit here. `EXPECTED_DEFERRED_IMPORTS` is the one
mirror-like element, and its maintenance cost is its purpose — the edit is the review gate.

**Solution.** Collect by "does this run at import time": walk the tree, excluding
function, class and `if TYPE_CHECKING:` bodies by name rather than relying on nesting
depth as a proxy.

**Wins.**

- locality: the rule matches its own statement
- closes the `try: import` blind spot in the region the codebase already inhabits
- class-body imports stop being invisible

---

## H. Move the validation seam to where input arrives — **Worth exploring**

**Files:** `model/validation.py:69`, `model/task.py:556`, `parser.py:156`, `cli.py:109`,
`qrcode/conversion.py:182`

**Problem.** The rules can only run against a fully-defaulted `Task`, reached through one
boolean on one of five entry points. `strict=` appears at three non-doc places, all in
`parser.py`. Bypassing it: `Task.from_dict`/`from_json`, `QRCodeTask.to_task()`, direct
construction — and `cli.py:109`, which calls `parse_task(input_data)` with no `strict` and
offers no `--strict` option, while `cli.py:26`'s own docstring advertises "strict error
handling". The one interface real users touch can never validate.

Two further interface problems:

- **A `QRCodeTask` cannot be validated at all.** You must convert first, which invents
  `version=1` (`conversion.py:42`), a `CLASSIC` task type (`conversion.py:233`) and a
  CYLINDER goal (`Task.__post_init__`). "Validate what actually arrived" is not
  expressible for QR input.
- **`validate()` over-promises its name.** All four `ValidationRule` members are about
  special-turnpoint arrangement. Nothing checks `version`, an empty waypoint name,
  `radius <= 0`, or the turnpoint-extension ordering rule that `model/task.py:110-112`
  documents. `test_every_rule_is_reachable` pins that every declared rule can fire, not
  that the declared set covers the spec.

Worth keeping as is: `validation.py` imports only `enums` and never `task` — the reason
`enums.py` is a separate module, and a good one — and "report, not gate" stays the right
default for a lenient reader. The question is only which doors can ask.

**Solution.** Check the arrived payload shape rather than the defaulted `Task`, so the
rules can run on either format before defaults are invented; give `parse_task` a three-way
policy (ignore / report / raise) instead of a boolean and wire it to a CLI flag.
`Task.validate()` stays as a convenience over the same rules.

**Wins.**

- leverage: one policy, every input format
- QR input becomes validatable
- locality: nothing invented before checking
- the CLI docstring becomes true

---

## Top recommendation

Start with **A**. It is the only candidate where the current shape ships wrong numbers:
the cumulative column and the drawn route come from the same `Task` and disagree by up to
5.09 km, because the optimizer discards its legs and the caller rebuilds them from
truncated tasks. The same change removes an n× cost, deletes
`calculate_cumulative_distances`, and drops a `dict[str, Any]` from the interface.

**B** is the natural second: same subsystem, same failure mode — one question with two
answers — and it closes a silent output hole plus the ADR 0003 departure. **G** is one
predicate, worth doing on the way past. **C** has the widest reach and the largest scope;
the 25 byte-exact QR golden strings make it safe to attempt, but it wants its own branch.

---

## Left alone (already deep)

- `tests/test_layering.py` as a whole — eight lines of declaration governing 30 modules,
  discovering its own subject. Only the collector predicate is wrong (G).
- `parser.py`'s `_FORMAT_PARSERS` tuple — a real seam: a new input format is one function
  plus one entry, with recognition next to parsing.
- `model/rounding.py` — the name and the Java `Math.round` rationale are the payload;
  inlining `floor(x + 0.5)` at six sites would delete them.
- `model/passthrough.py` — each of its four invariants marks a bug that already happened
  (`322ad01`). The module is small but its interface is not. Relocate with C, don't inline.
- `export/common.py`'s planar cylinder approximation — explicitly licensed as decorative,
  with the reason in the module docstring.
- Wire-key containment — full-format key literals appear in exactly two files
  (`model/task.py`, `qrcode/task.py`). The format/domain seam holds.

## Not re-litigated

ADRs 0001–0004 (optimizer choice, boundary semantics, earth-model selector, removed
beam-search surface); the 2026-06-30 deepening review (all four candidates applied); the
2026-08-16 code-quality plan (11/11 applied); the 2026-08-16 conformance audit (all
findings closed). B reports a place where the code *departs from* ADR 0003 rather than
proposing to change it; E cites ADR 0004 as precedent.

There is no `CONTEXT.md` in this repo. Several candidates would name a concept worth
recording there (the optimized route as a value, the goal line as one answer, a
serializable shape) — worth creating lazily when one is taken on.

---

## Progress

A, B, D and G are applied. Each remaining item is independent; C is next, and it
wants its own branch.

- [x] A. Optimized route as a value — one run, legs kept, cumulative by `accumulate`
  (`6d5651b` the value object, `7104ad3` the cumulative fix, `608963d` one route shared
  by both writers via `TaskDrawing`, `fb9392f` the table sharing it too)
- [x] B. `GoalLine.from_task` made total; `should_skip_last_turnpoint` removed; earth
  model honored (`3cf5af1`, `908275d`)
- [x] G. `_module_level_imports` / `_deferred_imports` collect by "runs at import time"
  (`03d1e1c`)
- [ ] C. One field table per serializable shape; `KNOWN_KEYS` derived; cross-format `unknown` quarantined
- [x] D. Colour as a value across the export seam; invalid `<color><Style>` fixed
  (`d92cc59` the invalid nesting, from the PR #13 review rather than from this card;
  `f875e50` the palette as `Color` values)
- [ ] E. One cylinder solver; dead SSS surface, `show_progress` and `config.py` retired
- [ ] F. `tests/corpus.py` adapter; dead fixtures deleted; inert `@patch`es fixed; PNGs to `tmp_path`
- [ ] H. Validation policy on arrival, wired to a CLI flag

Verification for any of these: `uv run pytest`, `ruff check`, `ruff format`, `mypy`
(strict), plus `import pyxctsk.<pkg>` for all four packages in isolation.

### Outcome of A and B

Both landed as six commits on `docs/arch-review-2026-08-17`, suite green throughout
(357 → 376 tests; the additions are the regressions below plus `tests/export/test_common.py`
and the projection tests, less the four that tested the two deleted functions).

- **A cost less than the card assumed and paid more.** `calculate_task_distances` is
  now about as expensive as one optimizer run (was 4.1× on `task_gimi`, 14.4× on
  `task_gibe`), and the whole suite went from 6.5 s to 2.8 s — the re-optimization loop
  was a measurable fraction of every test that touched a reference task. Distances are
  bit-identical: the legs are summed left to right in the order the old loop accumulated
  them, so no accuracy assertion moved.
- **The rounding stays in the report dict.** The card called the pre-rounding to 0.1 km
  a display artefact inside a computation; it *is* a display artefact, but the dict is
  the display — it exists for the task viewer. `OptimizedRoute` carries unrounded
  metres and the dict rounds when it projects, which is the split the card wanted
  without changing what the viewer reads.
- **A's cross-writer half took a value object, and paid for itself twice over.**
  `TaskDrawing.from_task` now derives what a task looks like once — turnpoints to draw,
  goal line, optimized route — and both writers render that value; `task_to_kml` and
  `generate_task_geojson` are one-liners over `drawing_to_kml` / `drawing_to_geojson`.
  Output is byte-identical (checked against the previous commit in a worktree, with
  simplekml's document-global ids normalized). The route halving is the small part. The
  larger part is that the four questions both writers were each answering separately —
  which turnpoints, which is the goal, where the route runs, is there a goal line — are
  now answered in one place, which is the shape B's defect needed in order to exist.
  Three things fell out of it rather than being pursued: the duplicated
  `original_turnpoints` + `task` parameters, the `isinstance(list)` union in
  `_create_optimized_route_feature` labelled *"Old API for testing"* (the drawing is the
  seam it was standing in for), and the four inert `@patch` decorators — `test_common.py`
  patches the name where it is actually looked up and asserts the count is 1.
- **The task viewer's second route is gone too.** `task_distances_from_route(task, route)`
  is the projection and `calculate_task_distances(task)` is optimize-then-project — the
  same split as `drawing_to_kml` beside `task_to_kml`, so nothing gained an optional
  parameter. The viewer derives one `TaskDrawing` and feeds `drawing.route` to both the
  table and the map: 2 optimizer runs per request became 1, 6.2 ms → 2.8 ms on
  `task_gibe`, with the report dict and the GeoJSON byte-identical. Two `show_progress`
  prints went with it — the ones naming values now computed inside the projection, which
  should not print; the flag is never passed `True` anywhere in the repo (see candidate E).
  With this, A's *"one run serves the table, KML and GeoJSON"* is true as written.
- **B's second defect was worse than reported.** The card said the red goal colour was
  unreachable for a LINE goal; it was unreachable *and* the fix is not a colour change
  but a consequence of the render list — with a goal line present the goal turnpoint is
  legitimately absent, and without one it is now present and red.
- **Regression tests added:** the cumulative column equals the route's prefixes
  (fails on the old code at 5.09 km); a coincident-previous-turnpoint LINE task keeps
  its goal in red while a normal LINE task still has it replaced by the line; and each
  goal-line endpoint sits `length / 2` from the goal *measured on the declared earth
  model* (fails on the old hardcoded ellipsoid by 58 m on a 40 km line).
- **Deleted:** `calculate_cumulative_distances` and `should_skip_last_turnpoint`, both
  public names, both second ways to ask a question that now has one answer. A follow-up
  pass took the rest of the surface A and B orphaned, on the repo owner's call that at
  this stage a second way to ask costs more than backwards compatibility saves:
  `GoalLine.data()` and `get_goal_line_data()` (the positional 4-tuple both writers
  unpacked), `calculate_goal_line_endpoints()`, `optimized_route_coordinates()`
  (it returned exactly `OptimizedRoute.points`), `export.common.get_turnpoints_to_render()`
  and `is_goal_turnpoint()` (both questions the drawing answers), the
  `distance.turnpoint.geod` back-compat alias, and `TaskTurnpoint.goal_line_length`.
  `generate_semicircle_arc` became private. Output stayed byte-identical throughout.
- **One documented rationale died with the cleanup, and is worth someone's attention.**
  `TaskTurnpoint.goal_line_length` was written by `task_to_turnpoints` and read nowhere —
  and that write was the *only* thing making `distance/` import `goal_line.py`. The
  2026-08-17 package-layout review placed the goal line in `distance/` for two reasons:
  that `task_distances` sizes a LINE goal's cylinder from the goal-line length (a real
  import cycle if it lived in `export/`), and that the shapes of a task should not live in
  the package that knows about file formats. The first is now false — a LINE goal's
  cylinder is sized by `radius=0`, not by the length — so `export/` is `goal_line.py`'s
  only consumer and the placement rests on the second reason alone. The module was left
  where it is: the surviving argument is the stronger one, and moving geometry into the
  format package is a layout decision, not a cleanup. The dated layout review is left as
  written, per this directory's convention.

### Outcome of G

Landed as `03d1e1c`, test-only: one classifier walks the tree and splits every relative
import into "runs at import time" and "deferred", with `_import_time_imports` and
`_deferred_imports` as its two projections. `_module_level_imports` was renamed because
"module level" was the wrong name for the question it was asking.

- **The gap was verified by mutation, not by argument.** A `try:`-guarded
  `from ..distance.turnpoint import …` and a class-body `from ..qrcode.encoding import …`,
  both added to `model/task.py`, pass every check on the previous collector and are both
  named with line numbers by the new one. That is the whole claim of the card, reproduced
  in both directions.
- **`if TYPE_CHECKING:` needed a distinction the card did not mention.** Only the guarded
  *body* is type-only — an `else:` on the same `if` is ordinary code that runs on import,
  so the walker skips `body` and keeps walking `orelse`. Pinned by its own test.
- **The card contradicts itself about class bodies, and the Problem paragraph is right.**
  G's **Solution** says to exclude "function, class and `if TYPE_CHECKING:` bodies", but
  its **Problem** says "a class-body import also runs at import time" — which it does, so
  excluding class bodies would have re-created the blind spot one level down. The
  implementation follows the Problem: a class-body import is collected as import-time and
  checked like any other, and only function bodies defer. The Solution's wording is the
  error, left as written per this directory's convention.
- **Nothing in `src/` moved.** All 30 modules still pass all four checks; the suite went
  388 tests with the eight new snippet tests, and the two optional-dependency `try:`
  blocks the card names remain absolute imports, so they are still correctly invisible.
- `CLAUDE.md`'s description of the guard was updated to state the import-time rule, since
  the old wording ("only module-level imports are checked") was the prose the code had
  been implementing.

### Outcome of D

The invalid `<color><Style>` nesting was fixed first, in `d92cc59`, out of the PR #13
review thread. The palette landed as `f875e50`: `Color` values, and one total renderer per
format — `.hex` for GeoJSON, `.kml(alpha)` for KML.

- **The drift was worse than the card counted.** It reports three of five entries lost;
  four of the five turnpoint roles were, with only the goal's red surviving the round trip
  through `simplekml.Color`:

  | role | GeoJSON | KML before | KML after |
  | --- | --- | --- | --- |
  | TAKEOFF | `#204d74` | `#00008b` | `#204d74` |
  | SSS | `#ac2925` | `#8b0000` | `#ac2925` |
  | ESS | `#ff8c00` | `#ffa500` | `#ff8c00` |
  | ordinary | `#269abc` | `#0000ff` | `#269abc` |
  | goal | `#ff0000` | `#ff0000` | `#ff0000` |
  | route | `#ff4136` | `#ff3641` | `#ff4136` |

- **The course line was a second instance of the same cause.** Not the lookup this time:
  its colour was hand-written as `E64136ff`, the digits of `#ff4136` in CSS order after
  the alpha, which KML reads as `aabbggrr` and draws as `#ff3641`. `Color.kml(alpha)` is
  the only place those bytes get ordered now.
- **Three colours the card did not name were not shared at all.** The goal line and the
  control zone's edge and fill were declared separately in each writer and disagreed
  outright — the goal line was red in KML and *green* in GeoJSON. They are palette entries
  now, on the GeoJSON values (repo owner's call): those are a chosen hex family, matching
  the turnpoint palette, where KML's red and cyan were stock `simplekml` constants — the
  same "whatever the library had" choice that produced the drift in the first place. KML's
  goal line becomes green and its control zone teal; GeoJSON output is unchanged
  throughout.
- **The tests had to change shape, not just grow.** `get_turnpoint_color_hex` was pure and
  fully covered while both defects lived in the caller adapting its output, so the new
  tests read the colour back out of *both* rendered documents and compare them — resolving
  KML's `styleUrl` references rather than counting occurrences. Verified by restoring the
  old mapping underneath them: both regressions fail. One further test is structural — no
  `#rrggbb`, `aabbggrr` or `simplekml.Color` literal may appear in either writer, so the
  next colour spelled out in a writer fails in the suite rather than in a map.
- **Deleted:** `get_turnpoint_color_hex`, replaced by `turnpoint_color` returning the
  value. It was never re-exported from the package.
