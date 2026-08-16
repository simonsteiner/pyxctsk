# 2026-08-16 — Code-quality review and refactor plan

Deep code-quality audit of the spec-conformance work (`774d675..033b738`, PR #10 plus the
follow-ups): `task.py`, `qrcode_task.py`, `qrcode_models.py`, `qrcode_encoding.py`,
`parser.py`, `route_optimization.py`, `cli.py`, `exceptions.py` — 1674 insertions.

The behavior is right and unusually well documented — every non-obvious decision carries a
comment explaining the spec text behind it. This review is not about correctness. It is about
what the diff left behind structurally: **derived state stored on the model, a dead
concept kept alive by a runtime dependency, and one passthrough idiom copy-pasted ten
times.** Those three are the blockers; the rest is decomposition and boundary cleanup.

Baseline for all of this: `uv run pytest -m "not slow"` is green at `033b738`. Every item
below must keep it green, and must not change any byte of the reference QR strings in
`tests/data/reference_tasks/qrcode_string/`.

## Status

Legend: `[ ]` todo · `[~]` in progress · `[x]` done · `[-]` dropped (record why)

### Blockers

- [x] **P1** — Delete `Goal.line_length`; derived state stored on the model, with three dead fallbacks
- [x] **P2** — Delete `QRCodeTask.turnpoints_polyline` and the `polyline` runtime dependency
- [x] **P3** — Extract the extensions/unknown passthrough idiom (10 copy-pasted sites)

### Structural

- [x] **P4** — Move `_round_half_up` out of `qrcode_encoding.py`; make it public
- [x] **P5** — Extract `Task ↔ QRCodeTask` conversion into its own module
- [x] **P6** — Drop the `simplified` flag; dispatch on `task_type` alone
- [x] **P7** — Collapse the four QR stringify entry points into one

### Boundaries

- [ ] **P8** — Stop inventing `(0, 0)` coordinates in `QRCodeTurnpoint.from_dict`
- [ ] **P9** — One source of truth for the obsolete-direction default

### Minor

- [ ] **M1** — `_collapse_duplicate_circles`: express "index 0 is special" directly
- [ ] **M2** — `parse_task`: validate once after the dispatch loop, not inside it

---

## P1 — `Goal.line_length` is derived state stored on the model

**Blocker.** This is the flagship finding: one derived number is computed in four places, and
three of the four are unreachable.

`Task.__post_init__` calls `_derive_goal`, which sets `goal.line_length = radius * 2` for every
`LINE` goal (`task.py:497`). So by the time any consumer sees a `Goal` that came out of a
`Task`, `line_length` is *always* populated and always equals `radius * 2`. Consequences:

- `Goal.from_dict` reads `lineLength` from JSON (`task.py:411`) — and `__post_init__` clobbers
  it moments later. That read is dead for every LINE goal parsed through `Task.from_dict`.
  The comment says it "tolerates files older pyxctsk versions wrote"; it does not, it discards
  them.
- `task_distances.py:42` — `if task.goal.line_length is not None: use it; else: derive`. The
  `else` is unreachable, and the `if` branch yields exactly what the `else` would have.
- `task_distances.py:56` — `if goal_line_length is None and tp.radius > 0:` derives it a
  *third* time, a few lines after the branch that already guaranteed it is not None.
- `goal_line.py:208` — the same `field or derive` fallback a fourth time, in a third module.

Meanwhile `goal_line_length_from_turnpoints()` (`goal_line.py:28`) already exists and its
docstring correctly claims to be "the single source of the rule". It is not the single source;
it is one of four.

Two further smells fall out of the same field: `__post_init__` **mutates the `Goal` object the
caller passed in**, and `line_length` is read from JSON but deliberately never written back
(the diff correctly stopped emitting the non-spec `lineLength` key) — a field that can enter
the model but not leave it.

**Remedy — delete the field.**

