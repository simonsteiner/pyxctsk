# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- **`DistanceReport`, the S7F distance report as a value** (`pyxctsk.DistanceReport`). `CLAUDE.md` calls the `distances` JSON keys and its `notes` block "part of the public surface" and the command "the one another implementation is meant to diff against", but the report was two private functions inside `cli.py` — reachable only by running the CLI. So every test of *what the report says* built a click runner, invoked a command, asserted an exit code and parsed stdout; `README.md` documented no distance interface at all; and `docs/s7f-distance-reference.md` told a library user to hand-roll the report from four imports, in a snippet that omitted the route points and raised `AttributeError` on any task with no speed section. `DistanceReport.from_task(task)` builds it, `as_dict()` renders the JSON surface and `as_text()` the human one — two renderings of one set of fields, where the dict and the text renderer used to select the same eleven numbers separately and had already drifted on what a missing value means. Output is byte-identical in both formats across the reference corpus. Also moved out of the CLI: the rule that a task needs two turnpoints to have a distance at all, now `TooFewTurnpointsError` rather than something only the CLI knew — a library caller used to get `0.0`.
- **`MeasuredTask`, a task bound to the optimized route flown for it** (`pyxctsk.MeasuredTask`). Every number S7F §7 defines is measured along one route and that route belongs to one task, but nothing bound the two: "the optimized route of this task" was a two-step incantation — convert the cylinders, then optimize them — written out at 12 call sites, and the pairing survived only as a sentence in two docstrings that no caller and no type checker could check. `MeasuredTask.from_task(task)` derives it once and carries the task, its cylinders and the route; `total_m` and `cumulative_m()` are projections of that route. `task_to_turnpoints` moved here from `task_distances`, beside the value that holds its result, which also removed the edge that made the goal line depend on the distance *report* module.
- **Four more structural rules**, reachable from both formats: a negative cylinder radius, a version the format does not define, a turnpoint carrying more manufacturer extensions than the root list has entries, and a turnpoint extension repeating the root's `id`. The last two are the checkable half of the spec's rule that turnpoint extensions sit "in the same order as the root extensions" with the id "not repeated" — position is the only thing linking one to a root entry, which is why the order is fixed. Note a radius of **zero is valid** and deliberately not rejected: every XC/Waypoints turnpoint has one, and the optimizer reads it as the point itself.
- **`pyxctsk convert --strict`** rejects a task that breaks the spec's structural rules instead of converting it, naming the rule that broke. The CLI's own help had advertised "strict error handling" since it was written, while `convert` called `parse_task` with no `strict` and offered no flag to set it — so the one interface real users touch could never validate anything. Off by default, matching the library: reading stays lenient so a malformed task can still be inspected and converted.
- **`QRCodeTask.validate()` checks a QR payload as it arrived.** Validation used to require a `Task`, so QR input had to be converted first — and conversion invents a `version=1`, a `CLASSIC` task type and a CYLINDER goal that the payload never carried, making the report partly a report on the converter. The rules now read exactly what they need (`validate_turnpoint_roles`: the order of the turnpoint roles, and whether this is a waypoints task), and each format adapts onto them. `Task.validate()` is unchanged.
- **`CONTEXT.md`** names the vocabulary the codebase is written in — the competition's (turnpoint, speed section, goal line, control zone, optimized route) and the format's (serializable shape, field table, wire key, unknown key). Where a concept has two spellings, one is picked and the others listed as ones to avoid.
- **Every serializable shape declares its wire mapping as one field table** (`pyxctsk.model.shape`). A turnpoint in the full format, a goal in the QR one, an XC/Waypoints task: each is an ordered table of fields, and `to_dict` / `from_dict` are the two traversals of it. A field owns *keys*, plural — a turnpoint's whole geometry is the single key `z`, and a QR takeoff is one value across the root `to` and `tc` — so the table stays total while the irregular cases stay one row each. Three things follow, each of which was a bug this release also fixes: `KNOWN_KEYS` is derived from the table rather than hand-declared beside it, read and write cannot drift, and row order is output order, which is where the byte-exact QR key orders now live. Output is byte-identical across all 65 reference inputs rendered four ways each.
- **`task_distances_from_route(task, route)`** projects an already-optimized route into the distance report, so a caller holding a route — `TaskDrawing.route`, say — gets the table beside the map without optimizing the task again. `calculate_task_distances(task)` is unchanged: it optimizes once and projects through the same function. The dev task viewer asks for distances and GeoJSON in one request and now runs the optimizer once instead of twice (6.2 ms → 2.8 ms on `task_gibe`, output identical).
- **`TaskDrawing`, the value both map writers render** (`pyxctsk.export.TaskDrawing`). `TaskDrawing.from_task(task)` derives what a task looks like once — which turnpoints to draw, the goal line if there is one, and the optimized route — and `drawing_to_kml` / `drawing_to_geojson` render that value. Rendering one task in both formats therefore optimizes the route once instead of twice, and the two formats cannot disagree about the task's shape, which is how the vanished-goal defect below was possible in the first place. `task_to_kml(task)` and `generate_task_geojson(task)` are unchanged and now one line each; output was byte-identical for this change (the KML fixes under *Fixed* do alter it, deliberately).
- **`QRCodeGoal` emits `d, fa, t`**, the key order tools.xcontest.org uses, so QR output stays byte-identical to the reference producer now that a fixture carries `fa` at all.
- **Unknown fields are preserved verbatim** in `Task.unknown` and `Turnpoint.unknown`, so a round-trip no longer silently discards data the spec does not define. Producers do put things outside the spec's `extensions` mechanism: the new `tests/data/reference_tasks/elevated-goal/` fixtures store their elevated goal altitude as a root `{"o": {"v": 2, "fa": 1220}}` and carry a per-turnpoint `{"o": {"a1": 180}}`, all of which used to be dropped on read. Nothing is interpreted — in particular `o.fa` is deliberately **not** mapped onto `goal.finishAltitude`, because that `fa` is absolute AMSL while the spec defines `finishAltitude` as metres AGL above the last turnpoint; copying it across would turn a value we merely fail to understand into one we report wrongly. Unknown keys can never shadow a spec field on output.
- **The `XCTSKZ:` compressed QR encoding is supported in both directions.** Reading is automatic — `parse_task`, the QR-image adapter and `QRCodeTask.from_string` accept either scheme. Writing is opt-in so existing output is unchanged: `to_string(compressed=True)`, `to_waypoints_string(compressed=True)`, and the CLI's `--compressed` / `-z` flag for the `png` and `qrcode-json` formats. On `task_bevo` the compressed payload is 483 bytes against 720.
- **`Task.validate()` checks the spec's structural rules** — TAKEOFF only on the first turnpoint; SSS and ESS exactly once; SSS before ESS — and returns one `ValidationIssue` per violation, each naming the `ValidationRule` it broke (see *Changed* below). Parsing stays lenient so a malformed task can still be read and inspected; `parse_task(data, strict=True)` raises the new `TaskValidationError` instead. XC/Waypoints tasks are exempt from the SSS/ESS rules.
- **Manufacturer `extensions` are preserved** through both task formats — the root list, per-turnpoint lists, and the QR format's `x` key — carried verbatim as opaque dicts in `Task.extensions` and `Turnpoint.extensions`. They were previously dropped silently on read.
- **`goal.finishAltitude` is supported** (`Goal.finish_altitude`, QR key `fa`). This elevated-goal altitude in meters AGL is a scored parameter and was previously dropped on every round-trip.

