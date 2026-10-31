# Phase 1 preflight: zero-API viability audit

Date 2026-10-19. No LLM or API calls were made. Phase 0 artefacts, upstream FlexSQL (`0ff2f51`) and the frozen fixtures were only read, never modified. The script used here is `preflight/inventory.py`; its output is `preflight/inventory.json`, and its replay outputs are in `preflight/replay_out/`.

**Conflict of interest, stated up front.** The same author built the Phase 0 fixtures and failure labels and is now designing the detector, so the author already knows which variants each failure omits. That knowledge cannot be removed. The mitigations are:

- a detector rule with no tuned thresholds, written from the principles in §5 and not from case details;
- code hashes frozen before any scoring;
- benign controls and a held-out schema variation, both written before the detector is run;
- scoring done by a separate script.

Even with these, the Stage C result is weaker evidence than a truly blind test.

## 1. Inventory of the 24 saved baseline runs

Every chosen program, and every candidate program, **replays offline and reproduces its saved `program_output_*.csv` exactly**:

- Python programs are replayed through upstream's own `utils/program_frame.py`, with the same `sub_queries_plan_*.json` and the same order of `dfs`.
- SQL programs are run on a read-only `sqlite3` connection.

| group | runs | chosen program | JSON access | scope |
|---|---|---|---|---|
| A (missing path) | 7 | 6 Python + 1 SQL (X_L1_r05) | `json.loads` ×2, `ast.literal_eval` ×3, both ×2 (with fallback); SQL `->` | relational filters (merge / date / site / mode) are applied **before** parsing in all 7 |
| B (seen, unused) | 2 | 2 Python | `ast.literal_eval` (H02 after `str.replace('null','None')…`) | H02 has no filter (the question covers all events); X_L2_r01 filters by merge and date first |
| E (parse artefact) | 3 | 3 Python | `ast.literal_eval`, no fallback | relational filters first |
| correct | 12 | 10 Python + 2 SQL (M01, X06; no JSON) | mixed | – |

Facts that hold for all 21 Python programs:

- `dfs` come only from the saved sub-queries, which are full-table projections. No program touches `conn` directly. So data lineage is fully recoverable: the program sees whole tables.
- Each program has at least one `try/except`, and 19 use `dict.get` with a default. A missing key or a parse failure is therefore always silent.
- JSON is parsed only via `json.loads` / `ast.literal_eval`. No regex or substring parsing was found in any chosen program.

## 2. Can the 9 A/B failures be assessed without gold?

A case counts as **eligible** if all of these hold, using only what exists at inference time:

1. the program replays deterministically;
2. its JSON reads go through an interceptable parse call (Python) or a SQL JSON operator inside a plain SELECT…FROM/JOIN…WHERE;
3. its population, meaning the rows that reach the JSON access, is determined by the program itself.

| case | type | eligible | how the scope is recovered | what a gold-free check could observe |
|---|---|---|---|---|
| X_L1_r05 | SQL | yes | rerun the same FROM/JOIN/WHERE with relational conjuncts only | rows where `$.metrics.energy_kwh` is absent |
| X_L1_r01 | Py | yes | rows reaching `ast.literal_eval` (after merge, site and month filters) | `metrics` missing → default 0 |
| X03 | Py | yes | after the June filter | `events` missing → `[]` |
| X04 | Py | yes | after merge and the `air` filter | `events` missing → `[]` |
| X05 | Py | yes | after the Q2 filter | v2025-03 rows lack `state`/`status` (the 1% `connect` variant does **not** lack them, so a row-level check cannot see it) |
| H01 | Py | yes | after merge and the EMEA filter | `object` missing → falls through → 0 |
| H03 | Py | yes | after the Q1 filter | `state`/`status` missing → early `return 0` |
| H02 | Py | yes | all rows (no filter) | `object` missing → neither branch taken |
| X_L2_r01 | Py | yes | after merge and the July filter | `status` missing → `''` |

