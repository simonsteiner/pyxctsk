# pyxctsk

A Python library and CLI for XCTrack's competition task format: it parses, writes, converts and draws `.xctsk` tasks, `XCTSK:`/`XCTSKZ:` QR payloads and QR images, and computes FAI S7F route distances.
`src/pyxctsk/` keeps only the front door at its top level (`parser.py` in, `renderer.py` out, `cli.py`, the public `__init__.py`); the work lives in four packages, `model/`, `qrcode/`, `distance/` and `export/`.
Dependencies run one way, `model → qrcode` and `model → distance → export`, and each package's `__init__.py` says what it is for.
Domain terms are in `GLOSSARY.md`; decisions and their trade-offs are in `docs/adr/`.

## Commands

```bash
uv sync --all-extras  # install the package, the dev group and the qr extra
uv sync --all-extras --group tools  # also install what scripts/ needs
uv run pytest  # run all tests
uv run pytest tests/qrcode/test_codec.py -vv -s  # run one test file, verbose, no capture
uv run pytest tests/distance -q  # run one test package
uv run ruff check --fix src/ tests/ scripts/  # lint and autofix
uv run ruff format src/ tests/ scripts/  # format
uv run mypy src/ tests/  # type-check (strict)
uv run rumdl check .  # lint Markdown
uv run lefthook install  # enable the pre-commit hooks (ruff, mypy, rumdl, cspell, token budget)
uv run lefthook run pre-commit  # run the hooks on staged files
uv run python scripts/check_qr_deps.py  # check the qr extra imports and decodes
scripts/verify.sh  # the full CI and release gate, including tests from the built sdist
uv run pyxctsk distances task.xctsk --format text  # try the CLI
```

## Conventions

### Layering

- **Dependencies run `model → qrcode` and `model → distance → export`, never back.** `model/` imports nothing else in the package; `tests/test_layering.py` enforces it on every import that runs at import time.
- **Inside a package, import sibling submodules directly, never through the package `__init__`.** `distance/__init__.py` and the other package `__init__`s only re-export.
- **Function-local imports are pinned by name.** A new one needs an entry with its reason in `EXPECTED_DEFERRED_IMPORTS` in `tests/test_layering.py`; the two that exist break import cycles.
- **Optional dependencies are imported under `try/except ImportError`.** The core must import without the `qr` extra; follow `src/pyxctsk/qrcode/image.py`.

### Reading and writing tasks

- **`parser.parse_task()` is the only way in, `renderer.render_task()` the only way out.** Callers never use a format-specific parser; `parse_task` never touches the filesystem, and `parser.load_task(path)` reads a file and hands it the bytes.
- **Each input format is a `FormatAdapter` in `src/pyxctsk/parser.py`.** It returns what arrived, a `Task` or a `QRCodeTask`, and the strict gate validates that before anything converts it.
- **Each output format is one row of `renderer.OUTPUT_FORMATS`.** The CLI's choices, `--help` and the README's `--format` list all come from it; `tests/test_renderer.py` holds the README to it.
- **`cli.py`'s `_read_input` and `_write_output` are the only CLI I/O.** They own UTF-8, the trailing newline and writing PNG bytes; a command parses, builds a value, renders it and writes.
- **The `pyxctsk distances` output is public surface.** Its JSON keys and `notes` are what other implementations diff against; it is `distance/report.py`'s `DistanceReport`, so tests assert on that value, not on stdout.

### Wire formats

- **Every wire shape is one ordered field table in `src/pyxctsk/model/shape.py`.** `to_dict` and `from_dict` traverse it, row order is output order, and adding a spec field is one row; a class with two shapes gets two tables, never a union key set.
- **Every scalar row names a wire-scalar codec** (`TEXT`, `NUMBER`, `WHOLE_METRES`, `INTEGER`, `LATITUDE`, `LONGITUDE`) from `model/shape.py`, which re-exports them from `model/codec.py` where they are defined. A bad value raises `MalformedPayloadError` from the table, with a path like `turnpoints[0].waypoint`.
- **JSON goes through `load_json` and `dump_json` in `model/shape.py`.** Name a `JsonLayout` (`compact`, `line` or `indented`); never call `json.dumps` with options of your own.
- **Unknown keys are preserved, never interpreted.** Use `model/passthrough.py` through `Shape`; never map a non-spec key onto a spec field because the names match.
- **`Task` ↔ `QRCodeTask` conversion lives only in `qrcode/conversion.py`.** Never import one format's task module from the other at module level; `Task.to_qr_code_task()` and `QRCodeTask.to_task()` reach conversion through function-local imports.
- **Both formats hold the same enums.** The QR integers are `wire_int_codec` tables in the QR field tables, and `tests/qrcode/test_conversion.py` checks they cover each enum.
- **The QR `z` codec has two encodings on purpose.** Competition turnpoints carry four numbers, XC/Waypoints ones three; decoding dispatches on the count, so don't unify them.

### Model and validation