### Changed

- **Breaking (API): `task_distances_from_route(task, route)` is now `task_distances_from(measured)`**, and `GoalLine.from_task`'s `route=` argument is replaced by `GoalLine.from_measured_task(measured)`. Both took a task and a route as two arguments with the pairing stated only in prose — *"Must be the task `route` was optimized for"* — and handing over a mismatched pair was silent: `task_distances_from_route(task_bevo, route_of_task_duna)` returned a fully formed report reading 81.2 km for a 94.0 km task, with a 36.9% "savings" figure and no error, while the reverse direction filled the cumulative column with a tail of zeros. Taking the pair as one value makes that unrepresentable at the call site, and retires the `if i < len(cumulative) else 0.0` guard it needed (unreachable when correct, a wrong-number generator when not). `calculate_task_distances(task)` is unchanged. `SpeedSection.from_measured_task` and `GoalLine.from_measured_task` are new beside the existing `from_task` constructors, which are unchanged; `TaskDrawing.route` still reads, now through `TaskDrawing.measured`. Every distance, KML document and GeoJSON document is byte-identical across the 24-task reference corpus.
- **`pyxctsk.distance.config` is gone; both its constants moved to `route_optimization`** and are still exported from `pyxctsk.distance`, so no import breaks. The module put a value the spec fixes next to one worth tuning and called the pair configuration: `DEFAULT_NUM_ITERATIONS` really is the sweep limit behind the public `num_iterations` parameter, while `CONVERGENCE_EPSILON_M` is FAI S7F §7.1.3's ε = 0.1 m, which ADR 0004 already settled is *not* a knob ("precision is governed by the spec's ε = 0.1 m, not by a sampling knob"). It keeps its name rather than being inlined, because the citation is the payload — the same reason `model/rounding.py` exists — but it now sits beside the convergence loop it governs, with the reasoning attached.
- **The validation rules read a `TaskStructure`**, not a `Task`: turnpoint roles and radii, the extensions at both levels, the declared version, and whether this is a waypoints task. Each format presents one, so a rule added once reaches both — the four new rules above did, without either adapter being touched.
- **Breaking (API): `pyxctsk.distance.sss` is removed**, with `calculate_sss_info` and `calculate_optimal_sss_entry_point`. The whole module was dead: `calculate_sss_info` had no caller anywhere and its only test body was `assert True`; its two private helpers existed for it alone; and `calculate_optimal_sss_entry_point` was a one-line pass-through to `TaskTurnpoint.optimal_point` that only tests called. An SSS entry point is a query on the computed route, and the tests that mattered — the optimizer reaching the SSS cylinder's boundary rather than its centre — now ask it that way.
- **Breaking (API): `show_progress` is gone** from `calculate_iteratively_refined_route`, `optimized_distance` and `calculate_task_distances`. Five signatures carried it and nine `print()` branches hung off it, in a library; nothing in the repo ever passed it `True`. `src/pyxctsk/` now contains no `print()` at all. Callers who passed it *positionally* should check their argument order — `optimized_distance(turnpoints, show_progress, num_iterations)` had it second.
- **Breaking (API): one solver and one projection policy for "the optimal point on a cylinder".** `TaskTurnpoint.optimal_point` projected into a Transverse Mercator plane centred on *that turnpoint*, while the route optimizer projected into the plane of the whole task area — the same paragraph of the spec (S7F §7.1.2) answered two ways, with the shipped answer being the optimizer's and every crossing-case test aiming at the other one. The plane is now a value: `LocalPlane` (new, exported from `pyxctsk.distance`) is built around one turnpoint or a whole task, and `optimal_point` takes one as an optional third argument. It defaults to a plane around its own turnpoint, so existing calls are unchanged; passing the task's plane returns exactly what the optimizer chooses. `plane_circle` (also new and exported) is the one statement of what a turnpoint is to the solver, including that a LINE goal is a zero-radius circle at the goal center — a rule that used to be written twice. `TaskTurnpoint._find_optimal_goal_line_point`, a twenty-line docstring over `return self.center`, is removed. Every route point and total is bit-identical to before across all 22 reference tasks with published distances.
- **Breaking (API): `calculate_iteratively_refined_route` returns an `OptimizedRoute`** instead of a `(distance_m, points)` tuple. The optimizer measures every leg on its way to the total and used to throw them away, leaving callers to reconstruct them; the value it returns now carries `points`, `legs` and the `earth_model` they were measured on, with `total_m` and `cumulative_m()` derived from those. `optimized_distance` is unchanged as the projection for callers wanting only the number, and the distances themselves are bit-identical — the legs are summed in the same order as before. Callers unpacking the tuple must use `.total_m` / `.points`. `OptimizedRoute` is exported from `pyxctsk.distance`.
- **Breaking (API): the package is split into `model`, `qrcode`, `distance` and `export`.** `src/pyxctsk/` had grown to 27 modules in one flat directory, with prefixes (`qrcode_*`, `task_*`) doing the job a directory should. The public API is unchanged — everything re-exported from `pyxctsk` itself is where it was — but every deep import path moves:

  | was | now |
  | --- | --- |
  | `pyxctsk.task`, `.task_enums`, `.time_of_day`, `.passthrough`, `.validation`, `.rounding` | `pyxctsk.model.{task,enums,time_of_day,passthrough,validation,rounding}` |
  | `pyxctsk.qrcode_{task,models,encoding,enums,image,conversion}` | `pyxctsk.qrcode.{task,models,encoding,enums,image,conversion}` |
  | `pyxctsk.turnpoint`, `.route_optimization`, `.task_distances`, `.sss_calculations`, `.optimization_config` | `pyxctsk.distance.{turnpoint,route_optimization,task_distances,sss,config}` |
  | `pyxctsk.kml`, `.geojson`, `.visualization_common` | `pyxctsk.export.{kml,geojson,common}` |
  | `pyxctsk.goal_line` | `pyxctsk.distance.goal_line` |
  | `pyxctsk.distance` | unchanged — the facade module became the package `__init__` |

  Dependencies now run one way, `model → qrcode` and `model → distance → export`. Goal-line geometry landed in `distance/` rather than beside the KML and GeoJSON writers that draw it, because `task_distances` sizes a LINE goal's cylinder from the goal-line length — with it in `export/` that edge closes a real import cycle. Each package's `__init__.py` re-exports its own interface and documents what it holds.
