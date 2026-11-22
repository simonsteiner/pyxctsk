# C2 · The drawing hands each writer features, not thirteen questions

[← Report](README.md)

🟢 **Strong** · `in-process` · ↔ `two-way` · builds on: none

`src/pyxctsk/export/common.py:102-310` · `src/pyxctsk/export/kml.py:85-184` · `src/pyxctsk/export/geojson.py:30-160` · `tests/export/test_common.py` · `tests/export/test_writers_agree.py` · `tests/export/test_geojson_goal_line.py:9`

```mermaid
flowchart LR
  subgraph before["Before"]
    direction TB
    K1["kml.py"]:::module
    G1["geojson.py"]:::module
    T1["TaskDrawing · is_goal · outline_of · color_of · label_of · description_of · role_of · route_label · goal_line_label · goal_line_description · control_zone_label · control_zone_description · route_coordinates · route_coordinates_lon_lat"]:::shallow
    K1 -- "13 calls, same order" --> T1
    G1 -- "13 calls, same order" --> T1
  end
  subgraph after["After"]
    direction TB
    K2["kml.py · serializes"]:::module --> F2["TaskDrawing · the features to draw"]:::deep
    G2["geojson.py · serializes"]:::module --> F2
    subgraph inside[" "]
      direction TB
      A2["turnpoint: name, description, colour, role, centre, radius, outline"]:::faded
      B2["route: name, lon-lat points"]:::faded
      C2["goal line and control zone: name, description, geometry"]:::faded
    end
    F2 -.- inside
  end
  before ~~~ after
  classDef module fill:#ffffff,stroke:#64748b,stroke-width:2px,color:#0f172a
  classDef shallow fill:#f1f5f9,stroke:#94a3b8,stroke-dasharray:4 3,color:#334155
  classDef deep fill:#0f172a,stroke:#0f172a,color:#e2e8f0
  classDef faded fill:#1e293b,stroke:#475569,color:#94a3b8
  classDef leak fill:#fef2f2,stroke:#dc2626,stroke-width:2px,color:#991b1b
  style inside fill:#0f172a,stroke:#0f172a
  style before fill:#fafaf9,stroke:#e2e8f0
  style after fill:#fafaf9,stroke:#e2e8f0
```

`TaskDrawing` has 13 public methods, most of them one to three lines, and each writer reads 13 of its attributes in the same order; `export/common.py` is in 20 commits in six months, changing with `kml.py` in 75% and `geojson.py` in 80%.

**Removes:**

- `src/pyxctsk/export/common.py:237-253,259-274`: `goal_line_description` and `control_zone_description` raise `ValueError` unless the caller checked `goal_line` first, an ordering rule each writer has to know.
- `src/pyxctsk/export/common.py:219-235,255-257`: `route_label`, `goal_line_label`, `control_zone_label` return constants and read nothing from the drawing.
- `src/pyxctsk/export/common.py:164,202,217`: `turnpoint.type or TurnpointType.NONE` normalized three times, though `role_of` exists to be the one reading.
- `src/pyxctsk/export/common.py:276-300`: `route_coordinates` and `route_coordinates_lon_lat`, two orders of one route, the first used only by tests.
- `src/pyxctsk/export/common.py:102`: `is_goal`, public for `color_of` and tests.
- `tests/export/test_geojson_goal_line.py:9`: the test that imports `_create_goal_line_features` (S4).

| Problem | Solution | Wins |
|---|---|---|
| The 2026-08-19 review moved each shared answer onto `TaskDrawing` as its own accessor, so the drawing's interface grew to match its implementation, and both writers still walk the same four kinds of thing asking the same questions in the same order. | The drawing yields the features to draw (turnpoints, the route, the goal line, the control zone), each a value carrying its name, description, colour and geometry; the writers only serialize them. | interface shrinks to the features<br>no call-order rule<br>agreement test compares features once<br>a new caption changes one module |

> [!NOTE]
> The 2026-08-19 review's card D stopped at accessors on purpose, to land the shared answers first; this is the step after it, not a reversal. KML, GeoJSON and the distance report must stay byte-identical across the corpus.

<details>
<summary>Decisions</summary>

<!-- filled during implementation, one line each -->

