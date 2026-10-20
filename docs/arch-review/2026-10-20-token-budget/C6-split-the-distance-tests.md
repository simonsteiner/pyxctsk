# C6 · Split the XCTrack accuracy tests

[← Report](README.md)

🟢 **Strong** · `in-process` · builds on: —

`tests/distance/test_xctrack_accuracy.py:1-457` · rides along: [S1](README.md#s1--two-identical-_race_task-builders) (`tests/distance/test_center_distance.py:23`, `tests/distance/test_measured_task.py:38`)

```mermaid
flowchart LR
  subgraph before["Before"]
    direction TB
    X1["test_xctrack_accuracy.py · 5.1k<br>reference · one solver · crossing · goal line · convergence · earth model"]:::leak
    R1["_race_task × 2, identical"]:::shallow
  end
  subgraph after["After"]
    direction TB
    X2["test_xctrack_accuracy.py · reference and one solver"]:::module
    G2["crossing, goal-line and convergence cases"]:::module
    E2["earth-model tests"]:::module
    R2["builders.py · one race task"]:::module
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

The file is 71 tokens over the budget and was touched in 14 commits in 3 months. It holds seven test classes:

| Lines | Classes |
|---|---|
| 70 | `TestReferenceAccuracy` |
| 152 | `TestOneSolverOneProjection` |
| 251 | `TestCrossingCase` |
| 325 | `TestGoalLine` |
| 358 | `TestConvergence` |
| 373–457 | `TestEarthModel`, `TestTheEarthModelSelector` |

| Problem | Solution | Wins |
|---|---|---|
| The reference-accuracy tests also carry geometry edge cases and the earth-model selector, which change for different reasons. | Split by what each class pins: the reference corpus, geometry cases, and earth model. Move the module constants to where every file can reach them. | locality: earth-model tests together<br>S1: one race task builder |

- **Constants:** `WITH_REFERENCE`, `CONVERGENCE_SAMPLE` and `REF_QUANTIZATION_M` must be reachable from every file that uses them.

<details>
<summary>Decisions</summary>

<!-- filled during implementation, one line each -->

</details>
