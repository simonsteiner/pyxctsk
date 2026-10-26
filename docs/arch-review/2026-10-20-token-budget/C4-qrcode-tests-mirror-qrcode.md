# C4 · `tests/qrcode/` mirrors `qrcode/`

[← Report](README.md)

🟢 **Strong** · `in-process` · builds on: —

`tests/qrcode/test_codec.py:1-865` · `tests/qr_test_utils.py` · `AGENTS.md` (names `tests/qrcode/test_codec.py` in Commands)

```mermaid
flowchart LR
  subgraph before["Before"]
    direction TB
    Q1["test_codec.py · 8.0k<br>tests four qrcode modules"]:::leak
    Q1 --> I1["image.py"]:::module
    Q1 --> M1["models.py"]:::module
    Q1 --> T1["task.py"]:::module
    Q1 --> E1["encoding.py"]:::module
  end
  subgraph after["After"]
    direction TB
    C2n["test_codec.py · corpus round-trips"]:::module
    I2["test_image.py"]:::module
    M2["test_models.py"]:::module
    T2["test_task.py"]:::module
    E2["test_encoding.py"]:::module
  end
  before ~~~ after
  classDef module fill:#ffffff,stroke:#64748b,stroke-width:2px,color:#0f172a
  classDef shallow fill:#f1f5f9,stroke:#94a3b8,stroke-dasharray:4 3,color:#334155
  classDef deep fill:#0f172a,stroke:#0f172a,color:#e2e8f0
  classDef faded fill:#1e293b,stroke:#475569,color:#94a3b8
  classDef leak fill:#fef2f2,stroke:#dc2626,stroke-width:2px,color:#991b1b
  style before fill:#fafaf9,stroke:#e2e8f0
  style after fill:#fafaf9,stroke:#e2e8f0
```

`src/pyxctsk/qrcode/` has no `codec.py`. `test_codec.py` (8,003 tokens, 15 commits in 3 months) tests four modules:

| Lines | Tests | Module |
|---|---|---|
| 1–316 | corpus and round-trip | `task.py` |
| 317–558 | field order, spec example and waypoints | `task.py` |
| 559–656 | probe, image reading, missing dependencies | `image.py` |
| 657–806 | nested models and the shape decision | `models.py`, `task.py` |
| 807–865 | polyline decoder | `encoding.py` |

| Problem | Solution | Wins |
|---|---|---|
| One test file, named after no module, tests four `qrcode/` modules and is the largest file in `tests/`. | Give each `qrcode/` module its own test file, as AGENTS.md's "`tests/` mirrors `src/pyxctsk/`" says. Keep the corpus round-trips as one file. | locality: a module's tests beside it<br>restores the mirror convention |

- **Helpers:** `REFERENCE_TASKS` (line 44) and `_normalized` (line 92) move with the tests that use them. `tests/qr_test_utils.py` already holds the image helpers.
- **AGENTS.md:** its Commands example runs `tests/qrcode/test_codec.py`. Keep that path valid or update the example.

<details>
<summary>Decisions</summary>

<!-- filled during implementation, one line each -->

