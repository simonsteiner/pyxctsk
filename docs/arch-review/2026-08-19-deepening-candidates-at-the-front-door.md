# 2026-08-19 — Deepening candidates at the front door

Reviewed at `8d4ce8d`, the merge of the pre-release code-quality review, on a suite of
**995 passing tests, 18 skipped, 98 % line coverage**, with `ruff` and `mypy src/ tests/`
green. Companion visual report:
[`2026-08-19-deepening-candidates-at-the-front-door.html`](2026-08-19-deepening-candidates-at-the-front-door.html).

Written in the deep-module vocabulary — **module, interface, implementation, depth, seam,
adapter, leverage, locality** — and in the domain vocabulary of
[`../../CONTEXT.md`](../../CONTEXT.md). Nothing recorded as applied by the
[2026-08-17](2026-08-17-deepening-candidates.md),
[2026-08-18](2026-08-18-deepening-candidates-after-s7f.md) or
[2026-08-19](2026-08-19-pre-release-code-quality-review.md) reviews is re-reported; every
claim below was re-verified against the source at this commit, and every claim about
behaviour was reproduced by running the library.

---

## The signal behind most of what follows

The last three reviews drove the friction *inward*. `distance/` was split into eleven
focused modules, the field tables were unified, the LINE rule got one owner, the measured
task became a value. The residue is no longer inside a module — **it is at the two seams
where the library meets the outside world, and at the one seam between its two formats.**

Three counts say it:

| | 2026-08-17 | 2026-08-18 | 2026-08-19 (today) |
|---|---|---|---|
| names in `distance.__all__` | 13 | 22 | **29** |
| names in `pyxctsk.__all__` | — | — | **52** |
| adapters with a recognition question | 0 of 4 | 0 of 4 | **0 of 4** |

The interface of `distance/` has more than doubled in three days while its implementation
was being *narrowed*. That is the shape of a package absorbing every new S7F number as a
new name rather than behind an existing one — and the front door has mirrored it, at 52.

The two live defects below both sit exactly there: at the parser's adapter seam (A) and at
the model↔QR format seam (B). Neither is inside a module any review has been looking at.

Reproduce the framing numbers:

```bash
python - <<'EOF'
import ast, subprocess
for commit in subprocess.run(
    ["git","log","--format=%h","--reverse","--","src/pyxctsk/distance/__init__.py"],
    capture_output=True, text=True).stdout.split():
    src = subprocess.run(["git","show",f"{commit}:src/pyxctsk/distance/__init__.py"],
                         capture_output=True, text=True).stdout
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", "") == "__all__" for t in node.targets):
            print(commit, len(node.value.elts)); break
EOF
```

---

## A. The parser's adapters have no recognition question — **Strong**

**Files:** `src/pyxctsk/parser.py`

`parser.py`'s module docstring states the interface its four adapters are supposed to
present (`parser.py:12-16`):

> The auto-detection works by trying an ordered list of focused format adapters (one per
> supported format). **Each adapter answers two questions independently: does the input
> *look like* my format, and can I parse it?** This keeps every format's recognition and
> parsing logic in one place and makes each adapter testable in isolation.

There is no recognition question. Each adapter is one function returning `Arrived | None`
(`parser.py:143, 163, 173, 183`), and "not my format" is expressed only by returning
`None` — which is indistinguishable from "is my format but malformed", except in
`_parse_xctsk_url`, which raises instead (`:158`). So the four adapters do not even share
one failure convention, and none of them can be asked whether an input is theirs.

Three consequences, all reproduced at this commit.

### A1 — the QR-JSON adapter accepts *any* JSON object

```python
>>> from pyxctsk.parser import _parse_qrcode_json
>>> _parse_qrcode_json('{}', b'')
QRCodeTask(...)
>>> _parse_qrcode_json('{"hello":"world"}', b'')
QRCodeTask(...)
```

It has no predicate at all — it is a total function on JSON objects. Every full-format
`.xctsk` document in the reference corpus is therefore also a valid input to it:

```python
>>> text = open('tests/data/reference_tasks/xctsk/task_bevo.xctsk').read()
>>> q = _parse_qrcode_json(text, b'')
>>> len(q.turnpoints), sorted(q.unknown)
(0, ['earthModel', 'goal', 'sss', 'turnpoints'])
>>> [str(i) for i in q.validate()]
['task has no turnpoints']
```

A ten-turnpoint competition task reads as a task with **zero** turnpoints, its entire
content parked in `unknown`. The only thing preventing that is `_parse_task_json` sitting
one line earlier in `_FORMAT_PARSERS` (`parser.py:218-223`). The comment above the tuple
gives the wrong reason — *"Order matters: more specific / cheaper formats come first"* —
because this is neither specificity nor cost: it is one adapter answering "yes" to input
that is not its format. Nothing in `tests/` asserts the order or the mutual exclusivity.

### A2 — junk input escapes as a bare `TypeError`

```console
$ echo -n '[]' | pyxctsk convert
Traceback (most recent call last):
  ...
  File ".../model/shape.py", line 217, in read
    return {self.attr: self.codec.from_wire(data[self.key])}
TypeError: list indices must be integers or slices, not str
```

`_PARSE_ERRORS` (`parser.py:54`) lists `JSONDecodeError, ValueError, KeyError,
UnicodeDecodeError`. A JSON array, `null` or a bare string produces `TypeError`, which is
not in it, so it passes through `parse_task` and past `cli.py:201`'s
`except (pyXCTSKError, OSError)` as a traceback. Same for `null` and `"x"`.

### A3 — the error path re-derives every adapter's predicate, outside the adapters

`_unrecognized` (`parser.py:100-130`) is a chain of ifs that restates the recognition
each adapter should own: image magic bytes (`:119`, against `_IMAGE_MAGIC:76`), JSON shape
(`:128`), path failure (`:117`). It exists to name *which* failure occurred — and for the
two commonest wrong inputs it never runs. A JSON object never reaches it (A1 accepts it),
and a JSON array crashes before it (A2). Its `"looks like JSON, but it is not a task in
any format"` branch is unreachable for any object.

The net effect at the front door:

