# Phase 0 report: does original FlexSQL fail because it under-explores heterogeneous JSON?

**Execution status: REAL_FLEXSQL_RUN (proxy model), partial coverage, single trial.** Upstream FlexSQL `0ff2f51`, unmodified, entry point `src/main.py --use_2step_batch_planning`, SQLite dialect, model `gemini-3.1-flash-lite`. 24 of 30 questions were executed once each, plus 1 diagnostic run. Total API spend was about 4.8 USD of the 5 USD budget.

## 1. Executive summary

- The authentic FlexSQL pipeline runs end-to-end on our custom SQLite JSON fixtures: planning, clarification, sub-SQL composition, Python/SQL stitching, self-evaluation and majority voting. All generated programs executed against the database.
- **12 of 24 executed questions were answered wrong, and all 12 were silent wrong answers** (the program ran and returned a plausible number). 7 have **Category A** as primary cause (the required JSON path was never shown to the agent), 2 are **B** (the path was shown but not used), and 3 are **E** (JSON-parsing errors, induced by how upstream displays data).
- The **rarity ladder** gives the cleanest causal signal (same data, same question, only the share of records in the legacy format varies). The energy question was correct at 0% and 20% but wrong at 5% and 1%, both times **exactly equal to the naive single-path answer**. The fault-count question was correct at 0%, 20% and 5% (a keyword search for "fault" hit the rare rows) and wrong at 1% (the evaluator saw the rare row and ignored it).
- **Existing capabilities.** One conventional `json_tree` path-frequency query through FlexSQL's own SQL tool reveals **100% of the required structures in all 18 heterogeneous cases**, including 1% variants, in about 75–260 tokens of output. The agent never issued such a query. In the one diagnostic run where that profile was injected into every prompt, the agent **still** gave the naive answer (n = 1).
- **Recommendation: PIVOT.** Reproducible exploration-related failures exist and they matter, but discovering the paths is cheap with existing tools, and supplying the paths did not fix the failure in the one test we could afford. The bottleneck looks like *using and verifying* the structural information (coverage checking), compounded by upstream display and voting artefacts, more than an exploration algorithm that is uncertainty-aware but otherwise conventional. This is a tentative conclusion: 1 trial, n = 24, synthetic data, a proxy model.

## 2. Environment and FlexSQL version
Details are in `environment.md` and `UPSTREAM_AUDIT.md`. Summary:
- Upstream `StringNLPLAB/FlexSQL` @ `0ff2f5107d80ea3bf92b6e12ddf61dfa2a925b68`, working tree unmodified, no LICENSE file.
- Python 3.12.13; SQLite 3.50.4; packages pinned to upstream `uv.lock`. vllm and transformers were not installed: they are used only for serving models and have no Windows build.
- **Deviations from the paper's setup** (this is a *proxy baseline*, not a replication):

| Setting | Paper | Phase 0 |
|---|---|---|
| Model | local gpt-oss-120b | gemini-3.1-flash-lite |
| Plans | 8 | 2 |
| Self-evaluation rounds | 3 | 1 |
| Database | Snowflake / Spider2-SQLite | synthetic SQLite |
| Trials | – | 1 |

- Tool mapping from paper to code:

| Paper tool | Code function |
|---|---|
| GetTableCol | `list_columns` |
| GetColValues | `get_distinct_values` |
| FindRows | `search_dimension_values` |
| SQLExecutor | `query_database` |
| PythonExecutor | `python_interpreter` |

## 3. Model provider and verified compatibility
Full record in `environment.md`.
- **Gemini via the OpenAI-compatible endpoint.**
  - Authentication was verified. The upstream default `extra_body.top_k=-1` is a vLLM-only parameter and is rejected with HTTP 400 by both Gemini and Groq, so the observation harness drops it (`-1` means "disabled" in vLLM anyway).
  - Gemini 3.x requires `thought_signature` on tool-call replay. Upstream `chat.py` drops it, so the harness re-attaches it to a copy of the outgoing request. This is transport-level only; no upstream file was edited.
- **Models tried:**
  - `gemini-2.5-flash` was rejected. Every stitching call on the JSON smoke case returned `MALFORMED_FUNCTION_CALL`; this was reproduced in isolation, even with `query_database` as the only tool.
  - `gemini-2.5-flash-lite`, the model you asked for, returns **404 "no longer available to new users"** for this key.
  - `gemini-3.8-flash` works, but costs about 1–1.5 USD per question.
  - **Selected: `gemini-3.1-flash-lite`** (your choice).
