# Elevated-goal fixtures

Eight real competition tasks that set an elevated goal — and store it in a
field the spec does not define. Exercised by
`tests/test_elevated_goal_fixtures.py`.

Each task is kept as the scanned QR photo (`*.jpg`) and its decoded `XCTSK:`
payload (`*.txt`). Tests should prefer the `.txt`, since reading the `.jpg`
needs the optional `zxing-cpp` and `Pillow` extras; the photos are the original
artifacts and exercise the image path when those extras are installed. Files are
numbered by SSS open time so the ordering is stable and meaningful.

## The non-spec `"o"` object

Every task carries an `"o"` object at two levels, byte-identical across the set:

```
root          "o": {"v": 2, "fa": 1220}      in all 8
per-turnpoint "o": {"a1": 180}               on all 61 turnpoints
```

`fa` is the elevated goal altitude. The goal waypoint `A01` sits at **1020 m**
in every task and `fa` is **1220** — a constant 200 m above it.

This departs from the spec three ways:

1. **Location.** The spec puts finish altitude at `g.fa`, inside the goal
   object. Here it is a top-level `o`.
2. **Datum.** The spec defines `finishAltitude` as *"meters AGL (computed from
   the altitude of the last turnpoint)"*, so a conformant encoding of this task
   would be `"g": {"fa": 200}`. This producer writes **1220, absolute AMSL**.
3. **Mechanism.** The spec reserves `x` for manufacturer extensions, each root
   entry carrying an obligatory `id`. `o` keyed by `v` is not discoverable as
   one.

`a1` is undocumented and constant at 180 across every turnpoint, so this sample
cannot say what it means.

## What they pin

- **Unknown fields survive a round-trip.** `Task.unknown` and
  `Turnpoint.unknown` carry `o` through both the QR and full-JSON formats. Before
  that, parsing these silently discarded the elevated goal.
- **`o.fa` is deliberately *not* mapped onto `goal.finish_altitude`.** The datum
  differs, so copying 1220 into a field the spec defines as AGL-above-goal would
  turn a lost value into a wrong one — off by the 1020 m the waypoint already
  sits at. A test asserts `finish_altitude is None` to keep a future change from
  quietly making that mistake.

## Provenance

Scanned QR photos, producer unknown. Not tools.xcontest.org: the key order is
`taskType, version, t, s, g, o`, `tc`/`to` are omitted rather than emitted as
nulls, and every turnpoint sets `d` equal to `n` (or to `""`).

There are no reference distances for these, so they pin self-consistency rather
than agreement with XCTrack's displayed numbers.

## Known, accepted round-trip differences

Re-encoding reproduces the source payload except for two documented behaviours:

- an empty description (`"d": ""`) is dropped, since empty and absent mean the
  same and the QR format exists to save bytes;
- the six tasks that omit `goal` entirely gain `"g": {"t": 2}`, CYLINDER being
  the spec's documented default (finding 10b of the conformance audit).
