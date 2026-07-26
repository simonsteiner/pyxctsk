# ADR 0004: Remove the beam-search era API instead of keeping deprecated no-ops

Date: 2026-07-07 · Status: Accepted

## Context

After the algorithm swap (ADR 0001), the beam-search tuning surface — `angle_step`
(perimeter sampling resolution) and `beam_width` (DP candidates per stage) — no longer
influenced anything. The first cut of PR #8 kept these parameters as documented no-ops to
avoid breaking callers. Silent no-ops are a trap, though: callers believe they are tuning
precision/performance while the values are ignored, and the parameters have to be
threaded through every layer (`task_distances`, `sss_calculations`, tests) forever.

## Decision

Remove the dead surface in one breaking change (repo owner's call), documented in
`CHANGELOG.md`:

- `angle_step`/`beam_width` parameters of `optimized_distance`,
  `optimized_route_coordinates`, `calculate_iteratively_refined_route`,
  `calculate_task_distances`, `calculate_cumulative_distances`,
  `calculate_optimal_sss_entry_point`, `calculate_sss_info`; the unused
  `task_turnpoints` parameter of `optimized_route_coordinates`; the
  `optimization_angle_step`/`beam_width` keys of `calculate_task_distances` results.
- `get_optimization_config`, `DEFAULT_BEAM_WIDTH`, `DEFAULT_ANGLE_STEP`
  (`optimization_config.py` now holds only `CONVERGENCE_EPSILON_M` and
  `DEFAULT_NUM_ITERATIONS`, re-exported via `pyxctsk.distance`).
- `TaskTurnpoint.perimeter_points` — its last consumer (SSS entry sampling) was replaced
  by the exact `optimal_point`; visualization draws cylinder outlines itself in
  `visualization_common.py`.

The remaining tunable is `num_iterations` (maximum alternating sweeps), which has real
meaning again; precision is governed by the spec's ε = 0.1 m, not by a sampling knob.

## Consequences

- Library consumers passing the removed keyword arguments get an immediate `TypeError`
  instead of silently ignored tuning — the failure mode is loud and easy to fix (delete
  the argument).
- Tests that parametrized over `angle_step` were replaced by a determinism test: with an
  exact optimizer, repeated runs must return identical results.
- Version bump guidance: this plus ADR 0001's protocol change warrants a minor version
  bump (pre-1.0 breaking change) with the CHANGELOG "Removed" section as the migration
  guide.
