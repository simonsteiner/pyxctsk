# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`pyxctsk` is a Python implementation of [XCTrack's task format](https://xctrack.org/Competition_Interfaces.html) for paragliding/hang gliding competitions. It parses, generates, manipulates, and visualizes XCTrack tasks (`.xctsk` files, `XCTSK:` URLs, and QR codes), and computes competition route distances.

## Environment & commands

This project uses [uv](https://docs.astral.sh/uv/). Run tools through `uv run` (which keeps the env in sync) rather than activating the venv or calling bare `python`. `requires-python` is `>=3.11` (raised from 3.10 because `scipy>=1.16` requires it). `.python-version` pins 3.11 for local dev.

```bash
# One-time dev setup: creates .venv and installs the package (editable) plus the
# `dev` dependency group and the `web` + `analysis` extras.
uv sync --all-extras

# Tests
uv run pytest                                # full suite
uv run pytest tests/qrcode/test_codec.py -vv -s   # single file, verbose, no capture
uv run pytest tests/distance -q               # one subpackage
uv run pytest -m "not slow"                   # skip slow-marked tests (none at present)

# Lint / format / typecheck
uv run ruff check --fix src/ tests/ scripts/   # lint (E/W/F/I/D) + autofix
uv run ruff format src/ tests/ scripts/        # format (black-compatible)
uv run mypy --config-file mypy.ini src/        # type check

# Git hooks are managed by lefthook (config in lefthook.yml)
uv run lefthook install                        # enable hooks on commit
uv run lefthook run pre-commit                 # run hooks against staged files

# Check optional QR dependencies are importable
uv run python scripts/check_qr_deps.py

# Build / publish (see RELEASING.md)
uv build
```

The CLI entry point is `pyxctsk` (`pyxctsk.cli:main`), e.g. `pyxctsk convert task.xctsk --format kml -o task.kml`. Formats: `json`, `kml`, `png` (QR image), `qrcode-json` (`XCTSK:` string); `--compressed`/`-z` switches the two QR formats to `XCTSKZ:`; `--strict` rejects a structurally invalid task instead of converting it. Reads from stdin when no input file is given.

## Architecture

**Four packages, one direction.** `src/pyxctsk/` keeps only the front door at its top level — `__init__.py` (the public API), `__main__.py`, `cli.py`, `parser.py`, `exceptions.py` — and everything else lives in one of four packages:

```
model/     task, enums, shape, time_of_day, passthrough, validation, rounding
qrcode/    task, models, encoding, enums, image, conversion
distance/  turnpoint, route_optimization, task_distances, goal_line
export/    kml, geojson, common
```

Dependencies run `model → qrcode` and `model → distance → export`, with no back edges: `model` imports nothing else in the package. `qrcode/conversion.py` sits above both packages it maps between, and the two convenience methods that read the other way (`Task.to_qr_code_task()`, `QRCodeTask.to_task()`) reach it through function-local imports for that reason alone. Each package's `__init__.py` is its interface and says what the package is for; **modules inside a package import sibling submodules directly, never through the package `__init__`**, which is what keeps partially-initialized imports from biting.

**`tests/test_layering.py` enforces all of that** by parsing the import graph — the layer rules, the sibling-import rule, and the exact set of function-local imports inside the packages. Adding a new one means adding it to `EXPECTED_DEFERRED_IMPORTS` with a reason — both of the two that exist break an import cycle, and only one of them crosses a package boundary. Both rules had already been broken once each while they were only prose, and the second broke `import pyxctsk` outright. The checks cover every import that **runs at import time**, not just the ones written at module level: a relative import inside a module-level `try:/except ImportError:` (the shape `parser.py` and `qrcode/image.py` already use for optional dependencies), inside any module-level `if`, or directly in a class body is checked like any other. `if TYPE_CHECKING:` bodies and function bodies are the two escape hatches, and only the latter is pinned by name.

**Single parse entry point.** `parser.parse_task()` detects and dispatches on input type (raw JSON, `XCTSK:`/`XCTSKZ:` URL, or QR-code image path) and returns a `Task`. All callers should go through it rather than format-specific parsers. Pass `strict=True` to also apply `Task.validate()` (the spec's structural rules) and raise `TaskValidationError`; parsing is lenient by default so malformed tasks can still be read and inspected. The CLI exposes it as `--strict`.

**One field table per serializable shape.** Every wire object — a turnpoint in the full format, a goal in the QR one, an XC/Waypoints task — declares its mapping once as an ordered table in `model/shape.py`, and `to_dict` / `from_dict` are the two traversals of it. **A field owns *keys*, plural**, which is what makes the table total: `z` is four attributes in one key, the QR takeoff is one attribute across `to`/`tc`, and `T` names a shape rather than carrying data — each is one row, a `Field` subclass declared beside the shape that needs it. Three things follow, and each was a shipped bug before: `KNOWN_KEYS` is *derived* from the table so it cannot disagree with what the shape reads; read and write cannot drift; and row order is output order, which is where the byte-exact QR key orders are stated. A class with two shapes gets two tables (`QRCodeTask`, `QRCodeTurnpoint`) — never a union key set, which is how a whole format's keys got swallowed. Adding a spec field is one row. See `CONTEXT.md` for the vocabulary.

**Unknown fields are preserved, never interpreted.** Every shape's `unknown` carries any key it doesn't define straight back out, and they can't shadow a spec field. `model/passthrough.py` holds those rules — `read_passthrough` / `write_passthrough` / `strip_foreign_keys`, reached through `Shape`; don't re-derive the idiom. Unknown is *relative to a shape*: crossing the format seam, `qrcode/conversion.py` drops keys the target shape defines, or a full-format turnpoint's `{"t": 99}` lands in the QR format's *type* slot and the payload can't be re-read. Real producers put data outside the spec's `extensions` mechanism — see `tests/data/reference_tasks/elevated-goal/`, which stores the elevated goal as a root `{"o":{"v":2,"fa":1220}}`. Resist mapping such a field onto a spec field just because the key matches: that `fa` is absolute AMSL where `goal.finishAltitude` is AGL above the last turnpoint, so copying it across would be wrong by ~1 km.

**Domain model (`model/task.py`).** `Task`, `Turnpoint`, `Waypoint`, `SSS`, `Goal`, `Takeoff` are plain dataclasses — they are not frozen and do not validate on construction; `Task.validate()` is the structural check, and only `TimeOfDay` rejects bad values in `__post_init__`. Constrained values are enums in `model/enums.py` (`TaskType`, `TurnpointType`, `SSSType`, `Direction`, `GoalType`, `EarthModel`), re-exported from `model/task.py`, so unknown strings do fail at parse time. `Task.to_json()`, `Task.to_qr_code_task()`, etc. handle serialization. Time-of-day values use `TimeOfDay` and serialize to `HH:MM:SSZ` — be careful with quoting when serializing (see recent qrcode time-of-day fix). Nothing derived is stored on the model: a goal line's length comes from `goal_line_length_from_turnpoints()`, not a field (see the 2026-08-16 code-quality plan).

**Spec validation lives in `model/validation.py`**, not on the model. It imports `model/enums.py` and never `task`, which is why the enums are a separate module — that is what lets the rules check the model without depending on it. Add a rule there, not to `Task`. The rules read a `TaskStructure` — turnpoint roles and radii, the extensions at both levels, the declared version and whether this is a waypoints task — and nothing else, and each format presents one: `Task.validate()` for the full one, `QRCodeTask.validate()` (via `qrcode/conversion.py`, which owns the enum translation) for the compact one. **Validate what arrived, not its conversion**: converting a QR payload first invents `version=1`, a `CLASSIC` task type and a CYLINDER goal it never carried. `validate()` returns `ValidationIssue` objects naming a `ValidationRule`; they stringify to the message, so don't compare them to bare strings.

**Distance subsystem is a facade.** `distance/__init__.py` only re-exports; the real work lives in focused submodules that must avoid importing back into each other (a circular import between `distance` and `task_distances` was deliberately broken — keep the `__init__` a thin re-export layer):

- `turnpoint.py` — `TaskTurnpoint`, `distance_through_centers`, earth-model helpers (WGS84 vs FAI sphere), and the one solver: `plane_optimal_point` (GetOptPi: crossing vs reflection cases per Ding, Xie & Jiang), `plane_circle` (what a turnpoint *is* to that solver — including that a LINE goal is a zero-radius circle at the goal center), and `LocalPlane`, the Transverse Mercator plane a route is solved in. **The plane is an argument, not a decision made twice**: `optimal_point` defaults to a plane around its own turnpoint but accepts the task's, which is how a test reaches the answer the optimizer actually ships
- `route_optimization.py` — shortest-path through turnpoint cylinders per FAI S7F §7 via the Ding–Xie–Jiang alternating point-circle-point method (`optimized_distance`, `calculate_iteratively_refined_route`): optimize in a local TM plane, converge at ε = 0.1 m, snap points onto true cylinder boundaries, measure geodesic legs. Touching semantics: every cylinder boundary must be touched in order (concentric turnpoints force out-and-back legs, matching XCTrack). `calculate_iteratively_refined_route` returns an `OptimizedRoute` — points, legs, earth model — and `total_m` / `cumulative_m()` are projections of it. Keep it that way: the legs are the only honest source for "how far along the route is turnpoint i", and re-deriving that by optimizing `turnpoints[:i+1]` gives a *different* number (the optimizer treats the last circle it is handed as the finish), which is the bug the value object was introduced to kill.
- `task_distances.py` — per-leg and cumulative task distances, projected from one `OptimizedRoute` rather than one optimizer run per turnpoint. `task_distances_from_route()` is that projection and `calculate_task_distances()` is optimize-then-project, so a caller that already holds a route (`TaskDrawing.route`) does not pay for a second one
- `goal_line.py` — the `GoalLine` deep module: goal-line length, endpoints, semicircular control zone, all on the task's `earthModel` (ADR 0003). It sits in `distance/` rather than beside the KML/GeoJSON writers that draw it because the shapes of a task must not depend on the formats it is exported to — and that is now the only reason. The original second reason (`task_distances` needing the goal-line length, which made `export/` placement a real import cycle) died with the dead `TaskTurnpoint.goal_line_length` attribute: `export/` is the only consumer of `goal_line.py` today. A LINE goal's cylinder is sized by `radius=0`, not by the length. **`GoalLine.from_task()` is the only answer to whether a task has a goal line** — `TaskDrawing.from_task()` derives the render list from it rather than asking again, because the goal line's presence is the whole reason to drop the last turnpoint. A second predicate (`should_skip_last_turnpoint`) used to answer with one clause fewer, and a coincident previous turnpoint made the goal disappear from both output formats. Callers use the object (`length`, `endpoints()`, `control_zone()`); the tuple-shaped `data()` and `get_goal_line_data()` that both writers used to unpack are gone.

Distances honor the task's `earthModel` field (WGS84 ellipsoid default, FAI sphere R = 6371 km) via `pyproj`; optimization uses `scipy`.

**QR code subsystem.** `qrcode/task.py` implements XCTrack's compact QR format (v2) with polyline-compressed coordinates for small, sunlight-readable codes. Supporting modules: `qrcode/models.py`, `qrcode/encoding.py`, `qrcode/enums.py`, `qrcode/image.py`. The package shares its name with the third-party `qrcode` library — absolute imports reach the library, relative ones reach the package. `model/time_of_day.py` holds `TimeOfDay`, the one value type both the full and QR models need; `model/rounding.py` holds `round_half_up` (Java `Math.round` semantics, matching the reference implementation), which both the domain model and the codec need. Two `z` encodings share one codec: the competition turnpoint is four numbers (lon, lat, alt, radius), the XC/Waypoints one is three (no radius) — decoding dispatches on length, so don't "unify" them, and anything else is a `ValueError` rather than a turnpoint at 0,0. Both the `XCTSK:` and compressed `XCTSKZ:` schemes are read; writing the latter is opt-in via `to_string(compressed=True)`.

**`Task` ↔ `QRCodeTask` conversion lives in `qrcode/conversion.py`**, the one module that imports both. Keep it that way: neither `model/task.py` nor `qrcode/task.py` may import the other at module level — the convenience methods on both reach conversion through function-local imports, and `tests/test_layering.py` pins that set at exactly two. The six enum pairs are translation tables written out per direction, with `tests/qrcode/test_conversion.py` asserting they stay mutual inverses and cover every member. The serialized QR shape follows `QRCodeTask.task_type` alone — there is no rendering flag beside it; `as_waypoints()` returns a retyped copy. Conversion is hand-written rather than table-driven: `Turnpoint` nests a `Waypoint` where `QRCodeTurnpoint` is flat, so there is no attribute copy to derive. It carries `unknown` across only for the four shapes with a 1:1 counterpart (`Task`, `Turnpoint`, `SSS`, `Goal`); a `Waypoint`'s and a `Takeoff`'s stay in the full format, because the QR format flattens both away and there would be nothing to split them apart by coming back.

**Visualization / export.** `export/kml.py` (`task_to_kml`), `export/geojson.py` (`generate_task_geojson`), `export/common.py` (`TaskDrawing` plus the styling both writers need). The geometry they draw is not here — cylinders come from `distance/turnpoint.py` and the goal line from `distance/goal_line.py`. **`TaskDrawing.from_task()` derives what a task looks like once** — turnpoints to draw, goal line, optimized route — and both writers render that value: `task_to_kml`/`generate_task_geojson` are one-liners over `drawing_to_kml`/`drawing_to_geojson`, so rendering both formats optimizes the route once and the two formats cannot disagree about the task's shape. Add a question both writers must answer identically as a field or method on the drawing, not as a fifth free function they each call.

## Conventions

- Optional/heavy dependencies (QR image handling: Pillow, qrcode, zxing-cpp) are imported with `try/except` so the core stays importable without them. Follow this pattern when adding optional features.
- Type hints are required on all function params and returns; mypy runs in strict mode (`disallow_untyped_defs`, `strict_optional`). Third-party stubs live in `stubs/`.
- All public functions/classes need Google-style docstrings (summary, `Args:`, `Returns:`, `Raises:`); private `_`-prefixed members need one only if non-trivial. Ruff's `D` rules (Google convention) enforce this.
- Do not add features, fallbacks, or config unless requested. When adding a dependency, update `pyproject.toml` (runtime deps under `[project]`, dev tools under `[dependency-groups]`, optional features under `[project.optional-dependencies]`) and run `uv lock` to refresh `uv.lock`.
- `scripts/` holds utilities, not library code: docstring (`D`) rules and mypy are not enforced there, and the vendored `scripts/task_viewer/airscore_clone` is fully excluded from ruff.

## Tests & reference data

`tests/corpus.py` is the reference corpus: one discovery, one pairing rule, one sort order, and an integrity check that makes a half-added task a collection error. `tests/builders.py` is for the tasks tests make up; keep the two apart. `tests/` mirrors the source layout — `model/`, `qrcode/`, `distance/`, `export/` — plus `conformance/` for the spec-audit regressions that cut across all of them, and `test_cli.py` at the root. `tests/paths.py` states every data directory once; test modules import from it rather than counting `Path(__file__).parent` levels, which is what makes a test file free to move. Reference fixtures live in `tests/data/reference_tasks/`: `xctsk/` (input `.xctsk`), `json/` (expected metadata incl. pre-computed distances and QR strings), `qrcode_string/` (expected `XCTSK:` strings). Every consumer discovers them through `tests/corpus.py`, never by globbing. Within `tests/distance/`, the three optimizer files divide up as: `test_route_optimization.py` (the algorithm's internals), `test_xctrack_accuracy.py` (our numbers vs XCTrack's published ones), `test_task_distances.py` (the pipeline above the optimizer). Note that corpus only covers the fields tools.xcontest.org exports — no `goal.finishAltitude`, no `extensions`, no non-integer radii — so it does not exercise the optional half of the spec; that blind spot is why several conformance gaps survived a green suite. Two further sets fill shapes it misses, each with its own README: `ess-goal/` (ESS as last turnpoint, and ESS duplicated as goal) and `elevated-goal/` (the same feature in two encodings — the spec's `goal.finishAltitude` in metres AGL, and SeeYou Navigator's non-spec root `o.fa` in absolute AMSL). `docs/arch-review/` holds the dated architecture and spec-conformance reviews; the 2026-08-16 conformance audit there is current.
