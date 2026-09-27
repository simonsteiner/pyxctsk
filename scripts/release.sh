#!/usr/bin/env bash
#
# Release helper for pyxctsk.
#
# Verifies the tree, rolls the CHANGELOG's [Unreleased] section into a dated
# release, bumps the version and the lockfile, commits, tags, and — after an
# explicit confirmation — pushes main and the tag atomically. Pushing the tag
# triggers the Publish workflow, which runs the test gate and uploads to PyPI.
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
scripts/verify.sh

# --- Version and CHANGELOG ---------------------------------------------------
# The version is worked out before anything is written, so an existing tag or
# a CHANGELOG that cannot be rolled stops here with the tree still clean.
VERSION="$(uv version --bump "$BUMP" --dry-run --short)"
TAG="v${VERSION}"
if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "Tag $TAG already exists; aborting." >&2
  exit 1
fi
python3 scripts/changelog_extract.py roll "$VERSION"
uv version --bump "$BUMP" --no-sync

# --- Commit and tag ----------------------------------------------------------
git add pyproject.toml uv.lock CHANGELOG.md
git commit -m "release ${TAG}"
git tag -a "$TAG" -m "Version ${VERSION}"

echo
echo "Prepared ${TAG}. Pushing will trigger the PyPI publish (irreversible)."
read -r -p "Push main and ${TAG} to origin now? [y/N] " reply
if [ "$reply" = "y" ] || [ "$reply" = "Y" ]; then
  # --atomic: main and the tag land together or not at all.
  git push --atomic origin HEAD:main "$TAG"
  echo "Pushed ${TAG}. Track the Publish workflow on GitHub."
else
  echo "Not pushed. To publish later:  git push --atomic origin HEAD:main ${TAG}"
  echo "To abort:                      git tag -d ${TAG} && git reset --hard HEAD~1"
fi
