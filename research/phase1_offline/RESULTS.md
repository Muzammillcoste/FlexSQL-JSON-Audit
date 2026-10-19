# Phase 1 Stage B/C: offline diagnostic results

**Scope.** This measures diagnostic signal only. It makes no claim of any end-to-end FlexSQL improvement: no agent was run, and nothing tested whether a warning would change an answer.

**Constraints honoured:**
- 0 LLM or API calls, 0 USD spent.
- Upstream FlexSQL, the Phase 0 fixtures, gold files, traces and labels are unmodified (one exception, see Deviations).

## What was evaluated

**Detector:** `detector/jcov.py`, with the rule as pre-registered in PREFLIGHT.md §5.
- Python programs are replayed with traced `json.loads` / `ast.literal_eval`. Every key or element access on the parsed objects is recorded as a hit or a miss.
- For SQL, the scope is rebuilt from FROM/JOIN plus the relational AND-conjuncts, and paths are tested with `json_type`.
- A row is **unread** if the program obtained no value from it.
- The detector warns when unread in-scope rows contain leaf paths that occur in **no** read row (`omitted_structure`).
- Valid-JSON rows that the program's parser rejected are reported separately (`parse_failure`).

**Arms:**

| arm | what it does |
|---|---|
| `detector` | primary rule; uses no question text |
| `detector_anchor` | pre-declared secondary arm: keeps a warning only if a question token shares a 4-character prefix with the unread structure's key names or values; lexical, and informed by Phase 0 knowledge |
| B1 any-missing | some key the program names is absent in ≥ 1 row of the column |
| B2 rare-missing | some named key has an absence rate in (0, 50%] (raw NULL-rate) |
| B3 profile-heterogeneity | the `json_tree` path profile has any path present in fewer than 100% of rows |

**Items (46):**
- **24 Phase 0 runs**, using the chosen program, which is the one that produced the scored answer:
  - 9 A/B targets;
  - 12 correct runs, the negative controls;
  - 3 E artefacts, scored separately.
- **17 synthetic control scenarios** (`controls/build_controls.py`, seed 9001):
  - 14 benign;
  - 2 row-level targets;
  - 1 array-element target.
- **5 held-out scenarios** (a different domain, key vocabulary and seed, 4242): 2 targets, 3 benign.

The synthetic programs are hand-written in FlexSQL's `processing(dfs)` style. **They are not FlexSQL outputs.**

## Results (v2, frozen; `outputs/scores_v2.md`)

A "warning" here means a path-coverage warning. A parse finding alone does not count as one.

| set | detector | detector_anchor | B1 | B2 | B3 |
|---|---|---|---|---|---|
| **A/B targets (Phase 0)** | **9/9** | 9/9 | 9/9 | 9/9 | 9/9 |
| **correct runs (Phase 0)**: false warnings | **0/12** | 0/12 | 5/12 | 5/12 | 8/12 |
| E artefacts: path warnings | 0/3 | 0/3 | 3/3 | 3/3 | 3/3 |
| benign controls (synthetic): false warnings | **5/14** | 0/14 | 14/14 | 10/14 | 14/14 |
| synthetic targets (row-level) | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| synthetic target (array element) | 0/1 | 0/1 | 0/1 | 0/1 | 1/1 |
| **held-out targets** | 2/2 | **0/2** | 2/2 | 2/2 | 2/2 |
| **held-out benign**: false warnings | **2/3** | 0/3 | 2/3 | 1/3 | 3/3 |

| arm | targets flagged (all sets) | benign flagged (all sets) | precision | A/B recall |
|---|---|---|---|---|
| detector | 13/14 | 7/29 | 13/20 | 9/9 |
| detector_anchor | 11/14 | 0/29 | 11/11 | 9/9 |
| B1 any-missing | 13/14 | 21/29 | 13/34 | 9/9 |
| B2 rare-missing | 13/14 | 16/29 | 13/29 | 9/9 |
| B3 profile-het | 14/14 | 25/29 | 14/39 | 9/9 |

**Other outcomes:**
- **Abstentions: 0 of 46.** Every evaluation program was simple enough to analyse, so the ABSTAIN logic was exercised only by the toy unit tests.
- **Determinism:** two complete v2 runs produced identical outputs for 46/46 items.
- **Runtime:** about 1 s per item and arm on 4k–6k-row tables.

## Pre-stated screening gate (primary detector)

| criterion | result |
|---|---|
| at least 5/9 A/B evaluable | **pass**: 9/9 |
| flag at least 4/9 A/B | **pass**: 9/9. All 9 hypotheses name a path that is truly required (checked against `relevant_json_paths` by the scorer, after the freeze). |
| at most 2 false warnings among the 12 correct runs | **pass**: 0/12 |
| do not fail the independent negative controls | **fail**: 7/17 flagged (5/14 synthetic, 2/3 held-out) |

The anchor arm passes the negative controls (0/17) but **misses both held-out targets (0/2)**. Their omitted variant is `obs[].code = 'HR'`, which shares no 4-character prefix with "heart rate". The arm also matches Phase 0 targets only because those questions name fields such as "status", "succeeded" and "currency". It is lexical keyword matching, close to FlexSQL's own FindRows, and it does not generalise here.

## Concrete examples

**p0_X_L1_r05** (SQL, A):
- The scope query `SELECT r.rowid, r.payload FROM readings r JOIN devices d … WHERE d.site='north' AND r.recorded_at LIKE '2025-06%'` returns 334 rows.
- 17 of them lack `$.metrics.energy_kwh`. They form one group with novel leaves `data.readings[].k/u/v` and `state.code`; example row ids are 2373, 2057, 2371.
- The 17 matches the fixture's documented count of legacy rows in this slice.
- At 1% (X_L1_r01) the same rule isolates 2 rows.

