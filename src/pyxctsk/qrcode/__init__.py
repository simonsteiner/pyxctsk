"""XCTrack's compact QR-code task format (version 2).

A second, independent encoding of the same competition task: single-letter
keys, integer enums and polyline-compressed coordinates, so the resulting QR
code stays small enough to read on a phone in sunlight. It is a *format*, not
a second domain model — anything the format cannot represent is dropped on the
way in, not invented on the way out.

The modules:

- :mod:`~pyxctsk.qrcode.task` — ``QRCodeTask`` and the ``XCTSK:`` /
  ``XCTSKZ:`` URL schemes
- :mod:`~pyxctsk.qrcode.models` — the nested ``QRCodeTurnpoint``, ``QRCodeSSS``,
  ``QRCodeGoal``, ``QRCodeTakeoff``
- :mod:`~pyxctsk.qrcode.encoding` — the polyline codec for the ``z`` field
- :mod:`~pyxctsk.qrcode.enums` — the format's integer enums
- :mod:`~pyxctsk.qrcode.conversion` — the only module that imports both this
  package and :mod:`pyxctsk.model`, holding the translation tables
- :mod:`~pyxctsk.qrcode.image` — optional Pillow/qrcode image rendering

Note for readers: this package is called ``qrcode`` and so is the third-party
image library. Absolute imports (``import qrcode`` in :mod:`~pyxctsk.qrcode.image`)
reach the library; relative imports (``from .task import ...``) reach this
package.

Modules inside the package import each other directly rather than through this
file; the re-exports below are for callers outside it.

:mod:`~pyxctsk.qrcode.conversion` is deliberately *not* re-exported here. It is
the one module that reaches into :mod:`pyxctsk.model`, and ``model.task``
imports ``qrcode.task`` for :meth:`~pyxctsk.Task.to_qr_code_task` — so pulling
conversion in from this file would run the two packages into a circular import
on the first ``import pyxctsk``. Import it as
``from pyxctsk.qrcode.conversion import task_to_qr_code_task``.
"""

from .enums import (
    QRCodeDirection,
    QRCodeEarthModel,
    QRCodeGoalType,
    QRCodeSSSType,
    QRCodeTaskType,
    QRCodeTurnpointType,
)
from .image import generate_qrcode_image
from .models import QRCodeGoal, QRCodeSSS, QRCodeTakeoff, QRCodeTurnpoint
from .task import (
    QR_CODE_SCHEME,
    QR_CODE_SCHEME_COMPRESSED,
    QR_CODE_TASK_VERSION,
    QRCodeTask,
)

__all__ = [
    "generate_qrcode_image",
    "QR_CODE_SCHEME",
    "QR_CODE_SCHEME_COMPRESSED",
    "QR_CODE_TASK_VERSION",
    "QRCodeDirection",
    "QRCodeEarthModel",
    "QRCodeGoal",
    "QRCodeGoalType",
    "QRCodeSSS",
    "QRCodeSSSType",
    "QRCodeTakeoff",
    "QRCodeTask",
    "QRCodeTaskType",
    "QRCodeTurnpoint",
    "QRCodeTurnpointType",
]
