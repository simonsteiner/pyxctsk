"""QR code image generation for XCTrack task handling."""

from ..exceptions import QR_EXTRA_INSTALL, MissingQRCodeSupportError

# Optional QR code dependencies
try:
    import qrcode
    from PIL import Image

    QR_CODE_SUPPORT = True
except ImportError:
    qrcode = None  # type: ignore
    Image = None  # type: ignore
    QR_CODE_SUPPORT = False


def generate_qrcode_image(data: str, size: int = 1024) -> "Image.Image":
    """Generates a QR code image from the provided string data.

    Args:
        data (str): The string data to encode in the QR code.
        size (int): The width and height (in pixels) of the generated QR code image. Defaults to 1024.

    Returns:
        Image: A PIL Image object containing the generated QR code.

    Raises:
        MissingQRCodeSupportError: If 'qrcode' or 'Pillow' are not installed.
            It subclasses ImportError, so an existing ``except ImportError``
            around this function keeps working.
    """
    if not QR_CODE_SUPPORT:
        raise MissingQRCodeSupportError(
            "rendering a QR code image requires 'qrcode' and 'Pillow' "
            f"(pip install '{QR_EXTRA_INSTALL}')"
        )

    qr = qrcode.QRCode(  # type: ignore
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,  # type: ignore
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Resize to requested size. Image.Resampling arrived in Pillow 9.1 and
    # pyproject pins >= 11.3, so there is no older-API branch to fall back to.
    resized: "Image.Image" = img.resize(  # type: ignore[no-any-unimported]
        (size, size),
        Image.Resampling.LANCZOS,  # type: ignore[union-attr]
    )
    return resized