- **Eligible: 9 of 9 with dynamic replay; 1 of 9 (the SQL case) with static analysis only.** Static extraction of Python key strings does not give scope and cannot separate "key absent → default" from "key absent → legitimately optional". The Python cases are assessable **only** with execution-time tracing of the program's JSON accesses.
- **Exclusions.** None of the 9 is excluded at the eligibility step. X05's rare 1% sub-variant is **not detectable at row level**, because its rows still yield `status`/`currency`. Only element-level or value-level analysis could catch it, and that analysis would need to know which leaf is "the amount", i.e. semantics. Only the v2025-03 omission in X05 is observable.

## 3. Situations likely to mislead a naive coverage check

The detector must return NO_EVIDENCE or ABSTAIN on these. Existing Phase 0 successes are used where they exist. The rest are new local synthetic controls (`controls/`), written before the detector was run.

| # | situation | source |
|---|---|---|
| 1 | Optional nested object absent (pickup orders have no `shipping`) | Phase 0 M03 (correct) |
| 2 | JSON `null` vs absent key (coupon `null` / absent / object) | synthetic C-null |
| 3 | Optional boolean present only when true (`gift_wrap`) | synthetic C-optional |
| 4 | **Irrelevant alternative shape**: event types with disjoint schemas, of which the question needs one | synthetic C-irrelevant (expected hardest) |
| 5 | Deliberately filtered subset: the alternative format exists only outside the program's relational filter | synthetic C-filtered; Phase 0 r00 rungs |
| 6 | Arrays: per-element vs per-row counts (`items[]`, `boxes[].items[]`) | Phase 0 M02, X02 (correct) |
| 7 | Unrelated fields with the same terminal key name (`code` in `events[]` vs `state.code`; billable vs physical weight) | Phase 0 X01; synthetic C-samename |
| 8 | Valid join restriction (inner join drops rows) | Phase 0 X04 scope, X06 |
| 9 | Numeric string vs number | Phase 0 M03, H10 |
| 10 | JSON-value filter that legitimately excludes rows (`status = fault`) | Phase 0 M_L2_r00 |
| 11 | Program already handles every variant | Phase 0 H_L1_r20, H_L2_r20 |
| 12 | No JSON at all | Phase 0 M01, X06 |
| 13 | **Correct by luck but incomplete** (v2025-03 ignored, max is a v1 value) | Phase 0 H10. A warning here is *true* about the program but still counts against the false-warning budget. |

## 4. Inputs, features and what needs intent

**Available at inference time:**
- the generated program (SQL text or Python source);
- the saved sub-queries;
- the SQLite file;
- Spider2-style table metadata (column names, types, descriptions, sample rows);
- the NL question text and external knowledge.

Gold SQL, gold answers and failure labels are **not** inputs.

**Deterministically extractable:**
- the SQL JSON path literals and the FROM/JOIN/WHERE scope (sqlglot AST);
- Python parse sites and every key access the program performs on each parsed object at run time: hits, misses, `in` tests, iteration;
- which rows reach the parse call, plus their DB row ids (matched by canonical JSON);
- per-row structural signatures (the set of key paths, with arrays normalised to `[]`);
- `json_type` per path, telling missing apart from JSON null and number from numeric string;
- parse failures on rows that are valid JSON.

**Requires understanding user intent (not decidable here):**
- whether rows the program reads nothing from *should* contribute;
- whether a leaf in an alternative shape means the same as the leaf the program reads (`v` with `u='Wh'` vs `energy_kwh`);
- whether an exclusion is a legitimate filter;
- unit conversion;
- element-level variants (X05 `connect`).

All of these are reported as **hypotheses**, never as equivalences.

**Supported program types:**
- (a) single-SELECT SQL over base tables, using JSON operators, with relational predicates combined by top-level AND;
- (b) Python programs whose JSON reads go through `json.loads` / `ast.literal_eval` on values from the saved sub-queries.

The detector abstains on: CTEs, subqueries, UNION, `json_each`/`json_tree`, OR-mixed JSON predicates, direct `conn` use, `eval`, regex or substring parsing of raw JSON, and programs that fail to replay.

## 5. Proposed check: what it adds beyond a profile query

A `json_tree` / `FLATTEN` profile describes **the column**. It cannot say whether **this program** reads anything from **the rows in its own scope**. The behavioural test proposed here is:

> Within the rows that reach the program's JSON access, find the rows from which the program's executed accesses obtained **no value at all**. Flag a hypothesis only if those rows have structure (key paths) that is **absent from every row the program did read**.

