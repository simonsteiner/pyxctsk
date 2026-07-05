# Architecture review — pyxctsk

**Date:** 2026-06-30
**Scope:** deepening opportunities in the distance & QR subsystems
**Companion:** [`2026-06-30-distance-qr.html`](./2026-06-30-distance-qr.html) (visual report)

Vocabulary follows the *deep module* framing: a **module** has an **interface**
(everything a caller must know) and an **implementation**; **depth** is leverage at
the interface; a **seam** is where behaviour can be altered without editing in place;
the **deletion test** asks whether removing a module makes complexity vanish (it was a
pass-through) or reappear across callers (it was earning its keep).

---

## A. Collapse the duplicated DP machinery — **Strong**

**Files:** `src/pyxctsk/route_optimization.py`

**Problem.** Two copies of the dynamic-programming route search are kept in sync by
hand:

- `_process_dp_stage` and `_process_dp_stage_with_refined_target` are identical but
  for how `next_center` is chosen; the beam-trim block is copy-pasted, and the refined
  variant has unreachable code after its `return` (lines ~152–153).
- `_compute_optimal_route_with_beam_search` and
  `_compute_optimal_route_with_refined_targets` both init the DP, run the forward pass,
  pick the best final point, and backtrack — twice.
- `_create_refined_turnpoints` is a pass-through: it rebuilds the turnpoint list with
  the same centers/radii while silently **stripping `goal_type`**. The refinement signal
  actually travels through `previous_route` / `next_target`, not through these rebuilt
  turnpoints.

**Solution.** One DP routine — `_run_dp(turnpoints, lookahead, beam_width)` — where the
look-ahead target is a parameter (a strategy): cylinder centers on pass 1, the previous
route's points on refinement passes. Delete `_create_refined_turnpoints` and the
unreachable code.

**Wins.**
- locality: one DP, one place to test
- leverage: refinement becomes one argument
- delete ~120 lines of duplication
- kills the latent `goal_type`-stripping bug

---

## B. Delete the dead perimeter layer in `turnpoint.py` — **Strong (deletion test)**

**Files:** `src/pyxctsk/turnpoint.py`

**Problem.** Three functions duplicate the cylinder / goal-line / center dispatch that
`optimal_point` already owns — and nothing calls them:

- `optimized_perimeter_points` — unreferenced.
- `_get_optimized_perimeter_points` — only the dead method above calls it.
- `goal_line_points` — referenced only in a comment.

What callers actually reach: `optimal_point` (the route optimizer, through the
`TurnpointGeometry` seam) and `perimeter_points` (SSS calculations).

**Solution.** Delete the three dead functions.

**Wins.**
- deletion test: complexity vanishes, nothing reappears
- interface shrinks to the one surviving dispatch
- removes a second copy of goal-line math (see C)
- less surface for the next reader to map

---

## C. Reunite goal-line geometry behind `GoalLine` — **Worth exploring**

**Files:** `src/pyxctsk/turnpoint.py`, `src/pyxctsk/goal_line.py`

**Problem.** `goal_line.py`'s `GoalLine` is the declared "single source" of goal-line
geometry (KML, GeoJSON, and distance code go through it). But `turnpoint.py`'s
`_find_optimal_goal_line_point` re-derives the perpendicular azimuth and the line
endpoints independently — so the rules live in two places and the docstring's claim is
false.

**Solution.** Move the optimal-crossing computation onto `GoalLine` (which already
exposes `endpoints()`), and have the turnpoint call through it.

**Caveat (grill the interface first).** The turnpoint needs a goal line oriented to an
arbitrary `prev_point` — the point currently being evaluated in the route — not the
task's fixed previous turnpoint. `GoalLine.from_task` binds the approach to a fixed
turnpoint, so the deepening must let the approach direction vary (e.g. an
`approach_from` parameter on the crossing method).

**Wins.**
- locality: goal-line rules in one module
- the "single source" docstring becomes true
- one endpoint primitive, one test surface
- pairs naturally with B (B removes the other copy)

---

## D. Table-drive the QR ↔ domain enum translation — **Worth exploring**

**Files:** `src/pyxctsk/qrcode_task.py` (`from_task` / `to_task`)

**Problem.** Six enum pairs — TaskType, EarthModel, GoalType, SSSType, TurnpointType,
Direction — are hand-mapped with `if/elif` chains in **both** directions across
`from_task` and `to_task`. A new enum value can touch up to four blocks. The mapping is
a shallow interface spread thin.

**Solution.** One small bidirectional table per enum pair, read both ways by a tiny
`convert`. Keep the field-ordering and null-handling logic as-is — only the enum mapping
moves. Scope stays tight.

**Wins.**
- locality: each pair defined once
- add an enum value in one row
- round-trip becomes table-symmetric
- scoped to mapping, not the ordering logic

---

## Top recommendation

Start with **A — collapse the DP machinery**: the deepest friction and the most
leverage. Do **B** first as a free warm-up (pure deletion), then **C** follows naturally
because B removes one of the two goal-line copies.

## Left alone (already deep)

- `goal_line.py` `GoalLine` — deep, single small interface over the geometry; thin
  backwards-compat adapters retained deliberately.
- `Task._derive_goal` (`task.py`) — goal defaults derived once in `__post_init__`;
  `from_dict` / `to_dict` rely on it rather than re-deriving.
- `TurnpointGeometry` protocol (`turnpoint.py`) — a real seam: lets the DP core run
  against lightweight fakes.