- **The domain model no longer imports the QR format.** `Task.to_qr_code_task()` pulled `pyxctsk.qrcode.task` into `pyxctsk.model.task` at module level; it now reaches `pyxctsk.qrcode.conversion` through a function-local import. Behaviour is identical, and `from pyxctsk.qrcode import task_to_qr_code_task` now works — the package's own interface could not name its conversion module while that edge existed. `tests/test_layering.py` parses the import graph and fails if any package imports one it may not depend on.
- **Breaking (API): the back-compat and duplicate accessors around the goal line and the route are removed.** The library is early enough that a second way to ask a question costs more than it saves:

  | removed | ask instead |
  | --- | --- |
  | `GoalLine.data()`, `get_goal_line_data(task)` | `goal_line.length`, `.endpoints()`, `.control_zone()` |
  | `calculate_goal_line_endpoints(...)` | `GoalLine.endpoints()` |
  | `generate_semicircle_arc(...)` | now `_generate_semicircle_arc`, internal to `control_zone()` |
  | `optimized_route_coordinates(turnpoints)` | `calculate_iteratively_refined_route(turnpoints).points` |
  | `export.common.get_turnpoints_to_render(task)` | `TaskDrawing.from_task(task).turnpoints` |
  | `export.common.is_goal_turnpoint(...)` | `TaskDrawing.is_goal(turnpoint)` |
  | `distance.turnpoint.geod` | `geod_for_earth_model(earth_model)` |
  | `TaskTurnpoint(..., goal_line_length=...)` | nothing — it was written and never read |

  The dead `AttributeError` branch in `generate_qrcode_image` went with them: it fell back to the pre-9.1 Pillow resampling API, and `pyproject.toml` pins `Pillow>=11.3.0`.

  `get_goal_line_data` and `geod` had no callers left at all; the rest had none in `src/`. Output is unchanged — verified byte-identical on `task_bevo`, `task_piga_line` and `task_nohe`.
