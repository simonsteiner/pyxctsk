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

The CLI entry point is `pyxctsk` (`pyxctsk.cli:main`), e.g. `pyxctsk convert task.xctsk --format kml -o task.kml`. Formats: `json`, `kml`, `png` (QR image), `qrcode-json` (`XCTSK:` string); `--compressed`/`-z` switches the two QR formats to `XCTSKZ:`. Reads from stdin when no input file is given.

## Architecture

**Four packages, one direction.** `src/pyxctsk/` keeps only the front door at its top level — `__init__.py` (the public API), `__main__.py`, `cli.py`, `parser.py`, `exceptions.py` — and everything else lives in one of four packages:

```
model/     task, enums, time_of_day, passthrough, validation, rounding
qrcode/    task, models, encoding, enums, image, conversion
distance/  turnpoint, route_optimization, task_distances, sss, goal_line, config
export/    kml, geojson, common
```

Dependencies run `model → qrcode` and `model → distance → export`, with one deliberate exception: `model/task.py` imports `qrcode/task.py` so `Task.to_qr_code_task()` exists. That edge is why `qrcode/__init__.py` must not re-export `conversion` — doing so closes the cycle on the first `import pyxctsk`. Each package's `__init__.py` is its interface and says what the package is for; **modules inside a package import sibling submodules directly, never through the package `__init__`**, which is what keeps partially-initialized imports from biting. Adding an eager import to any `__init__` that reaches sideways is the one move that can break the whole library at import time — check `uv run python -c "import pyxctsk.<pkg>"` for each package after doing it.

