# 2026-08-20 — Thermo-nuclear pre-release code-quality review

Reviewed at `7d7ec64` (`main`, 170 commits after tag `v0.5.0`) against the
whole project: `src/pyxctsk`, tests, packaging metadata, release automation,
public documentation, and the maintained scripts. Vendored AirScore code under
`scripts/task_viewer/airscore_clone` was treated as third-party code, matching
the repository's own lint exclusion.

## Verdict

**Hold the release until findings 1–3 are fixed.**

The library implementation is in strong shape. The package split is coherent,
the import-direction guard passes, no production file is near 1,000 lines, the
public values introduced by the recent architecture work are load-bearing, and
the suite covers 98% of production statements. I found no new correctness
defect in parsing, serialization, distance calculation, or export.

The release surface is not at the same standard. The documented local release
path cannot run, the installed CLI presents malformed help, and two advertised
extras install dependencies for tools that are not present in either built
artifact. Those are direct user/releaser failures, not cosmetic debt.

## Gate results

| Check | Result |
|---|---|
| Clean branch | `main` matched `origin/main` before this report was added |
| Ruff lint | pass |
| Ruff format check | pass; 96 files already formatted |
| Strict mypy | pass; 75 files |
| Full suite, Python 3.11 | 1,133 passed, 18 skipped, 1 warning |
| Full suite, Python 3.12 | 1,133 passed, 18 skipped, 1 warning |
| Full suite, Python 3.13 | 1,133 passed, 18 skipped, 1 warning |
| Full suite, Python 3.14 | 1,133 passed, 18 skipped, 1 warning |
| Coverage | 98%; 1,828 statements, 39 missed |
| CSpell | pass; 127 files, 0 issues |
| Lockfile | `uv lock --check` passes |
| QR image smoke test | pass; Pillow and zxing-cpp import and round-trip |
| Wheel/sdist build | succeeds, with setuptools license warnings |
| Built core wheel | pass; CLI, parsing, QR strings, distance, KML and GeoJSON work without the `qr` extra |
| Documented local release | **fails** at mypy before versioning |

The 18 skips are all the same intentional XCTrack-accuracy exclusion for
concentric turnpoints. The warning is the pytest 10 incompatibility in finding
5.

## Findings

### 1 — Blocker: release verification is copied three times, and the local copy is broken

**Files:** `scripts/release.sh:38-43`, `.github/workflows/release.yml:37-49`,
`.github/workflows/publish.yml:27-39`

`RELEASING.md` presents the local script and the GitHub workflow as equivalent
release paths. They are not. The local script still runs:

```console
uv run mypy --config-file mypy.ini src/
```

`mypy.ini` was deleted when configuration moved into `pyproject.toml`. Running
that exact command exits 2:

```text
mypy: error: Cannot find config file 'mypy.ini'
```

The two hosted workflows use `uv run mypy src/ tests/` and pass. They also run
the core-without-QR check; the local script does not. CSpell is only a staged
pre-commit hook and is absent from all three release gates.

This is the structural problem the concrete failure exposes: there are three
hand-maintained declarations of what “verified for release” means. One has
already drifted far enough to make a documented path unusable.

**Code-judo remedy:** create one non-mutating verification entry point and make
the local script and both workflows call it. It should own sync/lock checking,
Ruff lint and format, mypy over `src/ tests/`, pytest, CSpell, build, and the
core-wheel smoke test. Keep version bumping, tagging and publishing outside it.
Then the release paths differ only in orchestration, not in the quality bar.

**Release action:** mandatory before release, even if this release is cut via
GitHub Actions. A published release should not leave one of its two documented
paths dead.

### 2 — High: the installed CLI help is malformed and exposes implementation documentation

**Files:** `src/pyxctsk/cli.py:37-66,214-252`, `tests/test_cli.py:98-115,286-297`

Both Click callback docstrings are raw strings. Click's paragraph-preservation
marker is the backspace character `\b`; a raw string passes the two characters
backslash + `b` instead. The installed wheel therefore prints literal markers
and folds each intended block into one wrapped paragraph:

```text
\b Parameter Options:   --format ... --output ... --compressed ...
\b Examples:   pyxctsk convert ... pyxctsk convert ...
```

`pyxctsk distances --help` also publishes the callback's Google-style
`Args:`, `Returns:` and `Raises:` sections. They become a dense end-user
paragraph, including internal history about the exception hierarchy.

The test named `test_cli_main_command` checks only that `pyxctsk` and `convert`
occur somewhere in the output. `test_the_command_is_documented` similarly
checks only that option names occur. Both pass while the help is visibly
broken.

