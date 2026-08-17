"""QR code task format encoding utilities for XCTrack.

This module provides polyline-based encoding and decoding utilities for the XCTrack QR code task format. It enables compact representation of turnpoint coordinates (longitude, latitude, altitude, radius) as polyline-encoded strings for use in QR codes.

Functions:
- encode_num(num: int) -> str: Polyline-encodes a single integer value.
- encode_competition_turnpoint(lon: float, lat: float, alt: int, radius: int) -> str: Encodes a turnpoint's coordinates and parameters into a polyline string.
- decode_nums(encoded_str: str) -> list[int]: Decodes a polyline-encoded string into a list of integers.

Intended for internal use in QR code generation and parsing for paragliding/hang gliding competition tasks.
"""

from ..model.rounding import round_half_up


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
        return chr(63)

    while pnum > 0x1F:
        char_code = ((pnum & 0x1F) | 0x20) + 63
        result.append(chr(char_code))
        pnum = pnum >> 5

    result.append(chr(63 + pnum))
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

    Args:
        encoded_str: String to decode

    Returns:
        List of decoded integers
    """
    result = []
    current = 0
    pos = 0

    for char in encoded_str:
        c = ord(char) - 63
        current |= (c & 0x1F) << pos
        pos += 5

        if c <= 0x1F:
            # Extract the value (undo the encoding)
            tmp_res = current >> 1
            if (current & 0x1) == 1:
                tmp_res = ~tmp_res

            result.append(tmp_res)
            current = 0
            pos = 0

    return result