**p0_X03 / p0_X04** (Python, A):
- X03: 194 of 265 June shipments yield nothing to the program. Their missed access is `events`; their novel leaves are `history.checkpoints[].status/ts`. 194 equals the fixture's count of new-format rows.
- X04: 64 of 561 scoped rows, with the same structure.

**p0_H01 / H02 / H03 / X05** (Python): every unread group is a v2025-03 payload, with novel leaves including `transaction.value.amount`, `transaction.result.status` and `instrument.details.card_brand`. In **X05 the 1% `charges.data[]` sub-variant is not detected**: those rows still yield `status` and `currency`, so the program does read something from them. This blind spot was predicted in PREFLIGHT §2 and is reproduced by synthetic target T03 (0/1).

**False warnings, all of a class predicted in PREFLIGHT §3 #4:**
- C04, C11, C13: 45 `heartbeat` rows with no `type` key, correctly ignored by a purchase-amount query.
- C05: clicks and heartbeats correctly contributing 0.
- HO2, HO3: admin visits with no vitals, plus obs-format rows that have no allergies.
- C07 is different: a program that parses every row and only then filters by site. Its row-level scope is wider than its real scope.

**The key mechanical fact:** p0_H01, a target where v3 rows lack the guard key `object`, and C04, benign because heartbeat rows lack the guard key `type`, produce **the same trace pattern**: a missed guard key, and novel structure in the unread rows. Separating them requires knowing whether the question needs those rows.

**E artefacts:** the v2 detector raises `parse_failure` on all 3 E cases:

| case | rows the program's `ast.literal_eval` rejected |
|---|---|
| H04 | 449 of 2,500 |
| M04 | 1,231 of 1,500 |
| M05 | 751 of 915 |

It raises **0** parse findings on the 12 correct runs, including correct `ast.literal_eval` programs on data without JSON literals. This finding is plain exception tracing. It is useful, but it is not a path-coverage result.

## Cost (scan vs output)

- **Output** is small: about 1–3 KB of JSON per finding, with at most 10 row ids and at most 25 paths.
- **Scan cost** is not small:
  - Python: the detector re-executes the program on its full inputs, then makes one full pass over each JSON column to map parsed objects to row ids.
  - SQL: the scope query plus one `json_type` call per scope row and path.
  - It is cheap on these fixtures. At warehouse scale it costs at least one full materialisation of the program's inputs plus a column scan. That was not measured here.

## Deviations (reported, not hidden)

1. **Detector v1 → v2, after the freeze.** Both bugs were found by inspecting control outputs (C01, HO3, X05); no labels were loaded.
   - (a) A key access that returned a dict or list was not counted as a read. The pre-registered rule says "obtained ≥ 1 value", so `isinstance(p.get('coupon'), dict)` was treated as reading nothing.
   - (b) A row that failed `ast.literal_eval` but parsed through the program's own `json.loads` fallback was still reported as a parse failure.
   - v1 results are kept in `outputs/v1/` (`scores_v1.md`, `jcov_v1.py`, `FREEZE_v1.sha256`). v1 differs from v2 by one more benign false warning (6/14 controls), 3/3 E path warnings, and an anchor arm with 2/29 false warnings. **A/B detection and the Phase 0 correct-run results are identical in v1 and v2.**
2. **Scorer fix**, in `eval/score.py` only: path normalisation stripped `=…` before collapsing brackets, so `readings[k='energy'].v` was mangled. This affected only the "names required path" column.
3. **Phase 0 side effect.** The Stage A inventory replay used upstream's `program_frame.py`, which imports each program. That rewrote or created 43 `__pycache__/*.pyc` bytecode caches inside `research/phase0/traces/baseline/*/…/`. No source, output, log, label or fixture file changed: the fixture `FROZEN.sha256` still verifies and upstream `git status` is clean. Set `PYTHONDONTWRITEBYTECODE=1` to avoid this.

## Limitations

- **Author contamination.** The detector's author also built the fixtures, the labels and the controls, and wrote the controls already knowing the rule. The held-out set is "held-out data", not an independent author.
- **The Phase 0 target set does not discriminate between detectors.** All three naive baselines also flag 9/9. Every heterogeneity in the Phase 0 fixtures is *relevant* by construction, so the 0/12 on correct runs measures specificity only against relevant heterogeneity. Mixed event-type tables, the common real-world case, are represented only by synthetic controls, and that is where the primary rule fails.
- n is small: 9 targets, 1 trial, one proxy model. There is no confidence interval worth stating.
- The detector is row-level only, so it misses element-level and value-level variants (X05 `connect`, T03). It assumes parse-then-read programs and cannot see `json.dumps`, `**p` or C-level dict access.

## Reproduce (offline)

```bash
cd "FlexSQL Research"; PY=.venv-phase0/Scripts/python.exe; export PYTHONDONTWRITEBYTECODE=1
$PY research/phase1_offline/preflight/inventory.py          # Stage A replay inventory
(cd research/phase1_offline && sha256sum -c FREEZE.sha256)    # verify frozen detector/controls (do not rebuild controls)
(cd research/phase1_offline/detector && ../../../$PY test_jcov.py)
$PY research/phase1_offline/eval/run_all.py                  # detector + baselines, no labels read
$PY research/phase1_offline/eval/score.py                    # the only script that reads labels/gold
```