- **The task dataclasses in `model/task.py` and `model/task_parts.py` don't validate on construction (`TimeOfDay` is the one exception, rejecting an out-of-range field in `__post_init__`).** `Task.validate()` is the structural check, and nothing derived (such as a goal line's length) is stored on the model.
- **Spec rules live in `model/validation.py`, not on `Task`.** They read a `TaskStructure`, which `Task.validate()` and `QRCodeTask.validate()` each present; validate what arrived, not its conversion.
- **Parsing is lenient about structure and strict about scalars.** A negative radius or an unknown version still parses (`--strict` rejects it); a value of the wrong kind never does.
- **Every library error descends from `exceptions.pyXCTSKError`.** The CLI catches one tuple of them; add new errors to the hierarchy.
- **`metadata.pyxctsk_version()` is the only source of the library version.**

### Distances

- **Distances honour the task's `earthModel`.** Pass an `EarthModelLike` from `distance/earth.py`; anything that isn't one raises instead of meaning WGS84.
- **Every point placed at a distance from a centre goes through `geodesic_destination`.** It raises `UnmeasurableRouteError` when that earth has no such point.
- **A task and its route travel together as a `MeasuredTask`.** `MeasuredTask.from_task()` is the only place a route is derived; never pass a task and a route side by side.
- **Distance-so-far is read from the `OptimizedRoute` legs.** Never optimize a prefix of the turnpoints: the optimizer treats the last circle as the finish, so a prefix gives a different number.
- **The speed section is its own optimized route.** `distance/speed_section.py`'s `SpeedSection` optimizes to the ESS separately, as S7F does.
- **`GoalLine.from_task()` is the only answer to whether a task has a goal line.** Its orientation is a `GoalLineOrientation` parameter (2025 rule by default).
- **S7F does not define the distance through centres.** `distance/center_distance.py` names the readings and `PROPOSED_READING` is the one pyxctsk publishes.

### Export

- **`TaskDrawing.from_task()` in `export/common.py` derives what a task looks like once.** KML and GeoJSON both render that value; a question both writers must answer the same way becomes a method on `TaskDrawing`, not a free function each calls.
- **Geometry comes from `distance/`.** Cylinder outlines are `geodesic_arc` via `TaskDrawing.outline_of`, the goal line is `distance/goal_line.py`; the writers only draw.

### Tests

- **`tests/` mirrors `src/pyxctsk/`.** Cross-cutting spec regressions go in `tests/conformance/`, by subject.
- **Reference tasks are found only through `tests/corpus.py`, never by globbing.** Made-up tasks come from `tests/builders.py`, and data directories from `tests/paths.py`.
- **The reference corpus doesn't cover the optional half of the spec** (no `goal.finishAltitude`, no `extensions`, no non-integer radii). Test those with a conformance test or the `ess-goal/` and `elevated-goal/` fixture sets.

### Changes

- **Record user-visible changes under `## [Unreleased]` in `CHANGELOG.md`.** The release tooling rolls that section; see `docs/releasing.md`.
- **Don't add features, fallbacks or config that weren't asked for.**
- **A dependency change updates `pyproject.toml` and runs `uv lock`.** Runtime deps go under `[project]`, the QR image deps under the `qr` extra, dev tools in the `dev` group, and `scripts/` deps in the `tools` group.

## Hard constraints

- **Ask before adding a runtime dependency or an extra.**
- **Never cut a release, bump the version or push a tag unless asked.** Releases publish to PyPI through `.github/workflows/release.yml` or `scripts/release.sh`.
- **Never edit `scripts/task_viewer/airscore_clone/`.** It is vendored third-party code.
- **Never hand-edit the expected outputs in `tests/data/reference_tasks/` to make a test pass.** A mismatch there is a finding to report.

## Gotchas

- **Run everything through `uv run`.** Don't activate the venv or call bare `python`; `requires-python` is `>=3.11` because `scipy>=1.16` needs it.
- **`src/pyxctsk/qrcode/` shares its name with the third-party `qrcode` library.** Absolute imports reach the library, relative imports reach the package.
- **QR images go through `qrcode/image.py`.** Call `generate_qrcode_image` and `read_qrcode_image`, never zxing-cpp directly, including in tests and scripts.
- **A root `o.fa` is not `goal.finishAltitude`.** SeeYou Navigator's `fa` is absolute AMSL; the spec's is AGL above the last turnpoint.
- **`ValidationIssue`s stringify to their message.** Compare their `ValidationRule`, not bare strings.
- **cspell runs on commit.** Add new domain words to `cspell-dictionary.txt`.
- **`ruff format` also formats Python blocks in Markdown.** A tool bump can change a doc.
- **`scripts/` is utilities, not library code.** Docstring rules and mypy don't apply there, and the published wheel doesn't ship it.

## Docs

- `README.md` — what the library does, installation, Python and CLI usage.
- `docs/setup.md` — development setup, code-quality tools and troubleshooting.
- `docs/releasing.md` — how a release is cut and published to PyPI; read before touching the release workflows or scripts.
- `docs/updating-dependencies.md` — read before bumping dependencies.
- `docs/s7f-distance-reference.md` — what S7F defines about task distances and what it leaves open.
- `docs/adr/` — the route-optimizer, touching and earth-model decisions.
- `docs/arch-review/` — dated architecture and spec-conformance reviews; read the current two (`2026-08-16-competition-interfaces-audit.md`, `2026-08-18-s7f-2026-conformance-audit.md`) before changing conformance behaviour.
- `scripts/README.md` and `scripts/task_viewer/README.md` — the repository utilities.
- `CHANGELOG.md` — what each release changed.
