"""Print the CHANGELOG.md section for a version, for use as GitHub release notes.

Usage:
    python scripts/changelog_extract.py 0.4.0
    python scripts/changelog_extract.py v0.4.0

Prints everything between the matching ``## [vX.Y.Z] - <date>`` heading and the
next ``## [`` heading, exiting non-zero if no such section exists.
"""

import pathlib
import re
import sys


def extract(text: str, version: str) -> str:
    """Return the CHANGELOG body for ``version`` (without its heading)."""
    version = version.lstrip("v")
    heading = re.compile(rf"^## \[v?{re.escape(version)}\]")
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


def main() -> None:
    """Extract the section for the version given as the first CLI argument."""
    if len(sys.argv) != 2:
        sys.exit("usage: changelog_extract.py <version>")
    notes = extract(pathlib.Path("CHANGELOG.md").read_text(), sys.argv[1])
    if not notes:
        sys.exit(f"no CHANGELOG section found for version {sys.argv[1]}")
    print(notes)


if __name__ == "__main__":
    main()
