"""QR code images: rendering a payload as one, and reading payloads back out.

Both directions live here, behind one flag, because they are one optional
feature — the ``qr`` extra — and one question for a caller: can this install
handle QR *images*? The strings themselves (``XCTSK:``/``XCTSKZ:``) need none of
this. Decoding used to live in ``parser.py`` with its own flag checking a
different set of imports, and the library offered no decode function at all, so
tests and scripts called zxing-cpp directly in eight places.
"""

from io import BytesIO

from ..exceptions import (
    QR_EXTRA_INSTALL,
    MalformedPayloadError,
    MissingQRCodeSupportError,
)

# Optional QR code dependencies. The ``qr`` extra installs all three, so one
# flag answers for both directions.
try:
    import qrcode
    import zxingcpp
    from PIL import Image

    QR_CODE_SUPPORT = True
except ImportError:
    qrcode = None  # type: ignore
    zxingcpp = None  # type: ignore
    Image = None  # type: ignore
    QR_CODE_SUPPORT = False


def _require_support(action: str) -> None:
    """Refuse, naming the extra, when the image dependencies are missing."""
    if not QR_CODE_SUPPORT:
        raise MissingQRCodeSupportError(
            f"{action} requires 'qrcode', 'zxing-cpp' and 'Pillow' "
            f"(pip install '{QR_EXTRA_INSTALL}')"
        )


def generate_qrcode_image(data: str, size: int = 1024) -> "Image.Image":
    """Generates a QR code image from the provided string data.

    Args:
        data (str): The string data to encode in the QR code.
        size (int): The width and height (in pixels) of the generated QR code image. Defaults to 1024.

    Returns:
        Image: A PIL Image object containing the generated QR code.

    Raises:
        MissingQRCodeSupportError: If the ``qr`` extra is not installed.
            It subclasses ImportError, so an existing ``except ImportError``
            around this function keeps working.
    """
    _require_support("rendering a QR code image")

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


def read_qrcode_image(image: "bytes | Image.Image") -> list[str]:
    """Read the text of every QR code in an image.

    The decoding half of this module, and the only call to zxing-cpp in the
    library. It returns every code's text rather than a task: which of them is
    an ``XCTSK:`` payload, and whether that payload is a task, are the parser's
    questions, answered by the adapter that reads the text.

    Args:
        image: The encoded image file (PNG, JPEG, …) as bytes, or an image
            already opened with Pillow.

    Returns:
        The text of each QR code found, in detection order; empty if none.

    Raises:
        MissingQRCodeSupportError: If the ``qr`` extra is not installed.
        MalformedPayloadError: If the bytes are not an image Pillow can open.
    """
    _require_support("reading a QR code image")
    if isinstance(image, (bytes, bytearray)):
        try:
            image = Image.open(BytesIO(image))  # type: ignore[union-attr]
            image.load()
        except Exception as exc:  # Pillow raises a wide range here
            raise MalformedPayloadError(f"not a readable image: {exc}") from exc
    formats = zxingcpp.BarcodeFormats(zxingcpp.BarcodeFormat.QRCode)  # type: ignore[union-attr]
    return [code.text for code in zxingcpp.read_barcodes(image, formats=formats)]  # type: ignore[union-attr]
