"""Tests for QR image reading and generation and the optional-dependency probe."""

from io import BytesIO

import pytest

from pyxctsk import (
    InvalidFormatError,
    MalformedPayloadError,
    parse_task,
)
from pyxctsk.qrcode.image import generate_qrcode_image, read_qrcode_image
from pyxctsk.qrcode.task import QRCodeTask

# Use shared QR code test utilities
from tests.qr_test_utils import QR_CODE_SUPPORT, Image, zxingcpp


class TestQRSupportProbe:
    """The probe that decides whether the QR image tests run at all.

    Every image test in this module is gated on ``QR_CODE_SUPPORT``, so a
    probe that silently reported the wrong answer would turn this file into a
    green no-op rather than a failure.
    """

    def test_support_flag_matches_imports(self):
        """QR_CODE_SUPPORT is only True when both decoders actually imported."""
        if QR_CODE_SUPPORT:
            assert Image is not None
            assert zxingcpp is not None

    def test_support_flag_is_a_bool(self):
        """The probe answers True or False, never an exception or None."""
        assert isinstance(QR_CODE_SUPPORT, bool)


@pytest.mark.skipif(not QR_CODE_SUPPORT, reason="QR code dependencies not available")
class TestReadingAnImage:
    """The decoder beside the encoder, and the parser adapter composed on it."""

    def test_what_is_written_reads_back(self):
        """Encode and decode are one module's two directions."""
        written = generate_qrcode_image("XCTSK:hello", size=256)
        buffer = BytesIO()
        written.save(buffer, format="PNG")

        assert read_qrcode_image(buffer.getvalue()) == ["XCTSK:hello"]
        assert read_qrcode_image(written) == ["XCTSK:hello"]

    def test_bytes_that_are_not_an_image_are_malformed(self):
        """Pillow's many failure types become the library's one."""
        with pytest.raises(MalformedPayloadError, match="not a readable image"):
            read_qrcode_image(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)

    def test_a_malformed_payload_in_an_image_says_why(self):
        """The same reason the string reports inline, not "no QR code".

        The image adapter used to skip a code whose payload failed to parse,
        and then report that the image carried no ``XCTSK:`` code at all.
        """
        bad = 'XCTSK:{"taskType":"CLASSIC","version":2,"t":[1]}'
        buffer = BytesIO()
        generate_qrcode_image(bad, size=512).save(buffer, format="PNG")

        with pytest.raises(InvalidFormatError, match=r"t\[0\]: expected an object"):
            parse_task(buffer.getvalue())


class TestWithoutTheOptionalDependencies:
    """The documented behaviour when Pillow and zxing-cpp are absent.

    They are the library's only optional dependency, and both modules that use
    them carry a ``try: import ... except ImportError`` fallback — which
    nothing exercised, because the test environment always has them. One
    ``monkeypatch`` reaches the branch that real users without the extras hit.
    """

    def test_generating_an_image_says_what_is_missing(self, monkeypatch):
        """A named ImportError, not an AttributeError on None."""
        from pyxctsk.qrcode import image

        monkeypatch.setattr(image, "QR_CODE_SUPPORT", False)

        with pytest.raises(ImportError, match="qrcode.*Pillow"):
            image.generate_qrcode_image("XCTSK:{}")

    def test_the_parser_declines_an_image_rather_than_crashing(self, monkeypatch):
        """An image is simply not a format this install can read.

        The adapter returns None, so the input falls through to the others —
        not a NameError from the module-level ``Image = None``. The message
        used to be the same flat "invalid format" every other failure gave,
        which made a missing install indistinguishable from a corrupt file; it
        names the missing dependency now.
        """
        from pyxctsk.exceptions import InvalidFormatError
        from pyxctsk.qrcode import image

        monkeypatch.setattr(image, "QR_CODE_SUPPORT", False)

        # Matched on the extra rather than the prose: naming the wrong extra
        # is the failure this message has actually had.
        with pytest.raises(InvalidFormatError, match=r"pyxctsk\[qr\]"):
            parse_task(b"\x89PNG\r\n\x1a\n not really an image")

    def test_the_text_formats_still_work(self, monkeypatch):
        """Everything but image decoding is unaffected by the extras."""
        from pyxctsk.qrcode import image

        monkeypatch.setattr(image, "QR_CODE_SUPPORT", False)
        qr_string = QRCodeTask(version=2).to_string()

        assert parse_task(qr_string).version == 1
