# Codex — Phase 1: Zero-API Research Viability Gate

You are a skeptical research engineer. We have **no remaining API budget**, and the owner's time is limited. Your job is to decide whether one narrow extension to FlexSQL merits further work, **not** to make the project look promising.

## Context (read first)
- Read `research/phase0/PHASE0_REPORT.md`, `failures.md`, `results.csv`, `UPSTREAM_AUDIT.md`, `environment.md`, the frozen fixtures, the trace summaries, and existing capability-control reports. Locate equivalent paths if the directory layout differs; never invent missing files.
- Original FlexSQL source: https://github.com/StringNLPLAB/FlexSQL . Keep its source and baseline outputs unchanged.
- Phase 0: 24/30 authentic agent questions ran with a Gemini proxy model and reduced planning/evaluation. There were 12 incorrect answers; primary labels: 7 missing JSON paths (A), 2 seen-but-unused paths (B), 3 JSON parsing/type artifacts (E). One ordinary SQLite `json_tree` path-frequency query exposed all necessary paths in 18/18 evaluated heterogeneous cases, yet one trial with those paths supplied still failed. These are preliminary, single-trial, synthetic findings; verify against local files.

## Decision to investigate
**Stop pursuing generic JSON schema inference, recursive key listing, or semantic search.** The only remaining candidate is a **reference-free, low-cost diagnostic for silently incomplete JSON queries**: given a generated SQL/Python program, database metadata/data, and optionally the user's natural-language question, can we detect likely omission of relevant JSON variants *without using the correct answer or gold SQL*?

This is NOT a promise of research novelty. Compare prior work before coding:
1. SQLite `json_tree`: https://www.sqlite.org/json1.html
2. Snowflake recursive `FLATTEN` for path profiling: https://docs.snowflake.com/en/user-guide/querying-semistructured
3. MRSQLGen: https://doi.org/10.1145/3797146
4. SpotIt+: https://arxiv.org/abs/2603.04334
5. TraceSQL: https://arxiv.org/abs/2608.17795
6. FlexSQL: https://arxiv.org/abs/2605.02815
Summarize overlap and any *specific, defensible* remaining distinction with links. Do not claim novelty simply because FlexSQL lacks a named tool.

## Hard constraints
- **ZERO external LLM/API calls** (Gemini, Groq, OpenAI, etc.). Do not rerun FlexSQL or launch vLLM. Do not use paid services.
- Reuse saved programs, results, traces, frozen SQLite fixtures, and local tooling only. Do not modify upstream FlexSQL, gold answers, fixtures, original traces, or Phase 0 labels.
- Do not access gold answers or failure labels in detector logic. They may be used **only after the detector is frozen**, by a separate evaluation script. Avoid case-specific heuristics, manually inserted ground-truth path aliases, or leaking the right answer.
- Do not assert that merely executing valid SQL, having non-null values, or finding another path proves correctness. Optional fields, legitimate filters, joins, and semantically unrelated similarly named fields create false positives.
- Do not assert that full-column `json_tree` scanning is computationally cheap for large warehouses. Separate output-token size from database scan cost.
- Work in `research/phase1_offline/`. Do not delete or overwrite existing research artifacts.
- **Time-box the preflight. If the eligibility gate fails, STOP without implementing a validator.** Avoid unrelated refactors, benchmarking new models, and UI building.

## Stage A — Preflight feasibility audit (mandatory; do before coding)
1. Inventory all 24 saved baseline runs: final program kind (SQL, Python, mixed), path usage, known joins/filters, parsing artifacts, ability to replay locally, and whether required data lineage can be recovered. Inspect representative passing and failing traces.
2. For the 9 A/B cases, determine **how many can reasonably be assessed** without gold SQL/answers and without semantic field mappings provided by the test creator. Identify why any cannot be assessed. Cover both SQL and Python or explicitly quantify exclusions.
3. Identify at least 8–12 legitimate success/control situations likely to mislead a naive coverage check: intentionally optional fields, null values, irrelevant alternate paths, deliberate filtered subsets, array rows, unrelated fields sharing terminal key names, and valid join restrictions. Prefer existing Phase 0 successes, adding independent local synthetic controls where needed.
4. Write `research/phase1_offline/PREFLIGHT.md` covering: exact input available at inference time; features deterministically extractable; what requires understanding user intent; supported program types; likely false-positive modes; related work; and a go/no-go judgment.
5. **Stop if:** fewer than 5 of the 9 A/B failures are technically eligible for meaningful reference-free analysis; detection would require reading gold answers or hardcoded case-specific path aliases; or the proposed check would only reproduce a standard schema profiling query with no distinct behavioral test. Say `STOP: LOW RESEARCH VALUE` with reasons. Do not proceed to Stage B.