- **Breaking (API): the KML and GeoJSON writers take a `TaskDrawing`.** Their private helpers changed shape with it — `_create_turnpoint_feature(drawing, turnpoint, index)` instead of `(turnpoint, index, all_turnpoints, task=None)`, `_create_optimized_route_feature(drawing)` instead of a `Task`-or-`list` union that existed only so tests could inject coordinates, and `_create_goal_line_features(drawing)`. `export.common.get_optimized_route_coordinates` is deleted: it was a two-line pass-through whose only purpose was to be the writers' shared route accessor, which the drawing now is.
- **Breaking (API): `_task_to_turnpoints` is now `task_to_turnpoints`**, re-exported as `pyxctsk.distance.task_to_turnpoints`. It was private by name only — the export package, five test modules and a script all imported it, and it now crosses a package seam.
- **`Task` ↔ `QRCodeTask` conversion moved to the new `qrcode_conversion` module**, which imports both models at the top level. It was ~280 lines inside `qrcode_task.py` (686 lines → 428), reached through function-local `from .task import ...` blocks that existed only to dodge a circular import — the wire model knowing about the domain model, in the wrong direction. The six enum pairs are now translation tables rather than if/elif chains, with `tests/test_qrcode_conversion.py` asserting both directions stay mutual inverses and cover every enum member. `QRCodeTask.from_task()`, `.from_task_waypoints()`, `.to_task()` and `Task.to_qr_code_task()` are unchanged as API.
- **The spec's structural rules moved out of the domain model** into the new `validation` module, which imports `task_enums` but never `task`, so it checks the model without depending on it. `Task.validate()` is the entry point onto it and `task.py` drops from 690 to 566 lines, holding exactly the domain dataclasses. The enums it used to carry are now in `task_enums` and re-exported, so `from pyxctsk.task import TaskType` still works.
- **Breaking (API):** `Task.validate()` returns `list[ValidationIssue]` rather than `list[str]`, and `TaskValidationError.issues` holds the same. Each issue names the `ValidationRule` it broke, so a caller can react to a specific violation instead of matching English prose that is free to change. `str(issue)` gives the previous string and `str(error)` is unchanged. Both new types are exported from `pyxctsk`.
- **`shared_enums` is renamed `time_of_day`.** It held no enums — only `TimeOfDay` — and the name became actively misleading once `task_enums` took the job it implied. The canonical `from pyxctsk import TimeOfDay` is unaffected; only a direct `from pyxctsk.shared_enums import ...` breaks.
- **`round_half_up` moved to the new `rounding` module** and lost its underscore. `task.py` was importing `_round_half_up` from `qrcode_encoding` — the domain model reaching into the QR wire codec, across a private boundary, for a rule that belongs to neither: rounding `radius` and `altSmoothed` follows from those values being whole metres, not from the format they are written in.
- **Each layer names the obsolete-direction fallback beside its own enum.** `qrcode_models` hardcoded `QRCodeDirection.EXIT` with a comment pointing at `task.OBSOLETE_DIRECTION_DEFAULT`; two literals kept in sync by prose. The QR side is now `QR_OBSOLETE_DIRECTION_DEFAULT` in `qrcode_enums`, and `tests/test_qrcode_conversion.py` asserts the two agree. The reader also treats `"d": 0` as present rather than absent, which was only safe by accident of the enum having no zero member.
- **The extensions/unknown passthrough lives in one place**, the new `passthrough` module, instead of being written out by hand at each of its ten call sites (four readers, six writers, across `Task`, `Turnpoint`, `QRCodeTask` and `QRCodeTurnpoint`). Behavior is unchanged; the point is that the rule *"an unknown key never shadows a spec field"* is now stated and tested once rather than implied by a bare `setdefault` in six places.

### Fixed

