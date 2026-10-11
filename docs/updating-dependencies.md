# Updating dependencies

How to bump pyxctsk's dependencies. Setting up the environment is in
[setup.md](setup.md).

## Update process

1. **Sync first**: `uv sync --all-extras --group tools`
2. **Check outdated packages**: `uv pip list --outdated`, or
   `uv tree --outdated` to see which declared dependency pulls each one in
3. **Bump everything within the declared ranges**: `uv lock --upgrade`
4. **Bump a single package**: `uv lock --upgrade-package scipy`
5. **Raise the floors in `pyproject.toml`** to the versions you just locked. The
   convention here is that a floor names the version the suite is actually run
   against, so raising floors is a step in the update, not a separate decision.
   That covers every list:

    - runtime `dependencies` under `[project]`
    - the `qr` extra under `[project.optional-dependencies]`
    - the `dev` and `tools` groups under `[dependency-groups]`

   After editing `pyproject.toml`, run `uv lock` to refresh `uv.lock`.
6. **Test**: `uv sync --all-extras && uv run pytest`
7. **Re-run the checkers whenever `ruff`, `mypy` or `rumdl` moved** — a tool bump
   changes what they report, and none of them shows up in the test suite:

    ```bash
    uv run ruff check --fix src/ tests/ scripts/
    uv run ruff format src/ tests/ scripts/
    uv run mypy src/ tests/
    uv run rumdl check .
    ```

   Note that `ruff format` reaches beyond `*.py`: since 0.16 it also formats
   Python code blocks inside Markdown, so a docs file can turn up in the diff.
   The ruff hook is globbed to `*.py` and won't catch that.
8. **Run the full gate**: `scripts/verify.sh`

## Maintenance schedule

- **Monthly**: Check security updates, update dev dependencies
- **Quarterly**: Update main dependencies, check deprecated features
- **Before releases**: Update all dependencies, run full test suite

## Version history

| Date | Updated Packages | Notes |
|------|------------------|-------|
| 2026-08-18 | geopy, Pillow, zxing-cpp, matplotlib, mypy, ruff, coverage, lefthook, certifi, charset-normalizer, numpy, packaging, pygments, soupsieve, typing-extensions | `uv lock --upgrade`; all declared floors (runtime, extras, dev) raised to the versions the suite is run against. mypy 1.x → 2.3.1 and zxing-cpp 2.x → 3.1.1 are major bumps, both clean. ruff 0.16 reformatted one Markdown code block. 682 passed, 18 skipped |
| 2025-07-21 | click, geopy, polyline, pyproj, qrcode, beautifulsoup4, mypy, pytest, pytest-cov, requests, matplotlib, numpy | Dependency update: main and optional packages bumped to latest stable versions |
| 2025-07-08 | scipy, click, geopy, Pillow, pyproj, qrcode | Initial dependency audit and updates |
