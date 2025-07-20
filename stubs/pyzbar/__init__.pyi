"""Type stubs for pyzbar package."""

from typing import Any

class Decoded:
    data: bytes
    type: str
    rect: tuple[int, int, int, int]
    polygon: list[tuple[int, int]]

def decode(image: Any) -> list[Decoded]: ...