```console
$ echo -n '{"hello":"world"}' | pyxctsk convert
{"taskType":"CLASSIC","version":1,"turnpoints":[],"hello":"world"}
$ echo $?
0
```

The library invents a task type, a version and an empty turnpoint list for input that is
not a task in any format, and exits 0.

**Deepening.** Give the adapter the interface the docstring already describes: a value with
two members, `recognizes(text, raw) -> bool` and `parse(text, raw) -> Arrived`, one per
format, in the same tuple. Then `_unrecognized` *asks the adapters* which one recognized
the input and failed, instead of re-deriving four predicates; the order stops being
load-bearing because at most one adapter claims an input; and each adapter becomes testable
in isolation, which its docstring says is already true and which no test does.

**Deletion test:** deleting `_unrecognized` after that change concentrates its three
branches into the three adapters that own them. Deleting it today just moves them.

**Wins.** Locality: "is this my format" lives with the format. Leverage: adding a fifth
format is one tuple entry, not a tuple entry plus a branch in a function that runs only
when everything failed. The interface becomes the test surface — today no test names
`_FORMAT_PARSERS`, `_parse_task_json`, `_parse_qrcode_json`, `_parse_qrcode_image`,
`_unrecognized` or `Arrived`.

---

## B. The QR shape is chosen twice, on two different inputs — **Strong**

**Files:** `src/pyxctsk/qrcode/task.py`

The QR format has two serializable shapes, competition and XC/Waypoints, and
`QRCodeTask` picks between them twice:

- reading, on the payload's keys — `from_dict` dispatches on `"T" in data`
  (`qrcode/task.py:202`);
- writing, on the object's task type — `to_dict` dispatches on `self.task_type`
  (`:177` → `_shape_for`).

`_CompetitionTaskType.read` (`:394-401`) is the one row that can put the two into
disagreement. It reads the competition shape's `taskType` leniently, accepting `"W"` and
`"WAYPOINTS"` for old payloads, and its own docstring states the invariant it thereby
breaks: *"`CLASSIC` is the only value the competition shape defines — a WAYPOINTS task is
the **other** shape."*

Reproduced:

