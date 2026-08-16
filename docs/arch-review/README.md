# Architecture & conformance reviews

Point-in-time reviews of pyxctsk: how the code is structured, and how faithfully it
implements the [XCTrack Competition Interfaces](https://xctrack.org/Competition_Interfaces.html)
specification and FAI Sporting Code S7F. Each file is dated and kept as written —
superseded reviews stay for history rather than being edited. Newest first.

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

Design decisions that came out of these reviews are recorded in [`../adr/`](../adr/README.md).
