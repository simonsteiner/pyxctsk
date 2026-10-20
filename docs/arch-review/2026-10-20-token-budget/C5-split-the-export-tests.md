# C5 · Split the export tests; the writers' agreement gets its own file

[← Report](README.md)

🟢 **Strong** · `in-process` · builds on: —

`tests/export/test_common.py:1-709` · `tests/export/test_geojson.py:1-517` · `tests/builders.py`

```mermaid
flowchart LR
  subgraph before["Before"]
    direction TB
    C1n["test_common.py · 7.5k<br>TaskDrawing · outline · palette · KML ⇄ GeoJSON agreement"]:::leak
    G1["test_geojson.py · 5.2k<br>features · route · goal line"]:::leak
  end
  subgraph after["After"]
    direction TB
    C2n["test_common.py · TaskDrawing and outline"]:::module
    P2["palette tests"]:::module
    A2["both writers agree"]:::module
    G2["test_geojson.py · features and route"]:::module
    GL2["GeoJSON goal-line tests"]:::module
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

`TestOnePalette` (`test_common.py:329-709`, ~4.2k tokens) is most of the file's 2,458-token overage. About half of it compares the KML and GeoJSON writers, which neither writer's test file shows.

| Problem | Solution | Wins |
|---|---|---|
| The `TaskDrawing` tests and the writers' agreement tests share one 7.5k file, and the GeoJSON tests are 206 tokens over. | Split `test_common.py` into drawing, palette and agreement files, and split the GeoJSON goal-line tests out of `test_geojson.py`. Move the shared task and drawing helpers out of the files. | locality: agreement tests in one place<br>one helper instead of copies |

- **`_task` (`test_common.py:48`):** a goal-type variant of `tests/builders.py`'s `task()`.
- **`_drawing_of` (`test_geojson.py:51`):** used by both GeoJSON halves.
- **Placement:** decide between `builders.py` and an export conftest from who uses each helper.

<details>
<summary>Decisions</summary>

<!-- filled during implementation, one line each -->

</details>