- Q1 — What does `test_codec.py` measure, and does it test a `qrcode/codec.py`? → 32,011 bytes, about 8,002 tokens, and no `codec.py` exists (`qrcode/` holds `conversion`, `encoding`, `image`, `models`, `task`), because `wc -c` ÷ 4 gives 8,002 and `ls src/pyxctsk/qrcode/` lists those five modules.
- Q2 — Does `test_codec.py` keep its name? → yes, and it becomes the end-to-end round-trips (lines 1–316: the corpus string and image round-trips, `test_roundtrip_basic`, string parsing, image bytes, the no-dependency string path), with its 12-line docstring rewritten to say so, because those ranges measure ≈ 330 + 661 + 1,112 + 152 + 533 ≈ 2.8k, the card's After keeps it, and `AGENTS.md:14`, `docs/setup.md:31` and `tests/qrcode/test_conversion.py:4` name it for exactly those round-trips.
- Q3 — Where do field order, the spec example and the waypoints tests go? → lines 317–558 to a new `tests/qrcode/test_task.py`, because every test there builds `QRCodeTurnpoint`s into a `QRCodeTask` and asserts on `to_string`/`to_dict` (`json.loads` at :366, :398, :449), which `qrcode/task.py` owns; ≈ 553 + 1,456 ≈ 2.0k.
- Q4 — Where do `TestTheShapeIsDecidedOnce` and `TestAnUnreadableSectionIsCarriedNotEaten` go? → lines 707–806 to `test_task.py` too, because both call `QRCodeTask.from_dict`/`to_dict` (:730, :775, :784) and only build `QRCodeTurnpoint`s as input; ≈ 510 + 489, so `test_task.py` lands at ≈ 3.2k with imports, under 3,750.
- Q5 — Where do `TestQRSupportProbe`, `TestReadingAnImage` and `TestWithoutTheOptionalDependencies` go? → lines 559–656 to a new `tests/qrcode/test_image.py` (≈ 1.2k), because they call only `generate_qrcode_image`/`read_qrcode_image` and monkeypatch `qrcode.image.QR_CODE_SUPPORT` (:621–:654), and `zxingcpp` is used nowhere else in the file (:571).
- Q6 — Where does `TestTheNestedModelsAreReachableOnTheirOwn` go? → lines 657–706 to a new `tests/qrcode/test_models.py` (≈ 0.55k), because its four tests import only `QRCodeGoal`, `QRCodeSSS` and `QRCodeTakeoff` from `qrcode.models` (:667–:702).
- Q7 — Where does `TestThePolylineDecoderOwnsItsValidity` go? → lines 807–865 to a new `tests/qrcode/test_encoding.py` (≈ 0.75k), because it calls only `decode_nums`/`encode_num` from `qrcode.encoding` and is the file's only user of `re` (:856).
- Q8 — Does any moved test collide or merge with an existing `tests/qrcode/` file? → no, because `tests/qrcode/` holds only `__init__.py`, `test_codec.py` and `test_conversion.py` (3,876 tokens, untouched), and every test package has an `__init__.py`, so `tests/qrcode/test_task.py` and `tests/model/test_task.py` (or the two `test_codec.py`s) do not clash under pytest.
- Q9 — Do shared fixtures or helpers move? → no new shared helper; `REFERENCE_TASKS` (:44) and `_normalized` (:92) stay in `test_codec.py`, and each file imports from `tests/qr_test_utils.py` only what it uses, because `grep` finds `REFERENCE_TASKS` only at :47/:64, `_normalized` only at :80, `decode_qr`/`Image` only inside 1–316, and `zxingcpp` only at :571.
- Q10 — Does the function-local `from pyxctsk.model.shape import NUMBER, OPTIONAL, Value` (:802) stay valid in `test_task.py`, and does it need an `EXPECTED_DEFERRED_IMPORTS` entry? → it moves verbatim and needs none, because `shape.py:59` re-exports `NUMBER` (C2 Q4) and defines `OPTIONAL` (:109) and `Value` (:177), and `test_deferred_imports_are_the_known_cycle_breakers` scans only `SRC` (`tests/test_layering.py:144`); the other function-local imports (:621–:702) move the same way.
- Q11 — Does the split change `tests/corpus.py` or `tests/paths.py`? → no, because `reference_tasks()` is imported only by `test_codec.py` (:39), which keeps every user of it, and no test in the file uses `tests/paths.py`.
- Q12 — Which docs change? → none outside the report, because `AGENTS.md:14`, `docs/setup.md:31` and `test_conversion.py:4` name `test_codec.py` for the round-trips it keeps, and the mentions in `tests/conftest.py:11`, `tests/corpus.py:10` and `tests/model/test_shape.py:7` are history or point at `tests/model/test_codec.py`; the CHANGELOG gets no entry, because no user-visible behaviour changes.
- Q13 — Which files does the Build touch, and are any over 5,000 tokens today? → edited: `tests/qrcode/test_codec.py` (8,002 → ≈ 2.9k, this card's split); created: `tests/qrcode/test_task.py` ≈ 3.2k, `test_image.py` ≈ 1.2k, `test_models.py` ≈ 0.6k, `test_encoding.py` ≈ 0.8k; plus the report (`README.md` ≈ 2.7k, this card ≈ 1.9k); because those are `wc -c` ÷ 4 of the line ranges plus their imports, and no other file is touched.
- Q14 — How is behaviour shown to be preserved? → the collected test IDs before and after match one for one apart from the module path, and `pytest tests/qrcode`, `ruff` and strict `mypy` pass, because the split moves tests verbatim and only `ruff --fix` may drop imports a file no longer uses.

</details>
