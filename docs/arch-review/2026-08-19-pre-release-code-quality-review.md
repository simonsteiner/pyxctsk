# 2026-08-19 — Pre-release code-quality review

**Status: all twelve applied**, in the order the
[Suggested order](#suggested-order) sets out; see [Progress](#progress) at the end.

Findings 9, 10 and 11 were proposed for *after* the release and were then asked for
anyway. That was the right call — 10 turned out to be a live round-trip infidelity
rather than only an inconsistent docstring, and 11 exposed a layering guard that would
have gone quietly green through the move it was meant to survive.

This document is kept as written. The Progress section records what changed and where
it departed from what was proposed; the findings above it are the review as it stood at
`9d271f3`.

Reviewed at `9d271f3` (merge of PR #18), against the whole of `src/pyxctsk`, with the
release of 0.5.0 as the frame. The suite is green (`uv run pytest` — 0 failures, 18
skips, all in `test_xctrack_accuracy.py` behind the concentric-turnpoint marker),
`ruff check` passes, and `mypy src/` reports no issues in 33 files.

This is a *quality* review, not a conformance one: it asks whether the implementation is
as small, direct and hard to misuse as it could be, not whether it matches the spec. The
two current conformance audits ([2026-08-16](2026-08-16-competition-interfaces-audit.md),
[2026-08-18](2026-08-18-s7f-2026-conformance-audit.md)) already answer that question.

**Every claim below was reproduced by running the library at this commit.** Where a
simplification is proposed, it was implemented in a scratch script and checked against
the reference corpus or against randomized inputs; the check and its result are quoted
inline. No proposed change alters a number.

The codebase is in good shape. The four-package split holds, the layering guard is real,
and the values introduced by the last three reviews (`MeasuredTask`, `OptimizedRoute`,
`DistanceReport`, `Shape`, `TaskDrawing`, `GoalLine`) are load-bearing rather than
decorative. What follows is therefore mostly about **residue**: rules that survived in
two places after being centralized in one, helpers that were copied before the abstraction
that would have prevented it existed, and a packaging story that has drifted from what the
code and the README say about it.

Findings are ordered by what they cost, not by size of diff.

---

## Summary

| # | Finding | Kind | Severity |
|---|---------|------|----------|
| [1](#1--the-optional-dependency-story-is-incoherent-and-one-error-message-names-the-wrong-extra) | Optional deps are mandatory, the README says otherwise, and an error names the wrong extra | Release / boundary | **High** |
| [2](#2--the-line-goal-rule-is-applied-in-two-places-each-documented-as-the-only-one) | The LINE→zero-radius rule is applied twice, both claiming sole ownership | Duplication | **High** |
| [3](#3--the-goal-type-crosses-into-distance-as-a-bare-string) | `goal_type` crosses into `distance/` as a bare string | Type boundary | **High** |
| [4](#4--three-constants-for-one-number) | Three constants for "the full format is version 1" | Duplication | Medium |
| [5](#5--code-judo-task_to_turnpoints-is-60-lines-of-one-list-comprehension) | `task_to_turnpoints`: 60 lines → 14, verified identical | Simplification | Medium |
| [6](#6--code-judo-nested-and-nestedlist-are-value-with-a-different-codec) | `Nested`/`NestedList` are `Value` with a different codec | Simplification | Medium |
| [7](#7--code-judo-_generate_semicircle_arc-is-a-uniform-180-sweep) | `_generate_semicircle_arc`: 45 lines → 6, verified to 3e-14° | Simplification | Medium |
| [8](#8--two-copies-of-one-function-and-two-copies-of-one-branch) | Two copies of one function, and two copies of one branch | Duplication | Medium |
| [9](#9--the-library-publishes-two-report-shapes-one-of-them-untyped) | Two report shapes for one job, one of them `dict[str, Any]` | Type boundary | Medium |
| [10](#10--task__post_init__-stores-a-derived-goal-which-the-module-docstring-denies) | `Task.__post_init__` stores a derived goal, which its module docstring denies | Invariant | Medium |
| [11](#11--distanceturnpointpy-is-four-modules-under-one-name) | `distance/turnpoint.py` is four modules under one name, at 650 lines | Decomposition | Low |
| [12](#12--smaller-findings) | Eight smaller findings | Various | Low |

---

## 1 — The optional-dependency story is incoherent, and one error message names the wrong extra

**Files:** `pyproject.toml:26-45`, `src/pyxctsk/parser.py:34-42,114-119`,
`src/pyxctsk/qrcode/image.py:6-14`, `README.md:36-49,225-226`

This is the finding most specific to shipping, and it has four parts that only make sense
together.

**Pillow, qrcode and zxing-cpp are required, but the code and the README treat them as
optional.** `pyproject.toml` lists all three under `[project] dependencies`, so `pip
install pyxctsk` always installs them. Meanwhile two modules carry a `try/except
ImportError` and a `QR_CODE_SUPPORT` flag against them — `parser.py:34` and
`qrcode/image.py:6` — and `MissingQRCodeSupportError` exists as a third piece of
machinery for a state a normal install cannot reach. `CLAUDE.md` states the convention
("Optional/heavy dependencies (QR image handling: Pillow, qrcode, zxing-cpp) are imported
with `try/except` so the core stays importable without them"), and README §Dependencies
lists all three under **Optional**. The packaging says the opposite.

**The one user-facing consequence is wrong advice.** `parser.py:114` tells a user whose
PNG failed to parse:

```
looks like an image, but QR code support is not installed
(pip install 'pyxctsk[web]' for Pillow and zxing-cpp)
```

`[project.optional-dependencies] web` is `flask>=3.1.3`. Following that instruction
installs a web framework and changes nothing about the failure. On any real install the
message is unreachable, which is presumably why it was never caught; if the deps ever do
move to an extra, it is still wrong.

**Two dependencies are documented that are not used.** `geopy>=2.5.0` is a required
runtime dependency, and `src/` never imports it:

```console
$ grep -rn "^\s*\(import\|from\) geopy" src/     # no output
$ grep -rln "geopy" scripts/ tests/ | wc -l      # 6 — all outside the wheel
```

Every user of the wheel installs geopy and its transitive tree for the benefit of
`scripts/`, which is not packaged. Separately, README:41 lists **polyline** as a core
dependency; it is in neither `pyproject.toml` nor any import in the repo. (The
[2026-08-16 plan](2026-08-16-code-quality-refactor-plan.md) records removing "a dead
`polyline` concept holding a runtime dependency" — the dependency went, the README line
stayed.)

**Recommendation.** Pick one story and make all four places say it.

- If QR image handling is genuinely optional — which the code is written for — move
  `Pillow`, `qrcode[pil]` and `zxing-cpp` to a `qr` extra, fix the message to name it,
  and add a CI job that imports `pyxctsk` and runs `convert --format json` with the extra
  uninstalled. That is the only thing that keeps the `try/except` honest; today nothing
  exercises the `QR_CODE_SUPPORT is False` path at all.
- If they are required, delete both `try/except` blocks, both `QR_CODE_SUPPORT` flags,
  `MissingQRCodeSupportError`, the "QR code support is not installed" branch of
  `_unrecognized`, and the README's Optional section. That removes a whole category of
  never-taken branches from two modules.

Either way, drop `geopy` from `dependencies` (move it to the `analysis` extra or to the
dev group if `scripts/` needs it), and delete the `polyline` line from the README.

---

## 2 — The LINE goal rule is applied in two places, each documented as the only one

**Files:** `src/pyxctsk/distance/measured_task.py:40-44,64-74`,
`src/pyxctsk/distance/turnpoint.py:524-547`, `src/pyxctsk/distance/center_distance.py:88-103`

"A LINE goal is a zero-radius point at the goal centre" is the single most-repeated rule
in `distance/`, and it is applied twice.

`task_to_turnpoints` builds the last turnpoint with `radius=0` when the goal is a line,
and its docstring says it is *"the one place that reads a goal's type off the model and
turns it into geometry"*. `plane_circle` then does it again:

```python
radius = 0.0 if turnpoint.goal_type == "LINE" else float(turnpoint.radius)
```

and *its* docstring says it is *"the one place that says what a turnpoint is to the
optimizer, including the rule that a LINE goal is a zero-radius circle at the goal
center… That rule was stated twice"*. A third module, `center_distance._goal_radius`,
resolves the ambiguity by picking a side in prose: *"which is stated once, in
`task_to_turnpoints`. Reading it from there is what keeps this reading measuring to the
same place the optimized distance does."*

So three modules disagree about which of two implementations is canonical, and a reader
following any one docstring reaches a different conclusion. The redundancy is currently
harmless — both agree — but it is exactly the shape that was 151° wrong in the goal-line
finding of the [S7F audit](2026-08-18-s7f-2026-conformance-audit.md): one rule, two
implementations, only one of them maintained.

**Recommendation.** Delete the check in `plane_circle`. `task_to_turnpoints` is the
constructor for every `TaskTurnpoint` the library builds from a task, `_goal_radius`
already depends on it being the owner, and `MeasuredTask.turnpoints` is documented as
"A LINE goal is a zero-radius point here" — that is the invariant. `plane_circle` then
becomes `(x, y, float(turnpoint.radius))` and `TurnpointGeometry.goal_type` stops being
something the optimizer interprets.

If instead `plane_circle` should own it, then `task_to_turnpoints` must stop zeroing the
radius and `_goal_radius` must be rewritten — but note that `MeasuredTask.turnpoints[-1].radius`
is then the *half-line length* rather than the optimizer's radius, and
`LAUNCH_TO_GOAL_BOUNDARY` would silently start subtracting it. The first option is the
one that deletes complexity; the second moves it.

---

## 3 — The goal type crosses into `distance/` as a bare string

**Files:** `src/pyxctsk/distance/turnpoint.py:426,433,546,558,567`,
`src/pyxctsk/distance/measured_task.py:53-64`

`TurnpointGeometry.goal_type` and `TaskTurnpoint.goal_type` are typed `str | None`,
documented as `None, "CYLINDER", or "LINE"`, and compared against string literals.
`measured_task.py` converts *out* of the enum to produce them:

```python
goal_type = task.goal.type.value if task.goal.type else "CYLINDER"
...
if goal_type == "LINE":
```

`GoalType` is a `str`-backed enum in `model/enums.py`, and `distance/turnpoint.py` already
imports from that module (`from ..model.enums import EarthModel`), so there is no layering
reason for the string. The type checker currently cannot tell `"LINE"` from `"Line"` or
`"LNE"` — the same class of hole that `EarthModelLike` was introduced to close, whose own
docstring records that a misspelling *"cost 97.6 m on a 135 km leg and said nothing"*. The
comparison here is not a distance, but it decides whether the goal is a cylinder or a
point, which is worth up to the goal radius.

**Recommendation.** Type both attributes `GoalType | None`, drop the `.value` in
`task_to_turnpoints`, and compare `is GoalType.LINE`. Given finding 2 this removes the
last read of `goal_type` inside the optimizer, leaving it as pure metadata that only
`center_distance` and the drawing consult — at which point the `Protocol` may not need to
declare it at all.

---

## 4 — Three constants for one number

**Files:** `src/pyxctsk/__init__.py:79`, `src/pyxctsk/model/validation.py:41`,
`src/pyxctsk/qrcode/conversion.py:58`

```
src/pyxctsk/__init__.py:79:            VERSION = 1
src/pyxctsk/model/validation.py:41:    FULL_FORMAT_VERSION = 1
src/pyxctsk/qrcode/conversion.py:58:    TASK_VERSION = 1
```

All three mean "the version the full JSON task format declares". `VERSION` is exported in
`__all__` and reachable as `pyxctsk.VERSION`; `TASK_VERSION` is what `qr_code_task_to_task`
stamps onto every converted task; `FULL_FORMAT_VERSION` is what
`validate_task` checks against. So the library can be made to write a version its own
validator rejects by editing one of three files.

The QR side got this right — `QR_CODE_TASK_VERSION` is declared once in `qrcode/task.py`
and imported by `conversion.py` and used for both writing and validating.

**Recommendation.** Keep `FULL_FORMAT_VERSION` in `model/validation.py` (it sits beside
the rule that reads it), have `conversion.py` import it instead of declaring
`TASK_VERSION`, and make `pyxctsk.VERSION` an alias of it — or drop `VERSION` from the
public API, since nothing in `src/`, `tests/` or `docs/` reads it.

---

## 5 — Code judo: `task_to_turnpoints` is 60 lines of one list comprehension

**File:** `src/pyxctsk/distance/measured_task.py:37-97`

The function builds three near-identical `TaskTurnpoint(...)` calls inside a nested
if/else, with comments narrating the control flow (`# Check if this is the goal turnpoint
(last one)`, `# This is the goal turnpoint (last one in the list)`, `# Regular
turnpoint`). The three differ in exactly two values: the radius, and whether `goal_type`
is passed.

The whole body is one comprehension:

```python
goal_type = None
if task.turnpoints and task.goal:
    goal_type = task.goal.type or GoalType.CYLINDER

last = len(task.turnpoints) - 1
return [
    TaskTurnpoint(
        lat=tp.waypoint.lat,
        lon=tp.waypoint.lon,
        radius=0 if (i == last and goal_type is GoalType.LINE) else tp.radius,
        goal_type=goal_type if i == last else None,
        earth_model=task.earth_model,
    )
    for i, tp in enumerate(task.turnpoints)
]
```

**Verified.** Run against every `.xctsk` in `tests/data/reference_tasks/` (the 22-task
corpus plus the `ess-goal/` and `elevated-goal/` sets), comparing
`(center, radius, goal_type, earth_model)` per turnpoint:

```
task_to_turnpoints collapse: identical on 50 tasks
```

Sixty lines become fourteen, the three constructor calls become one, and the "which
turnpoint am I" question is asked once instead of twice. (Shown here with finding 3's
enum applied; the string version collapses the same way.)

---

## 6 — Code judo: `Nested` and `NestedList` are `Value` with a different codec

**File:** `src/pyxctsk/model/shape.py:223-296`

`Value`, `Nested` and `NestedList` each implement `keys`, `read` and `write`, and the
three `read` methods are the same eight lines three times:

```python
if self.optionality.required:
    return {self.attr: <convert>(data[self.key])}
raw = data.get(self.key)
if self.optionality.absent(raw):
    return {}
return {self.attr: <convert>(raw)}
```

The only difference is `<convert>`: `self.codec.from_wire`, `self.shape.read`, or a
comprehension over `self.shape.read`. The `write` methods differ the same way. But a
`Shape` already *is* a codec — `write` is `to_wire`, `read` is `from_wire` — and
`list_codec` already exists for the third case. So:

```python
def shape_codec(shape: "Shape[Any]") -> Codec:
    """A nested shape, as the codec for one value."""
    return Codec(shape.write, shape.read)
```

turns `Nested("sss", "s", QR_SSS_SHAPE, _A_DICT_OR_NOTHING)` into
`Value("sss", "s", shape_codec(QR_SSS_SHAPE), _A_DICT_OR_NOTHING)`, and
`NestedList("turnpoints", "t", QR_TURNPOINT_SHAPE, …)` into
`Value("turnpoints", "t", list_codec(shape_codec(QR_TURNPOINT_SHAPE)), …)`.

**Verified.** A `TASK_SHAPE` rebuilt with `Value` + `shape_codec` in place of both
classes, read and written over the reference corpus:

```
derived keys equal: True
Value+shape_codec reproduces Nested/NestedList byte-for-byte on 24 tasks (2 skipped)
```

(The two skipped files are QR-format payloads under `reference_tasks/`, which have no
`taskType` key; they exercise the QR shapes, not this one.)

Two of the four `Field` subclasses in `shape.py` disappear — about 75 lines — and the
concept count at the interface drops from "four kinds of row" to "a row is an attribute,
a key, a codec and an optionality; nesting is a codec". That is the same move the module
docstring already makes for `z`, the QR takeoff and `T`: an irregular field is a codec or
a `Field` subclass, not a new kind of row.

Note the six irregular subclasses (`_PolylineCoordinates`, `_CompetitionTaskType`,
`_TakeoffTimes`, `Discriminator`) stay as they are — they genuinely own more than one key
or no data at all, which is what `Field` exists for.

---

## 7 — Code judo: `_generate_semicircle_arc` is a uniform 180° sweep

**File:** `src/pyxctsk/distance/goal_line.py:165-209`

Forty-five lines, seven parameters, two halves that each normalize an angle difference
into (-180, 180] and interpolate. It has exactly one caller, `GoalLine.control_zone`,
which passes `start = azimuth - 90`, `through = azimuth`, `end = azimuth + 90`.

For those arguments — the only ones it ever gets — both halves reduce to the same uniform
step of 180°/20 per point. The function is:

```python
def _semicircle_arc(center_lon, center_lat, forward_azimuth, radius, earth_model=None):
    """The control zone's arc: 180° centred on the approach direction."""
    geod = geod_for_earth_model(earth_model)
    return [
        geod.fwd(
            center_lon, center_lat,
            (forward_azimuth - 90 + 180 * i / GOAL_LINE_NUM_POINTS) % 360,
            radius,
        )[:2]
        for i in range(GOAL_LINE_NUM_POINTS + 1)
    ]
```

**Verified.** Old against new over 300 random (lat, lon, azimuth, radius) combinations,
comparing all 21 points:

```
semicircle arc worst coord delta (deg): 2.842170943040401e-14
```

That is ~3 nm — pure float-ordering noise, not a different arc.

Three parameters vanish (`start_azimuth`, `end_azimuth`, `through_azimuth` become one
`forward_azimuth`), and with them the possibility of a caller passing three azimuths that
do not describe a semicircle. The generality was never used, and it is what made the
function long enough to need the two-branch structure in the first place.

---

## 8 — Two copies of one function, and two copies of one branch

**Files:** `src/pyxctsk/distance/route_optimization.py:131-155,214-225`,
`src/pyxctsk/distance/turnpoint.py:290-318`

**(a) `_closest_circle_point` and `_boundary_toward` are the same function.** Both take a
planar circle and a point and return the boundary point nearest that point; both special-case
`radius <= 0` to the centre and a zero distance to `(cx + radius, cy)`. They differ only in
argument order and in whether the local is called `dist` or `distance`.

```console
closest_circle_point vs boundary_toward differences: 0 /5000
```

(5000 random circles and points, including zero radii and coincident points.) They were
introduced at different times for different callers — the final-turnpoint update and the
chained initial placements — and neither author saw the other. Keep one, named for what it
computes rather than for who calls it.

**(b) `plane_optimal_point`'s crossing case is written twice.** Lines 298-315 of
`turnpoint.py`:

```python
if prev_inside != next_inside:
    ts = _segment_circle_intersections(...)
    if ts:
        t = ts[0] if next_inside else ts[-1]
        return <interpolate>
elif not prev_inside and not next_inside:
    ts = _segment_circle_intersections(...)
    if ts:
        t = ts[0]
        return <interpolate>
```

The two branches call the same function, test the same result and return the same
interpolation; only the root selection differs, and the difference is a single predicate.
Both branches together say "unless *both* neighbours are inside, take the crossing":

```python
if not (prev_inside and next_inside):
    ts = _segment_circle_intersections(prev_point, next_point, center, radius)
    if ts:
        t = ts[-1] if prev_inside else ts[0]
        return (
            prev_point[0] + t * (next_point[0] - prev_point[0]),
            prev_point[1] + t * (next_point[1] - prev_point[1]),
        )
```

**Verified** over 4000 random (p1, p2, centre, radius) configurations spanning all four
inside/outside combinations:

```
plane_optimal_point mismatches: 0 /4000
```

This is the module's most algorithmically delicate function, and it is the one where a
duplicated branch is most expensive to have: a fix applied to one copy and not the other
is a wrong distance, not a crash.

---

## 9 — The library publishes two report shapes, one of them untyped

**Files:** `src/pyxctsk/distance/task_distances.py:90-148`,
`src/pyxctsk/distance/report.py`, `src/pyxctsk/export/geojson.py:25,62,98,163,175`

`DistanceReport` was introduced by the last review precisely so that "every number pyxctsk
publishes about one task" is a value with named fields and two renderings. But
`calculate_task_distances(task) -> dict[str, Any]` and `task_distances_from(measured) ->
dict[str, Any]` are still exported from `pyxctsk` and still return an ad-hoc dictionary
covering overlapping ground — `center_distance_km`, `optimized_distance_km`, plus a
per-turnpoint list whose rows differ from `DistanceReport.route()`'s rows in both keys and
units (`cumulative_optimized_km` rounded to 0.1 km vs `cumulative_m` unrounded).

Two report shapes for one task is a maintenance liability at the *published* surface: a
consumer cannot tell which is canonical, and the rounding difference means they disagree
by up to 50 m by construction. `README.md` and `docs/s7f-distance-reference.md` both point
at the `distances` CLI command, i.e. at `DistanceReport`.

**Recommendation.** Decide which is the surface. If `DistanceReport` is (it is), give
`task_distances_from` a typed return — a small frozen dataclass with a `TurnpointRow`
sequence — or make it a rendering of `DistanceReport` (`as_table()`), and mark the dict
form as the display-oriented one it says it is. The `scripts/task_viewer` consumer wants
the rounded km table; that is a legitimate second *rendering*, not a second *report*.

Related and cheap: `export/geojson.py` annotates five functions with bare `dict` /
`dict | None` / `list[dict]`, two of them public (`generate_task_geojson`,
`drawing_to_geojson`). mypy's strict set here does not include `disallow_any_generics`, so
these pass while carrying no information. `dict[str, Any]` costs nothing and says
something. While there: `_create_turnpoint_feature` puts `drawing.role_of(turnpoint)` —
a `TurnpointType` member — into `properties["tp_type"]`. It serializes correctly only
because the enum subclasses `str`; every sibling accessor (`color_of`, `label_of`,
`description_of`) returns a rendered primitive, and this one leaks the domain enum into a
JSON document.

---

## 10 — `Task.__post_init__` stores a derived goal, which the module docstring denies

**File:** `src/pyxctsk/model/task.py:1-17,426-468`

`model/task.py`'s docstring says the dataclasses are plain, and that **"Nothing derived is
stored on them."** `CLAUDE.md` repeats it: *"Nothing derived is stored on the model: a goal
line's length comes from `goal_line_length_from_turnpoints()`, not a field."*

`__post_init__` stores a derived goal:

```console
$ in : {"taskType":"CLASSIC","version":1,"turnpoints":[{...}]}
$ out: {"taskType":"CLASSIC","version":1,"turnpoints":[{...}],"goal":{"type":"CYLINDER"}}
```

A task file with no `goal` key round-trips into one that has a `goal` object. This is the
only place in the library that *invents* output — the whole passthrough design exists
because, in `qrcode/__init__.py`'s words, "anything the format cannot represent is dropped
on the way in, not invented on the way out". The corpus does not catch it because every
reference task carries a goal, which is also why the README's "round-trip byte-identically"
claim survives.

The contract `_derive_goal` provides is genuinely useful — a caller wants
`task.goal.type` to be non-None. But storing it on the model is what makes it visible on
the wire, and it makes `Task` the one dataclass whose constructor rewrites its input.

**Recommendation.** Either make it a read-only projection (`Task.effective_goal` /
`Task.goal_type`, computed, with `goal` left as read) and let `to_dict` write only what was
read; or keep the mutation and state it as the contract in both docstrings, dropping the
"nothing derived is stored" claim. The first is the one that restores the invariant; the
second is a one-line documentation fix if the round-trip behaviour is wanted. Either is
fine — what is not fine is the codebase asserting the opposite of what it does, in the
file that does it.

---

## 11 — `distance/turnpoint.py` is four modules under one name

**File:** `src/pyxctsk/distance/turnpoint.py` (650 lines — the largest in `src/`)

`distance/` is otherwise the best-decomposed package in the library: eight modules, each
named for one concept, each with an `__init__` docstring paragraph explaining why it is
separate. `turnpoint.py` is the exception, and its own docstring says so by listing four
unrelated bullet groups:

1. earth-model selection and geodesy — `EarthModelLike`, `_is_fai_sphere`,
   `geod_for_earth_model`, `geodesic_distance`, `snap_to_boundary` (~120 lines);
2. the Localized Transverse Mercator plane — `ltm_scale_factor`,
   `_cached_tm_transformers`, `local_tm_transformers`, `task_area_center`, `LocalPlane`
   (~180 lines);
3. the planar GetOptPi solver — `_segment_circle_intersections`, `_plane_point_at`,
   `_plane_pcp_point`, `plane_optimal_point` (~140 lines);
4. the turnpoint itself — `TurnpointGeometry`, `plane_circle`, `TaskTurnpoint`,
   `distance_through_centers` (~130 lines).

Only (4) is what the filename says. Groups (1) and (2) are imported by `goal_line.py`,
`center_distance.py`, `speed_section.py` and `task_distances.py`, none of which want a
turnpoint; `route_optimization.py` imports seven names from here spanning all four groups.

**Recommendation — but not before the release.** This is pure movement, it touches every
importer in `distance/` and the layering test, and it changes no behaviour, so it buys
nothing for 0.5.0 and risks a mistake. Afterwards, `earth.py` / `plane.py` / `solver.py` /
`turnpoint.py` would give four modules of 120-180 lines that each match their name, and
would make the `distance/__init__.py` docstring's per-module paragraph writable for all of
them. Note the same argument applies to `tests/conformance/test_spec_conformance.py` at
1668 lines, which is the only file in the repo over 1000 and covers at least four distinct
subjects.

The module docstring's opening claim also wants a correction either way: it calls
`TaskTurnpoint` an *"immutable turnpoint model"*, and it is a plain mutable class with
four assigned attributes and a one-line docstring. It is a frozen dataclass waiting to
happen.

---

## 12 — Smaller findings

Each is small enough to fix in a line or two; none changes a number.

**a. `Task.find_ess_turnpoint` is dead, and `is_ess_goal` duplicates a rule with an
owner.** `find_ess_turnpoint` (`model/task.py:549`) has no caller outside `is_ess_goal`,
no test and no doc reference. `is_ess_goal` has one test and one doc mention and no
caller in `src/`. Both re-implement "find the turnpoint with role ESS", which
`speed_section._role_index` owns and which `speed_section_indices` documents as *"the one
answer"* — including the XC/Waypoints rule that these two ignore. Delete
`find_ess_turnpoint`; either delete `is_ess_goal` or have it read `speed_section_indices`.

**b. `distance_through_centers` uses the `getattr` pattern the codebase documents as a
mistake.** `turnpoint.py:643` reads `getattr(turnpoints[0], "earth_model", None)` against
a parameter typed `list[TaskTurnpoint]`, where the attribute always exists.
`TurnpointGeometry`'s docstring records this exact pattern as the bug that made a
protocol lie about its own interface, and `calculate_iteratively_refined_route:440`
carries a comment saying it was fixed. This is the copy that was missed.

**c. The KML goal-line altitude is a magic number at the call site.**
`export/kml.py:212` passes a literal `500` to `_create_goal_line_elements` with a comment
explaining it, in a module that names `DEFAULT_ALTITUDE = 5000` two lines above.
`GOAL_LINE_ALTITUDE = 500` beside it. (`drawing_to_kml:201` also aliases
`altitude = DEFAULT_ALTITUDE` and re-comments it; the alias earns nothing.)

**d. `_endpoints_from_coords` takes six positional floats for two points.**
`goal_line.py:129` is called once, from `GoalLine.endpoints()`, which unpacks
`self.center` and `self.approach_from` into four floats to do it. Inline it as a method
and the four floats become two tuples that cannot be swapped. Worth doing because this
module already flips axis order between neighbouring lines — `endpoints()` passes
`(lat, lon)` while `control_zone()` five lines later passes `self.center[1],
self.center[0]` — which is a class of mistake that costs a rotated goal line.

**e. `_calculate_savings` is a two-line helper with one caller** (`task_distances.py:22`),
returning an unnamed 2-tuple that the caller immediately unpacks. It is the kind of
pass-through the review standard calls out; inline it.

**f. `_has_line_goal`'s guard is redundant.** `goal_line.py:301-308` tests
`task.turnpoints and len(task.turnpoints) >= 2`; the second clause implies the first.

**g. `uv run mypy src/` — the command in `CLAUDE.md` — always prints a warning.**
`pyproject.toml: note: unused section(s): module = ['tests.*']`. The section is
deliberate (the lefthook hook checks staged tests), so the fix is either to document the
note or to make the documented command `mypy src/ tests/`.

**h. The front-door docstring is bug archaeology.** `src/pyxctsk/__init__.py`'s
module docstring is the package's `help(pyxctsk)` text and the first thing a generated
doc site renders. Two thirds of it is the history of a past export mistake ("That
distinction is the one this file got wrong — it exported `distance_through_centers`,
whose own docstring says…"). The rationale-in-docstring style serves this codebase well
*inside* the implementation, where the reader is a maintainer; at the public front door
the reader is a user, and what they need is the first paragraph plus the "reach into
`pyxctsk.distance` for the pieces below the answers" note. Move the archaeology to a
comment. (The same applies, less urgently, to `Color`, `TurnpointGeometry` and
`QRCodeTask.SIMPLIFIED_KEYS`, all of which are public.) Separately, `__all__` is in no
discernible order — sorting it makes an accidental omission visible.

---

## What this review did *not* find

Stated because their absence is the useful signal:

- **No layering violation.** `tests/test_layering.py` passes, and manual reading of the
  import graph found no back edge, no import through a package `__init__` from inside it,
  and exactly the two documented function-local imports.
- **No new spaghetti.** No ad-hoc conditional bolted into an unrelated flow; the
  special cases that exist (`_SPEED_SECTION_ONLY`, `_A_DICT_OR_NOTHING`,
  `_CompetitionTaskType`) are all declared as named policy objects beside the shape that
  needs them, which is the right shape.
- **No file pushed past 1000 lines by recent work.** The only file over it is a test
  file, and it got there gradually.
- **No unnecessary optionality or cast churn.** The `# type: ignore` comments are all
  against untyped third-party surfaces (simplekml, zxingcpp, PIL) and are individually
  justified.
- **No sequential orchestration that should be run in parallel.** The one place independent work is
  serialized is `_INITIAL_PLACEMENTS`, three sweeps run in a loop; they are sub-millisecond
  and the sequential form is what makes the result deterministic.

---

## Suggested order

Before 0.5.0, because they are user-visible or cheap:

1. Finding 1 — the packaging and the wrong `[web]` advice.
2. Finding 4 — the three version constants.
3. Finding 12b, 12c, 12f, 12h — one-liners.

Before or shortly after, because each deletes code and is verified:

4. Findings 5, 7, 8 — three verified collapses, ~130 lines removed, no behaviour change.
5. Findings 2 and 3 — one rule, one owner, one enum.
6. Finding 6 — two `Field` subclasses deleted.

Deliberately after the release:

7. Findings 9, 10, 11 — the report surface, the derived goal, and the `turnpoint.py`
   split. Each is a decision about a published contract or a large mechanical move, and
   neither is what a release week is for.


---

## Progress

Applied on `docs/code-quality-review-2026-08-19`, one finding or coherent group per
commit. Every commit ran the full suite, `ruff check`, `ruff format` and
`mypy src/ tests/` green, and each behaviour-preserving claim was checked against the
reference corpus rather than asserted.

```
77dae95 build: make QR image support the extra the code already assumes
4b5ea96 fix: one constant for "the full format is version 1"
2fb41d1 fix: five small corrections across the front door and the writers
4b6b99f refactor(distance): one boundary helper and one crossing branch
28b4674 refactor(distance): the goal line's geometry in the shape it is used
54bc1bf refactor(distance): the LINE goal rule gets one owner and one type
0f67e33 refactor(model): nesting is a codec, not a kind of row
6d48c35 fix(model): ask the goal whether it is the ESS, and inline a two-line helper
17b4615 fix(export): give the GeoJSON boundary a type, and stop leaking an enum
5019af0 docs: record the review's outcomes and the two departures
c17ec18 refactor(distance): the distance table is a rendering of the report, not a second one
7be1fa2 fix(model): derive the goal's default, stop storing it
78a62e0 refactor(distance): split turnpoint.py into the four modules it was
```

| # | Finding | Outcome |
|---|---------|---------|
| 1 | QR deps / wrong extra | **applied.** Pillow, qrcode and zxing-cpp moved to a `qr` extra; both messages name it, spelled once as `exceptions.QR_EXTRA_INSTALL`; `geopy` moved to the `dev` group; the `polyline` line left the README. `scripts/check_core_without_qr.py` is new and runs in both release workflows. |
| 2 | The LINE rule, twice | **applied.** `task_to_turnpoints` keeps it; `plane_circle` is a projection and nothing else. |
| 3 | Stringly-typed goal type | **applied**, and it went further than proposed: with `plane_circle` no longer reading it, nothing in the optimizer does, so `TurnpointGeometry` stops declaring it and the protocol test pins the attribute set both ways. |
| 4 | Three version constants | **applied.** `TASK_VERSION` deleted, `pyxctsk.VERSION` is an alias. Kept exported rather than removed — nothing reads it, but aliasing fixes the drift without breaking a public name. |
| 5 | `task_to_turnpoints` | **applied**, in the same commit as 2 and 3 rather than before them. Writing it with strings and then rewriting it with the enum would have written the same lines twice. |
| 6 | `Nested` / `NestedList` | **applied.** Both deleted for `shape_codec`; shape.py loses 52 lines and two of its five row kinds. |
| 7 | `_generate_semicircle_arc` | **applied**, together with 12d — both are the same module's parameter-count problem. |
| 8 | Two copies of one function, two of one branch | **applied.** `_closest_circle_point` deleted for `_boundary_toward`; the crossing branch collapsed. Route points and both §7.2 distances bit-identical across the corpus. |
| 9 | Two report shapes | **applied.** `DistanceReport` is canonical; `TaskDistanceTable`/`TurnpointRow` are it rounded for display, with `as_dict()` byte-identical to the dictionary they replace. The one datum the table had that the report lacked — `cumulative_center_m` — is new in `center_distance.py`, the module that owns the convention, and in the report's route rows. Its typed return immediately caught an unchecked `Optional` in a corpus test that the `Any` values had hidden. |
| 10 | The derived goal on `Task` | **applied**, and it was a live defect rather than only an inconsistent docstring: two corpus tasks gained `"goal":{"type":"CYLINDER"}` on every round trip. `Task.effective_goal` is the contract as a projection; `qrcode/conversion.py` moved to `task.goal` in the same spirit, so a task whose goal was never spelled out now writes a payload without a `g`. |
| 11 | `distance/turnpoint.py` at 650 lines | **applied.** Four modules of 125–228 lines: `earth`, `plane`, `solver`, `turnpoint`. Every published output byte-identical. It also caught the guard the finding did not anticipate — the scipy-is-deferred check read `distance/turnpoint.py` by name and would have passed while checking a file that no longer held the call. It walks all of `src/` now. |
| 12a | Dead `find_ess_turnpoint` | **applied**, with a **departure**: the finding suggested `is_ess_goal` read `speed_section_indices`, which it cannot — that lives in `distance/`, and `model/` may not import it. `is_ess_goal` instead asks the last turnpoint for its role, which removes the value-comparison hazard and is what the model should answer anyway. |
| 12b | The `getattr` earth model | **applied.** |
| 12c | The KML magic `500` | **applied**, as `GOAL_LINE_ALTITUDE` beside `TURNPOINT_ALTITUDE` (was `DEFAULT_ALTITUDE`). |
| 12d | `_endpoints_from_coords` | **applied**, with 7. `GoalLine.approach_azimuth()` is the name that fell out. |
| 12e | `_calculate_savings` | **applied.** Inlined. |
| 12f | `_has_line_goal`'s redundant clause | **applied.** |
| 12g | The mypy note | **applied.** `mypy src/ tests/` in all five places. |
| 12h | The front-door docstring | **applied**, and `__all__` sorted. |

### What the applied changes are worth

Only one changes a number a user sees, and it is the point of its finding: two
goal-less corpus tasks stop gaining a `goal` key on output. Verified per commit,
against every task in `tests/data/reference_tasks/`:

- optimizer duplication (8): route points and both §7.2 distances **bit-identical**;
- goal-line geometry (7, 12d): 3 of 1748 GeoJSON floats move, worst 7.1e-15° (~1 nm);
- the LINE rule and the enum (2, 3, 5): distances and both export formats
  **byte-identical**;
- the field tables (6): every task's full JSON, `XCTSK:` string and waypoints
  `XCTSK:` string **byte-identical**;
- `is_ess_goal` (12a): **identical** on all 26 corpus tasks;
- the distance table (9): `as_dict()` **byte-identical** to the dict it replaces;
- the derived goal (10): all 26 QR strings, all 26 GeoJSON documents and every
  distance unchanged; the two goal-less XC/Waypoints tasks now round-trip **exactly**;
- the module split (11): distances, KML, GeoJSON, both serializations and the display
  table all **byte-identical**.

The suite grew from 972 to 993 passing tests. The new ones are the cases the removed
duplication had left uncovered: a target at a circle's centre, that the optimizer needs
no goal vocabulary, that a nested row obeys the same optionality as any other, that the
converter stamps the version the validator checks, that the table is the report rounded
and its centre column ends at its centre total, that a task without a goal key writes
none, and the two shapes `is_ess_goal` used to get wrong.

### Breaking changes this produced

All are in `CHANGELOG.md` under Unreleased; collected here because they are the price
of the review:

- `pip install pyxctsk` no longer brings QR *image* support — `pyxctsk[qr]` does (1);
- `TaskTurnpoint.goal_type` is a `GoalType`, not a `str`, and `TurnpointGeometry` no
  longer declares it (3);
- `task_distances_from` / `calculate_task_distances` return a `TaskDistanceTable`;
  `.as_dict()` restores the dictionary exactly (9);
- `Task.__post_init__` no longer stores the CYLINDER default — `Task.effective_goal`
  derives it (10);
- `Task.find_ess_turnpoint` is gone (12a);
- `model.shape.Nested` and `NestedList` are gone, replaced by `shape_codec` (6);
- `export.kml.DEFAULT_ALTITUDE` is `TURNPOINT_ALTITUDE` (12c);
- code reaching into `pyxctsk.distance.turnpoint` for an earth model or a projection
  must name `pyxctsk.distance.earth` or `.plane`; everything stays exported from
  `pyxctsk.distance` itself (11).