**Single parse entry point.** `parser.parse_task()` detects and dispatches on input type (raw JSON, `XCTSK:`/`XCTSKZ:` URL, or QR-code image path) and returns a `Task`. All callers should go through it rather than format-specific parsers. Pass `strict=True` to also apply `Task.validate()` (the spec's structural rules) and raise `TaskValidationError`; parsing is lenient by default so malformed tasks can still be read and inspected.

**Unknown fields are preserved, never interpreted.** `Task.unknown` and `Turnpoint.unknown` carry any key the spec doesn't define straight back out in both formats (`KNOWN_KEYS` on each class is the allow-list), and they can't shadow a spec field. `model/passthrough.py` is the only implementation of those rules — `read_passthrough` / `write_passthrough`, called by all four models; don't re-derive the idiom in a fifth. Real producers put data outside the spec's `extensions` mechanism — see `tests/data/reference_tasks/elevated-goal/`, which stores the elevated goal as a root `{"o":{"v":2,"fa":1220}}`. Resist mapping such a field onto a spec field just because the key matches: that `fa` is absolute AMSL where `goal.finishAltitude` is AGL above the last turnpoint, so copying it across would be wrong by ~1 km.

**Domain model (`model/task.py`).** `Task`, `Turnpoint`, `Waypoint`, `SSS`, `Goal`, `Takeoff` are plain dataclasses — they are not frozen and do not validate on construction; `Task.validate()` is the structural check, and only `TimeOfDay` rejects bad values in `__post_init__`. Constrained values are enums in `model/enums.py` (`TaskType`, `TurnpointType`, `SSSType`, `Direction`, `GoalType`, `EarthModel`), re-exported from `model/task.py`, so unknown strings do fail at parse time. `Task.to_json()`, `Task.to_qr_code_task()`, etc. handle serialization. Time-of-day values use `TimeOfDay` and serialize to `HH:MM:SSZ` — be careful with quoting when serializing (see recent qrcode time-of-day fix). Nothing derived is stored on the model: a goal line's length comes from `goal_line_length_from_turnpoints()`, not a field (see the 2026-08-16 code-quality plan).

**Spec validation lives in `model/validation.py`**, not on the model. It imports `model/enums.py` and never `task`, which is why the enums are a separate module — that is what lets the rules check the model without depending on it. Add a rule there, not to `Task`. `validate()` returns `ValidationIssue` objects naming a `ValidationRule`; they stringify to the message, so don't compare them to bare strings.

**Distance subsystem is a facade.** `distance/__init__.py` only re-exports; the real work lives in focused submodules that must avoid importing back into each other (a circular import between `distance` and `task_distances` was deliberately broken — keep the `__init__` a thin re-export layer):

- `turnpoint.py` — `TaskTurnpoint`, `distance_through_centers`, earth-model helpers (WGS84 vs FAI sphere), local Transverse Mercator projection, and the planar `plane_optimal_point` (GetOptPi: crossing vs reflection cases per Ding, Xie & Jiang)
- `route_optimization.py` — shortest-path through turnpoint cylinders per FAI S7F §7 via the Ding–Xie–Jiang alternating point-circle-point method (`optimized_distance`, `calculate_iteratively_refined_route`): optimize in a local TM plane, converge at ε = 0.1 m, snap points onto true cylinder boundaries, sum geodesic legs. Touching semantics: every cylinder boundary must be touched in order (concentric turnpoints force out-and-back legs, matching XCTrack).
- `task_distances.py` — per-leg and cumulative task distances
- `sss.py` — Start-of-Speed-Section entry point / info
- `goal_line.py` — the `GoalLine` deep module: goal-line length, endpoints, semicircular control zone. It sits here rather than with the KML/GeoJSON writers that draw it because `task_distances` sizes a LINE goal's cylinder from the goal-line length; putting it in `export/` closes an import cycle.
- `config.py` — tunable params (`CONVERGENCE_EPSILON_M`, `DEFAULT_NUM_ITERATIONS` max sweeps)

Distances honor the task's `earthModel` field (WGS84 ellipsoid default, FAI sphere R = 6371 km) via `pyproj`; optimization uses `scipy`.

**QR code subsystem.** `qrcode/task.py` implements XCTrack's compact QR format (v2) with polyline-compressed coordinates for small, sunlight-readable codes. Supporting modules: `qrcode/models.py`, `qrcode/encoding.py`, `qrcode/enums.py`, `qrcode/image.py`. The package shares its name with the third-party `qrcode` library — absolute imports reach the library, relative ones reach the package. `model/time_of_day.py` holds `TimeOfDay`, the one value type both the full and QR models need; `model/rounding.py` holds `round_half_up` (Java `Math.round` semantics, matching the reference implementation), which both the domain model and the codec need. Two `z` encodings share one codec: the competition turnpoint is four numbers (lon, lat, alt, radius), the XC/Waypoints one is three (no radius) — decoding dispatches on length, so don't "unify" them, and anything else is a `ValueError` rather than a turnpoint at 0,0. Both the `XCTSK:` and compressed `XCTSKZ:` schemes are read; writing the latter is opt-in via `to_string(compressed=True)`.

**`Task` ↔ `QRCodeTask` conversion lives in `qrcode/conversion.py`**, the one module that imports both. Keep it that way: `qrcode/task.py` must not import `model/task.py` at runtime (it did, lazily, inside methods, to dodge a cycle). The six enum pairs are translation tables written out per direction, with `tests/qrcode/test_conversion.py` asserting they stay mutual inverses and cover every member. The serialized QR shape follows `QRCodeTask.task_type` alone — there is no rendering flag beside it; `as_waypoints()` returns a retyped copy.

**Visualization / export.** `export/kml.py` (`task_to_kml`), `export/geojson.py` (`generate_task_geojson`), `export/common.py` (the shapes and styling both writers need). The geometry they draw is not here — cylinders come from `distance/turnpoint.py` and the goal line from `distance/goal_line.py`.

## Conventions

- Optional/heavy dependencies (QR image handling: Pillow, qrcode, zxing-cpp) are imported with `try/except` so the core stays importable without them. Follow this pattern when adding optional features.
- Type hints are required on all function params and returns; mypy runs in strict mode (`disallow_untyped_defs`, `strict_optional`). Third-party stubs live in `stubs/`.
- All public functions/classes need Google-style docstrings (summary, `Args:`, `Returns:`, `Raises:`); private `_`-prefixed members need one only if non-trivial. Ruff's `D` rules (Google convention) enforce this.
- Do not add features, fallbacks, or config unless requested. When adding a dependency, update `pyproject.toml` (runtime deps under `[project]`, dev tools under `[dependency-groups]`, optional features under `[project.optional-dependencies]`) and run `uv lock` to refresh `uv.lock`.
- `scripts/` holds utilities, not library code: docstring (`D`) rules and mypy are not enforced there, and the vendored `scripts/task_viewer/airscore_clone` is fully excluded from ruff.

## Tests & reference data

`tests/` mirrors the source layout — `model/`, `qrcode/`, `distance/`, `export/` — plus `conformance/` for the spec-audit regressions that cut across all of them, and `test_cli.py` at the root. `tests/paths.py` states every data directory once; test modules import from it rather than counting `Path(__file__).parent` levels, which is what makes a test file free to move. Reference fixtures live in `tests/data/reference_tasks/`: `xctsk/` (input `.xctsk`), `json/` (expected metadata incl. pre-computed distances and QR strings), `qrcode_string/` (expected `XCTSK:` strings). `tests/distance/test_reference.py` and `tests/qrcode/test_codec.py` auto-discover these. Generated visual outputs go to `tests/data/visual_output/`. Note that corpus only covers the fields tools.xcontest.org exports — no `goal.finishAltitude`, no `extensions`, no non-integer radii — so it does not exercise the optional half of the spec; that blind spot is why several conformance gaps survived a green suite. Two further sets fill shapes it misses, each with its own README: `ess-goal/` (ESS as last turnpoint, and ESS duplicated as goal) and `elevated-goal/` (the same feature in two encodings — the spec's `goal.finishAltitude` in metres AGL, and SeeYou Navigator's non-spec root `o.fa` in absolute AMSL). `docs/arch-review/` holds the dated architecture and spec-conformance reviews; the 2026-08-16 conformance audit there is current.
