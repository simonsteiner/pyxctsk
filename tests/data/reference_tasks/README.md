# Reference Task and QR Code Test Data

This directory contains data files used for testing both distance calculation algorithms and QR code generation/parsing for XCTrack tasks in pyxctsk. The files represent a collection of real-life competition tasks used in paragliding competitions, as well as selected cases for QR code roundtrip and string validation.

## Directory Structure

- `xctsk/`: Contains XCTrack task files (`.xctsk`) used as input for both distance and QR code tests
- `json/`: Contains JSON files with reference metadata including pre-calculated distances
- `qrcode_string/`: Contains expected QR code strings in .txt files for QR code tests

## Purpose

These files serve two main purposes:

1. **Distance Calculation Validation**: Used by `test_distance_comparison.py` to validate that the distance optimization algorithms in pyxctsk produce results consistent with reference data.
2. **QR Code Generation and Parsing**: Used by `test_qrcode_generation.py` to test:
   - Generation of QR code strings from task files
   - Comparison with expected QR code strings
   - Generation of QR code images (when dependencies are available)
   - Roundtrip parsing of generated QR codes

## Usage in Tests

- The test fixtures in `test_distance_comparison.py` will automatically find the relevant files for distance calculation testing.
- The files in this directory are also used by `test_qrcode_generation.py` for QR code string and image validation.

## Visual Output

Generated QR code images are saved to `tests/data/visual_output/` during testing.