```python
>>> raw = {"g":{"d":"22:00:00Z","t":2}, "t":[{"n":"A","z":"b`dpMgc{YgsB_X"}],
...        "taskType":"W", "tc":None, "to":None, "version":2, "e":1}
>>> q = QRCodeTask.from_dict(raw)            # read in the competition shape
>>> q.goal, q.earth_model
(QRCodeGoal(deadline=TimeOfDay(22,0,0), type=CYLINDER, ...), 1)
>>> json.dumps(q.to_dict(), sort_keys=True)  # written in the waypoints shape
'{"T":"W","V":2,"t":[{"n":"A","z":"b`dpMgc{YgsB"}]}'
```

One round trip drops the goal, the deadline, the earth model, both takeoff times and the
turnpoint's radius — the `z` string is shortened from four numbers to three. Nothing in
`tests/` feeds `taskType: "W"` to the competition shape.

**The same seam has a second hole.** `_A_DICT_OR_NOTHING` (`qrcode/task.py:448-455`)
documents itself as preserving what it cannot read:

> A value of the wrong shape is not read rather than raising: **it lands in `unknown` and
> travels back out untouched**, which is what this library does with anything it cannot
> interpret.

It cannot. `g` is declared by its own row, so it is in `QR_TASK_SHAPE.keys`, and
`read_passthrough` (`passthrough.py:53`) excludes every declared key from `unknown` by
construction:

```python
>>> q = QRCodeTask.from_dict({"taskType":"CLASSIC","version":2,"t":[],
...                           "g":"nonsense","s":123,"tc":None,"to":None})
>>> q.goal, q.sss, q.unknown
(None, None, {})
>>> json.dumps(q.to_dict(), sort_keys=True)
'{"taskType":"CLASSIC","tc":null,"to":null,"version":2}'
```

Both `g` and `s` are gone. `Optionality.absent` and the passthrough allow-list are two
independent decisions that must agree, and nothing connects them: a row that declares a key
but declines to read its value is a third state neither `keys` nor `absent` accounts for.
`Optionality`'s docstring (`shape.py:122-126`) claims to have unified exactly this pair.

**Deepening.** The shape is a property of the payload, decided once when it is read and
read again when it is written — not re-derived from `task_type`. Either carry the shape on
the value, or make `_CompetitionTaskType.read` refuse the spelling it cannot round-trip.
And declare the third state: a row that declares a key it may decline to read must say so,
so `read_passthrough` can carry the value instead of eating it.

**Wins.** Locality: one decision about which shape a payload is. Leverage: the round-trip
property test that cannot currently be written — `from_dict(d).to_dict()` preserves every
key `d` had — becomes writable and covers both holes.

---

## C. The model↔QR crossing is the last hand-written field mirror — **Strong (largest scope)**

**Files:** `src/pyxctsk/qrcode/conversion.py:127-192`, `:213-275`; `model/shape.py`

`shape.py:8-13` states what the field table exists to abolish:

> What this replaces is a hand-written `to_dict` sitting beside a hand-written `from_dict`,
> with nothing making the two agree. Adding one turnpoint-level spec field meant **twelve
> edits across four files** and the type checker enforced none of them.

That is now true of the model↔**wire** seam. It is still exactly the situation at the
model↔**model** seam. `task_to_qr_code_task` and `qr_code_task_to_task` are two
hand-written field-by-field constructors of ~65 lines each, with nothing making them agree.

Adding one spec field to the goal today is **six** edits in four files, none of them linked:

| # | file | edit |
|---|---|---|
| 1 | `model/task.py:323-326` | `Goal` dataclass field |
| 2 | `model/task.py:374-382` | `GOAL_SHAPE` row |
| 3 | `qrcode/models.py:60-63` | `QRCodeGoal` dataclass field |
| 4 | `qrcode/models.py:84-91` | `QR_GOAL_SHAPE` row |
| 5 | `qrcode/conversion.py:175-180` | out-bound constructor |
| 6 | `qrcode/conversion.py:258-263` | in-bound constructor |

Miss #5 or #6 and mypy is silent, the corpus is silent (no reference task carries the new
key), and the field vanishes on every QR round trip. Rows 1–4 have a structural guard —
`tests/model/test_shape.py:358-378` pairs each table against its dataclass. Rows 5–6 have
none. The only checks pairing the two families are per-field and remembered one at a time
(`tests/conformance/test_spec_conformance.py:147, 156`, for `finish_altitude` alone).

Today three of the four class pairs are exactly parallel; nothing keeps them that way:

```
Goal      only: []              QRCodeGoal      only: []
SSS       only: ['time_close']  QRCodeSSS       only: []
Takeoff   only: ['unknown']     QRCodeTakeoff   only: []
Turnpoint only: ['waypoint']    QRCodeTurnpoint only: [alt_smoothed, description, lat, lon, name]
```

**Deepening.** Conversion is hand-written for a real reason recorded in `CLAUDE.md`
(`Turnpoint` nests a `Waypoint` where `QRCodeTurnpoint` is flat, so there is no attribute
copy to derive) — so the cheap move is not a table but a **guard**: a test asserting the two
dataclasses' field sets stay in the documented relation, in the shape
`test_shape.py:358-378` already has for the wire seam. The expensive move is a declared
crossing for the three flat pairs, leaving the turnpoint hand-written.

**Wins.** Locality: the drift is caught where it happens rather than in a corpus that does
not carry the field. Leverage: one guard covers every future spec field on the three
parallel shapes.

---

## D. The drawing answers for turnpoints, not for the goal line or the route — **Strong**

**Files:** `src/pyxctsk/export/common.py`, `export/kml.py`, `export/geojson.py`

`TaskDrawing` absorbed the per-turnpoint questions — `color_of:112`, `label_of:133`,
`description_of:150`, `role_of:174` — and `tests/export/test_common.py:373-440` pins them
cross-format. The other half of the drawing was never finished. Six rendering decisions are
still made once per writer:

| decision | KML | GeoJSON |
|---|---|---|
| unpack + discard the azimuth | `kml.py:141` | `geojson.py:117` (byte-identical) |
| the goal line's name | `kml.py:146` `"Goal Line"` | `geojson.py:129` `"Goal Line"` |
| `f"Goal line length: {…:.0f}m"` | `kml.py:147` | `geojson.py:132` (byte-identical) |
| the control zone's name | `kml.py:161` | `geojson.py:153` |
| **control-zone radius = length / 2** | `kml.py:162` | `geojson.py:141` |
| `f"Goal control zone radius: {…:.0f}m"` | `kml.py:162` | `geojson.py:156` (byte-identical) |

The fifth row is the one that matters: *"the control zone's radius is half the goal line"*
is geometry, already owned by `GoalLine.control_zone` (`goal_line.py:331-336`, which passes
`self.length / 2`), and both writers restate it to render a caption. One rule, three places.

**And the two formats already disagree about a user-visible name for the same thing:**

```
kml.py:114      name="Course Line"
geojson.py:91   "name": "Optimized Route"
```

Both are pinned, in different files, by tests that each know only their own format —
`tests/export/test_kml.py:82` asserts `"Course Line" in kml_result`;
`tests/export/test_geojson.py:173` asserts `props["name"] == "Optimized Route"`. The suite
*enforces* the divergence. This is precisely the shape of the defect the 2026-08-18 review
found and fixed for turnpoints (KML shipping `Type: TurnpointType.TAKEOFF` into map text,
"with a test pinning it as expected") — the fix was applied to one of the drawing's three
subjects.

`tests/export/test_common.py:413` has
`test_both_writers_describe_the_same_turnpoint_the_same_way`. The equivalent test for the
goal line cannot be written today, because there is no accessor on the drawing to compare
against.

**Deepening.** The four sibling methods the applied ones imply: `goal_line_label()`,
`goal_line_description()`, `control_zone_radius`, `control_zone_description()` — and one
name for the route, whichever the two formats should have agreed on. A question both
writers must answer identically is a method on the drawing, which is the rule
`export/common.py`'s own docstring states.

**Wins.** Locality: six duplicated decisions become four accessors. Leverage: the
cross-format test that exists for turnpoints extends to the goal line and the route.
Interface shrinks; the drawing absorbs the captions.

---

## E. Two write-only fields the interface still declares — **Strong**

**Files:** `src/pyxctsk/distance/turnpoint.py:118`,
`src/pyxctsk/distance/route_optimization.py:103`

`TurnpointGeometry`'s docstring (`turnpoint.py:41-47`) convicts both:

> `goal_type` has since gone the other way: it was declared here because `plane_circle` read
> it to collapse a LINE goal to a zero-radius circle, but that rule belongs to — and is now
> applied only by — `task_to_turnpoints`. […] **an interface declaring a value nothing reads
> misleads a caller just as an interface omitting one does.**

Finding 3 of the 2026-08-19 review removed `goal_type` from the protocol and from
`plane_circle`, and left it on the concrete class:

- **`TaskTurnpoint.goal_type`** — written at `measured_task.py:78`, stored at
  `turnpoint.py:118`, carrying a 5-line attribute docstring. **Zero reads in `src/`.** The
  only reads in the repo are three assertions in
  `tests/distance/test_xctrack_accuracy.py:225, 240, 338` that exist *because* the field
  exists. The fact it encodes ("this turnpoint is a LINE goal") is already carried
  losslessly by `radius == 0`, which is what `center_distance._goal_radius` reads.

- **`OptimizedRoute.earth_model`** — set at `route_optimization.py:434, 455`, documented at
  `:97-98` as *"The model the legs were measured on"*. **Zero reads in `src/`, `tests/` or
  `scripts/`.** Every consumer goes back to `task.earth_model` instead (`report.py:147`,
  `goal_line.py:293`, `center_distance.py:140`).

This is verbatim the pattern `distance/__init__.py:48-51` records as already retired
("the `TaskTurnpoint.goal_line_length` attribute that carried it turned out to be **written
and never read**"). It survived twice more in the same package.

The cost is not only the field. `TaskTurnpoint`'s constructor takes four parameters where
its interface (`TurnpointGeometry`) declares three attributes, and
`tests/distance/test_route_optimization.py:41-44` has to explain in prose why the fake
*omits* one of them. And because nothing consults `OptimizedRoute.earth_model`,
`tests/export/test_geojson.py:34-36` builds routes with the default `None` attached to
tasks that may declare `FAI_SPHERE`, and no test can detect the mismatch.

**Deletion test: passes cleanly on both.** Delete them and complexity vanishes; only the
three assertions written because the field is there go with them.

**Wins.** Interface shrinks to what the implementation reads, in both directions — which is
the property `TurnpointGeometry`'s docstring claims for itself.

---

## F. `optimal_point` is a second optimizer nobody ships — **Worth exploring**

**Files:** `src/pyxctsk/distance/turnpoint.py:121-160`

`grep` across `src/` returns **no caller**. Its only invocations are in
`tests/distance/test_xctrack_accuracy.py:174, 195, 196, 227, 260, 273, 340` and
`test_route_optimization.py:475, 487`.

`plane.py:146-153` narrates the bug this method caused and the fix that was applied:

> the route optimizer projected onto the task area, while `TaskTurnpoint.optimal_point`
> projected onto a plane centred on *that turnpoint*. Same paragraph of the spec, two
> different answers, and **the tests aimed at the one the product does not use — so a
> crossing-case fix could go green and ship nothing.**

The fix made the plane an argument. The method is still a second implementation of the same
four-step pipeline `route_optimization._corrected_path` runs, and the two do not spell it
the same way:

| step | `optimal_point` | `_corrected_path` |
|---|---|---|
| project | `plane_circle(self, plane)` `turnpoint.py:149` | `plane_circle(tp, plane)` `route_optimization.py:376` |
| zero-radius rule | `if radius == 0.0` `:150` | `if i == 0 or radius <= 0.0` `:383` |
| solve | `plane_optimal_point(...)` `:153` | `_optimize_plane_points(...)` `:377` |
| snap | against `self.radius` `:158-160` | against the *projected* radius `:391-393` |

A change to snapping policy has to be made twice. **And the tests have not followed the fix
through:** `test_xctrack_accuracy.py:246-266` and `:268-280` — the two crossing-case tests —
call `tp.optimal_point(prev, next)` *with no plane*, i.e. through the per-turnpoint
projection that no shipped code path builds. `TestOneSolverOneProjection` (`:152-205`)
exists in the same file to say those two projections are different answers.

The real bug surface — `_corrected_path` inside two nested loops in
`calculate_iteratively_refined_route` — is covered only by whole-corpus totals.

**Deletion test: passes.** Delete `optimal_point` and re-point those tests at
`calculate_iteratively_refined_route`, or at `solver.plane_optimal_point` +
`earth.snap_to_boundary` directly. The pipeline concentrates in one place, and the crossing
tests start testing the code that ships.

**Wins.** Locality: one pipeline, one place a snapping change is made. The interface becomes
the test surface — today the tests reach past it to a path the product does not run.

---

## G. One library, two error hierarchies — **Worth exploring**

**Files:** `src/pyxctsk/exceptions.py`, `src/pyxctsk/distance/report.py:82`,
`src/pyxctsk/__init__.py:53-59`, `src/pyxctsk/cli.py:201, 276`

Three related gaps in the error interface:

1. **`TooFewTurnpointsError(ValueError)`** (`distance/report.py:82`) is the one library
   error outside `pyXCTSKError`. `MissingQRCodeSupportError` (`exceptions.py:64-77`)
   documents why the base is load-bearing — *"`pyXCTSKError` puts it in this library's
   hierarchy, so the CLI's `except (pyXCTSKError, OSError)` reports it as a user-facing
   error rather than letting a traceback out"* — and the error added one review later
   breaks the rule. The CLI pays for it directly, in two commands with two catch tuples:

   ```python
   cli.py:201  except (pyXCTSKError, OSError) as e:                       # convert
   cli.py:276  except (pyXCTSKError, OSError, TooFewTurnpointsError) as e: # distances
   ```

   Adding a sixth library error today means editing `cli.py`. That is the library's
   exception hierarchy transcribed by hand into a command-layer module.

2. **`pyXCTSKError` — the one name a caller writes in `except` — is not exported.** The
   front door imports five of its subclasses and no base (`__init__.py:53-59`). The suite
   already reaches past it (`tests/test_cli.py:21`:
   `from pyxctsk.exceptions import pyXCTSKError`), which is exactly the pattern
   `tests/test_layering.py:376-405` was written to catch — and it cannot, because
   `pyXCTSKError` is not in its `DOCUMENTED` tuple.

3. **Two answers to "what version is this library".** `__init__.py:101` sets
   `__version__ = version("pyxctsk")`, commented *"Single source of truth"*, with zero
   readers anywhere. `distance/report.py:70-79` has `pyxctsk_version()`, which handles the
   editable/source-run case `__init__.py:101` would raise on. `pyxctsk --version` is served
   by the second one, reached from `cli.py:25` by a private-path import into
   `distance.report` — a general "what version am I" utility parked in the S7F report
   module, and the only reason `cli.py` has an import edge into `distance.report` at all.

**Deepening.** `TooFewTurnpointsError` moves to `exceptions.py` under `pyXCTSKError` (it
can: `exceptions` is a leaf, importable from anywhere); `pyXCTSKError` joins `__all__` and
`DOCUMENTED`; `pyxctsk_version` moves beside `__version__` at the front door, or
`__version__` is deleted for it.

**Wins.** Leverage: one `except pyXCTSKError` catches everything the library raises.
Locality: `exceptions.py` becomes the answer to "what can pyxctsk raise" — today it is 5
of 6. The CLI's two catch tuples become one, and stop needing to be edited when the library
grows an error.

---

## H. Rendering has no seam — **Worth exploring**

**Files:** `src/pyxctsk/cli.py:188-199`, `src/pyxctsk/__init__.py:84-85`,
`scripts/task_viewer/api.py`

Reading is one deep front door: `parse_task` detects and dispatches, and a caller learns one
name. Writing has no counterpart. A task goes out five different ways —
`Task.to_json()`, `task.to_qr_code_task().to_string(compressed=…)`, `task_to_kml(task)`,
`generate_task_geojson(task)`, `generate_qrcode_image(qr_string).save(buf, "PNG")` — and the
mapping *format name → renderer* exists in exactly one place: an if/elif chain in the CLI.

```python
cli.py:188  if   output_format == "json":        ... task.to_json()
cli.py:190  elif output_format == "kml":         ... task_to_kml(task)
cli.py:192  elif output_format == "qrcode-json": qr_string = task.to_qr_code_task().to_string(compressed=compressed)
cli.py:195  elif output_format == "png":         qr_string = task.to_qr_code_task().to_string(compressed=compressed)
```

Three things about that chain: there is **no `else`** — an unmatched format writes nothing
and exits 0, prevented only by `click.Choice`; line `:193` and line `:196` are the same
expression; and `export/common.py:255-265` argues the opposite policy for the palette
(*"spelled out rather than defaulted… a lookup with a default is what the old KML writer
had, and it meant a palette entry it did not know about rendered as an ordinary turnpoint
with nothing failing"*), enforced as total over the enum by
`tests/export/test_common.py:321-340`. The format table gets neither treatment.

**Two adapters, so the seam is real.** `scripts/task_viewer/api.py` is the second consumer
and re-spells two of the four: the six-line PNG incantation at `:70-101`
(parse → `to_qr_code_task` → `to_string` → `generate_qrcode_image` → `BytesIO` → `save`)
and KML at `:145-150`, each with its own MIME type
(`image/png`, `application/vnd.google-earth.kml+xml`) and its own filename convention.

Meanwhile the front door publishes two constants for exactly this job that nothing reads:

```python
__init__.py:84  EXTENSION = ".xctsk"     # zero references outside __all__
__init__.py:85  MIME_TYPE = "application/xctsk"  # zero references outside __all__
```

and `parser.py:51` spells its own extension list (`_FILE_EXTENSIONS`) independently.

**Deepening.** One rendering table beside `_FORMAT_PARSERS`: format name → renderer, MIME
type, binary-or-text, file extension. `render_task(task, "png") -> bytes` is then the
writing counterpart to `parse_task`, the CLI's chain becomes a lookup, the viewer stops
re-deriving it, and `MIME_TYPE`/`EXTENSION` either become rows or get deleted.

**Deletion test:** deleting the chain concentrates four format decisions in one table that
two consumers read. Deleting `EXTENSION` and `MIME_TYPE` today removes two published names
nothing uses.

**Wins.** Leverage: one interface for writing, as there is one for reading. Locality: a new
output format is one row, not a `click.Choice` entry plus a branch plus whatever the viewer
does.

---

## I. One task, two answers about its distance — **Worth exploring**

**Files:** `src/pyxctsk/distance/task_distances.py:189`,
`src/pyxctsk/distance/report.py:44, 118`

Both are exported from the front door. On the same one-turnpoint task:

```python
>>> calculate_task_distances(t).as_dict()
{'center_distance_km': 0.0, 'optimized_distance_km': 0.0, 'savings_km': 0.0,
 'savings_percent': 0.0, 'turnpoints': []}