- Q1: What shape is the deepened module's interface (design it twice: one tagged `Feature` class with optional per-kind fields, one typed stream, or four per-kind tuples)? → One typed stream: `TaskDrawing.features` returns `tuple[Feature, ...]`, `Feature = CylinderFeature | RouteFeature | GoalLineFeature | ControlZoneFeature`, cylinders first, then the route, the goal line, the control zone; each writer is one `match` ending in `typing.assert_never`, because both writers already emit the four kinds in that one order (`kml.py:230-233`, `geojson.py:190-199`), so the stream states the order once, and `assert_never` makes a new kind a mypy failure in every writer, the "spelled out rather than defaulted" rule `common.py:362-366` states for the palette; the tagged class needs a `None` check per optional field under strict mypy, and per-kind tuples leave the order to each writer and let a writer skip a new kind silently.
- Q2: What does each feature carry? → `CylinderFeature`: `index`, `name` (the `TP{n}` fallback applied), `description`, `role` (normalized to `TurnpointType.NONE` once), `color` (goal decided by identity), `centre` (lon, lat), `radius`, `outline()`; `RouteFeature`: `name`, `description`, `color`, `points` (lon, lat), present only at two points or more; `GoalLineFeature`: `name`, `description`, `color`, `length`, `ends()`; `ControlZoneFeature`: `name`, `description`, `edge_color`, `fill_color`, `radius`, `outline()`, because that is every read the writers make today (the 13 methods, the four palette constants each writer imports at `kml.py:8-15` and `geojson.py:18-24`, and `drawing.task` at `kml.py:139`), so afterwards a writer reads `drawing.features` and nothing else, and the goal-line `ValueError` ordering rule goes because those two features exist only when a goal line does.
- Q3: Is feature geometry computed when the drawing is built? → No: `outline()` and `ends()` are methods that compute on call, through `geodesic_arc` and `GoalLine.endpoints()`/`control_zone()` as now, because `tests/export/test_common.py:145-181` pins that a 10^300 m takeoff builds a drawing and GeoJSON and fails only KML, and a 10^300 m LINE goal builds a drawing and fails both writers, while `scripts/task_viewer/app.py:147-151` hands that drawing's `measured` to the distance table, so eager geometry would turn both into `from_task` failures.
- Q4: In what type does a cylinder carry its radius? → `turnpoint.radius` unconverted, because `model/task_parts.py:121` declares `radius: int` and both GeoJSON's `radius` property and the `Radius: {r}m` description render it, so a `float()` would write `400.0` and break byte identity.
- Q5: Do the dataclass fields (`turnpoints`, `goal_line`, `measured`) and the `task`/`route` properties stay? → Yes, and `features` is derived from them, because `tests/export/test_geojson.py:50-66,146-157` construct the drawing from those fields to skip the optimizer, `tests/export/test_common.py:85-94` reads `drawing.goal_line.approach_from`, `tests/distance/test_task_distances.py:262-274` reads `drawing.route`, and both task-viewer endpoints read `drawing.measured`.
- Q6: Is `features` cached? → No, a plain property built on each read, because with geometry deferred (Q3) it formats strings only and each writer reads it once.
- Q7: Where do the feature classes live? → In `export/common.py` beside `TaskDrawing` and the palette, because the 13 methods are 8,184 of the file's 15,995 bytes (lines 102-304), which leaves the four classes room under the hook's 20,000-byte (5,000-token) budget, while a separate `features.py` would import the palette from `common.py` and be imported by it, a cycle that needs the palette moved too.
- Q8: Does GeoJSON start writing the route's description now that the route feature carries it? → No, because every output must stay byte-identical; the feature carries it so KML stops reading `drawing.task` (`kml.py:139`), and the GeoJSON gap is left as found.
- Q9: Are the feature classes exported from `pyxctsk` or `pyxctsk.export`? → No, they are reachable at `pyxctsk.export.common`, because nothing outside the package names them (the task viewer reads only `from_task`, `measured` and `drawing_to_geojson`: `app.py:147-151`, `api.py:158-162`) and `tests/test_front_door.py` pins the export list.
- Q10: Breaking? → Yes, Breaking (API): the 13 public methods of `pyxctsk.TaskDrawing` (exported at `src/pyxctsk/__init__.py:68,148`) go with no shims, recorded under `## [Unreleased]` with an old → new table, because a grep finds no caller outside `src/pyxctsk/export/` and `tests/` (none in `scripts/`, `README.md`, `docs/`), `CHANGELOG.md:150-158` recorded the last removals of `TaskDrawing`/`export.common` names as Breaking (API), and AGENTS.md rules out fallbacks nobody asked for.
- Q11: Which tests survive, and how? → `test_writers_agree.py` keeps its 15 tests with the expected values read from `drawing.features`; `test_common.py` and `test_common_palette.py:105` move their `is_goal`, `route_coordinates` and `outline_of` assertions onto the features (the goal colour on the last cylinder, the route's lon-lat points, `CylinderFeature.outline()`), the laziness tests keeping their form; `test_geojson.py`'s private imports (`_create_turnpoint_feature`, `_create_optimized_route_feature`, `:23-27`) and the six `_create_goal_line_features` tests in `test_geojson_goal_line.py` (S4) assert through `drawing_to_geojson`/`generate_task_geojson`, filtered on `properties.type`, because each writer helper changes signature to take one feature, the coupling S4 names.
- Q12: How is byte identity shown? → Hash every `OUTPUT_FORMATS` row but `png`, with `compressed` both ways, over `corpus.reference_tasks()` (24) plus the `ess-goal` and `elevated-goal` fixtures (16) before and after: 40 tasks, 5 with a goal line, 320 outputs, and the hash list's digest at `ee90ca1` is `7cc1d49e6e69c6bc` (identical over two runs), because `tests/data/` holds no expected KML or GeoJSON, so the suite alone cannot show it; `distance/` is not touched, so the distance report cannot move.
- Q13: Which live docs name the removed methods? → `AGENTS.md:74-75` (reworded to "becomes a field on a feature" and "via `CylinderFeature.outline()`"), `model/task.py:232` and `tests/conformance/test_ess_goal_fixtures.py:133` (`TaskDrawing.is_goal`), and the `export/__init__.py` docstring; the released `CHANGELOG.md` entries stay, because a grep for the 13 names finds only these outside the export package and its tests.
- Q14: Dependency category and seam? → In-process: no port at the drawing, and the two writers are the feature stream's two adapters, so the seam is real, because the drawing is pure computation over `Task`, `MeasuredTask` and `GoalLine`.
- Q15: A new domain term? → **Feature**, added to `GLOSSARY.md`, because the design names the four kinds a map shows and the glossary had no word for one.
- Q16: Does C2 collide with S5 on `export/common.py`? → Yes, S5 trims the `color_of` docstring (`common.py:148-156`) that C2 deletes, and the batch order puts C2 first, so the S5 branch drops that hunk when it rebases.

</details>
