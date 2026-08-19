# Architecture & conformance reviews

Point-in-time reviews of pyxctsk: how the code is structured, and how faithfully it
implements the [XCTrack Competition Interfaces](https://xctrack.org/Competition_Interfaces.html)
specification and FAI Sporting Code S7F. Each file is dated and kept as written —
superseded reviews stay for history rather than being edited. Newest first.

- [2026-08-18 — Deepening candidates after the S7F audit](2026-08-18-deepening-candidates-after-s7f.md)
  — **all seven candidates and all eight smaller findings applied.** Seven candidates in *deep module* terms, reviewed at the merge
  of the S7F audit below and scoped by churn, which put `distance/` at the centre: its package
  interface had grown from 13 to 22 names in two days, every S7F number widening it rather
  than being absorbed. The headline is that a **task and the optimized route flown for it are
  never bound together** — the two-step incantation appears at 12 call sites, two interfaces
  carry the pairing as prose no type checker can check, and handing over a mismatched pair
  returns a fully formed report 12.8 km out reporting 36.9 % savings, with no error. Four
  candidates uncovered live defects rather than friction: `--strict` cannot report
  `UNKNOWN_VERSION` for *any* QR-format input, because three of the four adapters convert the
  payload away one line before the gate — the exact failure `model/validation.py` says the
  `TaskStructure` split exists to prevent; an XC/Waypoints task makes one CLI JSON document
  say both "no speed section" and "here is the distance from its start", because `9749a93`
  added that guard to one reader and not the other; KML writes `Type: TurnpointType.TAKEOFF`
  into user-visible map text, with a test pinning it as expected; and none of the four
  `-o` writes passes `encoding=`, which fails outright on a non-UTF-8 locale and mis-encodes
  silently on Windows. Companion visual report:
  [`2026-08-18-deepening-candidates-after-s7f.html`](2026-08-18-deepening-candidates-after-s7f.html).
- [2026-08-18 — FAI Sporting Code S7F 2026 conformance audit](2026-08-18-s7f-2026-conformance-audit.md)
  — **current for S7F; all eight actionable issues fixed,** tracked in a table in the file.
  The library against the 2026 V1.0 edition of the scoring code. Confirms PR #8 closed the
  2026-07-07 audit's four algorithm findings, and found nine more. The headline was a
  **split spec lineage**: the optimizer had moved to the 2026 edition while the goal line
  still implemented 2024, whose §6.2.3.1 orients it from "the last turn point that is
  different from the goal line centre" — the 2025 plenary changed that to follow the
  optimized route, and PR #8 took the other three geometry changes from the same list but
  not this one. One corpus task drew the line 151° out, control zone facing away from the
  approach. Also found and fixed: no speed-section distance (§7.2), a task-area centre
  that was the mean of the turnpoint centres rather than `FindTaskAreaCentre` and broke
  across the antimeridian (§7.1.6), an optimizer that returned a local optimum up to 98.6 m
  above the shortest path, `+k=1` where the spec fixes k₀ = 0.99994 (§7.1.2, worth 2 mm),
  and the elevated goal's two unchecked constraints (§6.2.3.2). The ninth is not ours to
  fix: the XCTrack format has no keys for S7F's control-zone altitude limits or its general
  line control zones.
- [2026-08-17 — Deepening candidates after the package split](2026-08-17-deepening-candidates.md)
  — **A and B applied,** six proposed. Eight candidates in *deep module* terms, each reproduced by
  running the library: cumulative distances that disagree with the drawn route by 5.09 km
  and cost n optimizer runs, a LINE goal that can vanish from both output formats, a
  per-field mapping written out twelve times with three live passthrough losses, a colour
  palette that drifts across the export seam alongside invalid KML, two rival cylinder
  solvers with the tests aimed at the unused one, a corpus with four discovery
  implementations and an orphan fixture, and a layering guard narrower than its docstring.
- [2026-08-17 — Package layout: 27 flat modules into four packages](2026-08-17-package-layout.md)
  — **applied.** The split into `model/`, `qrcode/`, `distance/` and `export/`, with
  dependencies running one way and each package's `__init__.py` as its interface.
  Records the two places the planned layout met a real import cycle, the eight tests
  deleted for testing only the standard library, and a packaging hazard where a stale
  `build/` shipped ghost modules. Includes the commit-by-commit progress list.
- [2026-08-16 — Code-quality review and refactor plan](2026-08-16-code-quality-refactor-plan.md)
  — **closed;** all eleven items applied, see its Outcome section. Structural audit of the
  conformance work itself. Found derived state stored on `Goal`, a dead `polyline` concept
  holding a runtime dependency, and the extensions/unknown passthrough copy-pasted ten times.
- [2026-08-16 — Competition Interfaces conformance audit](2026-08-16-competition-interfaces-audit.md)
  — **current.** Independent review against the raw spec text and the reference
  polyline snippet, with every finding reproduced by running the library. Finds two
  unimplemented spec fields (`goal.finishAltitude`, `extensions`), no `XCTSKZ:`
  support, two crashes on spec-valid input, and several non-spec fields in the output.
- [2026-07-07 — Route-optimization audit](2026-07-07-route-optimization-audit.md)
  — pyxctsk's route optimizer against FAI Sporting Code S7F 2026 §7 and the
  Ding–Xie–Jiang "Touring n Circles" algorithm it cites. Found the beam-search
  heuristic, the missing localized Transverse Mercator projection and the ignored
  `earthModel`; resolved in PR #8.
- [2026-07-07 — XCTrack optimized-distance findings](2026-07-07-optimized-distance-findings.md)
  — companion to the audit: what XCTrack's *displayed* optimized distances actually
  mean (circle-boundary touching semantics, takeoff/goal-line centers, and XCTrack's
  own ~1 % deviation from the true WGS84 optimum on giant-cylinder tasks).
- [2026-06-30 — Distance & QR architecture review](2026-06-30-distance-qr.md)
  — deepening opportunities in the distance and QR subsystems, in *deep module*
  terms (interface, depth, seam, deletion test). Companion visual report:
  [`2026-06-30-distance-qr.html`](2026-06-30-distance-qr.html).
- [2025-06-07 — Competition Interface support analysis](2025-06-07-competition-interfaces-analysis.md)
  — **superseded, retained for history.** Claims 100% coverage; the 2026-08-16 audit
  disproves that. Still useful as the record of the QR encoding fixes made at the time.

The findings these reviews produced that are addressed to *other implementers* rather than
to this codebase — what S7F defines, what it does not, and where pyxctsk and other vendors
disagree on a task's published distance — are collected in
[`../s7f-distance-reference.md`](../s7f-distance-reference.md).

Design decisions that came out of these reviews are recorded in [`../adr/`](../adr/README.md).
