"""What the installed package says about itself — its version.

A leaf module because three places need this string and none of them may
import the others: :mod:`pyxctsk.cli` for ``--version``,
:mod:`pyxctsk.distance.report` for the report's provenance line, and the
package ``__init__`` for :data:`pyxctsk.__version__`. It lived in
``distance/report.py`` — a general "what version am I" utility parked in the
S7F report module, reached from the CLI by a private-path import, and the only
reason ``cli.py`` had an import edge into ``distance`` at all.

Named for ``importlib.metadata`` rather than ``version``, which would shadow
the name ``__init__`` imports and read one letter from ``pyxctsk.VERSION``,
the *format*'s version and a different number entirely.

There were two answers, and they failed differently. ``__init__`` called
``importlib.metadata.version`` directly, which raises on a source run;
``report.py`` caught that and returned ``"unknown"``. Both are this now.
"""

from importlib.metadata import PackageNotFoundError, version

#: What the version reads as when the package is not installed — a source
#: checkout run in place, which is exactly when ``importlib.metadata`` has
#: nothing to find.
UNKNOWN_VERSION = "unknown"


def pyxctsk_version() -> str:
    """Return the installed library version, or :data:`UNKNOWN_VERSION`.

    Returns:
        The version string from package metadata.
    """
    try:
        return version("pyxctsk")
    except PackageNotFoundError:  # pragma: no cover - editable/source runs
        return UNKNOWN_VERSION
