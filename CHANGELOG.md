# Changelog

All notable changes to this project will be documented in this file.

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
