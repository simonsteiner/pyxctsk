# C2 · Run the suite once without the `qr` extra

[← Report](README.md)

🔧 infra · 🟡 **Worth exploring** · ↔ `two-way` · fix: `direct` · builds on: none

`scripts/verify.sh` (the sdist test run and the core-only wheel check) · `scripts/check_core_without_qr.py` · `tests/qr_test_utils.py:57` · `tests/test_cli.py:69` · `tests/qrcode/test_codec.py:58,172,248`

Every CI run installs `--all-extras` before `pytest`, so the `QR_CODE_SUPPORT` skip markers and the probe in `tests/qr_test_utils.py` have never run on the install they exist for.

**Now:** `scripts/verify.sh` runs the suite once, from the extracted sdist, after `uv sync --frozen --all-extras`, on Python 3.11–3.14. The core-only check is a wheel in a bare venv running `scripts/check_core_without_qr.py`, which imports the package and calls the image entry points; it has no pytest. The missing-extra error paths are tested by monkeypatching `QR_CODE_SUPPORT` (6 sites in `tests/test_cli_errors.py`, `tests/qrcode/test_image.py` and `tests/conformance/test_parser_diagnostics.py`), not by a real core-only install.

**Change:** one more pytest run in `verify.sh` against a core-only sync of the sdist (no `--all-extras`), on one Python version, so the skip markers and the import guard are exercised for real.

**Measure:** tests that pass or skip without the extra, now unknown (never run); CI median 59 s, from `gh run list --workflow ci.yml`. Expect about +15 s on one matrix leg.

| Problem | Fix | Wins |
|---|---|---|
| AGENTS.md says the core must work without the `qr` extra, but the suite only ever runs with it, so a test that needs the extra and lacks a skip passes in CI and fails for a contributor. | Run the suite once on a core-only install. | a missing skip fails CI<br>the import guard is tested for real |

**After:** 0 tests added or removed; 5 gated on `QR_CODE_SUPPORT` (Q1), each seen red on a core-only install before the gate. The core-only run from the extracted sdist: 1,617 passed, 65 skipped, 0 failed, 10.4 s locally (Measure: before, never run; on the unchanged tests, 5 failed). `scripts/verify.sh` passes end to end in 31.7 s locally.

<details>
<summary>Decisions</summary>

Measured on 9a91709 from an extracted sdist (`uv build --sdist`, then the same commands verify.sh runs): with `--all-extras` 1663 passed, 19 skipped; after `uv sync --frozen` (no extras) **5 failed, 1617 passed, 60 skipped**, 11 to 25 s locally against 14 to 34 s for the full run in the same sessions.

- Q1: does the suite pass core-only today? → no, 5 tests need the extra and have no skip: `tests/conformance/test_parser_diagnostics.py::TestUnrecognizedInputSaysWhy::test_an_image_with_no_qr_code_says_so` (imports `PIL` in the body) and `::test_an_unreadable_image_is_told_apart_from_a_blank_one`, `tests/test_cli.py::TestWritingOutput::test_a_png_is_written_as_bytes_not_text`, `tests/test_parser.py::TestExactlyOneAdapterRecognizesAPayload::test_a_qr_image_is_only_the_image_adapters`, and `tests/test_renderer.py::TestEveryRowRenders::test_the_payload_matches_the_rows_declared_kind[png]`; Build gates each on `QR_CODE_SUPPORT` from `tests/qr_test_utils.py` (the `[png]` case through a `pytest.param` mark, not a skip of the whole parametrize), because the failing run raised `MissingQRCodeSupportError` or `ImportError` in exactly these five and nowhere else.
- Q2: where does the run go? → in `scripts/verify.sh`, inside the existing step that `cd`s into the extracted sdist, after the `--all-extras` pytest: `uv sync --frozen` then `uv run --frozen pytest`, because that step is already the seam where the gate tests the shipped source, `uv sync` is exact so it uninstalled only `pillow`, `qrcode` and `zxing-cpp` in 0.36 s with no download, and the following `uv run` kept them out (the run skipped the QR tests).
- Q3: how does the run prove the extra is absent? → a one-line guard before the core-only pytest that fails if `PIL`, `qrcode` or `zxingcpp` resolves (`importlib.util.find_spec`), because the `tools` group already lists `Pillow` and `qrcode[pil]`, so a future move of either into `dev` would turn the core-only run into a second full run that passes silently; it is the same guard `scripts/check_core_without_qr.py` opens with.
- Q4: one matrix leg or all four? → every leg, a departure from the card's "one Python version", because the legs run in parallel (latest run: 43, 43, 48, 51 s), so one leg or four adds the same wall time, and picking one needs either a `ci.yml` change to pass the version in or a version hard-coded into verify.sh, which also runs locally.
- Q5: what does it cost? → about +12 to 15 s per leg, so a CI median near 72 s against 59 s, because CI's full sdist pytest takes 16.93 s (3.11 leg of the latest green run), the median of the last 20 green `ci.yml` runs is 59 s, and locally the core-only run takes about 0.7 of the full run (it skips 41 image tests).
- Q6: does `scripts/check_core_without_qr.py` become redundant? → no, keep it, because it runs from the installed wheel in a venv with no dev group, which catches a `src/` import of a dev-only package (`deepdiff`, `geopy`) or a module missing from the wheel; the pytest run uses the sdist source tree with the `dev` group installed and catches neither.
- Q7: any workflow or branch-protection change? → none, because `ci.yml`'s only step is `scripts/verify.sh`, so the run lands in the existing `Verify Python 3.x` checks; no new required check, so the door stays two-way and secure-github-actions is not needed.
- Q8: what else changes with it? → `docs/setup.md:57` gains the core-only suite run in its list of verify.sh steps, and `CHANGELOG.md` gets nothing, because the change is to the repository gate and tests, not to anything a user of the package sees.
- Q9: how does Measure show it worked? → the core-only run in CI reports 0 failed, 1617 passed and 65 skipped (19 that skip on every install, 41 already gated on the extra, 5 gated by Q1), next to the full run's 1663 passed and 19 skipped, because those are the scratch run's counts with Q1's five moved from failed to skipped.

</details>
