# Elevated-goal fixtures

Real tasks that set an elevated goal, in **two different encodings** — which is
the point of keeping them together. Exercised by
`tests/test_elevated_goal_fixtures.py`.

| files | producer | where the finish altitude lives | datum |
| --- | --- | --- | --- |
| `xcontest-conformant.*` | tools.xcontest.org | `goal.finishAltitude` / `g.fa` — as the spec defines | **300 m AGL** above the last turnpoint |
| `task1`–`task8` | SeeYou Navigator (per the person who collected them) | root `"o": {"v": 2, "fa": 1220}` — not a spec field | **1220 m absolute AMSL** |

The datums are the crux. In the conformant task the goal waypoint is at 428 m
and `finishAltitude` is 300 — *below* the waypoint's own altitude, so it can
only be a height above it (goal at 728 m AMSL). In the SeeYou tasks the goal
waypoint is at 1020 m and `o.fa` is 1220, which read as AGL would put the goal
1220 m above the ground; read as absolute it is a plausible 200 m elevated
goal. Same feature, incompatible conventions — which is why `o.fa` is preserved
but never mapped onto `goal.finish_altitude`.

The SeeYou tasks are kept as the scanned QR photo (`*.jpg`) and its decoded
`XCTSK:` payload (`*.txt`). Tests should prefer the `.txt`, since reading the
`.jpg` needs the optional `zxing-cpp` and `Pillow` extras; the photos are the
original artifacts and exercise the image path when those extras are installed.
They are numbered by SSS open time so the ordering is stable and meaningful.

## The conformant task

Downloaded from `https://tools.xcontest.org/api/xctsk/{load,loadV2}/6f83e4192cd55562`,
kept in both formats: `xcontest-conformant.xctsk` (v1) and
`xcontest-conformant_qr_code.txt` (v2, `XCTSK:`-prefixed). Our QR output is
byte-identical to it.

Besides the elevated goal it covers two more shapes worth having: the last
turnpoint is marked ESS (the spec's "ESS is identical to goal" case), and the
SSS shares its center with the goal at a 61.6 km versus 400 m radius — a
concentric pair of *different* radii, whose mandatory out-and-back leg makes the
optimized distance exceed the through-centers distance. That guards the
duplicate-collapse fix from over-reaching.

## The non-spec `"o"` object

Every `task1`–`task8` carries an `"o"` object at two levels, byte-identical
across the set:

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
- **The spec's own encoding still works**, via `xcontest-conformant.*`: the same
  feature read from `goal.finishAltitude` / `g.fa`, with `unknown` empty and the
  QR output byte-identical to the reference producer.

## Provenance

`task1`–`task8` are scanned QR photos, attributed to **SeeYou Navigator**
(Naviter) by the person who collected them — treat that as likely rather than
confirmed; nothing in the payload names the producer. It is certainly not
tools.xcontest.org: the key order is `taskType, version, t, s, g, o`, `tc`/`to`
are omitted rather than emitted as nulls, and every turnpoint sets `d` equal to
`n` (or to `""`).

`xcontest-conformant.*` came from tools.xcontest.org, task code
`6f83e4192cd55562`, uploaded specifically to provide a conformant counterpart.

There are no reference distances for any of these, so they pin
self-consistency rather than agreement with XCTrack's displayed numbers.

## Known, accepted round-trip differences

Re-encoding reproduces the source payload except for two documented behaviours:

- an empty description (`"d": ""`) is dropped, since empty and absent mean the
  same and the QR format exists to save bytes;
- the six tasks that omit `goal` entirely gain `"g": {"t": 2}`, CYLINDER being
  the spec's documented default (finding 10b of the conformance audit).
