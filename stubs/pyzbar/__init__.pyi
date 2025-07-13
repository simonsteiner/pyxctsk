"""Type stubs for pyzbar package."""

from typing import Any, Dict, List, Optional, Tuple, Union

class Decoded:
    data: bytes
    type: str
    rect: Tuple[int, int, int, int]
    polygon: List[Tuple[int, int]]

def decode(image: Any) -> List[Decoded]: ...
