
# Reference Task and QR Code Test Data

This directory contains data files for validating distance calculation algorithms and QR code generation/parsing for XCTrack tasks in `pyxctsk`. The files represent real-world competition tasks from paragliding events, as well as selected cases for QR code roundtrip and string validation.

## Directory Structure

- `xctsk/`: XCTrack task files (`.xctsk`) used as input for both distance and QR code tests.
- `json/`: JSON files with reference metadata, including pre-calculated distances and QR code strings.
- `qrcode_string/`: Expected QR code strings in `.txt` files for QR code tests.

## Purpose

These files serve two main purposes:

1. **Distance Calculation Validation**: Used by `test_distance_reference.py` to ensure that distance optimization algorithms in `pyxctsk` match reference results.
2. **QR Code Generation and Parsing**: Used by `test_qrcode.py` and related tests to:
   - Generate QR code strings from task files and compare with expected outputs.
   - Validate roundtrip parsing and QR code image generation (when dependencies are available).

## Usage in Tests

- Test fixtures in `test_distance_reference.py` and related test modules automatically discover and use these files for validation.
- QR code string and image validation is performed by `test_qrcode.py`.

## Visual Output

Generated QR code images and other visual outputs are saved to `tests/visual_output/` during testing.
