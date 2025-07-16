"""
QR Code Dependency Check
This script checks for Pillow, pyzbar, and the zbar system library, and provides installation hints tailored to your operating system if any are missing.
"""

import platform
import sys


def get_install_hint():
    """Get installation hint for installing the zbar system library based on the detected operating system.

    Returns:
        str: Installation command or hint appropriate for the user's OS and distribution.
    """
    system = platform.system()

    if system == "Linux":
        # Check for common Linux distributions
        try:
            with open("/etc/os-release") as f:
                os_info = f.read().lower()
                if "ubuntu" in os_info or "debian" in os_info:
                    return "sudo apt-get install libzbar0"
                elif "fedora" in os_info or "redhat" in os_info:
                    return "sudo dnf install zbar"
                elif "arch" in os_info:
                    return "sudo pacman -S zbar"
                elif "opensuse" in os_info:
                    return "sudo zypper install libzbar0"
                else:
                    return "Install zbar library using your package manager"
        except FileNotFoundError:
            return "Install zbar library using your package manager"
    elif system == "Darwin":  # macOS
        return "brew install zbar"
    elif system == "Windows":
        return "Download and install ZBar DLL from: https://sourceforge.net/projects/zbar/files/zbar/0.10/"
    else:
        return "Install zbar library appropriate for your system"


print(f"Python version: {sys.version}")
print(f"Operating system: {platform.system()} {platform.release()}")

# Check for Pillow
try:
    from PIL import Image

    print("✅ PIL/Pillow imported successfully")
    print(f"   Pillow version: {Image.__version__}")
except ImportError as e:
    print(f"❌ Error importing PIL/Pillow: {e}")
    print("   Install with: pip install Pillow")

# Check for pyzbar Python package
pyzbar_installed = False
try:
    import pyzbar

    pyzbar_installed = True
    print("✅ pyzbar Python package imported successfully")
    print(f"   pyzbar version: {pyzbar.__version__}")
except ImportError as e:
    print(f"❌ Error importing pyzbar: {e}")
    print("   Install with: pip install pyzbar")

# Check for zbar system library
zbar_library_available = False
if pyzbar_installed:
    try:
        from pyzbar import pyzbar as pyzbar_decode

        # Try to actually use the library to verify it works
        test_data = b"test"  # Some dummy data
        try:
            pyzbar_decode.decode(test_data)
            # If we get here without error, the library might be working
            # (we expect an error about invalid image format, not about missing library)
            zbar_library_available = True
        except Exception as e:
            if "zbar" in str(e).lower() and (
                "not found" in str(e).lower() or "unable to find" in str(e).lower()
            ):
                zbar_library_available = False
            else:
                # If we get an error unrelated to missing library, assume it's working
                zbar_library_available = True

        if zbar_library_available:
            print("✅ zbar system library is available")
        else:
            print("❌ zbar system library is not available")
            print(f"   Install hint: {get_install_hint()}")
    except Exception as e:
        print(f"❌ Error loading pyzbar module: {e}")
        print(f"   Install hint: {get_install_hint()}")

# Summary
print("\n=== QR Code Support Status ===")
if pyzbar_installed and zbar_library_available:
    print("✅ QR code support is AVAILABLE")
else:
    print("❌ QR code support is NOT AVAILABLE")
    print("   Some tests will be skipped unless dependencies are installed.")
