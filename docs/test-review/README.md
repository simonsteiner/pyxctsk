# Test reviews

Point-in-time reviews of pyxctsk's tests: where they miss behaviour that keeps
changing, where they cost time without guarding anything, and how they run. Each
review is a dated folder whose `README.md` status table is its backlog; reviews
stay as written. Newest first.

- [2026-11-23 — A quarter of the suite re-checks the renderer against the calls it wraps, and a skip hides the QR image round trip](2026-11-23-renderer-and-qr/README.md)
  — **2 candidates, 5 smaller findings, all open.** The first review. The suite is
  healthy: 1,691 tests in 14.2 s, 67 of 72 fix commits in six months added a test,
  and no test mocks a module the project owns. The one Strong candidate deletes a
  parametrized renderer test that compares each output row with the call the row
  makes (3.6 s per run).
