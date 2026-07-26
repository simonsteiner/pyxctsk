# Architecture Decision Records

Decisions made while making the route/distance optimization faithful to FAI Sporting
Code S7F 2026 §7 (PR #8). Background: [../Audit-of-pyxctsk-Route-Optimization.md](../Audit-of-pyxctsk-Route-Optimization.md)
and [../XCTrack-Optimized-Distance-Findings.md](../XCTrack-Optimized-Distance-Findings.md).

- [0001 — Use the Ding–Xie–Jiang alternating point-circle-point optimizer](0001-ding-xie-jiang-route-optimizer.md)
- [0002 — Circle-boundary ("touching") semantics for the optimized route](0002-circle-boundary-touching-semantics.md)
- [0003 — Honor the task's earthModel (WGS84 default, FAI sphere R = 6371 km)](0003-earth-model-handling.md)
- [0004 — Remove the beam-search era API instead of keeping deprecated no-ops](0004-remove-beam-search-api.md)
