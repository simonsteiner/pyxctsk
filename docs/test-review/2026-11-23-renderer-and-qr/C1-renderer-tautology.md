# C1 · Drop the renderer test that compares each row with the call it wraps

[← Report](README.md)

🗑️ waste · 🟢 **Strong** · ↔ `two-way` · fix: `prune-tests` · builds on: none

`tests/test_renderer.py:80-107` · `src/pyxctsk/renderer.py:50-57`

24 corpus parameters take 3.58 s of the 14.2 s suite (25%), on four Python versions in each of 11.9 CI runs a week; the expected value is the same call the row makes.

**Prune:**

| Test | Why | Still guarded by | Cost | Action |
|---|---|---|---|---|
| `tests/test_renderer.py:94` `test_each_row_agrees_with_the_call_it_replaced` (24 params) | the implementation: `render_task(task, "json")` is `task.to_json()` (`renderer.py:50-52`), `"kml"` is `task_to_kml(task)` (`:55-57`), and the geojson and qrcode-json rows wrap `generate_task_geojson` and `to_qr_code_task().to_string()`, so it asserts each call equals itself; its name and docstring guard a migration that is done (the past) | `TestEveryRowRenders::test_the_payload_matches_the_rows_declared_kind` (each row renders its declared kind), `test_a_rendered_task_reads_back` (`json` and `qrcode-json` round-trip), and each writer's own tests in `tests/export/` and `tests/qrcode/`; but none of these pins **which function** the `kml` and `geojson` rows call (pointing `_render_geojson` at the KML writer passes every other test), so one task's wiring check has to stay | 3.58 s per run | rewrite at one task |

The class `TestTheRenderingsAreWhatTheyAlwaysWere` keeps `test_compressed_reaches_the_two_rows_that_read_it` and `test_a_rendered_task_reads_back`, which guard current behaviour; only the parametrized test and its `_without_element_ids` helper go.

| Problem | Fix | Wins |
|---|---|---|
| A quarter of every run re-computes each row's output with the very call the row makes, across 24 tasks, when one task is enough to pin which writer each row calls. | Replace the parametrized test and its helper with one task's wiring check (a GeoJSON `FeatureCollection`, a `<kml` root, an `XCTSK:` prefix); the row-kind and read-back tests stay. | −3.6 s per run (−25%)<br>renderer refactors stop touching it |

**After:** −24 parametrized tests, +1 one-task wiring test (`test_each_map_row_calls_its_own_writer`, red when `_render_geojson` calls `task_to_kml`), so 1,691 → 1,668 at this layer. `tests/test_renderer.py` 3.0 s → 0.7 s, the suite 13.4 s → 12.1 s (`/usr/bin/time uv run pytest -q` with the pytest cache off, one run each on the same machine). The remaining class is `TestTheOptionsAndTheReadBack`.

<details>
<summary>Decisions</summary>

</details>
