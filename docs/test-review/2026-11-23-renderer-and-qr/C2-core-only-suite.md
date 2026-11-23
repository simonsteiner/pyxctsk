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

**After:** <!-- filled at Ship -->

<details>
<summary>Decisions</summary>

</details>
