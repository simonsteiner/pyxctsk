"""Roll and read CHANGELOG.md for a release.

Usage:
    python scripts/changelog_extract.py 0.4.0            # release notes
    python scripts/changelog_extract.py --title v0.4.0   # "v0.4.0 - 2026-06-30"
    python scripts/changelog_extract.py roll 0.4.0       # date [Unreleased]

The notes are everything between the matching ``## [vX.Y.Z] - <date>`` heading
and the next ``## [`` heading. The title is that heading's version and date, so
every release is named the same way and dated by the changelog it publishes.
Both exit non-zero if no dated section exists, so a workflow step using them
stops before anything is published.

``roll`` renames ``## [Unreleased]`` to ``## [vX.Y.Z] - <today>`` and leaves a
fresh empty ``## [Unreleased]`` above it. It refuses an empty ``[Unreleased]``
section and a version that already has one.

``CHANGELOG.md`` is read from the current directory. Every failure ends in a
one-line message on stderr and a non-zero exit, never a traceback.
"""

import datetime
import pathlib
import re
import sys

PATH = pathlib.Path("CHANGELOG.md")
UNRELEASED = "## [Unreleased]"
USAGE = "usage: changelog_extract.py [--title | roll] <version>"


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


def roll(text: str, version: str, date: datetime.date) -> str:
    """Return ``text`` with ``[Unreleased]`` renamed to a dated ``version``.

    Args:
        text: The CHANGELOG contents.
        version: The version being released, with or without a leading ``v``.
        date: The release date written into the new heading.

    Returns:
        The CHANGELOG with an empty ``[Unreleased]`` section above the new one.

    Raises:
        SystemExit: If there is no ``[Unreleased]`` section, it is empty, or
            ``version`` already has a section.
    """
    version = version.lstrip("v")
    lines = text.splitlines()
    try:
        start = lines.index(UNRELEASED)
    except ValueError:
        sys.exit(f"{PATH} has no '{UNRELEASED}' section.")
    if any(_heading(version).match(line) for line in lines):
        sys.exit(f"{PATH} already has a section for v{version}.")
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")),
        len(lines),
    )
    if not "\n".join(lines[start + 1 : end]).strip():
        sys.exit(f"{PATH} '{UNRELEASED}' section is empty; nothing to release.")
    lines[start : start + 1] = [
        UNRELEASED,
        "",
        f"## [v{version}] - {date.isoformat()}",
    ]
    return "\n".join(lines) + "\n"


def _read() -> str:
    try:
        return PATH.read_text(encoding="utf-8")
    except OSError as error:
        sys.exit(f"cannot read {PATH}: {error.strerror}")


def main() -> None:
    """Print the notes or ``--title`` for a version, or ``roll`` it in."""
    args = sys.argv[1:]
    command = args.pop(0) if args[:1] in (["--title"], ["roll"]) else "notes"
    if len(args) != 1 or not args[0].lstrip("v"):
        sys.exit(USAGE)
    version = args[0]
    text = _read()
    if command == "roll":
        PATH.write_text(roll(text, version, datetime.date.today()), encoding="utf-8")
        return
    result = title(text, version) if command == "--title" else extract(text, version)
    if not result:
        sys.exit(f"no dated CHANGELOG section found for version {version}")
    print(result)


if __name__ == "__main__":
    main()
