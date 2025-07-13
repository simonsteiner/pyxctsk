# Reference Task Files for Distance Calculation Tests

This directory contains reference task files used for testing distance calculation algorithms
in pyxctsk. The files represent a collection of real-life competition tasks used in
paragliding competitions.

## Directory Structure

- `xctsk/`: Contains XCTrack task files (`.xctsk`) used as input for the distance calculations
- `json/`: Contains JSON files with reference metadata including pre-calculated distances

## Purpose

These files are used by `test_distance_comparison.py` to validate that the distance
optimization algorithms in pyxctsk produce results consistent with the reference data.

## Usage in Tests

The test fixtures in `test_distance_comparison.py` will automatically find these files
and use them for testing.
