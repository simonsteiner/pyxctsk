# C7 · Split the three oversized `scripts/` utilities

[← Report](README.md)

🟡 **Worth exploring** · `in-process` · builds on: —

`scripts/xcontest_xctsk_tool.py:1-705` · `scripts/extract_task_data.py:1-622` · `scripts/task_viewer/templates/compare_view.html:1-564` · rides along: [S2](README.md#s2--a-process-branch-that-never-runs)

```mermaid
flowchart LR
  subgraph before["Before"]
    direction TB
    X1["xcontest_xctsk_tool.py · 6.0k<br>HTTP client · batch loops · main()"]:::leak
    E1["extract_task_data.py · 5.6k<br>one TaskDataExtractor class"]:::leak
    V1["compare_view.html · 5.6k<br>style · markup · inline script"]:::leak
  end
  subgraph after["After"]
    direction TB
    X2["xcontest_xctsk_tool.py · main()"]:::module --> XC2["XContest client and batch loops"]:::module
    E2["extract_task_data.py · orchestration"]:::module --> EP2["HTML → task data parsing"]:::module
    V2["compare_view.html · markup"]:::module --> VJ2["static compare_view.js / .css"]:::module
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

None of the three files has had a commit in 3 months, and the published wheel ships none of them. They block only the commit that next touches them.

| Problem | Solution | Wins |
|---|---|---|
| Three repository utilities can't be edited without a split first. | Split each along its seam: the XContest HTTP client from the CLI, the HTML parsing from the extractor's orchestration, and the viewer's inline script and style into `static/`. Every entry point stays where it is. | locality: HTTP apart from argparse<br>S2: dead branch gone |

- **The template:** it has only two Jinja expressions in its script (lines 373–374). `geojson_debug_view.html:284-287` already passes data in a `<script type="application/json">` block.
- **Docs:** `scripts/README.md` and `scripts/task_viewer/README.md` list these files.

<details>
<summary>Decisions</summary>

<!-- filled during implementation, one line each -->

</details>