>>> DistanceReport.from_task(t)
TooFewTurnpointsError: a task needs at least two turnpoints to have a distance.
```

The table does not merely round differently — it reports `turnpoints: []` for a task that
has one, and 0.0 km for a distance the report says does not exist. `report.py:42-43` records
that the library *"used to answer 0.0 and only the CLI knew to refuse"*; the 0.0 path is
still published, from `pyxctsk.calculate_task_distances`.

Underneath, "a task needs two turnpoints" is spelled **eight** times with **four** answers,
and only one of the eight names the constant declared for it:

| site | spelling | answer |
|---|---|---|
| `report.py:44, 118` | `MIN_TURNPOINTS_FOR_DISTANCE` | **raises** |
| `task_distances.py:189` | `< 2` | **zeros**, empty rows |
| `center_distance.py:128` | `< 2` | **None** |
| `turnpoint.py:184` | `< 2` | **0.0** |
| `route_optimization.py:340, 429` | `< 2` | empty-leg route |
| `speed_section.py:158` | `< 2` | **None** |
| `goal_line.py:266` | `>= 2` | **None** |

`task_distances.py:106-116` documents the divergence rather than removing it.

**Deepening.** Whether a task is measurable is one question with one owner —
`MIN_TURNPOINTS_FOR_DISTANCE` and a predicate beside it — and the two published shapes give
one answer. The primitives underneath may keep their total-function behaviour; the two
*front-door* answers must agree.

**Wins.** Locality: one rule, one place. Leverage: a caller stops needing to know which of
two published entry points refuses and which invents a zero.

---

## J. Two modules build the two earths — **Worth exploring**

**Files:** `src/pyxctsk/distance/earth.py:22-23`, `src/pyxctsk/distance/plane.py:19, 44, 54-65`

`earth.py`'s docstring (`:5-7`) claims: *"This module is where that choice is made,
**once**, and the rest of `distance/` takes an `EarthModelLike` and passes it down."* It is
not true of `plane.py`, which makes the same choice a second time in a different formalism:

```python
earth.py:22   _WGS84_GEOD      = Geod(ellps="WGS84")
earth.py:23   _FAI_SPHERE_GEOD = Geod(a=FAI_SPHERE_RADIUS_M, b=FAI_SPHERE_RADIUS_M)

