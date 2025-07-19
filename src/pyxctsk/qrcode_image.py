"""QR code image generation for XCTrack task handling."""

# Optional QR code dependencies
try:
    import qrcode
    from PIL import Image

    QR_CODE_SUPPORT = True
except ImportError:
    qrcode = None  # type: ignore
    Image = None  # type: ignore
    QR_CODE_SUPPORT = False


def generate_qrcode_image(data: str, size: int = 1024):
    """Generates a QR code image from the provided string data.

    Args:
        data (str): The string data to encode in the QR code.
        size (int): The width and height (in pixels) of the generated QR code image. Defaults to 1024.

    Returns:
        Image: A PIL Image object containing the generated QR code.

    Raises:
        ImportError: If the required 'qrcode' or 'Pillow' packages are not available in the environment.
    """
    if not QR_CODE_SUPPORT:
        raise ImportError("QR code support requires 'qrcode' and 'Pillow' packages")

    qr = qrcode.QRCode(  # type: ignore
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,  # type: ignore
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Resize to requested size
    try:
        # Try new Pillow API first
        img = img.resize((size, size), Image.Resampling.LANCZOS)  # type: ignore
    except AttributeError:
        # Fall back to old API for older Pillow versions
        img = img.resize((size, size), Image.LANCZOS)  # type: ignore
    return img
