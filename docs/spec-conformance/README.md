# Spec conformance

Reviews of pyxctsk against the official
[XCTrack Competition Interfaces](https://xctrack.org/Competition_Interfaces.html)
specification. Newest first.

- [2026-08-16 — Competition Interfaces conformance audit](2026-08-16-competition-interfaces-audit.md)
  — **current.** Independent review against the raw spec text and the reference
  polyline snippet, with every finding reproduced by running the library. Finds two
  unimplemented spec fields (`goal.finishAltitude`, `extensions`), no `XCTSKZ:`
  support, two crashes on spec-valid input, and several non-spec fields in the output.
- [2025-06-07 — Competition Interface support analysis](2025-06-07-competition-interfaces-analysis.md)
  — **superseded, retained for history.** Claims 100% coverage; the 2026-08-16 audit
  disproves that. Still useful as the record of the QR encoding fixes made at the time.

Route-optimization and distance accuracy are covered separately in
[`../Audit-of-pyxctsk-Route-Optimization.md`](../Audit-of-pyxctsk-Route-Optimization.md)
and [`../XCTrack-Optimized-Distance-Findings.md`](../XCTrack-Optimized-Distance-Findings.md).