1. Remove `line_length` from `Goal`, remove the `lineLength` read in `Goal.from_dict`, and
   remove the LINE rule from `Task._derive_goal` (it keeps only "default the type to
   CYLINDER", which no longer needs to mutate anything).
2. At all three consumer sites, call `goal_line_length_from_turnpoints(task.turnpoints)`
   unconditionally. The `if/else` pairs disappear.
3. Update `tests/test_geojson.py:248` and `tests/test_spec_conformance.py:165-172`, which
   construct/assert on the field.

Net: one mutable derived field, three conditionals, a dead JSON read and an in-place mutation
of a caller's object, all gone; the rule stated once, where it already claims to live.

## P2 — `turnpoints_polyline` is a dead concept holding a runtime dependency alive

**Blocker.** `QRCodeTask.from_task` runs `polyline.encode(coordinates, precision=5)` on every
single conversion (`qrcode_task.py:472`) and stores the result in `turnpoints_polyline`.
**`to_dict` never emits it.** The `coordinates` list accumulated in the turnpoint loop exists
only to feed this call. `import polyline` at `qrcode_task.py:36` is the only use of that
package anywhere in `src/`, and `polyline>=2.0.2` is a declared *runtime* dependency
(`pyproject.toml:28`).

It is worse than dead, though. `"p"` is listed in `QRCodeTask.KNOWN_KEYS`
(`qrcode_task.py:135`), described as "a legacy pyxctsk field, not a spec one, but it is read
here". Because it is on the allow-list, an incoming `p` is captured into `turnpoints_polyline`,
excluded from `unknown`, and then **silently dropped on the way out** — precisely the
round-trip data loss the new `unknown` machinery was built to prevent, hidden by the
allow-list that was supposed to make the passthrough safe.

**Remedy — delete the concept, don't polish it.**

1. Delete the `turnpoints_polyline` field, the `coordinates` accumulation, the three
   constructor sites that pass `None`, and the read in `from_dict`.
2. Remove `"p"` from `KNOWN_KEYS`, so any `p` a legacy file carries lands in `unknown` and
   round-trips losslessly for free.
3. Drop `import polyline`, the `polyline>=2.0.2` runtime dependency and its `mypy.ini`
   override; run `uv lock`.

Net: a dead per-conversion computation, a field, a silent data loss and a third-party runtime
dependency all removed. Note the *real* coordinate encoding is `qrcode_encoding.encode_num` —
the codebase's own polyline implementation — so nothing is lost.

## P3 — The extensions/unknown passthrough is copy-pasted ten times

**Blocker.** The diff introduced one good idea and then wrote it out by hand ten times.

Read side, four identical sites (`task.py:228-229`, `task.py:584-585`,
`qrcode_task.py:253-254`, `qrcode_task.py:310-311`, `qrcode_models.py:320-321`):

```python
extensions=list(data.get("x") or []),
unknown={k: v for k, v in data.items() if k not in cls.KNOWN_KEYS},
```

Write side, six identical sites (`task.py:200-203`, `task.py:539-542`,
`qrcode_task.py:169-172`, `qrcode_task.py:217-220`, `qrcode_models.py:238-241`,
`qrcode_models.py:266-269`):

```python
if self.extensions:
    result["x"] = self.extensions
for key, value in self.unknown.items():
    result.setdefault(key, value)
```

Plus four `KNOWN_KEYS` allow-lists and two different extension key names (`extensions` in the
full format, `x` in the QR one) that a reader has to keep straight per site.

The important cost is not the line count. The invariant — *unknown keys must never shadow a
spec field* — is currently expressed as a bare `setdefault` in six places, with nothing
naming it. It is documented in `CLAUDE.md` and nowhere in the code. Adding a seventh model
means re-deriving it from scratch.

**Remedy — one small module, two functions.** Boring and direct beats a mixin here; dataclass
field-ordering makes inheritance awkward and would buy nothing.

```python
# src/pyxctsk/passthrough.py
def read_passthrough(
    data: dict[str, Any], known: frozenset[str], ext_key: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Split a payload into its extensions list and its unknown-key remainder."""

def write_passthrough(
    result: MutableMapping[str, Any],
    extensions: list[dict[str, Any]],
    unknown: dict[str, Any],
    ext_key: str,
) -> None:
    """Append extensions and unknown keys, never shadowing a key already present."""
```

Ten call sites become ten one-liners, and the shadowing rule is stated once, in a docstring,
with a test pointed at it.

## P4 — `task.py` imports a private helper from the QR codec

`task.py:19` is `from .qrcode_encoding import _round_half_up`. Two problems in one line:

- **Direction.** The domain model now depends on the QR *wire codec* for a numeric rule. The
  rounding of `radius` and `altSmoothed` in `Turnpoint.from_dict`/`Waypoint.from_dict` is a
  property of those fields being whole metres, not a property of the QR encoding. `CLAUDE.md`
  records that a `distance` ↔ `task_distances` cycle was deliberately broken; this is the same
  class of drift, in a module that already sits at the centre of the import graph.
- **Privacy.** It is an underscore-private name crossing a module boundary, and
  `tests/test_spec_conformance.py:402` reaches for it too. Three importers means it is public
  in everything but name.

**Remedy.** Move it to a neutral home — a small `rounding.py` is the honest option
(`shared_enums.py` exists but the name would lie about its contents) — rename to
`round_half_up`, and have `qrcode_encoding.py`, `task.py` and the test import it from there.
Keep the excellent docstring about Java's `Math.round`; it is the reason the function exists.

## P5 — Extract the `Task ↔ QRCodeTask` conversion

`qrcode_task.py` is 686 lines and does four jobs: scheme constants, the zlib/base64 codec, the
wire dataclass, and ~280 lines of two-way mapping to the domain model (`from_task`,
`from_task_waypoints`, `to_task`).

The tell that this is one job too many is at `qrcode_task.py:421` and `:577` — both conversion
methods open with a function-local `from .task import (...)` block to dodge a circular import,
and the module also carries a `TYPE_CHECKING` guard for the same reason. Lazy imports inside
methods are a workaround for a layering problem, not a style choice. And the direction is
backwards: the *wire* model currently knows about the *domain* model.

**Remedy.** Move the three conversion methods into `qrcode_conversion.py`, which imports both
`task` and `qrcode_task` at module level and needs no tricks. `qrcode_task.py` drops to ~400
lines and becomes a pure wire model with zero knowledge of `Task`; both function-local import
blocks and the `TYPE_CHECKING` guard disappear. `Task.to_qr_code_task()` keeps a single lazy
import of the new module (or becomes a free function, if the API churn is acceptable).

Neither file crosses 1000 lines today (`task.py` 698, `qrcode_task.py` 686), but both took
150+ lines from this diff. This is the extraction to do before the next feature, not after.

## P6 — The `simplified` flag duplicates `task_type`

`QRCodeTask.to_dict` opens with:

```python
if simplified or self.task_type == QRCodeTaskType.WAYPOINTS:
```

Two sources of truth for one decision, and a caller now has to know that passing
`simplified=False` does not actually get them the full format. The flag threads through
`to_dict`, `to_json`, `to_waypoints_json` and `to_waypoints_string`.

The flag is not *purely* redundant — `tests/test_spec_conformance.py:612` calls
`to_waypoints_string()` on a CLASSIC task to downgrade it. But "downgrade to waypoints" is a
change of task type, not a rendering mode.

**Remedy.** Make `to_dict` dispatch on `self.task_type` alone and delete the parameter from
`to_dict`/`to_json`. Express the downgrade as what it is:

```python
def to_waypoints_json(self) -> str:
    return replace(self, task_type=QRCodeTaskType.WAYPOINTS).to_json()
```

`QRCodeTurnpoint.to_dict(simplified=...)` can keep its flag — the parent already knows which
branch it is in, and a turnpoint has no task type of its own.

## P7 — Four stringify entry points where one will do

`to_string(compressed=False)`, `to_compressed_string()`, `to_waypoints_string(compressed=False)`
and the private `_to_scheme_string`. `to_compressed_string` is a pure identity wrapper —
`return self.to_string(compressed=True)` — and its own docstring says so.

**Remedy.** Keep `to_string(compressed=False)`; delete `to_compressed_string` (four test call
sites to update); with P6, `to_waypoints_string` becomes a one-liner over `replace(...)`.
`_to_scheme_string` then has a single caller and can be inlined.

## P8 — `QRCodeTurnpoint.from_dict` invents coordinates

```python
lon, lat, alt_smoothed, radius = 0.0, 0.0, 0, 0
nums = decode_nums(data["z"]) if "z" in data else []
```

A payload with no `z` produces a perfectly valid-looking turnpoint at 0°N 0°E with radius 0 —
Null Island, in the Gulf of Guinea. A silent fallback papering over an invariant: `z` is
mandatory in *both* formats, so its absence is malformed input, not a default.

Two smaller issues in the same dispatch: the `len(nums) == 2` branch matches no format the spec
defines (the diff's own docstring says three or four), and `len(nums) >= 4` silently ignores a
fifth number rather than rejecting it.

Raising is already handled cleanly upstream — `parser._PARSE_ERRORS` catches `KeyError` and
`ValueError`, and `_parse_xctsk_url` turns them into a descriptive `InvalidFormatError`.
Leniency about *format* is a feature here; inventing coordinates is not.

**Remedy.** Require `z`; accept exactly 3 or 4 numbers; raise a clear `ValueError` naming the
count otherwise. Drop the 2-number branch.

## P9 — The obsolete-direction default lives in two places

`task.py:40` defines `OBSOLETE_DIRECTION_DEFAULT = Direction.EXIT` with a good comment.
`qrcode_models.py:124` hardcodes `QRCodeDirection.EXIT` with a comment reading "see
`task.OBSOLETE_DIRECTION_DEFAULT` so both readers agree". Two constants in two enums, kept in
sync by prose. The next person to change one will not change the other.

Note the *field* has to stay: `tests/data/reference_tasks/elevated-goal/task5_qr_code.txt`
carries `"d":1` (ENTER), so always emitting EXIT would break a byte-exact fixture. This is
about the default only.

Also minor, same site: `if data.get("d")` treats a falsy `d` as absent. Safe today because
`QRCodeDirection` has no zero member — but that is an accident of the enum, not an intent.
`if data.get("d") is not None` says what is meant.

**Remedy.** Name the constant in each layer next to its own enum, and have the comment in one
point at the other — or derive the QR default from the domain one at import time. Either is
fine; two bare literals synced by a comment is not.

## Minor

**M1 — `_collapse_duplicate_circles`.** The rule "index 0 is never collapsed, because the route
starts at the takeoff *center*" is encoded as `if len(unique) > 1 and _same_circle(...)`, with a
comment explaining the encoding. The reasoning in the docstring is excellent; the condition
should say it directly rather than needing a footnote.

**M2 — `parse_task` strict validation.** The `if strict:` block sits inside the parser-dispatch
`for` loop, so validation reads as part of format detection. Hoisting it after the loop
(assign `task`, `break`, then validate once) separates "which format is this" from "is this
task well formed".

## Approval

**Not approved as it stands.** The work is correct, tested and unusually well explained — but
it leaves three structural regressions in the codebase:

- **P1** stores derived state on the model and leaves three unreachable fallbacks behind it.
- **P2** keeps a dead concept alive with a runtime dependency, and silently loses a key that
  the diff's own new machinery would have preserved.
- **P3** copy-pastes one idiom ten times and states its central invariant nowhere in the code.

P1 and P2 are both *deletions* — they remove concepts rather than rearranging them, and neither
touches behavior. Do those two first; they are the cheapest items here and the ones that make
the module smaller. P3 next, then P5, which is the extraction that stops `qrcode_task.py` from
becoming the next 1000-line file.