## Stage B — Small offline diagnostic (only if Stage A passes)
Implement the *smallest* defensible diagnostic. NOT an agent and NOT an automatic SQL rewriter.

Input: original generated program; relevant database/JSON column; optional original NL question as text; standard metadata/data allowed in inference. Output one of:
- `SUSPICIOUS`: a specific, defensible omitted-path or missing-coverage hypothesis, with supporting database counts and row IDs.
- `NO_EVIDENCE`: no supported warning found; **not** a certificate of correctness.
- `ABSTAIN`: cannot assess the query safely (complex joins, Python operations, unknown semantics, optional fields, etc.).

Suggested diagnostics to *evaluate*, not assume effective:
- Extract actual JSON path references from SQL AST or appropriately scoped Python AST. Prefer existing parsers; avoid brittle regex-only extraction.
- Use `json_tree`, `json_type`, and simple counts on correctly scoped rows where scope is unambiguously recoverable.
- Find incompatible or alternative JSON shapes and report their support. Distinguish missing vs JSON null, numeric strings vs numbers, repeated array elements, and per-row vs per-element counts.
- Report potentially omitted variants as **hypotheses**, not automatically equivalent business fields. An identical leaf name in two paths does not prove identical meaning.
- If the source query is an aggregate, do not infer which rows *should* be included merely from low path coverage. If the selected population cannot be reconstructed reliably, `ABSTAIN`.

Do **not** create a hardcoded synonym dictionary based on the benchmark. If aliases are supplied as explicit metadata, evaluate this separately as an `alias-assisted` diagnostic rather than claiming it is reference-free without supervision.

## Stage C — Blind evaluation (only if Stage B succeeds)
1. Freeze detector code and configuration, save hashes. Only now load `failure_labels.json`, saved results/gold, and `results.csv` for scoring.
2. Score the existing 9 A/B failures as targets, 12 correct runs as negative controls, and the 3 E/artifact failures separately (do not count E as path-coverage wins). Test additional independent benign controls.
3. Report detection counts, false positives, abstentions, eligible coverage, precision/recall **with denominators**, and concrete examples. Avoid headline percentages without raw numbers.
4. Compare to two zero-cost baselines: (i) always warn on any missing JSON path; (ii) plain `json_tree` profile / raw NULL-rate heuristic. If the new detector provides no practical benefit, stop.
5. Conduct one small held-out or independently generated schema variation test, if possible, without using its answers during detector design. A detector crafted solely to the original fixtures is not credible.
6. Write `research/phase1_offline/RESULTS.md` and a reproducible offline command. Never claim an end-to-end FlexSQL improvement: this stage only evaluates diagnostic signal.

## Final decision / stopping criteria
Give an explicit `STOP`, `PIVOT`, or `CONDITIONAL GO`.
- **STOP:** Preflight is infeasible; obvious false positives; baseline `json_tree`/NULL-rate is equally effective; the checker needs gold/benchmarked aliases; or prior work already subsumes the proposed contribution.
- **PIVOT:** Useful engineering diagnostic but no credible novelty; package it as a small portfolio artifact instead of treating it as a paper.
- **CONDITIONAL GO:** A reference-free, explainable diagnostic identifies a meaningful fraction of A/B omissions while rarely warning on legitimate successful/control queries, abstains when uncertain, and outperforms simple checks. Even then, this is only a *feasibility* result, not published-level novelty or a proven end-to-end gain.

Use the following provisional, **non-publication** gate as a sanity threshold (and always report actual counts): at least 5 of the 9 A/B failures must be evaluable; the diagnostic should flag at least 4 of those 9 while producing no more than 2 false warnings among the 12 correct runs, and should not fail the independent negative controls. If this is not feasible without benchmark-specific assumptions, STOP. These cutoffs are practical screening criteria, not statistical guarantees.

## Final deliverables
- `research/phase1_offline/PREFLIGHT.md` — create always.
- `research/phase1_offline/RESULTS.md` and tiny code/tests — **only** if the preflight passes.
- `research/phase1_offline/DECISION.md` — create always, with evidence, related-work overlap, limitations, your best counterargument, and whether this is worth the owner's limited time before University of Alberta applications.

End with a concise verdict; list exactly what ran and what did not. **No API calls, no more spending, no feature creep, no predetermined positive conclusion.**
