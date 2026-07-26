"""Shared QR code test utilities for dependency checks and decoding.

QR image decoding uses ``zxing-cpp`` (imported as ``zxingcpp``), a maintained
library that ships self-contained binary wheels, so no system package is
required. The availability probe runs a real generate-and-decode roundtrip in a
*subprocess*: if the native decoder ever crashes (e.g. a segfault), the crash is
contained in the child process and ``QR_CODE_SUPPORT`` is set to ``False`` so the
test session skips QR image tests instead of dying.
"""

import subprocess
import sys

try:
    import zxingcpp
    from PIL import Image
except ImportError:
    Image = None  # type: ignore[assignment]
    zxingcpp = None  # type: ignore[assignment]


# A trivial roundtrip exercised in a subprocess to confirm the decoder actually
# works on this machine without risking the test process on a native crash.
_SMOKE_TEST = """
import qrcode, zxingcpp
img = qrcode.make("XCTSK:smoke").convert("L")
results = zxingcpp.read_barcodes(img, formats=zxingcpp.BarcodeFormat.QRCode)
assert any(r.text == "XCTSK:smoke" for r in results)
"""


def _probe_qr_support() -> bool:
    """Return True only if QR encode+decode actually works in a subprocess."""
    if Image is None or zxingcpp is None:
        print(
            "\nℹ️ QR code image tests will be skipped: required Python packages "
            "are missing. Install with: uv sync\n"
        )
        return False
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _SMOKE_TEST],
            capture_output=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    if proc.returncode != 0:
        print(
            "\nℹ️ QR code image tests will be skipped: the QR decoder failed a "
            "smoke test on this machine.\n"
        )
        return False
    return True


QR_CODE_SUPPORT = _probe_qr_support()


def decode_qr(image) -> list[str]:
    """Decode all QR codes in a PIL image, returning their text payloads.

    Args:
        image: A PIL ``Image`` containing zero or more QR codes.

    Returns:
        The decoded text of each QR code found, in detection order.
    """
    results = zxingcpp.read_barcodes(image, formats=zxingcpp.BarcodeFormat.QRCode)
    return [barcode.text for barcode in results]
