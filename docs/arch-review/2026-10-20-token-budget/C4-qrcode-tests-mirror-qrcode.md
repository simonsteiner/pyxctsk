# C4 · `tests/qrcode/` mirrors `qrcode/`

[← Report](README.md)

🟢 **Strong** · `in-process` · builds on: —

`tests/qrcode/test_codec.py:1-865` · `tests/qr_test_utils.py` · `AGENTS.md` (names `tests/qrcode/test_codec.py` in Commands)

```mermaid
flowchart LR
  subgraph before["Before"]
    direction TB
    Q1["test_codec.py · 8.0k<br>tests five qrcode modules"]:::leak
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

`src/pyxctsk/qrcode/` has no `codec.py`. `test_codec.py` (8,003 tokens, 15 commits in 3 months) tests five modules:

| Lines | Tests | Module |
|---|---|---|
| 1–316 | corpus and round-trip | `task.py` |
| 317–558 | field order, spec example and waypoints | `task.py` |
| 559–656 | probe, image reading, missing dependencies | `image.py` |
| 657–806 | nested models and the shape decision | `models.py`, `task.py` |
| 807–865 | polyline decoder | `encoding.py` |

| Problem | Solution | Wins |
|---|---|---|
| One test file, named after no module, tests five `qrcode/` modules and is the largest file in `tests/`. | Give each `qrcode/` module its own test file, as AGENTS.md's "`tests/` mirrors `src/pyxctsk/`" says. Keep the corpus round-trips as one file. | locality: a module's tests beside it<br>restores the mirror convention |

- **Helpers:** `REFERENCE_TASKS` (line 44) and `_normalized` (line 92) move with the tests that use them. `tests/qr_test_utils.py` already holds the image helpers.
- **AGENTS.md:** its Commands example runs `tests/qrcode/test_codec.py`. Keep that path valid or update the example.

<details>
<summary>Decisions</summary>

<!-- filled during implementation, one line each -->

</details>
