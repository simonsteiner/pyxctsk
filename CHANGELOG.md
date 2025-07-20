# Changelog

All notable changes to this project will be documented in this file.

## [v0.3.0] - 2025-07-21

### Added

- Switched codebase to require Python 3.10 or newer, enabling use of modern type hint syntax and language features
- Enhanced KML export: added `simplekml` dependency and improved KML export functionality
- Type stubs for `geopy`, `polyline`, and `pyzbar` for strict mypy compliance
- Essential smoke tests for distance calculations and comprehensive reference tests for validation
- QR code test utilities and comprehensive tests for QR code functionality
- SSS, turnpoint, and utility function tests; migrated and consolidated test files for efficiency

### Enhanced

- Refactored KML and GeoJSON generation: unified altitude handling, improved turnpoint feature creation, and introduced shared visualization utilities
- Refactored goal line calculations: consolidated logic into `goal_line` module and updated GeoJSON/KML generation
- Improved documentation and code quality: added pydocstyle to pre-commit hooks, improved module docstrings, and updated release instructions
- Improved error handling in QR code and distance modules
- Updated test data and documentation for clarity and improved coverage
- Update dependencies to latest versions for improved stability and performance

### Fixed

- Handled edge case for identical start and end points in cylinder optimization
- Corrected latitude/longitude values in route comparison outputs
- Updated route comparison coordinates for improved accuracy in visual output
- Resolved all mypy type errors for strict type compliance
- Fixed type hints and import statements for consistency and compatibility

### Refactored

- Split and reorganized modules for maintainability: QR code, KML, goal line, and utility functions
- Unified altitude parameter naming and removed unused calculations in KML generation
- Reorganized imports and updated `__all__` in `__init__.py`
- Cleaned up and improved formatting across test and source files
- Removed obsolete and outdated test files and data

## [v0.2.0] - 2025-07-09

### Added

- Support for simplified XC/Waypoints format in QRCodeTask and QRCodeTurnpoint serialization
- Complete XCTrack QR code format with custom polyline encoding

### Enhanced

- Parse_task function with improved file path checks and QR code task parsing

### Fixed

- JSON output to handle non-ASCII characters in QRCodeTask
- Include description in QRCodeTurnpoint only if non-empty
- Method naming after introducing simplified XC/Waypoints

### Refactored

- Split large qrcode_task.py into focused modules
- Reorganized import statements across multiple modules for clarity
- Enhanced code formatting for consistency and readability

## [v0.1.0] - 2025-06-30

### Added

- Initial public release with core XCTrack task format support
- Parse and write `.xctsk` (XCTrack JSON) files
- QR code generation and decoding for task sharing with XCTrack format compatibility
- Command-line interface for format conversion (JSON, KML, QR code image, XCTSK: URL)
- KML export for visualization with turnpoint color coding based on type
- Comprehensive data classes for all XCTrack task components
- Distance calculation module with advanced route optimization algorithms
- Iterative refinement for optimized route calculation to reduce look-ahead bias
- Dynamic programming methods for optimal route calculation
- Centralized optimization configuration for consistent parameters
- Beam search algorithms for route planning
- Goal line and control zone features for LINE type goals in GeoJSON generation

### Enhanced

- SSS (Start Speed Section) handling with optional time_close attribute
- QRCodeSSS and QRCodeTurnpoint serialization for improved compatibility
- Turnpoint features with color coding based on type
- Optimized route properties and visualization
- Goal handling in task and distance modules with support for goal lines
- Distance calculation logic with simplified route processing
- Cylinder point optimization methods for improved clarity and performance
- Optimized distance calculation starting from takeoff center

### Refactored

- Split distance.py into focused modules for better maintainability
- Dynamic programming methods for route calculation
- Route optimization by removing SSS-specific handling and treating all turnpoints uniformly
- Distance calculation logic by simplifying route processing
- Code formatting and organization with black & isort

### Technical

- Full pytest suite for all major features including distance calculations
- Type hints, PEP 8 compliance, linting, formatting, and type checking support
- Comprehensive test coverage for optimization algorithms and SSS handling
- Performance optimizations with caching mechanisms
- Renamed xctrack module to pyxctsk for better package organization
