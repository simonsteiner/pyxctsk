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
uv run pytest tests/test_qrcode.py -vv -s    # single file, verbose, no capture
uv run pytest -m "not slow"                  # skip slow-marked tests

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

The CLI entry point is `pyxctsk` (`pyxctsk.cli:main`), e.g. `pyxctsk convert task.xctsk --format kml -o task.kml`. Formats: `json`, `kml`, `png` (QR image), `qrcode-json` (`XCTSK:` string). Reads from stdin when no input file is given.

## Architecture

**Single parse entry point.** `parser.parse_task()` detects and dispatches on input type (raw JSON, `XCTSK:` URL, or QR-code image path) and returns a `Task`. All callers should go through it rather than format-specific parsers.

**Immutable domain model (`task.py`).** `Task`, `Turnpoint`, `Waypoint`, `SSS`, `Goal`, `Takeoff` are validated dataclasses. Constrained values are enums (`TaskType`, `TurnpointType`, `SSSType`, `Direction`, `GoalType`, `EarthModel`). `Task.to_json()`, `Task.to_qr_code_task()`, etc. handle serialization. Time-of-day values use `TimeOfDay` and serialize to `HH:MM:SSZ` — be careful with quoting when serializing (see recent qrcode time-of-day fix).

**Distance subsystem is a facade.** `distance.py` only re-exports; the real work lives in focused submodules that must avoid importing back into each other (a circular import between `distance` and `task_distances` was deliberately broken — keep `distance.py` as a thin re-export layer):

- `turnpoint.py` — `TaskTurnpoint`, `distance_through_centers`, earth-model helpers (WGS84 vs FAI sphere), local Transverse Mercator projection, and the planar `plane_optimal_point` (GetOptPi: crossing vs reflection cases per Ding, Xie & Jiang)
- `route_optimization.py` — shortest-path through turnpoint cylinders per FAI S7F §7 via the Ding–Xie–Jiang alternating point-circle-point method (`optimized_distance`, `calculate_iteratively_refined_route`): optimize in a local TM plane, converge at ε = 0.1 m, snap points onto true cylinder boundaries, sum geodesic legs. Touching semantics: every cylinder boundary must be touched in order (concentric turnpoints force out-and-back legs, matching XCTrack).
- `task_distances.py` — per-leg and cumulative task distances
- `sss_calculations.py` — Start-of-Speed-Section entry point / info
- `optimization_config.py` — tunable params (`CONVERGENCE_EPSILON_M`, `DEFAULT_NUM_ITERATIONS` max sweeps; `DEFAULT_ANGLE_STEP` for perimeter sampling, `DEFAULT_BEAM_WIDTH` deprecated/unused)

Distances honor the task's `earthModel` field (WGS84 ellipsoid default, FAI sphere R = 6371 km) via `pyproj`; optimization uses `scipy`.

**QR code subsystem.** `qrcode_task.py` implements XCTrack's compact QR format (v2) with polyline-compressed coordinates for small, sunlight-readable codes. Supporting modules: `qrcode_models.py`, `qrcode_encoding.py`, `qrcode_enums.py`, `qrcode_image.py`. `shared_enums.py` holds enums shared between the full and QR models.

**Visualization / export.** `kml.py` (`task_to_kml`), `geojson.py` (`generate_task_geojson`), `goal_line.py` (goal line geometry), `visualization_common.py`.

## Conventions

- Optional/heavy dependencies (QR image handling: Pillow, qrcode, zxing-cpp) are imported with `try/except` so the core stays importable without them. Follow this pattern when adding optional features.
- Type hints are required on all function params and returns; mypy runs in strict mode (`disallow_untyped_defs`, `strict_optional`). Third-party stubs live in `stubs/`.
- All public functions/classes need Google-style docstrings (summary, `Args:`, `Returns:`, `Raises:`); private `_`-prefixed members need one only if non-trivial. Ruff's `D` rules (Google convention) enforce this.
- Do not add features, fallbacks, or config unless requested. When adding a dependency, update `pyproject.toml` (runtime deps under `[project]`, dev tools under `[dependency-groups]`, optional features under `[project.optional-dependencies]`) and run `uv lock` to refresh `uv.lock`.
- `scripts/` holds utilities, not library code: docstring (`D`) rules and mypy are not enforced there, and the vendored `scripts/task_viewer/airscore_clone` is fully excluded from ruff.

## Tests & reference data

Reference fixtures live in `tests/data/reference_tasks/`: `xctsk/` (input `.xctsk`), `json/` (expected metadata incl. pre-computed distances and QR strings), `qrcode_string/` (expected `XCTSK:` strings). `test_distance_reference.py` and `test_qrcode.py` auto-discover these. Generated visual outputs go to `tests/data/visual_output/`. `XCTRACK_ANALYSIS.md` documents spec coverage against the official XCTrack interface.
