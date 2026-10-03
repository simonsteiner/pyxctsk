# 2026-09-27 — Deepening candidates after the solver deepening

Reviewed at `0b2ad41` (`main`), scoped by churn since the
[2026-08-19](2026-08-19-deepening-candidates-at-the-front-door.md) review: `distance/`
after `589b5c8` deepened the planar solver, the field tables, and the parser. Companion
visual report: [`2026-09-27-deepening-candidates.html`](2026-09-27-deepening-candidates.html).

Written in the deep-module vocabulary — **module, interface, implementation, depth, seam,
adapter, leverage, locality** — and the domain vocabulary of
[`../../GLOSSARY.md`](../../GLOSSARY.md). Nothing recorded as applied by an earlier review is
re-reported. Every claim about behaviour was reproduced by running the library.

**All eight candidates and all eight smaller findings are applied** — see
[Progress](#progress). The suite went to 1158 passing, 18 skipped, at 98 % line
coverage. Distance reports, QR strings and GeoJSON are byte-identical to `main` across the
reference corpus on both earth models; KML cylinder coordinates change, on purpose
(candidate 6).

---

## The signal

The last reviews drove friction out of the modules and onto their seams. This one found
the seams *existed* but were held by convention rather than enforced: a value whose
constructor did not check its own promise, a field table that trusted wire types, a
solver whose interface said "no turnpoint rules" while its implementation carried one, and
a format whose enums were a second type system for what is only a spelling.

## Candidates

### 1. The measured task's invariant was held by one constructor — **Strong, live defect**

`MeasuredTask` said a task paired with another task's route was *unrepresentable*, but
only `from_task` built the pair; the dataclass constructor was public and checked nothing.
`MeasuredTask(task=bevo, turnpoints=…, route=fobe.route)` reported **47.8 km for a
94.0 km task**, with no error — the 12.8 km bug the value was introduced to kill, still
reachable. The GeoJSON tests relied on the hole to skip the optimizer, and `TaskDrawing`
held a second `task` beside `measured.task`.

**Applied:** the cylinders are derived from the task in `__post_init__`, and the route must
fit them — one point per turnpoint, the task's earth model, every point inside its
cylinder — or `MismatchedRouteError` is raised. `TaskDrawing.task` reads through.

### 2. The field table trusted wire types — **Strong, live defect**

`echo -n 'XCTSK:[]' | pyxctsk convert` printed an `AttributeError` traceback, as did a
number where the goal belongs or a turnpoint in a QR `t` list. A string where an array
belongs was iterated character by character: `"timeGates": "12:00:00Z"` reported
`invalid time: '1'`. The parser's `_PARSE_ERRORS` was a record of whichever built-ins had
leaked so far.

**Applied:** `Shape.read` and `list_codec` check container types and convert every codec
failure into `MalformedPayloadError`, carrying a path such as
`turnpoints[0].waypoint: expected an object, got an array`. The parser catches that one
type.

### 3. The earth model was the task's, stored on every turnpoint — **Strong**

`TaskTurnpoint.earth_model` was copied onto every turnpoint and read from the first.
`"WSG84"` on turnpoint 1 was silently ignored where the same typo on turnpoint 0 raised,
and `[FAI, WGS, WGS]` and `[WGS, FAI, FAI]` measured **278 m** apart.

**Applied:** the optimizer takes `earth_model` once, supplied by `MeasuredTask`;
`TurnpointGeometry` is a centre and a radius. ADR 0003 carries an amendment: its reason
for the per-turnpoint mechanism (no signature churn for the CLI and the writers) had
lapsed, since all of them now go through `MeasuredTask.from_task`.

### 4. The solver seam said "no turnpoint rules" and held one — **Strong**

`solver.py` fixed its first point at the first centre and refused to merge circle 1 into
circle 0 — ADR 0002's takeoff rule — while `route_optimization` applied it again after
solving. Deleting both and projecting the takeoff as a zero-radius circle left all 52
corpus routes identical. `turnpoint.py` was a grab-bag: projection and correction helpers,
a test-only `boundary_point`, and a copy of `center_distance`'s polyline loop.

**Applied:** the rule is stated once, at projection; the solver touches every circle alike.
The projection/correction steps moved to `route_optimization.py`, the polyline to
`center_distance.py`; `turnpoint.py` is the protocol and the value.

### 5. QR images were encoded in one package and decoded in another — **Worth exploring**

Two `QR_CODE_SUPPORT` flags checked different imports, the library had no decode
function, and eight test and script call sites used zxing-cpp directly. A PNG carrying a
malformed `XCTSK:` payload reported "carries no XCTSK: QR code" — the image adapter
swallowed the reason the same string reports inline.

**Applied:** `qrcode/image.py` gains `read_qrcode_image` behind one flag; the image
adapter decodes and hands the text to the URL adapter.

### 6. Export drew cylinders on a flat earth — **Worth exploring**

KML cylinders used a fixed 111 320 m per degree and ignored `earthModel`: 8.7 m out at a
5 km radius and **129 m at 50 km**, so the route visibly missed the cylinder it touched.

**Applied:** `earth.geodesic_arc` is the one way the library draws a curve on the earth —
cylinders via `TaskDrawing.outline_of`, and the control zone (GeoJSON byte-identical).
GeoJSON still carries centre and radius for the client to draw.

### 7. The QR format's enums were a second type system — **Speculative**

Six `IntEnum`s cost twelve translation tables, defaults at every call site (a new
`TurnpointType` silently became `NONE` going out and `None` coming back), and forced
`QRCodeTask.validate` into `conversion.py` behind a function-local import.

**Applied:** the QR models hold the model's enums; the integers are `wire_int_codec`
codecs over one table per field, each tested for totality. Every QR serialization,
conversion and validation result is byte-identical.

### 8. `parse_task` guessed whether a string was a path — **Worth exploring**

`parse_task(Path(...))` failed as "invalid format", nine call sites wrapped paths in
`str()`, and untrusted text could read local files and learn from the error which exist.

**Applied:** `load_task(path)` reads files; `parse_task` never touches the filesystem.

## Smaller findings

1. `DistanceReport` optimized the speed section at construction — a second route per
   distance table, which never shows it (~45 ms per task in the viewer).
2. The distance table read the report's rows through eight string keys; typing them
   surfaced `radius_m` as an `int`.
3. `GoalLine`'s two constructors each repeated the LINE guard and the candidate choice,
   and `_build` checked for a length the guard had ruled out.
4. Four ways across the format boundary where one each way suffices
   (`QRCodeTask.from_task` had no callers), a `simplified=` flag nothing set, and the QR
   key union computed separately in the parser and the converter.
5. `pyxctsk.VERSION` aliased `FULL_FORMAT_VERSION`; `EXTENSION`/`MIME_TYPE` aliased a row
   nothing read them from.
6. `Task.to_json` escaped non-ASCII where `QRCodeTask.to_json` did not; the `Goal`
   docstring named a nonexistent module and the superseded 2024 orientation rule.
7. `task_viewer` looked up an `OUTPUT_FORMATS` row, then passed its name back to be looked
   up again.
8. `pyxctsk.distance` exported the optimizer's tuning constants, read by nothing outside
   their modules.

## Progress

| Item | Commit | Breaking |
|---|---|---|
| 1 — measured task checks its pair | `2341db1` | yes: no `turnpoints=`, no `TaskDrawing(task=)` |
| 3 — one earth model per route | `d62ddcd` | yes: `TaskTurnpoint` loses `earth_model` |
| 2 — field table refuses malformed payloads | `720c17c` | yes: `MalformedPayloadError` replaces `KeyError` & co. |
| 4a — takeoff rule once, outside the solver | `8e7685f` | no |
| 4b — `turnpoint.py` holds what a turnpoint is | `fe01dbc` | no (package exports unchanged) |
| 5 — read QR images beside writing them | `2a6ab01` | yes: `parser.QR_CODE_SUPPORT` removed |
| 6 — geodesic cylinders | `f91be0a` | yes: flat-circle helpers removed; KML changes |
| 8 — `load_task` / `parse_task` | `272474a` | yes: `parse_task` opens no files |
| 7 — QR enums as codecs | `d5e17ba` | yes: `pyxctsk.qrcode.enums` removed |
| s1 — lazy speed section | `10fccc9` | no |
| s2 — typed route rows | `c442d6e` | yes: `route()` returns `RouteRow` |
| s3 — one path through `GoalLine` | `49a20de` | no |
| s4 — one crossing each way | `46448ef` | yes: five methods and two key aliases removed |
| s5 — one name per value | `e8f2fcd` | yes: `VERSION`, `EXTENSION`, `MIME_TYPE` removed |
| s6 — non-ASCII and `Goal` docs | `10adf8d` | no |
| s7 — viewer renders through its row | `87ed773` | no (script) |
| s8 — tuning constants unexported | `981897c` | yes |

**Departure from the report:** candidate 6 proposed that GeoJSON also emit geodesic
polygons. It does not — its centre-plus-radius shape is what the task viewer's client
draws from, and changing it would change that contract for no measured error.
