"""QR code task format encoding utilities for XCTrack.

This module provides polyline-based encoding and decoding utilities for the XCTrack QR code task format. It enables compact representation of turnpoint coordinates (longitude, latitude, altitude, radius) as polyline-encoded strings for use in QR codes.

Functions:
- encode_num(num: int) -> str: Polyline-encodes a single integer value.
- encode_competition_turnpoint(lon: float, lat: float, alt: int, radius: int) -> str: Encodes a turnpoint's coordinates and parameters into a polyline string.
- decode_nums(encoded_str: str) -> list[int]: Decodes a polyline-encoded string into a list of integers, refusing what encode_num cannot write.

Intended for internal use in QR code generation and parsing for paragliding/hang gliding competition tasks.
"""

from ..exceptions import MalformedPayloadError
from ..model.rounding import round_half_up

#: The first character a chunk is written as: ``?``, a final chunk of 0.
_FIRST_CHAR = 63
#: The last character a chunk is written as: ``~``, a continuation chunk of 31.
_LAST_CHAR = _FIRST_CHAR + 0x3F
#: The largest final chunk; one above it carries the continuation bit.
_MAX_FINAL_CHUNK = 0x1F
#: The most chunks one number takes: the reference format's numbers are
#: 32-bit, and 33 bits (the sign folded in) fit in seven 5-bit chunks.
#: Without a bound, a run of continuation chunks is an integer no float can
#: hold, read in quadratic time.
_MAX_CHUNKS = 7


def encode_num(num: int) -> str:
    """Encode a single number using the polyline algorithm.

    Args:
        num: Integer to encode

    Returns:
        Encoded string
    """
    result = []

    # This is to ensure the sign bit is handled correctly
    # If num is negative, we will flip all bits later
    # Shift left by 1 (multiply by 2)
    pnum = num << 1
    # If negative, flip all bits
    if num < 0:
        pnum = ~pnum

    if pnum == 0:
        return chr(_FIRST_CHAR)

    while pnum > _MAX_FINAL_CHUNK:
        char_code = ((pnum & 0x1F) | 0x20) + _FIRST_CHAR
        result.append(chr(char_code))
        pnum = pnum >> 5

    result.append(chr(_FIRST_CHAR + pnum))
    return "".join(result)


def encode_competition_turnpoint(lon: float, lat: float, alt: int, radius: int) -> str:
    """Encode a competition turnpoint as the four numbers of a v2 ``z`` field.

    The competition format encodes longitude, latitude, altitude and radius.
    See :func:`encode_waypoint_turnpoint` for the XC/Waypoints variant, which
    has no radius.

    Args:
        lon: Longitude
        lat: Latitude
        alt: Altitude in meters
        radius: Radius in meters

    Returns:
        Encoded string
    """
    return encode_waypoint_turnpoint(lon, lat, alt) + encode_num(round_half_up(radius))


def encode_waypoint_turnpoint(lon: float, lat: float, alt: int) -> str:
    """Encode a waypoint as the three numbers of an XC/Waypoints ``z`` field.

    The XC/Waypoints task is a "simple route from waypoints without cylinders",
    so its ``z`` carries only longitude, latitude and altitude — appending a
    radius here would not round-trip against XCTrack.

    Args:
        lon: Longitude
        lat: Latitude
        alt: Altitude in meters

    Returns:
        Encoded string
    """
    # Round coordinates to 5 decimal places (same as Google's polyline)
    lon_int = round_half_up(lon * 1e5)
    lat_int = round_half_up(lat * 1e5)

    return encode_num(lon_int) + encode_num(lat_int) + encode_num(round_half_up(alt))


def decode_nums(encoded_str: str) -> list[int]:
    """Decode a string of encoded numbers using the polyline algorithm.

    Reads exactly what :func:`encode_num` writes: every character is a chunk
    from ``?`` to ``~`` (63–126), and the string ends on a final chunk
    (``?`` to ``^``), and no number takes more than the seven chunks a 32-bit
    integer does. Anything else is refused rather than decoded, because the
    reference decoder reads any character as a chunk and drops an
    unterminated tail — junk becomes numbers, and a truncated string becomes
    a shorter list that still looks like a turnpoint.

    Args:
        encoded_str: String to decode

    Returns:
        List of decoded integers

    Raises:
        MalformedPayloadError: If a character is outside the polyline
            alphabet, a number is longer than a 32-bit integer encodes to,
            or the last number is unterminated.
    """
    result: list[int] = []
    current = 0
    pos = 0

    for index, char in enumerate(encoded_str):
        if not _FIRST_CHAR <= ord(char) <= _LAST_CHAR:
            raise MalformedPayloadError(
                f"{char!r} at index {index} is not a polyline character (? to ~)"
            )
        c = ord(char) - _FIRST_CHAR
        current |= (c & 0x1F) << pos
        pos += 5

        if c > _MAX_FINAL_CHUNK and pos >= _MAX_CHUNKS * 5:
            raise MalformedPayloadError(
                f"number {len(result)} is longer than {_MAX_CHUNKS} chunks, "
                "more than a 32-bit integer"
            )
        if c <= _MAX_FINAL_CHUNK:
            # Extract the value (undo the encoding)
            tmp_res = current >> 1
            if (current & 0x1) == 1:
                tmp_res = ~tmp_res

            result.append(tmp_res)
            current = 0
            pos = 0

    if pos:
        raise MalformedPayloadError("the last number is unterminated")
    return result
