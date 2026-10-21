"""Tests for the QR polyline number encoding."""

import re

import pytest

from pyxctsk import (
    MalformedPayloadError,
)
from pyxctsk.qrcode.encoding import decode_nums, encode_num


class TestThePolylineDecoderOwnsItsValidity:
    """``decode_nums`` reads only what ``encode_num`` can write.

    The encoder writes a continuation chunk as ``_`` to ``~`` (95–126) and a
    final one as ``?`` to ``^`` (63–94), and always ends on a final chunk. The
    decoder used to read any character as a chunk and drop an unterminated
    tail, which made junk into numbers and a truncated string into a shorter
    one.
    """

    @pytest.mark.parametrize(
        "num", [0, 1, -1, 31, -32, 400, 4_650_000, -18_000_000, 2**31 - 1]
    )
    def test_what_is_written_reads_back(self, num):
        """Encode and decode are one module's two directions."""
        assert decode_nums(encode_num(num) * 3) == [num] * 3

    @pytest.mark.parametrize("num", [-(2**31), 2**31 - 1])
    def test_a_32_bit_integer_is_the_longest_number(self, num):
        """The reference format's numbers are 32-bit: seven chunks at most."""
        assert len(encode_num(num)) == 7
        assert decode_nums(encode_num(num)) == [num]

    @pytest.mark.parametrize("length", [7, 400, 200_000])
    def test_a_longer_number_is_refused_before_it_is_read(self, length):
        """An unbounded run of chunks was an integer no float holds.

        ``~`` * 400 passed here and raised ``OverflowError`` dividing it by
        1e5; 200 000 of them took over a second to read.
        """
        with pytest.raises(MalformedPayloadError, match="number 1 is longer"):
            decode_nums("?" + "~" * length + "?")

    def test_the_whole_alphabet_is_read(self):
        """Every character from ``?`` to ``~`` is a chunk; ``?`` alone is 0."""
        alphabet = "".join(chr(c) + "?" for c in range(95, 127))

        assert len(decode_nums(alphabet)) == 32
        assert decode_nums("^") == [-16]  # the last final chunk, 31
        assert decode_nums("") == []

    @pytest.mark.parametrize(
        ("encoded", "char", "index"),
        [("1234", "1", 0), ("??>", ">", 2), ("?\x7f", "\x7f", 1), ("?é", "é", 1)],
    )
    def test_a_character_outside_the_alphabet_is_refused(self, encoded, char, index):
        """It was read as a number: ``"1234"`` decoded to four of them."""
        with pytest.raises(
            MalformedPayloadError,
            match=f"^{re.escape(repr(char))} at index {index} is not a polyline character",
        ):
            decode_nums(encoded)

    def test_an_unterminated_final_number_is_refused(self):
        """A truncated string lost its last number and read as a shorter one."""
        truncated = encode_num(4_650_000)[:-1]

        with pytest.raises(MalformedPayloadError, match="number is unterminated"):
            decode_nums("??" + truncated)
