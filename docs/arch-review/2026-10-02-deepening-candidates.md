# pyxctsk: the field table checks containers, and nothing owns a scalar

`2026-10-02` · at `003f9c3` (`main`) · scope: all of `src/pyxctsk` (churn since the [2026-09-27](2026-09-27-deepening-candidates.md) review is release tooling plus `6b361c5`'s lenient radius in `model/shape.py`), and `scripts/release.sh`, `scripts/changelog_extract.py`, `scripts/task_viewer/api.py` · glossary: `CONTEXT.md` · ADRs read: 0001, 0002, 0003, 0004

**Jump to:** [Status](#status) · [Where it hurts](#where-it-hurts) · [C1](#c1--one-owner-for-a-wire-scalar) · [C2](#c2--the-distance-report-owns-the-two-turnpoint-minimum) · [C3](#c3--the-polyline-decoder-owns-its-own-validity) · [C4](#c4--the-solver-refuses-a-route-it-cannot-measure) · [C5](#c5--one-json-writer) · [C6](#c6--one-release-sequence) · [Smaller findings](#smaller-findings) · [Recommendation](#recommendation)

<details>
<summary>Legend</summary>

```mermaid
flowchart LR
  M["module"]:::module
  S["shallow module"]:::shallow
  D["deep module"]:::deep
  M -. "seam" .- S
  S -- "leak" --> L["leaking module"]:::leak
  classDef module fill:#ffffff,stroke:#64748b,stroke-width:2px,color:#0f172a
  classDef shallow fill:#f1f5f9,stroke:#94a3b8,stroke-dasharray:4 3,color:#334155
  classDef deep fill:#0f172a,stroke:#0f172a,color:#e2e8f0
  classDef faded fill:#1e293b,stroke:#475569,color:#94a3b8
  classDef leak fill:#fef2f2,stroke:#dc2626,stroke-width:2px,color:#991b1b
```

</details>

## Status

The backlog, in rank order. After the scan only three parts of this file change: this table, each candidate's **Decisions**, and **Departures**. The findings stay as found.

| ID | Deepening | Strength | Lens | Status | Branch | PR | Breaking | Notes |
|---|---|---|---|---|---|---|---|---|
| [C1](#c1--one-owner-for-a-wire-scalar) | One owner for a wire scalar | 🟢 Strong · 🔴 live defect | deepening | pr-open | `refactor/wire-scalars` | [#29](https://github.com/simonsteiner/pyxctsk/pull/29) | yes | batch 2026-10-02: C1 → C2 → C3 → C4 |
| [C2](#c2--the-distance-report-owns-the-two-turnpoint-minimum) | The distance report owns the two-turnpoint minimum | 🟢 Strong · 🔴 live defect | deepening | pr-open | `refactor/report-owns-minimum` | [#30](https://github.com/simonsteiner/pyxctsk/pull/30) | no | |
| [C3](#c3--the-polyline-decoder-owns-its-own-validity) | The polyline decoder owns its own validity | 🟢 Strong · 🔴 live defect | deepening | pr-open | `refactor/polyline-decoder-validity` | [#31](https://github.com/simonsteiner/pyxctsk/pull/31) | no | |
| [C4](#c4--the-solver-refuses-a-route-it-cannot-measure) | The solver refuses a route it cannot measure | 🟢 Strong · 🔴 live defect | deepening | todo | `refactor/unmeasurable-route` | | | builds on C1 |
| [C5](#c5--one-json-writer) | One JSON writer | 🟡 Worth exploring | maintainability | todo | `refactor/one-json-writer` | | | |
| [C6](#c6--one-release-sequence) | One release sequence | 🟡 Worth exploring | maintainability | todo | `refactor/one-release-sequence` | | | |
| [S1](#s1--qr-tasktype-swallows-an-unknown-value) | QR `taskType` swallows an unknown value | — | maintainability | pr-open | rides with C1 (`refactor/wire-scalars`) | [#29](https://github.com/simonsteiner/pyxctsk/pull/29) | yes | |
| [S2](#s2--the-qr-recognizer-decodes-twice-and-is-not-total) | The QR recognizer decodes twice and is not total | — | maintainability | todo | `refactor/smaller-findings-2026-10-02` | | | |
| [S3](#s3--kml-leaks-an-expaterror) | KML leaks an `ExpatError` | — | maintainability | todo | `refactor/smaller-findings-2026-10-02` | | | |
| [S4](#s4--timeofday-raises-two-types-and-wraps-its-message-twice) | `TimeOfDay` raises two types and wraps its message twice | — | maintainability | todo | `refactor/smaller-findings-2026-10-02` | | | |
| [S5](#s5--the-goal-default-is-applied-twice) | The goal default is applied twice | — | maintainability | todo | `refactor/smaller-findings-2026-10-02` | | | |
| [S6](#s6--four-hand-written-format-lists-all-missing-geojson) | Four hand-written format lists, all missing `geojson` | — | maintainability | todo | `refactor/smaller-findings-2026-10-02` | | | |
| [S7](#s7--changelog_extract-stops-at-any---heading) | `changelog_extract` stops at any `## ` heading | — | maintainability | todo | rides with C6 | | | |
| [S8](#s8--task_viewer-guards-an-import-that-cannot-fail) | `task_viewer` guards an import that cannot fail | — | maintainability | todo | `refactor/smaller-findings-2026-10-02` | | | |

Strength: 🟢 Strong · 🟡 Worth exploring · ⚪ Speculative · 🔴 live defect (a bug reproduced during the scan).
Status: `todo` · `in-progress` · `pr-open` · `merged` · `blocked` · `dropped`. `blocked` and `dropped` always carry a reason in Notes.

## Where it hurts

```mermaid
flowchart LR
  W["wire payload"]:::module --> P["parser adapters"]:::module
  P --> SH["model/shape.py · field table"]:::module
  SH -- "scalar unchecked" --> M["Task / QRCodeTask"]:::leak
  P --> PL["qrcode/encoding.decode_nums"]:::shallow
  PL -- "junk → coordinates" --> M
  M --> PLN["distance/plane + solver"]:::leak
  M --> RPT["distance/report"]:::leak
  M --> EXP["export/kml"]:::leak
  classDef module fill:#ffffff,stroke:#64748b,stroke-width:2px,color:#0f172a
  classDef shallow fill:#f1f5f9,stroke:#94a3b8,stroke-dasharray:4 3,color:#334155
  classDef leak fill:#fef2f2,stroke:#dc2626,stroke-width:2px,color:#991b1b
```

Every red module is where a malformed scalar that the field table let through finally fails, as a traceback or a silent wrong number. The 2026-09-27 review made the table refuse a wrong *container*; `6b361c5` then widened one scalar codec by hand, and the same week's churn shows the pattern repeating.

## Since the last review

- `2026-09-27` — all eight candidates and eight smaller findings merged in #22. Candidate 2 (the field table trusted wire types) is extended here by C1, from containers to scalars.

---

## C1 · One owner for a wire scalar

🟢 **Strong** · 🔴 **live defect** · `in-process` · builds on: —

`src/pyxctsk/model/shape.py:62,163-221` · `src/pyxctsk/model/task.py:111-115,174,384,586` · `src/pyxctsk/qrcode/models.py:107,349-362` · `src/pyxctsk/qrcode/task.py:462,472`

```mermaid
flowchart LR
  subgraph before["Before"]
    direction TB
    R1["Value row"]:::module --> I1["IDENTITY · lat, lon, name, version, fa"]:::leak
    R1 --> RI1["ROUNDED_INT · str→float, bool ok"]:::shallow
    R1 --> LI1["LENIENT_INT · str→int, 2.0 refused"]:::shallow
    R1 --> WI1["wire_int_codec · bool refused"]:::shallow
    I1 -- "leak" --> D1["plane.py / report.py / validation.py"]:::leak
    RI1 -- "OverflowError" --> D1
  end
  subgraph after["After"]
    direction TB
    R2["Value row"]:::module --> S2["wire scalars · number, whole metre, integer, coordinate, text"]:::deep
    subgraph absorbed[" "]
      direction TB
      F2["finite"]:::faded
      B2["not a bool"]:::faded
      N2["numeric string"]:::faded
      T2["valid text"]:::faded
    end
    S2 -.- absorbed
  end
  before ~~~ after
  classDef module fill:#ffffff,stroke:#64748b,stroke-width:2px,color:#0f172a
  classDef shallow fill:#f1f5f9,stroke:#94a3b8,stroke-dasharray:4 3,color:#334155
  classDef deep fill:#0f172a,stroke:#0f172a,color:#e2e8f0
  classDef faded fill:#1e293b,stroke:#475569,color:#94a3b8
  classDef leak fill:#fef2f2,stroke:#dc2626,stroke-width:2px,color:#991b1b
  style absorbed fill:#0f172a,stroke:#0f172a
  style before fill:#fafaf9,stroke:#e2e8f0
  style after fill:#fafaf9,stroke:#e2e8f0
```

> [!CAUTION]
> **Live defect:** on a two-turnpoint task, `"radius":"inf"` (or `1e400`) → `OverflowError` traceback from every command; `"lat":"46"` → `TypeError` in `plane.py` from `distances`; `"lat":true` → exit 0, `task_distance_m` 4 996 226 m, the turnpoint read as 1°N; `"name":123` → `ValueError: Unknown format code 's'` from `distances --format text`; `"name":"\ud800"` → `UnicodeEncodeError` from `convert`; full-format `"version":"1"` under `--strict` → `this format defines version 1, the task declares 1`.

| Problem | Solution | Wins |
|---|---|---|
| "A number on the wire" is answered four ways (`IDENTITY`, `ROUNDED_INT`, `LENIENT_INT`, `wire_int_codec`) and "text on the wire" not at all, so a bad scalar parses and fails downstream, and `_READ_ERRORS` is again a list of whichever built-ins leaked (`OverflowError` is missing). | Give `shape.py` one family of scalar codecs that every row reads through, so a bad scalar becomes a `MalformedPayloadError` with its path. | locality: one rule per scalar kind<br>leverage: every row checked<br>downstream modules trust the model<br>`_READ_ERRORS` stops growing |

<details>
<summary>Decisions</summary>

- Q1 — Where does a scalar's rule live, and behind what seam? → as module-level `Codec` values in `model/shape.py` beside `list_codec` and `enum_codec`, raising `MalformedPayloadError`; no new seam, because `Value.read` already sends every value through `codec.from_wire` inside `_read_at`, which attaches the path — `turnpoints[1].radius: expected a finite number, got 'inf'` came out with no change to the traversal.
- Q2 — Which kinds? → `NUMBER`, `WHOLE_METRES`, `INTEGER`, `LATITUDE`, `LONGITUDE`, `TEXT`, because those six cover every scalar `Value` row in both formats (`grep 'Value("'` over `src/`: names and descriptions are text, `lat`/`lon` coordinates, `radius`/`altSmoothed` whole metres, `version`/`V` and the five wire-integer tables integers, `finishAltitude`/`fa` a number); time-of-day and enums already had a single owner each.
- Q3 — Does `Value` keep a pass-through default codec? → no: `codec` is required and `IDENTITY` is deleted, because the ten rows that relied on the default (full: `name`, `lat`, `lon`, `description`, `version`, `finishAltitude`; QR: `fa`, `d`, two `n`) are exactly the ten unchecked scalars behind the card's reproductions.
- Q4 — Is a number spelled as a string accepted, and for which kinds? → for every number kind, written back as a number, and `wire_int_codec`'s `lenient=` flag is deleted, because Burnair's `"radius": "700"` (`tests/model/test_task.py`) and the QR `version`/`e` strings (read by `int(str(...))` before `447e294`) are the real-world precedents, and a per-row flag is the drift being removed. `"lat": "46"` used to parse and raise `TypeError` in `plane.py`; it now reads as 46. "Spelled as a string" means JSON's own number grammar, not Python's `int()`/`float()`, which also read `" 700 "`, `"1_000"` and `"٣"` (Arabic-Indic three) — found in review.
- Q5 — Does `NUMBER` normalize `int` to `float`? → no, JSON's int/float is kept, because the corpus is written back byte-for-byte: `pyxctsk convert` (json, qrcode-json, `-z`) and `distances` (json, text) over all 26 `.xctsk` files under `tests/data/reference_tasks` and the 24 expected QR strings — 178 outputs — are identical to the base branch.
- Q6 — Is a JSON boolean a number? → never, for any kind, because `"lat": true` was read as 1°N and reported a 4 996 226 m task with exit 0, and `ROUNDED_INT` accepted `true` as 1.
- Q7 — What counts as finite? → whatever a float can hold: `NaN`, `Infinity` (which Python's `json` reads) and an integer beyond float range are refused, because `"inf"` and `1e400` escaped as `OverflowError` from every command and `math.isfinite(10**400)` itself raises `OverflowError`.
- Q8 — Are coordinates range-checked at read? → yes, closed `[-90, 90]` and `[-180, 180]`, and the QR `z` row applies the same two codecs to what it decodes, because `"lat": 95` reaches the solver's `assert` (C4's reproduction, whose card says C1 refuses it) and every corpus coordinate is in range (golden outputs identical).
- Q9 — Is `2.0` an integer? → yes, read as `2` and so written back as `2`, because before C1 only `LENIENT_INT` (the QR root `version` and `e`) refused it: the full format's `version` was `IDENTITY` and every other `wire_int_codec` row accepted `2.0` (`2.0 in inverse`), and a producer holding a double writes `1.0`. Found in review of #29, which first refused it. `2.5` is refused.
- Q10 — Is a non-string name coerced to text? → refused, not coerced, because `str(123)` would quietly change the value round-tripped; a lone surrogate is refused because `convert` raised `UnicodeEncodeError` writing it. Control characters stay text here: they are valid JSON and UTF-8, and only KML refuses them (S3).
- Q11 — The full-format `version`? → `INTEGER`, because `"version": "1"` under `--strict` reported `this format defines version 1, the task declares 1`; it now reads as 1 and `version: true` is refused rather than written back as `true`.
- Q12 — S1: what does an unknown QR `taskType` do? → raise `'FOO' is not a valid TaskType`, the full format's wording; `null` stays absent, because all 60 `taskType` values in `tests/data` are `CLASSIC` (`grep -oE '"taskType": ?"[^"]*"'`), so no real input changes, and the value was being lost on re-write.
- Q13 — Does `_READ_ERRORS` change? → no: `OverflowError` is not added, because the scalar codecs raise `MalformedPayloadError` themselves; a sweep of 24 scalar paths × 14 bad values (336 parses, both formats, QR `z` included) shows every input is either refused at read or survives json, qrcode-json, kml, geojson and the distance report.
- Q14 — Dependency category and test surface? → `in-process`; tests at the parser interface (`tests/conformance/test_parser_diagnostics.py`: the card's six reproductions, S1, and the sweep) plus the six rules at the codec interface (`tests/model/test_shape.py`); the `IDENTITY`/`ROUNDED_INT`/`LENIENT_INT` tests are replaced, because those codecs are gone.
- Q15 — One-way door? → no: no key, spelling or default the library writes changes (golden outputs identical); what changes is reading — values that crashed or were silently wrong are refused, and numeric strings in more places are read as numbers. Breaking for the `model.shape` API (three codecs and `lenient=` removed, `Value` needs a codec) and for inputs such as `"name": 123` that `convert` used to pass through.

</details>

---

## C2 · The distance report owns the two-turnpoint minimum

🟢 **Strong** · 🔴 **live defect** · `in-process` · builds on: —

`src/pyxctsk/distance/report.py:43-51,156-170` · `src/pyxctsk/distance/task_distances.py:180-181`

```mermaid
flowchart LR
  subgraph before["Before"]
    direction TB
    FT1["DistanceReport.from_task"]:::module --> G1["guard"]:::shallow
    TD1["task_distances_from"]:::module --> G1b["guard (copy)"]:::shallow
    FM1["DistanceReport.from_measured_task"]:::leak
    G1 --> C1x["DistanceReport(...)"]:::module
    G1b --> C1x
    FM1 -- "no guard" --> C1x
  end
  subgraph after["After"]
    direction TB
    FT2["from_task"]:::module --> C2x["DistanceReport · checks its own minimum"]:::deep
    FM2["from_measured_task"]:::module --> C2x
    TD2["task_distances_from"]:::module --> C2x
  end
  before ~~~ after
  classDef module fill:#ffffff,stroke:#64748b,stroke-width:2px,color:#0f172a
  classDef shallow fill:#f1f5f9,stroke:#94a3b8,stroke-dasharray:4 3,color:#334155
  classDef deep fill:#0f172a,stroke:#0f172a,color:#e2e8f0
  classDef leak fill:#fef2f2,stroke:#dc2626,stroke-width:2px,color:#991b1b
  style before fill:#fafaf9,stroke:#e2e8f0
  style after fill:#fafaf9,stroke:#e2e8f0
```

> [!CAUTION]
> **Live defect:** a one-turnpoint task → `DistanceReport.from_measured_task(MeasuredTask.from_task(t)).task_distance_m` is `0.0`, no error — the answer `report.py:48-51` says the rule's single owner exists to prevent. `DistanceReport.from_task(t)` raises `TooFewTurnpointsError`.

| Problem | Solution | Wins |
|---|---|---|
| The rule documented as having one owner is two copies at two entry points, and the third public entry point has neither. | The report's constructor enforces the minimum; the entry-point copies go. | locality: rule in one place<br>no entry point bypasses it |

<details>
<summary>Decisions</summary>

- Q1 — Does the minimum belong on `DistanceReport` or on `MeasuredTask`? → on `DistanceReport`, because `MeasuredTask` is what `TaskDrawing` measures for `convert --format kml`/`geojson`, and a one-turnpoint task converts to both with exit 0 (`tests/export/test_kml.py::test_task_to_kml_single_turnpoint`, `tests/test_cli.py`'s one-turnpoint format tests, and a manual `convert` of a one-turnpoint file on both branches, byte-identical); `test_a_task_with_no_turnpoints_measures_to_nothing` already pins `MeasuredTask` as total — the pair, not the verdict.
- Q2 — In each constructor classmethod, or in `__post_init__`? → `__post_init__`, because a report has three ways in — `from_task`, `from_measured_task` and the dataclass constructor — and the red test refused in only two of six cases: `from_measured_task` and `DistanceReport(measured=...)`, on zero and one turnpoints, all returned a report with `task_distance_m == 0.0`. Only the constructor is common to all three.
- Q3 — Does `from_task` still check before it measures? → yes, through the same private `_require_distance` that `__post_init__` calls, so the rule keeps one owner. The first version measured and constructed, reasoning that `MeasuredTask.from_task` is total on zero and one turnpoints (Q1); review of #30 found that measuring can still fail first — a one-turnpoint task with `"radius": -5` reported `route point 0 is 5.0 m outside turnpoint 0's cylinder` instead of the minimum. Counting is free, so it comes first, and `pyxctsk distances` on a one-turnpoint file prints the same message with exit 1 on both branches.
- Q4 — `task_distances_from`'s copy of the guard? → deleted, with its imports of `MIN_TURNPOINTS_FOR_DISTANCE`, `TOO_FEW_TURNPOINTS_MESSAGE` and `TooFewTurnpointsError`, because its only path to a table is `DistanceReport.from_measured_task`, which now raises; the comparisons against `MIN_TURNPOINTS_FOR_DISTANCE` in `src/` fall from two (`report.py:156`, `task_distances.py:180`) to one, in `DistanceReport.__post_init__`.
- Q5 — `from_measured_task` is now the constructor spelled differently: delete it? → keep it, because `GoalLine.from_measured_task` and `SpeedSection.from_measured_task` name the same construction in the two sibling modules, it is reachable as `pyxctsk.DistanceReport.from_measured_task`, and deleting it would break the API while removing no concept; it gains the `Raises:` it lacked.
- Q6 — Which tests survive? → `tests/distance/test_report.py::TestTooFewTurnpoints` becomes one test over the three ways in × zero and one turnpoints, plus the two-turnpoint boundary, replacing three `from_task`-only tests; `test_task_distances.py`'s refusal test keeps the two table entry points and drops its `DistanceReport.from_task` case, now pinned in `test_report.py`; `test_measured_task.py` is unchanged, because it pins Q1.
- Q7 — Dependency category? → `in-process`: pure computation over a value, tested at the `DistanceReport` interface.
- Q8 — One-way door, breaking? → neither: `pyxctsk distances` (json, text) and `convert` (json, kml, geojson) over all 26 `.xctsk` files under `tests/data/reference_tasks` — 130 outputs — are byte-identical to `refactor/wire-scalars`; the only behaviour that changes is two entry points refusing what `TooFewTurnpointsError` is documented to refuse, instead of reporting 0.0 m.

</details>

---

## C3 · The polyline decoder owns its own validity

🟢 **Strong** · 🔴 **live defect** · `in-process` · builds on: —

`src/pyxctsk/qrcode/encoding.py:88-116` · `src/pyxctsk/qrcode/models.py:281-305`

```mermaid
flowchart LR
  subgraph before["Before"]
    direction TB
    PC1["_PolylineCoordinates.read · counts 3 or 4"]:::module --> DN1["decode_nums · any char, drops unterminated tail"]:::shallow
    DN1 -- "junk → numbers" --> PC1
  end
  subgraph after["After"]
    direction TB
    PC2["_PolylineCoordinates.read · counts 3 or 4"]:::module --> DN2["decode_nums · alphabet + termination checked"]:::deep
  end
  before ~~~ after
  classDef module fill:#ffffff,stroke:#64748b,stroke-width:2px,color:#0f172a
  classDef shallow fill:#f1f5f9,stroke:#94a3b8,stroke-dasharray:4 3,color:#334155
  classDef deep fill:#0f172a,stroke:#0f172a,color:#e2e8f0
  style before fill:#fafaf9,stroke:#e2e8f0
  style after fill:#fafaf9,stroke:#e2e8f0
```

> [!CAUTION]
> **Live defect:** `XCTSK:{…"t":[{"n":"A","z":"1234"},{"n":"B","z":"_d{r@_fn~Go}@_"}]}` → exit 0; A is lat −0.0001, lon 0.00009, radius −11 (junk read as coordinates in the Gulf of Guinea, which the `from_dict` docstring says the format refuses), and B, whose fourth number was truncated, is read as a radius-0 waypoint.

| Problem | Solution | Wins |
|---|---|---|
| `decode_nums` accepts characters outside the polyline alphabet and silently drops an unterminated final number, so the only check its caller can make — three or four numbers — passes on garbage. | The decoder refuses a character outside 63–126 and an unterminated final number. | locality: encoding rules in the codec<br>no invented coordinates |

<details>
<summary>Decisions</summary>

- Q1 — Does the reproduction still slip through on C1's base? → yes, all of it, because on `refactor/report-owns-minimum` the card's payload parses with exit 0 to A at lat −0.0001, lon 0.00009, radius −11 and B as a radius-0 waypoint: C1's `LATITUDE`/`LONGITUDE`/`WHOLE_METRES` check the decoded numbers' range, and junk decodes to small in-range numbers. A third case surfaced: `"z": ["?", "?", "?"]` was iterated like a string and read as a turnpoint at 0°N 0°E.
- Q2 — Where do the alphabet and termination rules live? → in `decode_nums`, beside `encode_num` in `qrcode/encoding.py`, because that is the only module that knows them (the encoder writes continuation chunks as 95–126 and a final chunk as 63–94, and always ends on a final one), and `_PolylineCoordinates.read`, its only caller (`git grep decode_nums src/`: one call site), can only count; no new seam.
- Q3 — Should the decoder be stricter than XCTrack's? → yes, because the reference `decodeNums` ([GitLab snippet 1927372](https://gitlab.com/xcontest-public/xctrack-public/snippets/1927372), fetched 2026-10-02) has the same two holes — any `char` minus 63 is a chunk, and a trailing `current` is never flushed — while its `encodeNum` writes only `?`–`~` and always terminates, so the checks refuse nothing a conforming producer writes: all 346 `z` strings under `tests/data/reference_tasks` are in the alphabet and terminated.
- Q4 — What does the decoder raise? → `MalformedPayloadError` carrying only the reason, and the field table's `_read_at` adds the path, because that is how C1's scalar codecs raise (C1 Q13) and the result is `t[0].z: '1' at index 0 is not a polyline character (? to ~)`, with no new exception type and `_READ_ERRORS` unchanged.
- Q5 — Is `z`'s wire type checked, and by whom? → by C1's `TEXT` codec before decoding, because it already owns "a string on the wire", and without it a JSON array of one-character strings decoded (Q1) and `"z": 5` leaked `'int' object is not iterable`; both now say `expected a string`.
- Q6 — Are non-canonical encodings refused (`_?` for 0, a zero continuation chunk)? → no, because they decode to one unambiguous number, the reference decoder reads them identically, and refusing them would reject inputs that mean what they say — the card's defect is invented numbers, not redundant chunks.
- Q7 — Does the three-or-four count move into the decoder? → no, it stays in `_PolylineCoordinates.read`, because the decoder reads any number of numbers (the encoder writes three or four depending on the shape), and the count is the field's knowledge of which encoding it is.
- Q8 — Dependency category and test surface? → `in-process`: `decode_nums` at its own interface (`tests/qrcode/test_codec.py::TestThePolylineDecoderOwnsItsValidity`: round trip, the alphabet's edges, out-of-alphabet characters with their index, an unterminated tail) and the card's reproductions at the parser interface (`tests/conformance/test_parser_diagnostics.py::TestAPolylineIsReadOnlyIfItIsOne`); `test_wrong_number_count_raises` survives unchanged, because the count rule did not move. No test is deleted: the decoder had none.
- Q9 — One-way door, breaking? → neither: no key or spelling the library writes changes — `convert` to json, qrcode-json and qrcode-json `-z` over every `.xctsk`, `.txt` and `.png` under `tests/data/reference_tasks` (67 inputs, 201 outputs, all exit 0) is byte-identical to `refactor/report-owns-minimum` — and `decode_nums` keeps its signature; what changes is that strings no encoder writes are refused instead of read as invented coordinates.
- Q10 — Is a number's length bounded? → yes, at seven chunks, the most a 32-bit integer takes (`-(2**31)` and `2**31 - 1` are both seven), because the reference format's numbers are Java `int`s, and an unbounded run of continuation chunks passed the decoder: `"~" * 400` raised `OverflowError` from `nums[0] / 1e5` with a traceback, and 200 000 of them took over a second to read. Found in review of #31.

</details>

---

## C4 · The solver refuses a route it cannot measure

🟢 **Strong** · 🔴 **live defect** · `in-process` · builds on: C1

`src/pyxctsk/distance/solver.py:308-322` · `src/pyxctsk/distance/plane.py`

```mermaid
flowchart LR
  subgraph before["Before"]
    direction TB
    MT1["MeasuredTask.from_task"]:::module --> PL1["LocalPlane projection"]:::module
    PL1 -- "NaN / inf lengths" --> S1x["optimize_plane_route · assert best is not None"]:::leak
  end
  subgraph after["After"]
    direction TB
    MT2["MeasuredTask.from_task"]:::module --> S2x["plane + solver · non-finite → pyXCTSKError"]:::deep
  end
  before ~~~ after
  classDef module fill:#ffffff,stroke:#64748b,stroke-width:2px,color:#0f172a
  classDef deep fill:#0f172a,stroke:#0f172a,color:#e2e8f0
  classDef leak fill:#fef2f2,stroke:#dc2626,stroke-width:2px,color:#991b1b
  style before fill:#fafaf9,stroke:#e2e8f0
  style after fill:#fafaf9,stroke:#e2e8f0
```

> [!CAUTION]
> **Live defect:** two radius-0 turnpoints at (0, 0) and (0, 180) — valid by `Task.validate()` — → bare `AssertionError` from `pyxctsk distances`, `convert --format kml` and `--format geojson`. `"lat":95` reaches the same assert. The comment on it says it cannot fire (`_INITIAL_PLACEMENTS is never empty`).

| Problem | Solution | Wins |
|---|---|---|
| A task the local Transverse Mercator plane cannot represent produces non-finite candidate lengths, and the solver reports it as an assertion about its own placements. | The plane/solver seam refuses a non-finite projection with a library error naming the cause; C1 already refuses out-of-range coordinates at read. | error mode in the interface<br>CLI reports, not traceback |

> [!NOTE]
> ADR 0001: the Ding–Xie–Jiang solver is kept as is; only its failure mode changes.

<details>
<summary>Decisions</summary>

</details>

---

## C5 · One JSON writer

🟡 **Worth exploring** · `in-process` · builds on: —

`src/pyxctsk/renderer.py:63` · `src/pyxctsk/cli.py:269` · `src/pyxctsk/model/task.py:500` · `src/pyxctsk/qrcode/task.py:217` · `src/pyxctsk/model/shape.py` (`load_json`)

```mermaid
flowchart LR
  subgraph before["Before"]
    direction TB
    J1["Task.to_json · ensure_ascii=False"]:::module
    Q1["QRCodeTask.to_json · ensure_ascii=False"]:::module
    G1["renderer geojson · escaped"]:::shallow
    D1["cli distances · escaped"]:::shallow
  end
  subgraph after["After"]
    direction TB
    W2["dump_json beside load_json"]:::deep
    J2["task / QR / geojson / distances"]:::module --> W2
  end
  before ~~~ after
  classDef module fill:#ffffff,stroke:#64748b,stroke-width:2px,color:#0f172a
  classDef shallow fill:#f1f5f9,stroke:#94a3b8,stroke-dasharray:4 3,color:#334155
  classDef deep fill:#0f172a,stroke:#0f172a,color:#e2e8f0
  style before fill:#fafaf9,stroke:#e2e8f0
  style after fill:#fafaf9,stroke:#e2e8f0
```

<!-- `Ch\u00e2teau` is an escape, not a word. cspell:ignore teau -->
Four `json.dumps` call sites choose their own options: a waypoint named `Château` is written as-is by `json` and `qrcode-json`, and as `Ch\u00e2teau` by `geojson` and `distances`.

| Problem | Solution | Wins |
|---|---|---|
| Reading JSON has one owner (`load_json`); writing has four, and the 2026-09-27 fix for non-ASCII reached two of them. | One writer beside the reader; every JSON output goes through it. | locality: output options in one place<br>four outputs agree |

<details>
<summary>Decisions</summary>

</details>

---

## C6 · One release sequence

🟡 **Worth exploring** · `local-substitutable` · builds on: —

`scripts/release.sh:44-71` · `.github/workflows/release.yml:55-86`

```mermaid
flowchart LR
  subgraph before["Before"]
    direction TB
    RS1["release.sh · tag pre-check, roll → bump"]:::module
    RY1["release.yml · bump → roll, no pre-check"]:::leak
  end
  subgraph after["After"]
    direction TB
    RS2["release.sh"]:::module --> ONE["one bump/roll/commit/tag script"]:::deep
    RY2["release.yml"]:::module --> ONE
  end
  before ~~~ after
  classDef module fill:#ffffff,stroke:#64748b,stroke-width:2px,color:#0f172a
  classDef deep fill:#0f172a,stroke:#0f172a,color:#e2e8f0
  classDef leak fill:#fef2f2,stroke:#dc2626,stroke-width:2px,color:#991b1b
  style before fill:#fafaf9,stroke:#e2e8f0
  style after fill:#fafaf9,stroke:#e2e8f0
```

`842eb6e`'s origin-tag pre-check landed in `release.sh` only; the two run roll and bump in opposite orders, and `release.sh` bumps twice (`--dry-run` at `:44`, for real at `:66`) with the tree already dirty between them.

| Problem | Solution | Wins |
|---|---|---|
| The release sequence is written twice and the two copies have already drifted. | Both paths call one script that applies the version it computed once. | locality: a release fix lands once<br>no half-applied tree |

<details>
<summary>Decisions</summary>

</details>

---

## Smaller findings

### S1 · QR `taskType` swallows an unknown value

`src/pyxctsk/qrcode/task.py:352` · rides with C1

`_CompetitionTaskType.read` maps anything but `CLASSIC`/`WAYPOINTS`/`W` to absent, so `XCTSK:{"taskType":"FOO",…}` is re-written as `"taskType":"CLASSIC"` with the value lost, where the full format refuses `'FOO' is not a valid TaskType`. Refuse it the same way.

### S2 · The QR recognizer decodes twice and is not total

`src/pyxctsk/parser.py:197-204` · rides with `refactor/smaller-findings-2026-10-02`

`_qr_url_text` re-decodes `inp.raw` strictly after `Input.of` already found it not UTF-8, so `printf 'XCTSK:\xff' | pyxctsk convert` prints a `UnicodeDecodeError` traceback from a recognizer documented as total. Recognize on the byte prefix and let the reader raise `InvalidFormatError` when `inp.text is None`.

### S3 · KML leaks an `ExpatError`

`src/pyxctsk/export/kml.py:204` · rides with `refactor/smaller-findings-2026-10-02`

A waypoint name holding a control character (`"a\u0001"`, valid JSON) makes `convert --format kml` crash with simplekml's `xml.parsers.expat.ExpatError`, outside the `pyXCTSKError` hierarchy the CLI catches. Characters XML 1.0 cannot carry need handling before the text reaches simplekml.

### S4 · `TimeOfDay` raises two types and wraps its message twice

`src/pyxctsk/model/time_of_day.py:32-36,71` · rides with `refactor/smaller-findings-2026-10-02`

`__post_init__` raises a bare `ValueError` while its parser raises `InvalidTimeOfDayError`, and the latter's message reads `invalid time: 'Invalid time string: 12:00Z'`. One error type, one message prefix.

### S5 · The goal default is applied twice

`src/pyxctsk/distance/measured_task.py:71` · `src/pyxctsk/model/task.py:432-451` · rides with `refactor/smaller-findings-2026-10-02`

`task_to_turnpoints` re-applies `goal.type or GoalType.CYLINDER` after `effective_goal` already guaranteed a type, and `effective_goal`'s docstring names the QR conversion as a user while `qrcode/conversion.py` deliberately reads `task.goal`. Trust the guarantee and correct the docstring.

### S6 · Four hand-written format lists, all missing `geojson`

`README.md:197-202` · `CLAUDE.md:47` · `src/pyxctsk/cli.py:8,182,188` · rides with `refactor/smaller-findings-2026-10-02`

`renderer.OUTPUT_FORMATS` is the one table of formats, yet the README, CLAUDE.md and two `cli.py` docstrings restate the list and each omits `geojson`, which `--help` shows. Point at the table or `--help`, and add `geojson` where a list stays.

### S7 · `changelog_extract` stops at any `## ` heading

`scripts/changelog_extract.py:8-9,43,87` · rides with C6

The docstring says a section runs to the next `## [` heading; the code stops at any `## ` line, so a `## Migration` subsection is cut from the release notes. Match on `## [`.

### S8 · `task_viewer` guards an import that cannot fail

`scripts/task_viewer/api.py:8-20,121,155` · rides with `refactor/smaller-findings-2026-10-02`

`XCTRACK_AVAILABLE` guards importing pyxctsk inside a tool that exists to display it, costs seven `# type: ignore`, and is checked in two of the three routes that need it. Import unconditionally and delete the flag.

## Recommendation

> [!IMPORTANT]
> **Start with [C1 · One owner for a wire scalar](#c1--one-owner-for-a-wire-scalar)** — it removes the most tracebacks and silent wrong numbers, and C4 builds on it.
>
> **Proposed batch** (every 🟢 Strong, in order): C1 → C2 → C3 → C4

## Departures

<!-- filled during implementation: where a PR deliberately differs from this report, and why -->

- **C1 · the QR `z` row reads through the scalar codecs too.** The card names the `Value` rows; the polyline row decodes the same four values the full format reads as `lat`, `lon`, `altSmoothed` and `radius`, so it reads them through `LATITUDE`, `LONGITUDE` and `WHOLE_METRES` rather than keeping a second, absent rule — review found a `z` radius of 10**400 parsed and raised `OverflowError` from `distances`. That touches `qrcode/models.py`'s `_PolylineCoordinates`, which C3 also changes — but only its decoder call, not these checks.
- **C1 · numeric strings are read, not refused.** The CAUTION lists `"lat":"46"` and `"version":"1"` among the failures, which reads as if they should be refused; they are now read as the numbers they spell (Q4, Q11), because the radius already was (Burnair, v0.6.1) and one rule per kind cannot accept the spelling for a radius and refuse it for a latitude. The spelling must be JSON's number grammar.
- **C3 · `z` is read through `TEXT` before it is decoded.** The card names the alphabet and the termination; a JSON array of one-character strings passed both, because iterating it yields characters, and decoded to a turnpoint at 0°N 0°E. Whether `z` is a string is the wire-type rule C1's `TEXT` codec already owns, so `_PolylineCoordinates.read` applies it rather than `decode_nums` growing a second one.
