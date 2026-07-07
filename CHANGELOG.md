# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Changed

- **Route optimization is now faithful to FAI Sporting Code S7F 2026 §7** (see `docs/Audit-of-pyxctsk-Route-Optimization.md`). The dynamic-programming + beam-search heuristic in `route_optimization.py` was replaced by the algorithm the spec cites — Ding, Xie & Jiang, *"An Efficient Algorithm for Touring n Circles"* (MATEC Web of Conf. 232, 03027, 2018): one route point per turnpoint, alternately updating odd/even points with the exact planar GetOptPi solution (crossing vs. reflection case), iterated until the total path length changes by less than ε = 0.1 m (§7.1.3). Optimization runs in a localized Transverse Mercator plane centred on the task area (§7.1.2); the converged points are snapped back onto the true cylinder boundaries (ProjectionCorrection, §7.1.7) before legs are summed geodesically. The optimizer is both more accurate (true optimum instead of a heuristic) and much faster.
- **The "crossing" case is now handled** (Ding et al. Theorem 1): when the previous or next route point lies inside a cylinder, or the leg passes through it, the optimal point is the segment–circle intersection — no spurious detours for nested/overlapping cylinders or a takeoff inside the SSS. Concentric turnpoints of different radii keep their mandatory out-and-back legs (touching semantics, matching XCTrack's displayed distances, e.g. `task_nohe`).
- **The `earthModel` task field is honored**: distances and boundary points are computed on the WGS84 ellipsoid (default) or on the FAI sphere (great circles, R = 6 371 000 m) when the task specifies `FAI_SPHERE`. New helpers `geodesic_distance`, `geod_for_earth_model` and constant `FAI_SPHERE_RADIUS_M` in `turnpoint.py`; `TaskTurnpoint` gained an `earth_model` attribute that `_task_to_turnpoints` fills from the task.
- `TaskTurnpoint.optimal_point` places points via the planar GetOptPi in a local Transverse Mercator plane and snaps them to exactly radius *r* on the earth model (previously: scipy `fminbound` over the azimuth, which could stall in the 0°/360° wrap and returned the cylinder center when the neighbours nearly coincided). `calculate_optimal_sss_entry_point` now returns this exact point instead of the nearest of the 10°-sampled perimeter points.
- `optimized_distance`, `optimized_route_coordinates` and `calculate_iteratively_refined_route` gained an `earth_model` parameter; `num_iterations` now bounds the alternating sweeps (default `DEFAULT_NUM_ITERATIONS = 100`; convergence normally stops after a handful). New `CONVERGENCE_EPSILON_M = 0.1` in `optimization_config.py`.

### Removed

- **Breaking (library API):** all parameters of the removed beam-search optimizer were dropped rather than kept as no-ops: the `angle_step` and `beam_width` parameters of `optimized_distance`, `optimized_route_coordinates`, `calculate_iteratively_refined_route`, `calculate_task_distances` and `calculate_cumulative_distances`; the `angle_step` parameter of `calculate_optimal_sss_entry_point` and `calculate_sss_info`; and the unused `task_turnpoints` back-compat parameter of `optimized_route_coordinates`. The `calculate_task_distances` result dictionary no longer contains the `optimization_angle_step` and `beam_width` keys.
- **Breaking (library API):** `optimization_config.py` lost `get_optimization_config`, `DEFAULT_BEAM_WIDTH` and `DEFAULT_ANGLE_STEP` (it now holds only `CONVERGENCE_EPSILON_M` and `DEFAULT_NUM_ITERATIONS`, both re-exported from `pyxctsk.distance`), and `TaskTurnpoint.perimeter_points` was removed — the exact `optimal_point` replaced its last consumer (SSS entry points); cylinder outlines for visualization are drawn in `visualization_common.py`.
- The private beam-search internals of `route_optimization.py` (`_run_dp`, `_init_dp_structure`, `_process_dp_stage`, `_backtrack_path`, `_center_lookahead`, `_route_lookahead`) were removed with the algorithm swap. The `TurnpointGeometry` protocol now names the attributes the optimizer needs (`center`, `radius`, `goal_type`) instead of an `optimal_point` method.
- **Breaking (library API):** removed three dead, duplicated methods/helpers from `turnpoint.py`: `TaskTurnpoint.optimized_perimeter_points`, `TaskTurnpoint.goal_line_points`, and the module-level `_get_optimized_perimeter_points`. They duplicated the cylinder/goal-line/center dispatch already owned by `TaskTurnpoint.optimal_point` and were unused within the package. Callers should use `TaskTurnpoint.optimal_point` (optimal crossing point) or `TaskTurnpoint.perimeter_points` (cylinder sampling), both of which are retained.

## [v0.4.1] - 2026-06-29

### Added

- The release workflows now create a GitHub Release automatically, taking the notes from the matching `CHANGELOG.md` section (via `scripts/changelog_extract.py`) and attaching the built wheel and sdist.

## [v0.4.0] - 2026-06-30

### Changed

- Migrated project and dependency management to [uv](https://docs.astral.sh/uv/): added `uv.lock` and `.python-version`, moved dev dependencies to a `[dependency-groups]` table, and switched the publish workflow to `uv build`/`uv publish`.
- Raised the minimum Python version to 3.11 (`scipy>=1.16` already required it).
- Replaced the QR image decoder `pyzbar` with [`zxing-cpp`](https://github.com/zxing-cpp/zxing-cpp), which ships self-contained binary wheels — QR image tests no longer need the system `zbar` library and now run by default.
- `pyxctsk.__version__` is now read from package metadata so `pyproject.toml` is the single source of truth.
- Replaced the black + isort + flake8 + pydocstyle toolchain with [ruff](https://docs.astral.sh/ruff/), and switched git hook management from pre-commit to [lefthook](https://github.com/evilmartians/lefthook).
- Automated releases: a `scripts/release.sh` helper and a manually-triggered `Release` GitHub Actions workflow bump the version, update the changelog, tag, and publish; the `Publish` workflow now runs the test/lint/type gate before uploading to PyPI.

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
