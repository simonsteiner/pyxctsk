"""QR Code Dependency Check.

Checks for Pillow and zxing-cpp and verifies that QR decoding actually works.
Unlike the old pyzbar/zbar setup, zxing-cpp ships self-contained binary wheels,
so no system package needs to be installed.
"""

import platform
import sys

print(f"Python version: {sys.version}")
print(f"Operating system: {platform.system()} {platform.release()}")

pillow_ok = False
zxing_ok = False
decode_ok = False

# Check for Pillow
try:
    from PIL import Image

    pillow_ok = True
    print("✅ PIL/Pillow imported successfully")
    print(f"   Pillow version: {Image.__version__}")
except ImportError as e:
    print(f"❌ Error importing PIL/Pillow: {e}")
    print("   Install with: uv sync")

# Check for zxing-cpp
try:
    import zxingcpp

    zxing_ok = True
    print("✅ zxing-cpp imported successfully")
except ImportError as e:
    print(f"❌ Error importing zxing-cpp: {e}")
    print("   Install with: uv sync")

# Verify decoding actually works end to end
if pillow_ok and zxing_ok:
    try:
        import qrcode

        img = qrcode.make("XCTSK:check").convert("L")
        results = zxingcpp.read_barcodes(img, formats=zxingcpp.BarcodeFormat.QRCode)
        decode_ok = any(r.text == "XCTSK:check" for r in results)
        if decode_ok:
            print("✅ QR encode/decode roundtrip succeeded")
        else:
            print("❌ QR decode returned no/incorrect result")
    except Exception as e:
        print(f"❌ QR decode raised an error: {e}")

# Summary
print("\n=== QR Code Support Status ===")
if decode_ok:
    print("✅ QR code support is AVAILABLE")
else:
    print("❌ QR code support is NOT AVAILABLE")
    print("   Some tests will be skipped unless dependencies are installed.")
    sys.exit(1)