- **Each QR shape is measured against the keys it reads.** `QRCodeTask` carried a single allow-list spanning both of the format's shapes, while `from_dict` reads only one shape's half. A competition key in an XC/Waypoints payload therefore passed for a key the class understands: `e`, `to` and `g` were neither read into an attribute nor captured by the unknown-key passthrough, so they were dropped on the way in and had nothing to write on the way out. The discriminator that already picks the shape now picks its allow-list too, and each shape's is derived from its own table. **Breaking (API):** `QRCodeTask.KNOWN_KEYS` is replaced by `COMPETITION_KEYS` and `SIMPLIFIED_KEYS`; a union that no longer governs anything is the second way to ask that caused this. The QR turnpoint had the same split one level down — a `d` in a waypoints payload was read into `description` and then dropped by `as_waypoints()` on the way out — and now has two tables as well.
- **Unknown keys survive inside nested objects.** `Task` and `Turnpoint` carried them; the objects nested in them did not, so a non-spec key in a `waypoint`, `sss`, `goal` or `takeoff` was read past and lost on every round-trip. `Waypoint`, `SSS`, `Goal`, `Takeoff`, `QRCodeGoal` and `QRCodeSSS` now each declare their keys and carry the remainder. Two shapes deliberately stay out: `QRCodeTakeoff` is not an object on the wire (the task flattens it to root `to`/`tc`), and the goal's non-spec `lineLength` is read and discarded rather than carried, because it is always twice the last turnpoint's radius and echoing it back would preserve a derived duplicate a task can contradict. No reference output moves — the corpus has no nested unknown keys.
- **An unknown key can no longer cross into a foreign slot.** `unknown` means "a key the format it arrived in does not define", so it is meaningful only relative to that format; conversion copied it across verbatim, where it kept its spelling but changed namespace. A full-format turnpoint carrying `{"t": 99}` — a key that format spells `type` — landed in the QR format's *type* slot, and the payload written from it could not be read back at all (`99 is not a valid QRCodeTurnpointType`). The never-shadow rule cannot catch this: it protects keys already written, and `t` is emitted for SSS and ESS turnpoints only, so on a plain one the slot is free and the foreign key wins. `strip_foreign_keys` checks every key the target shape defines, and `qrcode/conversion.py` applies it at each crossing. Colliding keys are dropped rather than raised on — the task they came from is legal and unchanged in its own format. SeeYou's root `o` still crosses, as the elevated-goal fixtures require. `SSS` and `Goal` now carry their unknown keys across too; `Waypoint` and `Takeoff` do not, because the QR format flattens both away and there would be nothing to split them apart by coming back.
- **KML draws the palette the GeoJSON writer draws.** The two writers shared their colours as `#rrggbb` strings, and KML mapped each one back to a `simplekml.Color` constant through a hand-written dict — which re-declared the whole palette and lost four of its five turnpoint values: a TAKEOFF turnpoint was `#204d74` in GeoJSON and `#00008b` (`darkblue`) in KML, SSS `#ac2925` became `#8b0000`, ESS `#ff8c00` became `#ffa500`, and an ordinary turnpoint `#269abc` became `#0000ff`. Only the goal's red survived the round trip, and the dict's `.get(hex, blue)` default meant a sixth palette entry would have quietly rendered as blue. The course line drifted the same way for a different reason: its colour was hand-written as `E64136ff`, the digits of `#ff4136` in CSS order after the alpha, but KML reads `aabbggrr`, so it drew `#ff3641`. The palette is now `Color` values that each writer renders with a total function of its own format (`.hex` for GeoJSON, `.kml(alpha)` for KML), so there is nothing to look up and nothing to default to. The goal line and control zone were not shared at all — each writer declared its own, and they disagreed outright: the goal line was red in KML and green in GeoJSON, the control zone cyan against `#00bcd4` over `#4ecdc4`. They are palette entries now too, on the GeoJSON values, so KML's goal line becomes green and its control zone teal. GeoJSON output is unchanged throughout; the KML colours that change are the four drifted turnpoint roles, the course line, the goal line and the control zone. **Breaking (API):** `export.common.get_turnpoint_color_hex` is replaced by `turnpoint_color`, which returns a `Color`; ask for `.hex` if you wanted the string.
- **`OptimizedRoute.cumulative_m()` keeps its documented invariant.** It promises one entry per point, but a route with no points returned `[0.0]` — `accumulate`'s `initial` seed reporting a distance to a point that does not exist. It returns `[]` now. Callers reading it positionally against `points` were guarded by a length check, so no output changes.
- **KML no longer emits invalid geometry or styling.** Two defects found in review of PR #13, both in the turnpoint/course-line writer:
  - A task with fewer than two route points still got a `<LineString>`: one turnpoint produced a one-coordinate line, and an *empty* task produced a phantom course line at 0°N 0°E, because simplekml writes an empty coordinate list as a single `0.0,0.0,0.0`. The line is now omitted, which is what GeoJSON already did with the route feature — the two writers agree.
  - Every centre-point placemark set `iconstyle.color` to a whole `simplekml.Style`, nesting a `<Style>` element inside `<color>`. The style is now built once per turnpoint, assigned to its cylinder, and the icon takes that style's colour string, so the centre point matches the cylinder it sits in. (The separate palette *drift* between the two writers — KML maps the shared hex through `simplekml.Color` constants and loses the values — is untouched here; it is candidate D of the 2026-08-17 review.)
- **Goal-line geometry honors the task's `earthModel`.** `goal_line.py` built its own `Geod(ellps="WGS84")` and never looked at the field, so a task declaring `FAI_SPHERE` had its route and distances measured on the sphere while the goal line and its semicircular control zone were measured on the ellipsoid — two earth models inside one exported document, against ADR 0003. `GoalLine` now carries the model, `from_task` fills it from the task, and `calculate_goal_line_endpoints` / `generate_semicircle_arc` accept it like every other function in the subsystem. On a 40 km goal line the endpoints move 58 m.

- **A LINE goal no longer vanishes from KML and GeoJSON.** Whether a task has a goal line was answered twice, by `GoalLine.from_task` and by `should_skip_last_turnpoint`, and the second had one clause fewer: it did not require a previous turnpoint at *different* coordinates. A LINE goal whose previous turnpoint sits on the goal has no approach azimuth and therefore no line, but the last turnpoint was dropped anyway — so neither output contained anything representing the goal. The render list is now derived from `GoalLine.from_task`, so the turnpoint is dropped exactly when there is a line to replace it, and the goal is drawn as a red cylinder otherwise. This also makes the goal colour reachable for LINE goals at all: `is_goal_turnpoint` compares against the last turnpoint, which the renderer had already removed. **Breaking (API):** `should_skip_last_turnpoint` is deleted; ask `GoalLine.from_task(task) is not None`.

- **Cumulative optimized distances are measured along the task's own route.** `calculate_task_distances` recomputed each turnpoint's optimized distance by re-optimizing `turnpoints[:i + 1]`. The optimizer treats the last circle it is handed as the finish, so those runs bent the route towards turnpoint i instead of passing through it: the `cumulative_optimized_km` column held optima of truncated tasks, not distances along the route drawn beside them — 5.09 km apart at turnpoint 7 of `task_bevo`, both from the same `Task`. The column now comes from `OptimizedRoute.cumulative_m()`, so a prefix is a prefix and the last entry is the task distance. One optimizer run per task instead of n + 1, which also removes the 4–14× cost. **Breaking (API):** `calculate_cumulative_distances` is deleted — it was a copy of the loop body it had been extracted from, with no caller in `src/`.

