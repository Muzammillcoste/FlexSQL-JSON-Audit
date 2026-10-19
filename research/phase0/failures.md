# Phase 0 failure analysis

**Scope.** Unmodified FlexSQL @ `0ff2f51`, proxy model `gemini-3.1-flash-lite`, 2 plans per question, 1 self-evaluation round, **1 trial per question** (budget). 24 of 30 questions executed. A failure here means the upstream majority-vote answer did not match gold.

Every label below was assigned by hand from the observable trace in `traces/baseline/<case>/trial_1/` (`evidence.json`, `llm_trace_*.jsonl`, `flexsql_output/<case>/log.txt`). The automatic "observed/used" flags in `results.csv` are regex heuristics and were checked by hand: one false positive (the "used" flag for X03) is corrected below. Machine-readable labels are in `failure_labels.json`.

All 12 failures are **silent**: a program executed without error and returned a plausible wrong number. There were no runtime failures, no provider failures and no timeouts. One run (H02) was cut off by the per-run cost cap during self-evaluation, after its candidates had been written.

## Summary

| case | tier | gold | answer | primary | secondary | one-line cause |
|---|---|---|---|---|---|---|
| p0_X_L1_r05 | hardest | 548.40 | 524.50 | **A** | | 5% legacy Wh format never seen; answer equals the naive single-path sum |
| p0_X_L1_r01 | hardest | 548.40 | 546.72 | **A** | | 1% legacy format never seen; answer equals the naive sum |
| p0_X03 | hardest | 226 | 58 | **A** | | Post-drift `tracking.history.checkpoints` format never seen; answer equals the naive count |
| p0_X04 | hardest | 36.9 | 36.8 | **A** | | Same time drift (epoch-ms timestamps); post-drift air shipments silently dropped |
| p0_X05 | hardest | 24724.66 | 14778.88 | **A** | B | Rare 1% `charges.data[]` variant never seen; v2025-03 was seen but not handled |
| p0_H01 | hard | 73101.63 | 58556.16 | **A** | | v2025-03 `transaction.value.amount` never seen (v1 and v2 handled correctly) |
| p0_H03 | hard | 2301.81 | 2174.58 | **A** | | v2025-03 `pricing.fees` never seen; code says "unknown object type → 0" |
| p0_H02 | hard | 994 | 828 | **B** | | Wallet/v3 payloads returned by FindRows, then ignored in the final program |
| p0_X_L2_r01 | hardest | 37 | 36 | **B** | E | Evaluator's own query showed the legacy `state.code='FAULT'` row; it approved anyway |
| p0_H04 | hard | 429 | 0 | **E** | A | `ast.literal_eval` on JSON with `null` fails on every row → 0 |
| p0_M04 | medium | 379 | 103 | **E** | | `ast.literal_eval` drops rows with `null`/`true`; 1–1 vote tie-break chose this candidate |
| p0_M05 | medium | 29 | 3 | **E** | | Same `ast.literal_eval` failure; 1–1 tie-break |

**Counts (primary):** A = 7, B = 2, E = 3; C, D, F, G, H = 0. A and B together are 9/12 of failures, or 9/24 = 38% of executed questions.

One correct answer was reached without discovery: **p0_H10** (v2025-03 never observed). The true maximum happens to be a v1 value, so the program was right by construction of the data, not because the schema was understood.

## Representative failures (trace-backed)

