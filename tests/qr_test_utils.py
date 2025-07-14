"""Shared QR code test utilities for dependency checks and imports."""

try:
    from PIL import Image
    from pyzbar import pyzbar

    # Try to actually use pyzbar to make sure the system dependency is available
    QR_CODE_SUPPORT = True
    try:
        # Just accessing the decode function to test if it's available
        _ = pyzbar.decode
    except Exception:
        # If there's any error (like missing zbar library), QR support is not available
        QR_CODE_SUPPORT = False
        print(
            "\nℹ️ QR code image tests will be skipped: zbar system library is missing."
        )
        print("   Run the diagnostic script for installation instructions:")
        print("   .venv/bin/python scripts/check_qr_deps.py\n")
except ImportError:
    Image = None
    pyzbar = None
    QR_CODE_SUPPORT = False
    print(
        "\nℹ️ QR code image tests will be skipped: required Python packages are missing."
    )
    print("   Run the diagnostic script for installation instructions:")
    print("   .venv/bin/python scripts/check_qr_deps.py\n")