- **Groq `openai/gpt-oss-120b`** (the paper's model) authenticates and runs the tool loop. It is **infeasible** on this account because of the 8,000 tokens-per-minute limit: a single FlexSQL request is often larger than that.
- **Smoke tests:**
  - Relational p0_M01 (gemini-2.5-flash): correct.
  - JSON p0_M02 (gemini-3.1-flash-lite): correct. 2 Python programs were executed via `utils/program_frame.py` against the SQLite database, and majority voting returned 828 = gold.

## 4. Questions actually executed

| tier | planned | executed (1 trial each) | correct | wrong (all silent) | errors / timeouts | not executed (budget) |
|---|---|---|---|---|---|---|
| medium | 10 | 7 | 5 | 2 | 0 | 3 (M06, M07, M08) |
| hard | 10 | 7 | 3 | 4 | 0 | 3 (H05, H06, H09) |
| hardest | 10 | 10 | 4 | 6 | 0 | 0 |
| **total** | 30 | **24** | **12** | **12** | 0 | 6 |

- The 6 questions that were not executed are **not counted as failures**.
- Trials 2 and 3 were planned but not run (5 USD budget), so this phase cannot separate reproducible failures from stochastic ones. Each candidate count is out of 2 plans.
- Diagnostic arm: 1 run (`diag_pathprofile`, p0_X_L1_r05).
- Tokens: 4.70M across the 24 baseline runs (about 196K per run, about 33 LLM calls per run), estimated 1.91 USD.

## 5. Accuracy by difficulty
- Medium: 5/7 (71%). Hard: 3/7 (43%). Hardest: 4/10 (40%). With n = 7–10 and one trial, these are counts, not stable rates.
- Positive controls (relational M01 and X06; JSON ladder r00 L1 and L2) were **4/4 correct**, so the harness itself works. H09 was not executed.

## 6. JSON-path discovery failure rate
- In 16 executed cases with heterogeneous structure, the agent **never saw at least one required structure in 9 cases (56%)**.
  - "Seen" means the structure appeared in any tool output or example-row block shown to the model (heuristic, checked by hand).
  - 8 of those 9 were answered wrong. The exception, H10, was right because the data happened to put the maximum in an observed version.
- Of the 7 cases where every structure was seen, 5 were correct. 2 were wrong anyway (H02, X_L2_r01; category B).

## 7. Silent incorrect-answer rate
**12/24 executed questions (50%)** returned a wrong answer from a program that executed without error.

Self-evaluation (1 round) issued 47 verdicts with 18 rejections:
- In 9 of the 12 failing runs it approved at least one wrong candidate.
- In H01, H04 and X05 it rejected both candidates. The single repair round was not re-verified and stayed wrong.
- Only some rejections pointed at the real problem. In X05 the evaluator noticed payloads with a `transaction` key. **6 rejections, in 5 runs, falsely claimed the payload is "Python-style, single-quoted" and told the writer to stop using `json.loads`.** That is an artefact of upstream's display format (§11.5).

## 8. Root-cause breakdown (primary label; see `failures.md`)

| Category | Count | Cases |
|---|---|---|
| A. Required JSON path never discovered | **7** | X_L1_r05, X_L1_r01, X03, X04, X05, H01, H03 |
| B. Path discovered but not used / wrong path | **2** | H02, X_L2_r01 |
| C. Schema understood, generation wrong | 0 | – |
| D. Correct query, execution failed | 0 | – |
| E. Type / null / JSON-parsing error | **3** | M04, M05, H04 (all `ast.literal_eval` on JSON) |
| F. Ambiguous question / bad gold | 0 | – |
| G. Model / tool compatibility | 0 in baseline | gemini-2.5-flash was excluded *before* the baseline for G-type failure |
| H. Other | 0 | – |

Secondary labels: X05 also B, H04 also A, X_L2_r01 also E.

## 9. Representative queries

**Success: p0_H_L1_r20.** The legacy format was visible in a `list_columns` example, so the program handles both formats:

```python
if 'metrics' in payload and 'energy_kwh' in payload['metrics']: return float(payload['metrics']['energy_kwh'])
if 'data' in payload and 'readings' in payload['data']:
    for item in payload['data']['readings']:
        if item.get('k') == 'energy' and item.get('u') == 'Wh': return float(item.get('v')) / 1000.0
```

Result 548.40 = gold. The same question at 5% and 1% rarity produced the single-path program below:

```sql
SELECT ROUND(SUM("r"."payload" -> '$.metrics.energy_kwh'), 2) FROM "readings" r JOIN "devices" d ON ...
WHERE d.site='north' AND r.recorded_at LIKE '2025-06%'      -- 524.50 / 546.72 (gold 548.40)
```

The upstream sqlglot pass has already rewritten `json_extract` to `->` here (UPSTREAM_AUDIT.md).

More failures with trace citations: `failures.md`. Every trace is in `traces/baseline/<case>/trial_1/`.

## 10. Effects of extra exploration using existing tools (Phase 6)

**Tool-level controls** (`diagnostics/existing_capability_controls.md`). These need no LLM: the conventional queries are run through the *upstream* `query_database` tool and we check whether its output would reveal each case's required structures.

| Control | Reveals all required structures | Output size |
|---|---|---|
| First 5 rows (`LIMIT 5`) | 3/18 (the two 20% ladder rungs and X02) | 0.6–2.7K chars |
| First 20 rows | 3/18 | 2.2–9.8K chars |
| First 100 rows | 8/18 (misses all payments cases and the tracking drift) | 11–51K chars |
| 20 random rows (mean over 20 seeds) | 1% variants found in 15–20% of samples | 2–5K chars |
| 100 random rows | 1% variants found in 50–70% | 11–26K chars |
| **One `json_tree` path-enumeration query** | **18/18** | 231–841 chars |
| **One `json_tree` path-frequency query (GROUP BY path)** | **18/18, with counts** (e.g. `$.charges.data[*]."amount_cents" \| 25`) | 301–1,057 chars |

- **Could the original agent have used this?** Yes. `query_database` accepts this exact SQL: SQLite JSON1 is available and the query survives upstream's sqlglot rewrite. In 24 runs the agent **never** issued `json_tree`, `json_each`-based key enumeration, or a GROUP BY over keys. Its exploration of JSON consisted of `LIMIT 1–10` samples, `get_distinct_values` on the whole payload (sorted, hence biased), and keyword FindRows.
- **Cost.** One query per JSON column, about 75–260 tokens of output. This is negligible next to the roughly 196K tokens each run used.

**Agent-level diagnostic (1 run)**, `diag_pathprofile`, p0_X_L1_r05:
- The path-frequency profile was injected through upstream's own BIRD-style `evidence` field, with no code change. The trace confirms it appeared in 7 prompts across planning, clarification, stitching and evaluation.
- Result: **still wrong (524.50)**, using `metrics.energy_kwh` only, and the evaluator approved it twice.
- With n = 1 this is weak evidence. It does fit the B failures: *showing* the agent the structure was not enough, and the agent did not relate the rare path to the question.
- **Implication.** Cheap, ordinary JSON inspection fully solves the *discovery* step. The remaining problem is getting the agent to use and verify coverage. As MASTER.md puts it, "if the oracle hint does not improve the outcome, the failure is unlikely to be solely missing path discovery". The oracle-hint arm itself was built (`diagnostics/questions_diag_oracle.jsonl`) but **not run** (budget).

## 11. Limitations and confounders
1. **One trial per question.** Stochastic and reproducible failures cannot be told apart. The ladder pairs lend some causal weight, but every rung is a single sample.
2. **Proxy model.** `gemini-3.1-flash-lite` is far weaker and cheaper than the paper's gpt-oss-120b. We ran 2 plans and 1 self-evaluation round, against the paper's 8 and 3. A stronger model, or 8 plans voting, might explore more or catch more problems. gemini-3.8-flash explored far more in smoke tests (61 clarification tool calls on a trivial question).
3. **Coverage.** 24 of 30 questions; 6 not executed, among them a hard-tier positive control.
4. **Synthetic data designed by us.** Rare variants were placed deliberately: rare rows were guaranteed to fall inside each question's slice, and H10's maximum was forced to sit in an observed version.
5. **Upstream artefacts that confound JSON behaviour on SQLite:**
   - The sqlglot rewrite `json_extract`→`->`. It caused 3 false empty results during exploration and indirectly *helped* one success.
   - Python-repr display of JSON. This induced the `ast.literal_eval` habit (51% of Python programs) and all 3 E failures, and it misled one evaluator into rejecting a correct program.
   - `n_example_rows=1` in the clarification-stage SQL tool.
   - `get_distinct_values` uses `ORDER BY`, which biases sampling.
   - With 2 candidates, majority voting reduces to a lexicographic tie-break; this decided M04 and M05.
   - Any of these could shift results in either direction for a different model or setup.
6. **Discovery flags** are regex heuristics over tool outputs, checked by hand for every failure; one false positive (X03 "used") was corrected.
7. **Compat shims and model choice.** The two transport shims are believed to be semantics-neutral (dropping `top_k`, re-attaching `thought_signature`). The model was chosen after smoke tests on two other models, a selection step that is documented.
8. **Spend.** About 2.8 USD went on model-selection smoke tests (gemini-3.8-flash) before your 5 USD limit was stated. That left about 2 USD for the baseline.

## 12. Recommendation: **PIVOT**

| Criterion | Evidence |
|---|---|
| Reproducible JSON exploration failures exist? | **Yes, but only n=1 per question.** 7 A plus 2 B out of 24, all silent, and they increase with rarity on the ladder. |
| Do they materially affect correctness? | **Yes.** They account for 9 of the 12 wrong answers. |
| Not resolved by cheap existing techniques? | **Discovery: resolved.** One `json_tree` GROUP BY query through the existing SQLExecutor reveals every required structure in 18/18 cases for about 100–250 tokens. **Outcome: not resolved** in the single diagnostic run where that information was supplied. |

This matches the PIVOT definition: failures exist, but existing inspection techniques solve the information gap cheaply, and the failures that remain involve using and verifying what was found. A research claim along the lines of "uncertainty-aware exploration finds rare paths that FlexSQL misses" would have to beat a one-line `json_tree` baseline, which already reaches full path recall here.

Directions that are better supported by the evidence:
1. **Coverage-aware verification.** Make the planner and evaluator check what fraction of the target rows the chosen JSON path actually covers (NULL rate per path, variants per row), and act when coverage is below 100%. No evaluator in any run computed coverage. Wrong programs were approved in 9 of 12 failing runs. When an evaluator did spot a missing variant (X05), the 1-round repair budget ran out before the fix could be re-checked. The uncertainty-aware idea could be reframed as uncertainty about *coverage*, not about which paths exist.
2. **Structural profiling as a step in the pipeline**, set against the plain `json_tree` profile as the baseline that has to be beaten.
3. Fix or ablate the upstream artefacts listed in §11.5 before attributing any accuracy gain to exploration.

**Smallest next experiment, about 2–3 USD at flash-lite prices.** Take the 9 A/B cases and run 4 arms × 3 trials:
- baseline;
- path-profile in `evidence`;
- oracle paths in `evidence`;
- the same baseline with the stronger gemini-3.8-flash for a subset.

This measures whether (i) the failures reproduce, (ii) supplying information recovers them, and (iii) a stronger model narrows the gap. GO should only be considered if the path-profile arm recovers clearly less than the oracle arm, i.e. if there is a measurable gap that a smarter exploration policy could close.

## Deliverables
| Path | Contents |
|---|---|
| `PHASE0_REPORT.md` | this report |
| `failures.md`, `failure_labels.json` | root-cause analysis |
| `results.csv` | one row per execution, baseline plus diagnostic; explicit nulls |
| `environment.md`, `UPSTREAM_AUDIT.md` | environment, setup, compatibility, code audit with file:line references |
| `fixtures/` | `generate.py` (seeds 101/202/303/404/7), 7 SQLite DBs + metadata, `questions.jsonl`, `cases.jsonl`, `gold/` (CSV + SQL), `GROUND_TRUTH_REVIEW.md`, `FROZEN.sha256` (written before any benchmark run) |
| `traces/baseline/<case>/trial_1/` | full LLM transport trace, FlexSQL outputs, plans, programs, CSVs, majority vote, `evidence.json` |
| `traces/diag_pathprofile/` | diagnostic run |
| `traces/_archive_model_selection/` | gemini-2.5-flash and gemini-3.8-flash smoke runs |
| `diagnostics/` | tool-level controls, diagnostic question files, aggregate tables |
| `scripts/` | `run_flexsql.py`, `score_runs.py`, `aggregate.py`, `existing_capability_controls.py`, `build_diagnostic_questions.py`, `review_ground_truth.py`, `summarize_trace.py`, `provider_probe.py`, `replay_stitching.py` |
| `harness/` | `p0_trace.py` (trace, backoff, compat shims), `sitecustomize.py`, `p0_env.py` |
| `config/baseline_config.json` | fixed baseline configuration |