**Code-judo remedy:** separate command help from implementation documentation.
Use short Click-facing help text (ordinary strings with actual `\b` markers,
or explicit `help=` text), and move callback implementation details to module
comments or helper functions. Add golden-ish assertions that the output has no
literal `\\b`, no `Args:/Returns:/Raises:`, and that representative examples
remain on separate lines.

**Release action:** mandatory. This is the first output a new user sees.

### 3 — High: `web` and `analysis` are published extras for code that is not shipped

**Files:** `pyproject.toml:31-52`, `README.md:227-235`,
`scripts/task_viewer/README.md:1-66`

The wheel contains only `pyxctsk`; the sdist contains `pyxctsk` and five
top-level test files. Neither contains `scripts/`. Yet the package metadata and
README advertise:

```console
pip install pyxctsk[web]       # “for web interface components”
pip install pyxctsk[analysis]  # “for analysis tools”
```

The web interface is a standalone development app under
`scripts/task_viewer`. Installing the wheel with `[web]` installs Flask but no
web component or entry point. The analysis dependencies likewise serve
repository scripts that a PyPI installation does not receive. That boundary is
also incomplete inside the checkout: `scripts/extract_qr_from_html.py` requires
OpenCV (`cv2`), which is in neither the `analysis` extra nor the dev group, while
`matplotlib` is in the extra and has no Python import in the maintained scripts.

This is feature-specific tooling leaking into the public package contract. The
extra names imply installed capabilities that do not exist.

**Code-judo remedy:** decide whether these tools are product or repository
support.

- If support only, delete `web` and `analysis` from published optional
  dependencies and put the exact script dependencies in named development
  groups. Document that the scripts require a source checkout.
- If product, move the maintained tools under a packaged namespace, add console
  entry points, include their assets, and test the installed wheel with each
  extra.

The first option deletes the false surface and is the safer pre-release move.

**Release action:** mandatory. Do not publish extras that install no advertised
feature.

### 4 — Medium: the planar route solver is split across the wrong seam

**Files:** `src/pyxctsk/distance/solver.py:1-12`,
`src/pyxctsk/distance/route_optimization.py:126-352`,
`tests/distance/test_route_optimization.py:22-31`

`solver.py` defines itself as pure planar geometry that knows nothing about
turnpoints, tasks, projections or the earth. It currently owns only the
single-circle GetOptPi primitive. The rest of the pure planar algorithm lives
in `route_optimization.py`:

- duplicate-circle collapse;
- planar polyline length;
- three initial placements;
- nearest-boundary placement;
- alternating sweeps;
- multi-start winner selection.

Only after line 355 does that module cross into projection correction and task
orchestration. The test makes the missing seam visible by importing eight
private names from `route_optimization` to test the planar engine directly.

This is not spaghetti inside the functions; the functions are direct and well
documented. The problem is ownership. The module named as orchestration also
contains an independently testable 225-line solver, while the module named as
the solver contains only its innermost primitive.

**Code-judo remedy:** move the planar engine behind one focused seam—either
deepen `solver.py` or create `planar_route.py`. Give it one route-level entry
point such as `optimize_plane_route(circles, max_sweeps, epsilon)`. Keep
`route_optimization.py` responsible for projecting turnpoints, invoking the
planar solver twice, snapping to the earth, and measuring geodesic legs. Split
the tests along the same boundary. This removes the eight-name private import
fan-out and makes the implementation match its own module vocabulary.

**Release action:** not worth destabilizing the numerical core during the last
release hour, but it remains the clearest production-code deepening opportunity.

### 5 — Medium: the test architecture has crossed the size boundary and already carries a future failure

**Files:** `tests/conformance/test_spec_conformance.py` (1,681 lines),
`tests/distance/test_task_distances.py:46-62`

No production file exceeds 587 lines, but the principal conformance test has
grown to 1,681 lines and 139 test methods. It mixes at least five independently
navigable subjects: Competition Interfaces wire conformance, passthrough and
unknown-key behavior, QR shapes, S7F geometry, and parser diagnostics. A test
failure is searchable, but a maintainer still has to hold the whole audit
history under one filename.

The suite also emits `PytestRemovedIn10Warning` on every supported interpreter:
the class-scoped `test_turnpoints` fixture is an instance method. Pytest states
that this form is deprecated and will stop working in pytest 10. The fixture is
just a constant four-element list; class scope buys nothing.

**Remedy:** replace the fixture with a module constant or a normal function
fixture immediately. Split the conformance file by the boundaries already
present in its class names—for example `test_competition_interfaces.py`,
`test_qr_conformance.py`, `test_s7f_conformance.py`, and
`test_parser_diagnostics.py`. Preserve the audit references in each module
docstring so the split improves locality without losing provenance.

