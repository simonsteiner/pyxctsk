"""Print the CHANGELOG.md section for a version, for use as a GitHub release.

Usage:
    python scripts/changelog_extract.py 0.4.0            # release notes
    python scripts/changelog_extract.py --title v0.4.0   # "v0.4.0 - 2026-06-30"

The notes are everything between the matching ``## [vX.Y.Z] - <date>`` heading
and the next ``## [`` heading. The title is that heading's version and date, so
every release is named the same way and dated by the changelog it publishes.
Exits non-zero if no such section exists.
"""

import pathlib
import re
import sys


def _heading(version: str) -> re.Pattern[str]:
    version = version.lstrip("v")
    return re.compile(rf"^## \[v?{re.escape(version)}\](?: - (?P<date>\S+))?")


def extract(text: str, version: str) -> str:
    """Return the CHANGELOG body for ``version`` (without its heading)."""
    heading = _heading(version)
    out: list[str] = []
    capturing = False
    for line in text.splitlines():
        if line.startswith("## "):
            if capturing:
                break
            if heading.match(line):
                capturing = True
            continue
        if capturing:
            out.append(line)
    return "\n".join(out).strip()


def title(text: str, version: str) -> str:
    """Return the release title ``vX.Y.Z - <date>`` from the CHANGELOG heading."""
    for line in text.splitlines():
        match = _heading(version).match(line)
        if match and match["date"]:
            return f"v{version.lstrip('v')} - {match['date']}"
    return ""


def main() -> None:
    """Print the notes, or with ``--title`` the title, for the given version."""
    args = sys.argv[1:]
    want_title = args[:1] == ["--title"]
    if want_title:
        args = args[1:]
    if len(args) != 1:
        sys.exit("usage: changelog_extract.py [--title] <version>")
    text = pathlib.Path("CHANGELOG.md").read_text()
    result = title(text, args[0]) if want_title else extract(text, args[0])
    if not result:
        sys.exit(f"no dated CHANGELOG section found for version {args[0]}")
    print(result)


if __name__ == "__main__":
    main()
