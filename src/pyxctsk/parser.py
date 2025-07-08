"""Parser for XCTrack task data."""

import json
from io import BytesIO
from typing import Union

from .exceptions import EmptyInputError, InvalidFormatError
from .qrcode_task import QR_CODE_SCHEME, QRCodeTask
from .task import Task

# Optional QR code dependencies
try:
    from PIL import Image
    from pyzbar import pyzbar

    QR_CODE_SUPPORT = True
except ImportError:
    QR_CODE_SUPPORT = False


def parse_task(data: Union[bytes, str]) -> Task:
    """
    Parse a Task from data.

    Args:
        data: Input data as bytes, string, or file path. Can be:
            - JSON string/bytes containing task data
            - XCTSK: URL string/bytes
            - Image bytes containing QR code
            - File path to any of the above

    Returns:
        Parsed Task object

    Raises:
        EmptyInputError: If input data is empty
        InvalidFormatError: If input format is invalid or cannot be parsed
    """
    if not data:
        raise EmptyInputError("empty input")

    # Check if data is a file path
    if isinstance(data, str):
        # Check if it looks like a file path, but exclude QR code URLs
        # QR code URLs start with XCTSK: and are typically very long
        if not data.startswith(QR_CODE_SCHEME) and (
            "/" in data
            or "\\" in data
            or data.endswith((".xctsk", ".json", ".png", ".jpg", ".jpeg"))
        ):
            try:
                # Try to read as file
                with open(data, "rb") as f:
                    file_data = f.read()
                return parse_task(file_data)  # Recursive call with file contents
            except (FileNotFoundError, IsADirectoryError, PermissionError):
                # If file reading fails, treat as regular string data
                pass

        # Convert string to bytes for further processing
        data_bytes = data.encode("utf-8")
    else:
        # Ensure we have bytes (not memoryview)
        data_bytes = bytes(data)

    print(f"Parsing task from data: {data_bytes[:100]}...")  # Debug output

    # Try parsing as XCTSK: URL
    if data_bytes.startswith(QR_CODE_SCHEME.encode("utf-8")):
        try:
            qr_task_json = data_bytes[len(QR_CODE_SCHEME) :].decode("utf-8")
            qr_task = QRCodeTask.from_json(qr_task_json)
            return qr_task.to_task()
        except (json.JSONDecodeError, ValueError, KeyError):
            pass

    # Try parsing as regular JSON
    try:
        if isinstance(data, str):
            task = Task.from_json(data)
        else:
            task = Task.from_json(data_bytes.decode("utf-8"))
        return task
    except (json.JSONDecodeError, ValueError, KeyError):
        pass

    # Try parsing as QR code task JSON (supports both full and simplified waypoints format)
    try:
        if isinstance(data, str):
            qr_task = QRCodeTask.from_json(data)
        else:
            qr_task = QRCodeTask.from_json(data_bytes.decode("utf-8"))
        return qr_task.to_task()
    except (json.JSONDecodeError, ValueError, KeyError):
        pass

    # Try parsing as image with QR code
    if QR_CODE_SUPPORT:
        try:
            image = Image.open(BytesIO(data_bytes))
            qr_codes = pyzbar.decode(image)

            for qr_code in qr_codes:
                payload = qr_code.data
                if payload.startswith(QR_CODE_SCHEME.encode("utf-8")):
                    try:
                        qr_task_json = payload[len(QR_CODE_SCHEME) :].decode("utf-8")
                        qr_task = QRCodeTask.from_json(qr_task_json)
                        return qr_task.to_task()
                    except (json.JSONDecodeError, ValueError, KeyError):
                        continue

        except Exception:
            pass

    raise InvalidFormatError("invalid format")
