#!/usr/bin/env bash
#
# Release helper for pyxctsk.
#
# Runs the verification gate on an up-to-date main, then has
# scripts/prepare_release.sh — the release sequence release.yml runs too —
# roll the CHANGELOG, set the version, commit and tag. After an explicit
# confirmation it pushes main and the tag atomically. Pushing the tag triggers
# the Publish workflow, which runs the test gate and uploads to PyPI.
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

# --- Commit and tag ----------------------------------------------------------
VERSION="$(scripts/prepare_release.sh "$BUMP")"
TAG="v${VERSION}"

# --- Push, after confirmation ------------------------------------------------
echo
echo "Pushing ${TAG} will trigger the PyPI publish (irreversible)."
read -r -p "Push main and ${TAG} to origin now? [y/N] " reply
if [ "$reply" = "y" ] || [ "$reply" = "Y" ]; then
  # --atomic: main and the tag land together or not at all.
  if git push --atomic origin HEAD:main "$TAG"; then
    echo "Pushed ${TAG}. Track the Publish workflow on GitHub."
    exit 0
  fi
  echo "Push failed; neither main nor ${TAG} reached origin."
  status=1
else
  echo "Not pushed."
  status=0
fi
echo "To publish later:  git push --atomic origin HEAD:main ${TAG}"
echo "To abort:          git tag -d ${TAG} && git reset --hard HEAD~1"
exit "$status"
