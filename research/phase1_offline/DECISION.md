# Phase 1 decision

## Verdict: **STOP** (as a research direction)

**Do not invest further research time in "reference-free detection of silently incomplete JSON queries".** The code already built can be kept as a small engineering sample without further work. That is **not** a recommendation to keep developing it (see "Why not PIVOT").

## Evidence

1. **The preflight passed only on technical grounds** (PREFLIGHT.md §7):
   - 9/9 A/B failures are eligible, but only through dynamic replay of the generated Python; static analysis makes just 1/9 eligible;
   - no gold or aliases are needed;
   - the program-linked, row-level test is distinct from a `json_tree` profile.
2. **The target set is easy.** Every naive baseline also flags 9/9 A/B failures:
   - B1 any-missing;
   - B2 NULL-rate;
   - B3 `json_tree` heterogeneity.

   The detector's only advantage is specificity:

   | false warnings on | detector | baselines |
   |---|---|---|
   | Phase 0 correct runs | 0/12 | 5–8/12 |
   | synthetic benign controls | 5/14 | 10–14/14 |

3. **It fails the pre-stated negative-control condition.** It flagged 7 of 17 independent benign controls:
   - 5/14 synthetic;
   - 2/3 held-out.

   Six of the seven are one predicted class: in-scope rows of an *irrelevant* type with a disjoint schema. Real-world mixed event tables have exactly this property.
4. **That failure class cannot be fixed mechanically.** Target p0_H01 (v3 rows lack the guard key `object`) and benign C04 (heartbeat rows lack the guard key `type`) produce the same execution trace. Telling them apart needs to know what the question requires, which is the semantic judgement the brief told us to stop pursuing.
5. **The only arm that removes the false warnings does not generalise.** The lexical question-anchoring arm (0/29 false warnings):
   - misses both held-out targets (0/2, because "heart rate" ≠ `HR`);
   - matches Phase 0 only because those questions name fields such as "status" or "succeeded";
   - is close to FlexSQL's own keyword FindRows.
6. **There is no end-to-end evidence.** Phase 0 showed that injecting a complete `json_tree` path profile into FlexSQL did **not** fix p0_X_L1_r05 (n = 1). Whether a row-level warning would do better is untested, and testing it needs paid API runs.
7. **The Phase 0 benchmark cannot measure the critical quantity.** All of its heterogeneity is relevant by construction, so the favourable 0/12 is an optimistic measurement, not a real-world false-positive rate.

## Related-work overlap

| work | overlap | checked? |
|---|---|---|
| SQLite `json_tree` / Snowflake recursive `FLATTEN` | Full path and type profiling: discovery is solved. One query exposed every required structure in 18/18 Phase 0 cases. | yes (used locally / standard documentation) |
| FlexSQL (arXiv 2605.02815) | Has no coverage check. Its LLM self-evaluator approved wrong programs in 9/12 failing runs. That shows a gap, not a new principle. | code inspected |
| Why-not provenance (Chapman & Jagadish 2009; Herschel et al.); `mlinspect` (Grafberger et al.); Deequ completeness checks | Row lineage through filters, "which tuples went missing", and per-group drop reporting in pandas pipelines. This detector is an application of these ideas with JSON-shape grouping. | from memory, not re-checked |
| MRSQLGen (doi 10.1145/3797146), SpotIt+ (arXiv 2603.04334), TraceSQL (arXiv 2608.17795) | **Unknown.** Not read, because of the no-external-call constraint. TraceSQL is the highest risk of subsuming this. | **no** |

Defensible distinction, at most: tracing the JSON accesses an LLM-generated program actually executes, within the scope it defines, and contrasting by structure the rows it read nothing from. That is narrow, its novelty is unverified against three papers, and it is conceptually adjacent to well-established provenance work.

## Best counterargument (steel-man for continuing)

> "On real agent output the detector was 9/9 with correct, explainable hypotheses (row ids and the exact omitted paths, e.g. the 17 legacy rows in X_L1_r05) and 0/12 false warnings, clearly beating every naive check. The false warnings come from adversarial controls the same author wrote to break it, and a human dismisses '45 heartbeat rows unread' in seconds. As a triage aid with precision 13/20 it is useful, and an LLM relevance judge could filter the irrelevant-type warnings."

**Rebuttal.**
- The 0/12 comes from a benchmark with no irrelevant heterogeneity, and the 9/9 is matched by trivial baselines.
- "A human triages it" concedes the semantic step. An LLM relevance judge reintroduces API cost and the very self-evaluation that already failed in Phase 0, where the evaluator approved wrong programs in 9/12 failing runs.
- There is no end-to-end evidence of benefit.
- Novelty is thin even before reading the three unverified papers.
- With n = 9, 1 trial and synthetic data, nothing here would survive review as a contribution.

## Why not PIVOT or CONDITIONAL GO

- **CONDITIONAL GO** requires rarely warning on legitimate controls and not failing the independent negative controls. The primary rule fails that; the anchor arm fails on held-out data.
- **PIVOT** ("package it as a portfolio artifact") would spend more of the owner's time on polish. The artefact is already documented (PREFLIGHT, RESULTS, code, tests, frozen hashes). Extra packaging adds little and is not justified.

## Limitations of this decision

- Single author for fixtures, labels, controls and detector.
- Synthetic data; one proxy model; 1 trial.
- Three related papers unread.
- No paid run to test the end-to-end effect.

A different author's realistic mixed-type JSON benchmark could change the false-positive picture in either direction. Nothing here suggests it would favour the detector.

## Is it worth the owner's time before the University of Alberta applications?

**No further research time.** At most an hour to read PHASE0_REPORT.md and this file, if the owner wants to describe the project in a statement of purpose as a carefully run negative result.

That story would be: built a reproducible baseline audit; found real silent failures and upstream confounds (Python-repr display, the sqlglot `->` rewrite); pre-registered a diagnostic and controls; and stopped when it failed its own negative controls. Rigorous negative results, not a weak positive one, are the credible thing to show.

## What ran / what did not

**Ran (all offline, 0 API calls, 0 USD):**
- the Stage A replay inventory of all 48 candidate programs from the 24 Phase 0 runs (all replayed, all outputs reproduced);
- toy unit tests (6/6);
- the frozen detector, its anchor arm and 3 baselines on 46 items, twice (identical results);
- scoring.

**Did not run:**
- any LLM, FlexSQL or vLLM;
- any web or paper fetch;
- any end-to-end test of warnings in the agent loop;
- a fully independent (third-party) held-out set.