plane.py:55   geo_crs = CRS.from_proj4(f"+proj=longlat +R={FAI_SPHERE_RADIUS_M} +no_defs")
plane.py:56   tm_crs  = CRS.from_proj4(f"... +R={FAI_SPHERE_RADIUS_M} ...")
plane.py:62   # else: CRS.from_epsg(4326) / "+ellps=WGS84"
```

Adding a third earth model, or correcting the sphere's radius, means editing both files, and
only `earth.py` would raise on an unknown value. The seam leaks twice more:

- `plane.py:19` imports `earth.py`'s **private** predicate:
  `from .earth import FAI_SPHERE_RADIUS_M, EarthModelLike, _is_fai_sphere`.
- `plane.py:44` degrades the model to a **bool** for its `lru_cache` key
  (`_cached_tm_transformers(lat0, lon0, fai_sphere: bool)`), so the plane's cache is keyed
  on a two-valued encoding of a type `earth.py:33` deliberately widened to
  `EarthModel | str | None`.

This does not contradict ADR 0003 — it fulfils its first bullet ("One selector"), which
today has two implementations.

**Deepening.** A value that owns both representations of one earth (`Geod` and the CRS
pair), so `plane.py` asks the earth for its projection base rather than re-deriving it from
a boolean, and the private import disappears.

**Wins.** Locality: one place knows what an earth model *is*. Leverage: the raise-on-unknown
guard `earth.py` already has covers the projection too.

---

## Smaller findings

Each verified; none large enough for a card.

1. **`report.route()`'s rows are a string-keyed wire format with three consumers.** The
   2026-08-18 review deliberately left them `dict[str, Any]` because *"a dataclass between
   the fields and `json.dumps` would be a layer with one caller"*. There are three now:
   `as_dict:240`, `as_text:278-284` (7 lookups), and — in a different module —
   `TaskDistanceTable.from_report` (`task_distances.py:146-156`, 8 lookups). The typed row
   type already exists (`TurnpointRow`) and is built *from* the untyped one. A key rename in
   `report.py` breaks `task_distances.py` at runtime with nothing for mypy to see.

2. **`route_optimization.py` is still two modules.** By `solver.py:8-12`'s own rule (*"Pure
   planar geometry. It knows nothing about turnpoints, tasks or the earth"*), lines 70–352
   belong there: `PlaneCircle`, `_collapse_duplicate_circles` (ADR 0002's most delicate
   rule), `_boundary_toward`, the three `_place_*` strategies, `_sweep_to_convergence`,
   `_optimize_plane_points`. The test file already reports it —
   `tests/distance/test_route_optimization.py:17-27` imports **eight private names** against
   two public ones, all of them total functions over `list[PlaneCircle]`.

3. **`TaskDrawing` is the only measured value without a `from_measured_task`.** `GoalLine`,
   `SpeedSection` and `DistanceReport` all have one; `TaskDrawing` holds a `MeasuredTask`
   (`common.py:61`) and can only be built from a `Task`. A caller holding a report and
   wanting a map re-runs the optimizer. Producing all four answers about one task costs
   **six optimizer runs** (~220 ms on a 10-turnpoint corpus task); the constructor that
   would let them share is three lines.

4. **`validate_qr_code_task` has no structural guard.** `tests/model/test_validation.py:360-378`
   AST-walks `validate_task` and asserts every `TaskStructure` field is set, with the hazard
   in its own docstring: *"A field the adapter forgets defaults to something harmless and
   hides."* `validate_qr_code_task` (`qrcode/conversion.py:278`) is the second adapter onto
   the same eight-field structure and has no equivalent. `finish_altitude` is still the only
   defaulted field — the hole is exactly the one the test was written for, on the adapter it
   does not cover.

5. **The turnpoint-type table is the one enum pair with no totality test.** Five of six
   pairs in `qrcode/conversion.py` are checked both directions; the turnpoint one is
   excluded (`tests/qrcode/test_conversion.py:62-63`) because of one member,
   `TurnpointType.NONE`. A seventh member added tomorrow maps silently to `NONE` at
   `conversion.py:143`, to `None` at `:232` and to `None` at `:299` — the last feeds
   `TaskStructure.roles`, so a new role would be invisible to every validation rule. A
   totality test over `set(enum) - {NONE}` restores it.

6. **`model/shape.py` is not in the model package's interface.** `model/__init__.py`'s
   docstring enumerates six modules; `shape.py` — the largest in the package, and the one
   `qrcode/` depends on most (nine and eleven imported names) — is in neither the docstring
   nor `__all__`. It is format-agnostic serialization machinery, which is the property that
   earned `rounding.py` its own module. Related: `model/passthrough.py:32` declares
   `QR_EXTENSIONS_KEY = "x"` and `model/__all__` publishes it: the domain-model package
   exports a QR wire key, and `tests/test_layering.py` permits it because it checks packages,
   not keys.

7. **Three of the four package interfaces have zero callers.** `model/`, `qrcode/` and
   `export/` each publish an `__all__` (20, 18 and 5 names) that nothing in the repo imports
   through — the front door reaches into `.model.task`, `.qrcode.image`, `.export.kml` etc.
   directly, and only `distance` is imported as a package. They are not free:
   `qrcode/__init__.py:38-58` eagerly imports `.image` and `.conversion`, so `import pyxctsk`
   costs **94 ms** with `PIL`, `qrcode`, `zxingcpp`, `simplekml` and `pyproj` all resident
   (only `scipy` is deferred).

8. **`GoalLine`'s two constructors duplicate a guard and a branch.** `from_task:225-229` and
   `from_measured_task:252-260` each run `_has_line_goal` and each branch on orientation; in
   the default path `_has_line_goal` runs twice per call, and a third `GoalLineOrientation`
   means editing both. `_build`'s `if length is None: return None` (`:285-287`) is
   unreachable — `goal_line_length_from_turnpoints` returns `None` only for an empty
   sequence, and `_build` is reachable only through a guard requiring two turnpoints.

9. **`earth.snap_to_boundary` carries two axis orders in one signature and is called by no
   test.** `(lon, lat)` for the point, `(lat, lon)` for the centre, `(lat, lon)` out
   (`earth.py:99-125`). `grep snap_to_boundary tests/` → nothing; its behaviour is reachable
   only through whole-route corpus totals. Same class as the six-positional-floats hazard
   finding 12d fixed inside `goal_line.py`.

10. **The `(lat, lon) → (lon, lat)` flip is written twice, differently.**
    `kml.py:110` `[(lon, lat) for lat, lon in …]` vs `geojson.py:82`
    `[[coord[1], coord[0]] for coord in …]`. A `route_coordinates_lon_lat()` beside the
    existing accessor removes both.

11. **Test-suite residue.** `tests/test_cli.py:228-238, 249-258, 260-269` pin corpus
    distances through `CliRunner` and stdout, against that class's own docstring rule
    (*"What the report says is asserted on the value"*) and with `:210-214` right there as
    the model. `tests/export/test_kml.py` asserts KML as substrings (`assert "8.0" in
    kml_result`, which matches inside `48.0123`) while `test_common.py:255-299` has proper
    `styleUrl`-resolving helpers that are private to it. `tests/export/test_geojson.py:32-64`
    invented the drawing seam that lets a feature be rendered without the optimizer;
    `test_kml.py` has none and pays a full optimizer run in all ten of its tests.
    `tests/corpus.py`'s four `@cached_property`s are decorative — `reference_tasks()`
    (`:118-136`) has no memoization and rebuilds every instance on every call.
    `tests/paths.py`'s `TESTS_DIR`, `DATA_DIR` and `REFERENCE_TASKS_DIR` have zero consumers.
    Untested: `pyxctsk --version` (added 2026-08-18, shipped with no test), `__main__.py`,
    every parser adapter in isolation, `generate_circle_coordinates_2d`/`_3d`.

12. **`generate_circle_coordinates_2d` is public with one caller one line below and no
    test.** `export/common.py:288-312`, called only at `:329` inside the `_3d` variant.
    GeoJSON draws no polygons, so it is KML-only geometry living in the shared module.

13. **`distance_through_centers` has no caller in `src/`.** `turnpoint.py:163-199`; every
    consumer is a test or a script, where it serves as the reference the optimizer is
    compared against. It is a published name whose only role is to be a test oracle, and the
    fourth place in the package that knows what a geodesic polyline is
    (`center_distance.py:82-85`, `:171-177`, `route_optimization`).

14. **`local_tm_transformers` is a pass-through.** `plane.py:71-91` — 21 lines whose body is
    one call to `_cached_tm_transformers`, converting types for the cache key, with one
    `src/` caller four lines below (`:197`). It is public only because
    `tests/conformance/test_spec_conformance.py:41` imports it.

---

## Top recommendation

**A — give the parser's adapters the recognition question their docstring promises.**

It is the only candidate here with a demonstrated silent wrong answer at the library's front
door, and it reproduces in one line:

```console
$ echo -n '{"hello":"world"}' | pyxctsk convert
{"taskType":"CLASSIC","version":1,"turnpoints":[],"hello":"world"}
```

The interface it needs is already written down in `parser.py:12-16`; the implementation is
four predicates that currently live, in a different form, in `_unrecognized`. It removes the
load-bearing tuple order, makes the four adapters testable in isolation as the docstring
claims they are, and turns `_unrecognized` from a chain of ifs that re-derives four
recognition rules into a question asked of the adapters that own them.

**B** is the runner-up and is cheaper: two holes at the model↔QR seam, both reproducible,
both with a docstring asserting the opposite of the behaviour, and one round-trip property
test covering both once the shape is decided in one place.

**D** and **E** are the cheapest wins — one is four accessors on a value that already exists,
the other is two `git rm`-sized deletions the package's own docstrings argue for.

---

## Not re-litigated

ADRs 0001–0004. The 2026-06-30, 2026-08-16, 2026-08-17, 2026-08-18 and 2026-08-19 reviews,
all of whose findings are recorded as applied. J touches ADR 0003's territory but fulfils
its "one selector" bullet rather than contradicting it; E deletes `TaskTurnpoint.goal_type`,
not the `earth_model` attribute ADR 0003 puts there.

## Left alone (already deep)

- `distance/center_distance.py` — a convention S7F does not define, with the readings named,
  the 39.9 km spread measured, and the proposed one stated. The module *is* the argument.
- `distance/measured_task.py` and `distance/report.py` — the two values the last review
  introduced are holding; every finding above that touches them is about a caller, not
  about them.
- `model/shape.py`'s field tables — the twelve-edit problem is gone at the wire seam, which
  is what makes C's remaining six edits visible as the exception they are.
- `tests/test_layering.py` — still eight lines of declaration governing 36 modules. G and
  smaller finding 6 are gaps in *what it is told to check*, not in how it checks.

---

## Progress

**All ten candidates applied**, on `docs/deepening-candidates-2026-08-19`, one per commit.
Every commit ran the full suite, `ruff check`, `ruff format` and `mypy src/ tests/` green,
and each behaviour-preserving claim was checked against the reference corpus rather than
asserted. The suite went from **995 to 1133 passing** at the same 98 % line coverage.

```
b7312b4 fix(parser)!: give the adapters the recognition question their docstring promised
2965787 fix(qrcode): decide the QR shape once, and carry a section it cannot read
ca1e754 fix(export)!: let the drawing answer for the goal line and the route too
e5cff73 fix(distance)!: retire one write-only field, and give the other a reader
db09cb7 test(qrcode): guard the one field mirror still written by hand
bc91b3f refactor(distance): one spelling of §7.1.7, and no plane the product never builds
5c64d43 fix!: one exception hierarchy, and one answer to what version this is
41ecd7b feat: give writing a task the seam reading one already has
17f911f fix(distance)!: one task, one answer about whether it has a distance
c0466b2 refactor(distance): the earth is chosen in the module that says it is
```

| # | Candidate | Outcome |
|---|-----------|---------|
| A | Adapters have no recognition question | **applied.** `FormatAdapter` is a name, a `recognizes` and a `read`. The two JSON recognizers' key sets are *derived* from the shapes (`FULL_FORMAT_ONLY_KEYS`, `QR_FORMAT_ONLY_KEYS`), so a recognizer cannot claim a key its shape does not read. `Input` decodes the payload once, removing three dead parameters and two redundant `json.loads`. A recognized-but-unreadable payload raises with the reason. `tests/test_parser.py` is new. |
| B | The QR shape chosen twice | **applied**, in two parts. `from_dict` reduces a legacy `taskType:"W"` payload through `as_waypoints()`, restoring the invariant that an object equals what re-reading its own payload produces. `Field.unread` + `Optionality.carry_unreadable` are the third state a key can be in, which is what makes `_A_DICT_OR_NOTHING`'s docstring true. Every corpus rendering byte-identical. |
| C | The last hand-written field mirror | **applied as the guard**, which the card named as the cheap move — and *not* as a field-set guard, which would not have caught the hole: adding a field to both dataclasses and both tables while forgetting either constructor leaves the field sets matching. `TestEveryFieldCrossesTheSeam` populates every field of every 1:1 shape and asserts each survives the crossing. Verified by mutation: deleting any single field line from either constructor fails it, naming the field. |
| D | The drawing stops at the turnpoints | **applied.** Five accessors (`route_label`, `goal_line_label`, `goal_line_description`, `control_zone_label`, `control_zone_description`) plus `route_coordinates_lon_lat`, and `GoalLine.control_zone_radius` for §6.2.3.1's "half the line". KML's "Course Line" becomes "Optimized Route" — one line per document across all 24 tasks, and the only user-visible change. GeoJSON byte-identical. |
| E | Two write-only fields | **applied, with a departure.** `TaskTurnpoint.goal_type` is deleted as proposed. `OptimizedRoute.earth_model` is **not**: it was accurate and unread while `DistanceReport.earth_model` answered the same question off the *task*, so it got a reader instead. That is the better fix — for a hand-built pair the report was naming a model its own numbers had not been computed on. `earth.name_of` came with it. |
| F | A second optimizer nobody ships | **applied, with a departure.** Deleting `optimal_point` outright would have pushed the four-step pipeline into the test file, which is worse than the duplication. Instead: `point_on_boundary` is the one spelling of §7.1.7, called by the optimizer *and* by `boundary_point`, which is the single-circle answer as a function with the **plane required** — so a test cannot reach the per-turnpoint projection without saying it means to. `TaskTurnpoint` is now exactly the three attributes its interface declares. |
| G | Two error hierarchies | **applied.** `TooFewTurnpointsError` moves to `exceptions.py` as `(pyXCTSKError, ValueError)`; the CLI's two catch tuples become one, pinned by a test. `pyXCTSKError` joins `__all__` and the layering guard's `DOCUMENTED`. `metadata.py` is a new leaf holding `pyxctsk_version`, read by all three places that needed it — the layering guard caught the new edge on the first run. |
| H | Rendering has no seam | **applied.** `renderer.py` holds `OUTPUT_FORMATS` — name, media type, extension, binary, renderer — and `render_task` is the counterpart to `parse_task`. `cli.py`'s convert body is two lines; `scripts/task_viewer/api.py` drops both copies; `EXTENSION`/`MIME_TYPE` become aliases onto the `json` row. `geojson` becomes a CLI format on the way past. |
| I | One task, two answers | **applied, with a departure.** The two published shapes agree — `calculate_task_distances` raises where the report raises, and `TaskDistanceTable.empty()` is gone. The card's "eight spellings of one rule" was wrong on re-reading: the other six guards are *four different rules* that share a number (a polyline of <2 points, a route of <2 circles, a speed-section slice, a goal line needing an approach). They stay total, and the commit says why. |
| J | Two modules build the two earths | **applied.** `earth.py` answers for both shapes of a model — `geod_for_earth_model`, `crs_for_earth_model`, `datum_proj4`, `canonical`. `plane.py` no longer names an ellipsoid, an EPSG code or a radius (asserted by a test), loses the private `_is_fai_sphere` import and the cached twin it converted arguments for, and `LocalPlane.around(centers, "WSG84")` now raises. Byte-identical on both earth models. |

### Live defects fixed

Four candidates were reproducible wrong answers rather than friction:

- **A** — `echo '{"hello":"world"}' | pyxctsk convert` printed an invented task and exited 0;
  `[]` escaped as a bare `TypeError`; every `.xctsk` document was also a valid input to
  the QR adapter, kept apart only by tuple order.
- **B** — a QR payload spelling `taskType:"W"` lost the goal, the deadline, the earth model,
  both takeoff times and every turnpoint radius in one round trip; a malformed `g` or `s`
  was dropped where the optionality's docstring promised it was carried.
- **D** — KML and GeoJSON named the same route differently, with a test in each file
  pinning the divergence.
- **I** — one task got 0.0 km with an empty turnpoint list from one front-door call and an
  exception from another.

### What the applied changes are worth

Verified per commit against every task in `tests/data/reference_tasks/`:

- **parser (A)**: all 24 tasks round-trip identically in all four input spellings.
- **QR codec (B)**: every task's QR JSON, `XCTSK:`, `XCTSKZ:`, waypoints JSON and full
  JSON **byte-identical**.
- **export (D)**: GeoJSON **byte-identical**; KML differs by exactly one line per document,
  which is the finding.
- **distance (E, F, I, J)**: every distance report **byte-identical**, on WGS84 *and* on
  the FAI sphere.
- **rendering (H)**: every format byte-identical to the call it replaced, and the CLI's
  four formats byte-identical to what they printed.

### Breaking changes this produced

1. `parse_task` refuses a JSON object matching neither format (was: an invented empty task).
2. `parse_task` refuses a malformed payload of a recognized format (was: fall-through).
3. `TaskTurnpoint.goal_type` and the `goal_type=` constructor argument are gone.
4. `TaskTurnpoint.optimal_point` is gone; use `turnpoint.boundary_point`, plane required.
5. KML names the optimized route "Optimized Route", not "Course Line".
6. `calculate_task_distances` and `task_distances_from` raise `TooFewTurnpointsError`
   for a task with fewer than two turnpoints; `TaskDistanceTable.empty()` is gone.
7. `TooFewTurnpointsError` is now a `pyXCTSKError` as well as a `ValueError`.
8. `LocalPlane.around` raises on an earth-model value it does not know.
9. `QRCodeTask.from_dict` reduces a legacy `taskType:"W"` payload to the waypoints value.

### Smaller findings addressed in passing

1 (`route()` rows), 3 (`TaskDrawing.from_measured_task`) and 12–14 were **not** taken on —
they are independent of the ten and stand as written. Fixed alongside their candidate: 10
(the axis flip, with D), and the untested `pyxctsk --version` and `_FORMAT_PARSERS`
(with G and A).
