"""QR code task format encoding utilities.

This module contains the polyline encoding and decoding utilities used in the
XCTrack QR code task format. These utilities handle the compression of turnpoint
coordinates (lon, lat, alt, radius) into polyline-encoded strings.
"""

from typing import List


def encode_num(num: int) -> str:
    """Encode a single number using the polyline algorithm.

    Args:
        num: Integer to encode

    Returns:
        Encoded string
    """
    result = []
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
    """Encode turnpoint data using the XCTrack format.

    Args:
        lon: Longitude
        lat: Latitude
        alt: Altitude in meters
        radius: Radius in meters

    Returns:
        Encoded string
    """
    # Round coordinates to 5 decimal places (same as Google's polyline)
    lon_int = round(lon * 1e5)
    lat_int = round(lat * 1e5)

    # Encode each component
    encoded_lon = encode_num(lon_int)
    encoded_lat = encode_num(lat_int)
    encoded_alt = encode_num(alt)
    encoded_radius = encode_num(radius)

    # Concatenate all encoded values
    return encoded_lon + encoded_lat + encoded_alt + encoded_radius


def decode_nums(encoded_str: str) -> List[int]:
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
