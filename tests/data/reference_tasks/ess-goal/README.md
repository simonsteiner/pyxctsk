# ESS / goal relationship fixtures

Real tasks covering how the End of Speed Section relates to the goal — a case
the main corpus in `../xctsk/` barely exercises. Exercised by
`tests/test_ess_goal_fixtures.py`.

| file | shape |
| --- | --- |
| `do-t3.xctsk` | 9 turnpoints, **ESS is the last turnpoint** — the spec's "if the last turnpoint is marked ESS then it is identical to goal" case |
| `task2_qr_code.png` | 8 turnpoints, ESS **duplicated** as a separate goal turnpoint (identical coordinates, altitude and radius) |
| `task3_qr_code.png` | 5 turnpoints, same duplicate pattern |
| `task4_qr_code.png` | 9 turnpoints, same duplicate pattern, plus a turnpoint that repeats the takeoff waypoint at a larger radius |

Each `*_qr_code.txt` is the `XCTSK:` payload decoded from the PNG beside it.
Tests should prefer the `.txt`, since reading the `.png` needs the optional
`zxing-cpp` and `Pillow` extras; the PNGs are kept as the original artifacts and
to exercise the image path when those extras are installed.

## Provenance

Downloaded (Windows zone marker present, no source URL recorded); producer
unknown but **not** tools.xcontest.org — the QR key order is
`version, taskType, t, s, g` rather than xcontest's alphabetical
`g, s, t, taskType, tc, to, version`, and these omit `tc`/`to` entirely instead
of emitting nulls. Both are spec-legal, which is the useful part: it shows the
null `tc`/`to` in `../qrcode_string/` is one producer's habit, not a rule.

Unlike `../json/`, there are no reference distances for these — no XCTrack
display values came with them — so they pin *self-consistency*, not agreement
with XCTrack's numbers.

## Note on the name

These were collected while looking for tasks with an **elevated goal**, and the
directory was originally named for that. They do not contain one: there is no
`goal.finishAltitude` in `do-t3.xctsk` and no `fa` key in any of the three QR
payloads. `goal.finishAltitude` support is covered by unit tests in
`tests/test_spec_conformance.py`; real-world coverage for it is still missing.

## What they pin

1. **Parsing and validation** — all four parse, `Task.validate()` is clean, and
   the QR payloads round-trip semantically.
2. **The duplicate-turnpoint degeneracy.** Two consecutive route points on one
   circle used to freeze the alternating optimizer at a spurious local minimum:
   once the points coincide, moving either adds length to the leg between them
   exactly as fast as it saves on the neighbouring leg. On `task2` this left the
   final point at bearing 90.05° from the goal center instead of 170.16°,
   inflating the optimized distance by 168 m. Consecutive identical circles are
   now collapsed before optimizing, so a duplicated turnpoint contributes
   exactly zero. Concentric turnpoints of *different* radii keep their
   mandatory out-and-back leg (see `docs/adr/0002-circle-boundary-touching-semantics.md`).
