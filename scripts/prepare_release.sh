#!/usr/bin/env bash
#
# Make the release commit and tag for pyxctsk, locally. Pushes nothing.
#
# The one release sequence, called by both ways of cutting a release —
# scripts/release.sh and .github/workflows/release.yml — so a fix to it lands
# once. Each caller keeps what is its own: the gate it runs first (verify.sh,
# or ci.yml), the git identity it commits as, and whether and how it pushes.
#
# In order, it:
#   1. refuses a dirty working tree;
#   2. works out the new version once, writing nothing;
#   3. refuses a tag that already exists, locally or on origin;
#   4. rolls the CHANGELOG's [Unreleased] section into that version;
#   5. sets that version in pyproject.toml and uv.lock (`uv version <version>`);
#   6. checks the release notes and title publish.yml will read are there;
#   7. commits `release vX.Y.Z` and tags `vX.Y.Z`.
#
# Any failure puts the branch back where it started, so the tree is never left
# half-released. On success the version (without the `v`) is the only line on
# stdout; everything else goes to stderr.
#
# Usage:
#   scripts/prepare_release.sh [major|minor|patch]   # default: patch
#
set -euo pipefail

# stdout carries the version alone; send everything else, ours and the tools',
# to stderr.
exec 3>&1 1>&2

BUMP="${1:-patch}"
case "$BUMP" in
  major | minor | patch) ;;
  *)
    echo "Usage: $0 [major|minor|patch]"
    exit 2
    ;;
esac

cd "$(git rev-parse --show-toplevel)"

# Checked first: putting the branch back on failure is only safe from a clean
# tree.
if [ -n "$(git status --porcelain)" ]; then
  echo "Working tree is not clean; commit or stash changes first."
  exit 1
fi
start="$(git rev-parse HEAD)"

# --- Version: computed once, before anything is written ----------------------
VERSION="$(uv version --bump "$BUMP" --dry-run --short)"
TAG="v${VERSION}"
if git rev-parse --verify --quiet "refs/tags/$TAG" >/dev/null; then
  echo "Tag $TAG already exists locally; aborting."
  exit 1
fi
# `git pull` does not fetch every tag, so ask origin as well. ls-remote exits 2
# when the tag is absent; anything else but 0 means origin was not reached.
remote_status=0
git ls-remote --exit-code --tags origin "refs/tags/$TAG" >/dev/null || remote_status=$?
case "$remote_status" in
  0)
    echo "Tag $TAG already exists on origin; aborting."
    exit 1
    ;;
  2) ;;
  *)
    echo "Could not check origin for tag $TAG; aborting."
    exit 1
    ;;
esac

# --- Write, commit, tag: all of it or none of it ----------------------------
restore() {
  status=$?
  if [ "$status" -ne 0 ]; then
    echo "Release of $TAG failed; restoring the branch to ${start:0:12}."
    git tag -d "$TAG" >/dev/null 2>&1 || true
    git reset --hard --quiet "$start"
  fi
  exit "$status"
}
trap restore EXIT

python3 scripts/changelog_extract.py roll "$VERSION"
uv version "$VERSION" --no-sync
# The notes and title publish.yml will read must exist before anything is
# published.
python3 scripts/changelog_extract.py "$VERSION" >/dev/null
python3 scripts/changelog_extract.py --title "$VERSION"

git add pyproject.toml uv.lock CHANGELOG.md
git commit --quiet -m "release ${TAG}"
git tag -a "$TAG" -m "Version ${VERSION}"
trap - EXIT

echo "Prepared ${TAG}."
echo "$VERSION" >&3
