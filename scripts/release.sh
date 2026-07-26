#!/usr/bin/env bash
#
# Release helper for pyxctsk.
#
# Verifies the tree, bumps the version, rolls the CHANGELOG's [Unreleased]
# section into a dated release, refreshes the lockfile, commits, tags, and —
# after an explicit confirmation — pushes. Pushing the tag triggers the Publish
# workflow, which runs the test gate and uploads to PyPI.
#
# Usage:
#   scripts/release.sh [major|minor|patch]   # default: patch
#
set -euo pipefail

BUMP="${1:-patch}"
case "$BUMP" in
  major | minor | patch) ;;
  *)
    echo "Usage: $0 [major|minor|patch]" >&2
    exit 2
    ;;
esac

cd "$(git rev-parse --show-toplevel)"

# --- Preconditions -----------------------------------------------------------
branch="$(git rev-parse --abbrev-ref HEAD)"
if [ "$branch" != "main" ]; then
  echo "Releases must be cut from 'main' (currently on '$branch')." >&2
  exit 1
fi
if [ -n "$(git status --porcelain)" ]; then
  echo "Working tree is not clean; commit or stash changes first." >&2
  exit 1
fi
git pull --ff-only origin main

# --- Verify ------------------------------------------------------------------
uv sync --all-extras
uv run ruff check src/ tests/ scripts/
uv run ruff format --check src/ tests/ scripts/
uv run mypy --config-file mypy.ini src/
uv run pytest

# --- Bump version ------------------------------------------------------------
uv version --bump "$BUMP"
VERSION="$(uv version --short)"
TAG="v${VERSION}"
uv lock

if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "Tag $TAG already exists; aborting." >&2
  exit 1
fi

# --- CHANGELOG: roll [Unreleased] into a dated release section ---------------
python3 - "$VERSION" <<'PY'
import datetime
import pathlib
import sys

version = sys.argv[1]
path = pathlib.Path("CHANGELOG.md")
text = path.read_text()
marker = "## [Unreleased]"
if marker not in text:
    sys.exit("CHANGELOG.md has no '## [Unreleased]' section to release.")
dated = f"## [v{version}] - {datetime.date.today().isoformat()}"
path.write_text(text.replace(marker, f"{marker}\n\n{dated}", 1))
PY

# --- Commit and tag ----------------------------------------------------------
git add pyproject.toml uv.lock CHANGELOG.md
git commit -m "release ${TAG}"
git tag -a "$TAG" -m "Version ${VERSION}"

echo
echo "Prepared ${TAG}. Pushing will trigger the PyPI publish (irreversible)."
read -r -p "Push to origin/main now? [y/N] " reply
if [ "$reply" = "y" ] || [ "$reply" = "Y" ]; then
  git push --follow-tags origin main
  echo "Pushed ${TAG}. Track the Publish workflow on GitHub."
else
  echo "Not pushed. To publish later:  git push --follow-tags origin main"
  echo "To abort:                      git tag -d ${TAG} && git reset --hard HEAD~1"
fi