- Rows that only lack an optional key have a signature that is a subset of the read rows' signatures, so they yield NO_EVIDENCE.
- Rows the program fails to parse although they are valid JSON are reported separately as a parse finding (category E). These are **not** counted as path-coverage detections.
- The rule has no tuned threshold: support ≥ 1 row, and novel structure is a set difference.

**Known false-positive mode, accepted in advance:** situation #4. A program that correctly ignores an irrelevant event type with a disjoint schema, by reading only a key that type lacks, will be flagged. Telling it apart needs intent.

## 6. Related work and overlap

The phase protocol allowed no external calls, so **no paper was fetched in this phase**. Only sources whose content could be checked are characterised.

| work | status here | overlap |
|---|---|---|
| SQLite JSON1 `json_tree` (https://www.sqlite.org/json1.html) | used locally (SQLite 3.50.4) | Full recursive path/type profile of a column. One GROUP BY query surfaced every required structure in 18/18 Phase 0 cases. **Fully covers discovery.** Its scan cost is O(total JSON size) per column, so it is cheap on these 4k–6k-row fixtures but not free on warehouse-scale VARIANT columns (output size ≠ scan cost). |
| Snowflake `FLATTEN(…, RECURSIVE=>TRUE)` (https://docs.snowflake.com/en/user-guide/querying-semistructured) | known standard practice | The same profiling capability for VARIANT. Covers discovery. |
| FlexSQL (https://arxiv.org/abs/2605.02815; code inspected) | code read in Phase 0 | Has exploration tools and an LLM self-evaluator. It has **no** coverage, row-level or program-linked check (verified in code and in 47 traced evaluator verdicts). |
| MRSQLGen (https://doi.org/10.1145/3797146) | **not read** | Unknown. If it is metamorphic testing of generated SQL, it is reference-free like this proposal, and the overlap could be material. |
| SpotIt+ (https://arxiv.org/abs/2603.04334) | **not read** | From memory, unverified: the SpotIt line searches for database instances on which generated and *gold* SQL differ. That is reference-based; if SpotIt+ keeps that design, it is distinct. |
| TraceSQL (https://arxiv.org/abs/2608.17795) | **not read** | Unknown; the name suggests execution tracing. **The highest overlap risk; it could subsume this proposal.** |
| Related lines from memory, not re-checked: why-not provenance (Chapman & Jagadish, SIGMOD 2009; Herschel et al., Artemis); `mlinspect` (Grafberger et al., data-distribution debugging of pandas pipelines); Deequ completeness constraints (Schelter et al., VLDB 2018); JSON schema inference (Baazizi et al.) | – | Row lineage through filters and "which tuples went missing and why" are well studied. mlinspect already instruments pandas pipelines to report rows that operators drop, grouped by attributes. |

**The specific remaining distinction**, if any: tracing the JSON key accesses that an *LLM-generated* program executes, inside the scope the program itself defines, and contrasting the rows it read nothing from by *structure*. Neither json_tree/FLATTEN (no link to a program) nor FlexSQL does this. Against why-not provenance and mlinspect, the distinction is narrow: it is an application of row lineage with JSON-shape grouping, not a new principle. Against MRSQLGen, SpotIt+ and TraceSQL it is **unverified**.

## 7. Gate judgement

| stop condition (from the [protocol](../PROTOCOL.md)) | result |
|---|---|
| fewer than 5 of the 9 A/B failures technically eligible | **not triggered**: 9/9 eligible with dynamic replay (only 1/9 with static analysis) |
| detection would need gold answers or case-specific path aliases | **not triggered by design**: the rule uses the program, the DB and set differences only; no alias dictionary |
| the check would only reproduce a standard profiling query | **not triggered**: the test is program-linked and row-level (what the program read), which a profile cannot give |

**Preflight: PASS (technical), with a weak novelty position.** Proceeding to a minimal, time-boxed Stage B/C is justified only because an offline evaluation costs no money and answers the open empirical question: does the signal separate the 9 targets from the 12 correct runs, and does it beat the naive baselines? The pass is **not** evidence of research value. The novelty question stays open until the three unread papers are checked.