- **A repeated final turnpoint is drawn as the goal.** KML and GeoJSON identified the goal by searching the turnpoint list for an equal value. `Turnpoint` is a plain dataclass, so a task that ends by flying the same turnpoint twice — same name, coordinates, radius and type — matched the earlier occurrence and drew its goal in the default blue instead of red. The comparison is by identity now. The reference corpus never exposed it: the `ess-goal` fixtures duplicate their final waypoint but differ in `type`.
- **A task omitting the obsolete `sss.direction` now parses.** The spec requires readers to ignore the field, but `SSS.from_dict` raised `KeyError` when it was absent. It falls back to `OBSOLETE_DIRECTION_DEFAULT` (`EXIT`, the value in all 22 reference tasks) and is still written on export for older devices. The QR reader's fallback changed from `ENTER` to `EXIT` so both paths agree.
- **XC/Waypoints tasks encode and decode three numbers, not four.** Its `z` holds longitude, latitude and altitude — a "route without cylinders". pyxctsk read every `z` as the four-number competition form, so waypoint altitudes were discarded (read as 0) and a 1000 m radius was invented; writing then appended that fabricated radius. Decoding now dispatches on the `z` length.
- **A waypoints QR payload missing its `V` key no longer parses as a competition task.** `QRCodeTask.from_dict` required both `T` and `V` to recognize the simplified format, so a payload carrying only `T` fell through to the competition reader: `task_type` came out `None`, `T` was swallowed into `unknown`, and re-serializing emitted the competition shape (`tc`/`to`/`version` plus a stray `T`). Each format is identified by its own task-type key alone — `T` or `taskType` — and the competition format has no `T`.
- **A QR turnpoint with no usable `z` is now a parse error, not a turnpoint at 0°N 0°E.** Both formats require the field, but `QRCodeTurnpoint.from_dict` defaulted the coordinates to zero, producing a valid-looking turnpoint in the Gulf of Guinea and reporting the task as read successfully. A missing `z`, or one that decodes to anything other than the defined three or four numbers, now raises — which `parse_task` already turns into a descriptive `InvalidFormatError`.
- **A non-integer `radius` or `altSmoothed` no longer crashes QR encoding** with `TypeError`. The spec types both as `number`; they are rounded to whole meters at the parse boundary, which is all the QR encoding can carry.
- **A duplicated turnpoint no longer inflates the optimized distance.** Tasks that repeat their ESS as a separate goal turnpoint — identical coordinates, altitude and radius — put two route points on one circle, which froze the alternating optimizer at a spurious local minimum: once the points coincide, moving either adds length to the leg between them exactly as fast as it saves on the neighbouring leg. On the new `ess-goal/task2` fixture the final point stuck at bearing 90.05° from the goal center instead of 170.16°, making the route 168 m longer than the same route without the duplicate. Consecutive identical circles are now collapsed before optimizing (`_collapse_duplicate_circles`). Concentric turnpoints of *different* radii keep their mandatory out-and-back leg, and the takeoff still starts at its center; all 24 reference tasks produce bit-identical distances to before. See `docs/adr/0002-circle-boundary-touching-semantics.md`.
- **Polyline rounding matches the reference implementation.** Ties now use `floor(x + 0.5)` (Java's `Math.round`) instead of Python's banker's rounding, which differed by ~1.1 m of longitude on exact halves.

### Removed

- **Breaking (serialized output and API):** `goal.lineLength` is neither written nor read, and `Goal.line_length` is gone from the model. It is not a spec field, was emitted as a string, and is always twice the last turnpoint's radius — which the spec already defines that radius to mean. It was also never anything but derived: `Task.__post_init__` overwrote whatever was parsed with `radius * 2`, so the value read from JSON never reached a consumer. `goal_line_length_from_turnpoints()` is now the single source of the rule, called directly by `task_distances` and `GoalLine.from_task`; three redundant `field or derive` fallbacks across three modules went with it. Files written by older versions still parse — the key is simply ignored.
- The non-spec `x`/`y`/`a`/`r` turnpoint coordinate keys are no longer read from QR JSON. Nothing produced them, and `x` is the spec's per-turnpoint extensions key.
- **Breaking (API):** `QRCodeTask.turnpoints_polyline` and the `polyline` runtime dependency are gone. The field held a Google-polyline encoding of the turnpoint coordinates that `to_dict` never emitted — `from_task` computed it on every conversion and threw it away, and `polyline` was imported for nothing else. Its QR key `p` was also on `KNOWN_KEYS`, so an incoming `p` was captured into the dead field and silently dropped on output; with the key off the allow-list it now round-trips through `unknown` like any other non-spec key. The coordinate encoding XCTrack actually uses is unaffected — that is pyxctsk's own implementation in `qrcode_encoding`.
- **Breaking (API):** the `simplified` parameter is gone from `QRCodeTask.to_dict()` and `.to_json()`, and `to_compressed_string()` is gone. `to_dict` opened with `if simplified or self.task_type == WAYPOINTS` — two sources of truth for one decision, where passing `simplified=False` did not actually get you the full format. The serialized shape now follows `task_type` alone, and the downgrade says what it is: the new `as_waypoints()` returns a copy typed WAYPOINTS, which `to_waypoints_json()` and `to_waypoints_string()` render without touching the original. `to_compressed_string()` was a pure identity wrapper over `to_string(compressed=True)`; call that instead.
- **Breaking (serialized output):** the competition QR format no longer emits `"taskType":"WAYPOINTS"`, which is not a value either format defines. A WAYPOINTS task now serializes as the simplified `"T":"W"` form from `to_string()` as well as `to_waypoints_string()`, so it reproduces XCTrack's own payload byte-for-byte.

See `docs/arch-review/2026-08-16-competition-interfaces-audit.md` for the full review; every finding it raised is now closed. All 25 reference tasks still round-trip byte-identically against the tools.xcontest.org QR codes and pass `Task.validate()` cleanly.

## [v0.5.0] - 2026-07-07

### Changed

- **Route optimization is now faithful to FAI Sporting Code S7F 2026 §7** (see `docs/arch-review/2026-07-07-route-optimization-audit.md`). The dynamic-programming + beam-search heuristic in `route_optimization.py` was replaced by the algorithm the spec cites — Ding, Xie & Jiang, *"An Efficient Algorithm for Touring n Circles"* (MATEC Web of Conf. 232, 03027, 2018): one route point per turnpoint, alternately updating odd/even points with the exact planar GetOptPi solution (crossing vs. reflection case), iterated until the total path length changes by less than ε = 0.1 m (§7.1.3). Optimization runs in a localized Transverse Mercator plane centred on the task area (§7.1.2); the converged points are snapped back onto the true cylinder boundaries (ProjectionCorrection, §7.1.7) before legs are summed geodesically. The optimizer is both more accurate (true optimum instead of a heuristic) and much faster.
- **The "crossing" case is now handled** (Ding et al. Theorem 1): when the previous or next route point lies inside a cylinder, or the leg passes through it, the optimal point is the segment–circle intersection — no spurious detours for nested/overlapping cylinders or a takeoff inside the SSS. Concentric turnpoints of different radii keep their mandatory out-and-back legs (touching semantics, matching XCTrack's displayed distances, e.g. `task_nohe`).
- **The `earthModel` task field is honored**: distances and boundary points are computed on the WGS84 ellipsoid (default) or on the FAI sphere (great circles, R = 6 371 000 m) when the task specifies `FAI_SPHERE`. New helpers `geodesic_distance`, `geod_for_earth_model` and constant `FAI_SPHERE_RADIUS_M` in `turnpoint.py`; `TaskTurnpoint` gained an `earth_model` attribute that `_task_to_turnpoints` fills from the task.
- `TaskTurnpoint.optimal_point` places points via the planar GetOptPi in a local Transverse Mercator plane and snaps them to exactly radius *r* on the earth model (previously: scipy `fminbound` over the azimuth, which could stall in the 0°/360° wrap and returned the cylinder center when the neighbours nearly coincided). `calculate_optimal_sss_entry_point` now returns this exact point instead of the nearest of the 10°-sampled perimeter points.
- `optimized_distance`, `optimized_route_coordinates` and `calculate_iteratively_refined_route` gained an `earth_model` parameter; `num_iterations` now bounds the alternating sweeps (default `DEFAULT_NUM_ITERATIONS = 100`; convergence normally stops after a handful). New `CONVERGENCE_EPSILON_M = 0.1` in `optimization_config.py`.

### Removed

- **Breaking (library API):** all parameters of the removed beam-search optimizer were dropped rather than kept as no-ops: the `angle_step` and `beam_width` parameters of `optimized_distance`, `optimized_route_coordinates`, `calculate_iteratively_refined_route`, `calculate_task_distances` and `calculate_cumulative_distances`; the `angle_step` parameter of `calculate_optimal_sss_entry_point` and `calculate_sss_info`; and the unused `task_turnpoints` back-compat parameter of `optimized_route_coordinates`. The `calculate_task_distances` result dictionary no longer contains the `optimization_angle_step` and `beam_width` keys.
- **Breaking (library API):** `optimization_config.py` lost `get_optimization_config`, `DEFAULT_BEAM_WIDTH` and `DEFAULT_ANGLE_STEP` (it now holds only `CONVERGENCE_EPSILON_M` and `DEFAULT_NUM_ITERATIONS`, both re-exported from `pyxctsk.distance`), and `TaskTurnpoint.perimeter_points` was removed — the exact `optimal_point` replaced its last consumer (SSS entry points); cylinder outlines for visualization are drawn in `visualization_common.py`.
- The private beam-search internals of `route_optimization.py` (`_run_dp`, `_init_dp_structure`, `_process_dp_stage`, `_backtrack_path`, `_center_lookahead`, `_route_lookahead`) were removed with the algorithm swap. The `TurnpointGeometry` protocol now names the attributes the optimizer needs (`center`, `radius`, `goal_type`) instead of an `optimal_point` method.
- **Breaking (library API):** removed three dead, duplicated methods/helpers from `turnpoint.py`: `TaskTurnpoint.optimized_perimeter_points`, `TaskTurnpoint.goal_line_points`, and the module-level `_get_optimized_perimeter_points`. They duplicated the cylinder/goal-line/center dispatch already owned by `TaskTurnpoint.optimal_point` and were unused within the package. Callers should use `TaskTurnpoint.optimal_point` (optimal crossing point), which is retained. (`TaskTurnpoint.perimeter_points` was suggested as an alternative here at the time, but it has since been removed as well — see the entry above.)

## [v0.4.1] - 2026-06-29

### Added

- The release workflows now create a GitHub Release automatically, taking the notes from the matching `CHANGELOG.md` section (via `scripts/changelog_extract.py`) and attaching the built wheel and sdist.

## [v0.4.0] - 2026-06-30

### Changed

- Migrated project and dependency management to [uv](https://docs.astral.sh/uv/): added `uv.lock` and `.python-version`, moved dev dependencies to a `[dependency-groups]` table, and switched the publish workflow to `uv build`/`uv publish`.
- Raised the minimum Python version to 3.11 (`scipy>=1.16` already required it).
- Replaced the QR image decoder `pyzbar` with [`zxing-cpp`](https://github.com/zxing-cpp/zxing-cpp), which ships self-contained binary wheels — QR image tests no longer need the system `zbar` library and now run by default.
- `pyxctsk.__version__` is now read from package metadata so `pyproject.toml` is the single source of truth.
- Replaced the black + isort + flake8 + pydocstyle toolchain with [ruff](https://docs.astral.sh/ruff/), and switched git hook management from pre-commit to [lefthook](https://github.com/evilmartians/lefthook).
- Automated releases: a `scripts/release.sh` helper and a manually-triggered `Release` GitHub Actions workflow bump the version, update the changelog, tag, and publish; the `Publish` workflow now runs the test/lint/type gate before uploading to PyPI.

## [v0.3.0] - 2025-07-21

### Added

- Switched codebase to require Python 3.10 or newer, enabling use of modern type hint syntax and language features
- Enhanced KML export: added `simplekml` dependency and improved KML export functionality
- Type stubs for `geopy`, `polyline`, and `pyzbar` for strict mypy compliance
- Essential smoke tests for distance calculations and comprehensive reference tests for validation
- QR code test utilities and comprehensive tests for QR code functionality
- SSS, turnpoint, and utility function tests; migrated and consolidated test files for efficiency

### Enhanced

- Refactored KML and GeoJSON generation: unified altitude handling, improved turnpoint feature creation, and introduced shared visualization utilities
- Refactored goal line calculations: consolidated logic into `goal_line` module and updated GeoJSON/KML generation
- Improved documentation and code quality: added pydocstyle to pre-commit hooks, improved module docstrings, and updated release instructions
- Improved error handling in QR code and distance modules
- Updated test data and documentation for clarity and improved coverage
- Update dependencies to latest versions for improved stability and performance

### Fixed

- Handled edge case for identical start and end points in cylinder optimization
- Corrected latitude/longitude values in route comparison outputs
- Updated route comparison coordinates for improved accuracy in visual output
- Resolved all mypy type errors for strict type compliance
- Fixed type hints and import statements for consistency and compatibility

### Refactored

- Split and reorganized modules for maintainability: QR code, KML, goal line, and utility functions
- Unified altitude parameter naming and removed unused calculations in KML generation
- Reorganized imports and updated `__all__` in `__init__.py`
- Cleaned up and improved formatting across test and source files
- Removed obsolete and outdated test files and data

## [v0.2.0] - 2025-07-09

### Added

- Support for simplified XC/Waypoints format in QRCodeTask and QRCodeTurnpoint serialization
- Complete XCTrack QR code format with custom polyline encoding

### Enhanced

- Parse_task function with improved file path checks and QR code task parsing

### Fixed

- JSON output to handle non-ASCII characters in QRCodeTask
- Include description in QRCodeTurnpoint only if non-empty
- Method naming after introducing simplified XC/Waypoints

### Refactored

- Split large qrcode_task.py into focused modules
- Reorganized import statements across multiple modules for clarity
- Enhanced code formatting for consistency and readability

## [v0.1.0] - 2025-06-30

### Added

- Initial public release with core XCTrack task format support
- Parse and write `.xctsk` (XCTrack JSON) files
- QR code generation and decoding for task sharing with XCTrack format compatibility
- Command-line interface for format conversion (JSON, KML, QR code image, XCTSK: URL)
- KML export for visualization with turnpoint color coding based on type
- Comprehensive data classes for all XCTrack task components
- Distance calculation module with advanced route optimization algorithms
- Iterative refinement for optimized route calculation to reduce look-ahead bias
- Dynamic programming methods for optimal route calculation
- Centralized optimization configuration for consistent parameters
- Beam search algorithms for route planning
- Goal line and control zone features for LINE type goals in GeoJSON generation

### Enhanced

- SSS (Start Speed Section) handling with optional time_close attribute
- QRCodeSSS and QRCodeTurnpoint serialization for improved compatibility
- Turnpoint features with color coding based on type
- Optimized route properties and visualization
- Goal handling in task and distance modules with support for goal lines
- Distance calculation logic with simplified route processing
- Cylinder point optimization methods for improved clarity and performance
- Optimized distance calculation starting from takeoff center

### Refactored

- Split distance.py into focused modules for better maintainability
- Dynamic programming methods for route calculation
- Route optimization by removing SSS-specific handling and treating all turnpoints uniformly
- Distance calculation logic by simplifying route processing
- Code formatting and organization with black & isort

### Technical

- Full pytest suite for all major features including distance calculations
- Type hints, PEP 8 compliance, linting, formatting, and type checking support
- Comprehensive test coverage for optimization algorithms and SSS handling
- Performance optimizations with caching mechanisms
- Renamed xctrack module to pyxctsk for better package organization
