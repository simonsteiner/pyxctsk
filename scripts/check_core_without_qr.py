"""Verify the core install works with the `qr` extra absent.

Pillow, qrcode and zxing-cpp are an extra, not dependencies, and `parser.py`
and `qrcode/image.py` are both written for their absence. Nothing exercised
that: while they were mandatory the `QR_CODE_SUPPORT is False` branches were
unreachable, and the error one of them raised told the user to install the
`web` extra, which is flask.

Run this inside a venv holding `pyxctsk` and nothing else:

    uv venv /tmp/core && VIRTUAL_ENV=/tmp/core uv pip install .
    /tmp/core/bin/python scripts/check_core_without_qr.py

It exits non-zero if the extra turns out to be installed after all (the check
would prove nothing), or if any core path needs it.
"""

import sys

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"✅ {name}")
    else:
        print(f"❌ {name}{f': {detail}' if detail else ''}")
        failures.append(name)


# The extra must genuinely be absent, or nothing below means anything.
for module in ("PIL", "qrcode", "zxingcpp"):
    try:
        __import__(module)
    except ImportError:
        continue
    print(f"❌ {module} is installed — run this in a venv without the `qr` extra")
    sys.exit(1)
print("✅ the `qr` extra is absent, as this check requires")

import pyxctsk  # noqa: E402

check("import pyxctsk", True)
check("QR image support reports itself absent", not pyxctsk.parser.QR_CODE_SUPPORT)

TASK = (
    '{"taskType":"CLASSIC","version":1,"turnpoints":['
    '{"radius":400,"waypoint":{"name":"A","lat":47.0,"lon":8.0,"altSmoothed":500}},'
    '{"radius":1000,"waypoint":{"name":"B","lat":47.1,"lon":8.2,"altSmoothed":900}}]}'
)

task = pyxctsk.parse_task(TASK)
check("parse the full JSON format", len(task.turnpoints) == 2)
check("write it back", "taskType" in task.to_json())

qr_string = task.to_qr_code_task().to_string()
check("write an XCTSK: string", qr_string.startswith("XCTSK:"))
check("read one back", len(pyxctsk.parse_task(qr_string).turnpoints) == 2)
check(
    "write the compressed XCTSKZ: form",
    task.to_qr_code_task().to_string(compressed=True).startswith("XCTSKZ:"),
)

check("measure the task", pyxctsk.DistanceReport.from_task(task).task_distance_m > 0)
check("render KML", pyxctsk.task_to_kml(task).startswith("<?xml"))
check(
    "render GeoJSON", pyxctsk.generate_task_geojson(task)["type"] == "FeatureCollection"
)

# The two paths that do need the extra must say so, and name the right one.
try:
    pyxctsk.parse_task(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
except pyxctsk.InvalidFormatError as exc:
    check("reading an image names the extra", "pyxctsk[qr]" in str(exc), str(exc))
else:
    check("reading an image names the extra", False, "no error raised")

try:
    pyxctsk.generate_qrcode_image(qr_string)
except pyxctsk.MissingQRCodeSupportError as exc:
    check("writing an image names the extra", "pyxctsk[qr]" in str(exc), str(exc))
else:
    check("writing an image names the extra", False, "no error raised")

print()
if failures:
    print(f"❌ {len(failures)} core path(s) need the `qr` extra: {', '.join(failures)}")
    sys.exit(1)
print("✅ the core install is complete without the `qr` extra")
