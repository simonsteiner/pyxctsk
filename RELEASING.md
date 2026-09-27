# Releasing pyxctsk

Releases are automated, and only one workflow publishes: **Publish**
(`.github/workflows/publish.yml`). The two ways of cutting a release below both
end by running it at a `vX.Y.Z` tag. It checks that the tag matches the
`pyproject.toml` version and has a dated `CHANGELOG.md` section, runs the CI
gate, builds the wheel and sdist once, attests their build provenance, uploads
them to PyPI with trusted publishing, and creates the GitHub Release (notes and
title from the changelog section, with the wheel and sdist attached). If the
check or the gate fails, nothing is built.

Between releases, add entries under `## [Unreleased]` in `CHANGELOG.md`. A
release renames that section to `## [vX.Y.Z] - <date>` and leaves a fresh empty
`## [Unreleased]` above it (`scripts/changelog_extract.py roll`), and refuses to
run while it is empty or when the version already has a section.

## Option A — GitHub Actions

Actions → **Release 🚀** → *Run workflow* on `main` → choose the bump
(`patch`/`minor`/`major`). It runs only on `main`; started from another branch,
every job is skipped.

`release.yml` then:

1. runs the CI gate (`ci.yml`) on the commit being released
2. bumps the version in `pyproject.toml` and `uv.lock` (`uv version --bump`)
3. rolls the changelog, stopping here if `[Unreleased]` is empty
4. commits `release vX.Y.Z`, tags `vX.Y.Z`, and pushes both to `main` in one
   atomic push — rejected if `main` moved since the run started
5. dispatches `publish.yml` at the tag

A tag pushed with `GITHUB_TOKEN` does not start workflows, but a
`workflow_dispatch` does, which is why step 5 exists and why the trusted
publisher only needs to name `publish.yml`. Releases run one at a time.

## Option B — Local script

```bash
scripts/release.sh minor   # or: major | patch (default)
```

The script runs on `main` with a clean tree. It calls `scripts/verify.sh`, the
same gate CI runs, works out the new version, rolls the changelog, bumps the
version and lockfile, commits, and tags. It asks before pushing `main` and the
tag in one atomic push; the tag push triggers **Publish**.

## Dry run

Running **Publish** from the Actions tab on a branch is a dry run: the tag check
is skipped, the CI gate runs, and the package is built and uploaded as a
workflow artifact, but nothing is attested, published, or released.

## Trusted publishing setup

Publishing uses PyPI [trusted publishing](https://docs.pypi.org/trusted-publishers/),
so no API token is stored in the repository. One-time setup:

1. On pypi.org → pyxctsk → *Publishing*, add a GitHub publisher: owner
   `simonsteiner`, repository `pyxctsk`, workflow `publish.yml`, environment
   `pypi`.
2. The `pypi` environment (GitHub → Settings → Environments) is created on the
   first publishing run if it does not exist. Add a required reviewer to it for
   a manual approval before each upload.
3. Once a release has published this way, delete the old `PYPI_API_TOKEN`
   repository secret and revoke the token on pypi.org.

`release.yml` pushes to `main` with `GITHUB_TOKEN`. If `main` gets branch
protection, allow GitHub Actions to bypass it.

## What "version" means

`pyproject.toml` is the single source of truth; `pyxctsk.__version__` reads it at
runtime via `importlib.metadata`. `uv version --bump <level>` updates it (and the
lockfile).

## Verifying a release

Run `scripts/verify.sh` to execute the complete non-mutating gate: lockfile,
lint, formatting, types, spelling, artifact build, the full test suite from the
built sdist, and a smoke test of the built wheel without the optional `qr`
extra. The **CI** workflow runs that gate on Python 3.11, 3.12, 3.13, and 3.14
on every pull request and push to `main`; **Release** and **Publish** call the
same workflow rather than repeating the matrix.

- Check the [PyPI project page](https://pypi.org/project/pyxctsk/) and the
  [GitHub releases page](https://github.com/simonsteiner/pyxctsk/releases).
- Check the provenance: `gh attestation verify dist/<file> -R simonsteiner/pyxctsk`.
- Smoke-test in a throwaway environment: `uvx --from pyxctsk pyxctsk --help`.

## Manual fallback

If the scripts are unavailable, the same steps by hand — the tag push runs
**Publish**, with the same checks:

```bash
VERSION="$(uv version --bump minor --dry-run --short)"
python3 scripts/changelog_extract.py roll "$VERSION"
uv version "$VERSION" --no-sync
git commit -am "release v${VERSION}"
git tag -a "v${VERSION}" -m "Version ${VERSION}"
git push --atomic origin HEAD:main "v${VERSION}"
```

Uploading from a local machine is no longer set up: trusted publishing only
accepts uploads from `publish.yml`.