**Release action:** fix the warning before release; split the giant file soon
after unless the release branch is still open for mechanical moves.

### 6 — Medium: the supported-Python contract is broader than the automated gate

**Files:** `pyproject.toml:18-23`, `.github/workflows/release.yml:32-43`,
`.github/workflows/publish.yml:22-33`

Metadata declares Python 3.11, 3.12 and 3.13 classifiers and an open-ended
`Requires-Python: >=3.11`. Both release workflows run the full gate only on
3.11. A dependency or syntax change can therefore ship while breaking an
explicitly classified interpreter.

For this review I ran the complete suite in isolated environments on 3.11,
3.12, 3.13 and 3.14. All four produced the same 1,133 pass / 18 skip result, so
there is no current compatibility defect. That manual result is not a durable
guard.

**Remedy:** add a Python matrix to the non-publishing verification job. At
minimum test every classifier; because `>=3.11` also permits 3.14, either test
and classify 3.14 or document a deliberate support policy. Build and publish
once after the matrix, not once per interpreter.

### 7 — Medium: built artifacts succeed but packaging hygiene is ambiguous

**Files:** `pyproject.toml:10,14-18`; no explicit sdist manifest

`uv build` succeeds and the wheel contents are clean. It emits setuptools
warnings on every sdist and wheel phase because the license is a TOML table and
the MIT license classifier is deprecated. Setuptools gives 2027-02-18 as the
deadline for removing the deprecated table form.

The sdist also includes exactly five tests—the top-level files—and excludes
every test package, fixture and corpus. That is the least useful of the two
coherent policies: it is too incomplete to validate the source artifact and
still adds accidental test content.

**Remedy:** use an SPDX expression (`license = "MIT"`) and remove the deprecated
license classifier. Then make the sdist policy explicit: include the complete
suite and test data if downstream source validation is a goal, or exclude tests
entirely if the artifact is meant to contain only build inputs and the library.

### 8 — Low: contributor instructions describe a repository that no longer exists

**File:** `.github/copilot-instructions.md:12-66`

The current `CLAUDE.md` accurately documents the four-package architecture and
the `uv` workflow. The Copilot instructions still say:

- update a nonexistent `requirements.txt`;
- install a nonexistent `[dev]` extra;
- use removed flat modules such as `distance.py` and `qrcode_task.py`;
- treat mutable dataclasses as immutable;
- run tests that were deleted or renamed;
- use `.venv/bin/python` instead of the repository's documented `uv run` seam.

This is not harmless stale prose. It is executable context for a code-writing
tool and directly encourages architecture drift that `tests/test_layering.py`
then has to catch.

**Remedy:** delete it in favor of one canonical contributor document, or reduce
it to a pointer to `CLAUDE.md`/a tool-neutral `AGENTS.md`. One architecture
should have one maintained description.

## What is already strong

The review bar is intentionally harsh, so the absence of findings in these
areas is meaningful:

- The four-package dependency direction is enforced by code, not just prose.
- Serialization uses one field table per wire shape; read, write and known-key
  behavior are no longer independent mirrors.
- Parsing and rendering each have one front-door seam.
- `MeasuredTask`, `OptimizedRoute`, `DistanceReport`, `TaskDrawing`, and
  `GoalLine` bind values that were previously paired only by convention.
- Distance code keeps the earth model, projection, planar solver and geodesic
  correction distinguishable.
- Optional QR image support was tested both present and absent from a built
  wheel.
- Strict mypy covers production and tests; source coverage is high without a
  large untested module hiding behind the total.
- No production module is close to the 1,000-line threshold. The largest are
  `model/task.py` (587), `qrcode/task.py` (526), and
  `distance/route_optimization.py` (479).

## Recommended order

Before release:

1. Centralize and repair the release gate (finding 1).
2. Fix and regression-test installed CLI help (finding 2).
3. Remove or actually package the `web`/`analysis` surfaces (finding 3).
4. Remove the pytest 10 warning (the immediate part of finding 5).
5. Modernize license metadata while the packaging files are open (finding 7).

Immediately after, or before if the release is not time-sensitive:

6. Add the supported-Python CI matrix (finding 6).
7. Put the planar optimizer behind its natural module seam (finding 4).
8. Split the 1,681-line conformance test and retire stale contributor guidance
   (findings 5 and 8).

## Approval bar

**Not approved for release as reviewed.** The implementation itself clears the
maintainability bar, but a release includes its automation, installed CLI and
package metadata. Findings 1–3 are high-conviction, directly reproduced, and
have simpler fixes than explanations for shipping them.

