# Releasing pyxctsk

Releases are automated. Pick one of the two paths below; both verify the code,
bump the version, roll the `CHANGELOG.md` `[Unreleased]` section into a dated
release, tag, and publish to PyPI.

Prerequisite: the `PYPI_API_TOKEN` secret must be set in the repository
(GitHub → Settings → Secrets and variables → Actions).

## Option A — Local script

```bash
scripts/release.sh minor   # or: major | patch (default)
```

The script runs on `main` with a clean tree. It verifies (ruff, mypy, pytest),
bumps the version with `uv version`, refreshes `uv.lock`, updates the changelog,
commits, and tags. It asks before pushing; pushing the tag triggers the
**Publish** workflow, which re-runs the test gate and uploads to PyPI.

## Option B — GitHub Actions

Actions → **Release 🚀** → *Run workflow* → choose the bump (`patch`/`minor`/`major`).

The workflow verifies, bumps, updates the changelog, commits, tags, pushes back
to `main`, and publishes to PyPI — no local steps needed.

## What "version" means

`pyproject.toml` is the single source of truth; `pyxctsk.__version__` reads it at
runtime via `importlib.metadata`. `uv version --bump <level>` updates it (and the
lockfile). Keep a `## [Unreleased]` section at the top of `CHANGELOG.md` between
releases — the release tooling renames it to `## [vX.Y.Z] - <date>` and leaves a
fresh empty `## [Unreleased]` above it.

## Verifying a release

- Check the [PyPI project page](https://pypi.org/project/pyxctsk/).
- Smoke-test in a throwaway environment: `uvx --from pyxctsk pyxctsk --help`.

## Manual fallback

If you need to publish by hand:

```bash
uv version --bump minor && uv lock
# edit CHANGELOG.md, then:
git commit -am "release v$(uv version --short)"
git tag -a "v$(uv version --short)" -m "Version $(uv version --short)"
git push --follow-tags origin main      # triggers the Publish workflow
# or build/upload directly (needs UV_PUBLISH_TOKEN):
uv build && uv publish
```

For test uploads use TestPyPI: `uv publish --publish-url https://test.pypi.org/legacy/`.