### A — p0_X_L1_r05 (5% rare legacy format). Clean case.
- **Seen.** `list_columns` showed two examples, both `{'fw': '4.x', 'metrics': {'energy_kwh': …}, 'status': …}`. Self-eval ran `SELECT payload FROM readings LIMIT 5` (standard format only) and later `SELECT count(*), sum(json_extract(payload,'$.metrics.energy_kwh')) …`, which returned `334 | 524.505`.
- **Never seen.** `{'fw': '2.9.0', 'data': {'readings': [{'k':'energy','v':…,'u':'Wh'}, …]}, 'state': {...}}` (200 of 4,000 rows, 17 of them in the question's slice).
- **Why the answer was wrong.** Every plan says "extract energy_kwh nested within payload". The evaluator counted 334 rows but never checked how many had a non-null `energy_kwh`. The question's "1 kWh = 1000 Wh" hint was not acted on. 524.50 is exactly the value of the naive query (`fixtures/GROUND_TRUTH_REVIEW.md`).
- **Paired evidence.** The same question on the same canonical data:
  - 0% rare: correct.
  - 20% rare: correct. The legacy format appears in a `list_columns` example, and the program handles both formats with a Wh→kWh conversion.
  - 5%: wrong (524.50).
  - 1%: wrong (546.72 = naive).

### A — p0_H01 (multi-version API, third version missed)
- **Handled correctly.** v2023-01 (`amount`, `status`, `currency`) and v2024-06 (`amount_cents/100`, `state`, lowercase `currency_code`).
- **Never seen.** v2025-03 (`transaction.value.amount` as a string, `transaction.result.status`).
- **Contributing tool behavior.** Clarification called `get_distinct_values(payment_events, payload)`. Upstream implements this as `SELECT DISTINCT … ORDER BY payload LIMIT 100` (`src/tools.py:99`), so the 100 payloads returned are the **lexicographically smallest**, which are all `{"object": "charge", …}` (v1). That sample is systematically biased, not random.
- **Missed signal.** In stitching, the agent printed the set of `object` values, `{'charge', 'payment_intent', None}`. `None` marks the v3 payloads, but the agent did not investigate it. It also never queried the relational `api_version` column, which has 3 distinct values.

### A — p0_X03 (schema drift by time, no version column)
FindRows(`DELIVERED`) and `SELECT tracking … LIMIT 5` both return the earliest rows, which predate the format change on 2025-06-10. The program reads `events[code='DELIVERED']` only. The answer 58 equals the naive count; the gold is 226 (194 of the 265 June shipments use the new format).

### B — p0_H02 (discovered, then ignored)
Clarification ran FindRows(terms=`['wallet']`) and got back v2025-03 payloads with `instrument.details.card_brand`. The final program branches only on `object ∈ {charge, payment_intent}`. The evaluator then wrote that the program "properly identifies … Visa cards (including those in digital wallets)", which is false.

### B — p0_X_L2_r01 (rare row shown to the evaluator, not acted on)
The evaluator's query `SELECT payload FROM readings WHERE payload LIKE '%fault%' LIMIT 5` returned the legacy row `… 'state': {'code': 'FAULT'}` as its 4th result, yet the verdict was `makes_sense=True` for a `payload.status`-only program (36 vs 37). For the other plan, the evaluator **rejected a correct `json.loads` program**, claiming the payload "contains single quotes instead of double quotes". That claim is false; it is an artifact of how upstream displays data (next section).

### E — p0_M04 / p0_M05 / p0_H04 (JSON parsing error induced by the upstream display format)
Upstream renders every JSON value the agent sees as a **Python repr**: `str(truncate_nested_data(json.loads(cell)))` gives `{'notes': None, 'gift_wrap': True}` (`src/get_ddl.py:646`, `src/schema_linking.py:59-91`, `src/tools.py:487`). The model therefore believes the column holds Python literals and parses it with `ast.literal_eval`, which raises on JSON `null`/`true`/`false`. The surrounding `try/except` swallows the error and silently drops the row.
- Prevalence: **22 of 43 Python candidate programs (51%) use `ast.literal_eval`; 14 have no `json.loads` fallback.**
- This only hurts where the data contains JSON literals (retail, payments). Fleet and logistics payloads have none, so the same habit was harmless there (e.g. in the successful p0_H_L1_r20).
- M04 and M05 also show that the **2-candidate majority vote degenerates into a tie-break** (upstream `select_majority_group`: more columns, then lexicographic file name), which picked the wrong candidate in both cases.

## Contrast: why some heterogeneous cases succeeded

| case | rare structure | how it was found |
|---|---|---|
| H_L1_r20, H_L2_r20 | legacy format (20%) | visible in the 2 `list_columns` examples (metadata sample) |
| X01, X02 | pallet / envelope packages | a pallet appears in a `list_columns` example; the program generalised to the `type` field |
| X_L2_r05 | `state.code='FAULT'` (5%) | the question's keyword "fault" drove `payload LIKE '%fault%'` searches (FindRows / SQL), and these matched the rare rows. In this run the sqlglot rewrite made `json_extract(...)='fault'` return no rows, which pushed the agent to `LIKE`. So a harness defect helped this success. |

Discovery succeeded when the rare structure either showed up in the two metadata examples or carried a **lexical anchor from the question** (a value such as "fault"). It failed when the rare variant differed only in structure, units or key names, as with energy in Wh, `amount_cents` nested under `charges.data`, or epoch-ms checkpoints.

## Other confounds observed (not counted as A/B)

- **sqlglot rewrite** (`json_extract(c,'$.p')` → `c -> '$.p'`, UPSTREAM_AUDIT.md §Defects 1). 16 exploration queries compared `json_extract(...)` to a string; 3 of them falsely returned no rows (M03, X_L2_r05). Neither final answer was broken by it in this sample: 43 of the 48 candidate programs were Python, which bypasses the rewrite. The remaining SQL programs only applied `->` to numbers, where the semantics happen to coincide.
- **`query_database` returns one row** in plan clarification unless the query has its own `LIMIT` (registry default `n_example_rows=1`), although the tool description says "20 example rows".
- **Self-evaluation.** Over all runs there were 47 verdicts and 18 rejections.
  - No evaluator computed coverage (for example, the share of rows where the chosen path is NULL).
  - Wrong programs were approved in 9 of the 12 failing runs.
  - In X05 the evaluator *did* notice payloads with a `transaction` key, but with `max_self_eval_rounds=1` the repaired program was never re-checked.
  - **6 rejections, in 5 runs (H01, H04, H10, X03, X_L2_r01), falsely stated that payloads are "Python-style / single-quoted" and steered the writer away from `json.loads`.** This is the same display artefact behind the E failures.
