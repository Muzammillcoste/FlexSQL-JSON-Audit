# Study protocol

This file records the protocol fixed before each phase ran: the research question, integrity rules, procedure and decision criteria. Results are in [phase0/PHASE0_REPORT.md](phase0/PHASE0_REPORT.md) and [phase1_offline/DECISION.md](phase1_offline/DECISION.md).

**Research question.** Can uncertainty-aware exploration of heterogeneous JSON columns improve the planning and execution accuracy of FlexSQL-style text-to-SQL agents under constrained exploration budgets?

References:
- FlexSQL paper: https://arxiv.org/abs/2605.02815 (section 3 and appendix F: JSON/VARIANT execution is already supported, so lack of JSON support is not a claim this study can make)
- FlexSQL code: https://github.com/StringNLPLAB/FlexSQL

**Scope.** Semi-structured JSON and JSON stored as text. Out of scope: semantic search, multimodal data, regex generation, and building a replacement SQL agent. All benchmark data is synthetic and non-sensitive.

## Integrity rules (both phases)

1. Pin the upstream commit SHA, environment, entry point, dialect, model name/version, inference settings and harness configuration. Leave upstream files unchanged; all instrumentation and fixtures live under `research/`. Modified upstream code is not eligible for an "unmodified baseline" claim.
2. A model or harness different from the paper's is a **proxy baseline**, labelled as such, and never described as a reproduction of published results.
3. If execution is blocked (credentials, compute, datasets, tooling), report **BLOCKED** with the missing prerequisite. Never substitute another agent, a plain SQL script or a direct model prompt for FlexSQL.
4. No secrets in files or logs (`.env` is gitignored; see `.env.example`). No unbounded paid API runs.
5. Gold answers are computed deterministically and independently of the agent. Fixtures and labels are frozen (hashed) before results are viewed; any later change is recorded.
6. Keep the full observable trace: tool calls, sanitized inputs/outputs, generated SQL/Python, errors, answer, duration, tokens/cost where reported. Only visible tool calls and outputs are collected, never hidden model reasoning.
7. Keep failed, incomplete and timed-out runs. No selective retries of failures. Single runs are exploratory, not statistically conclusive.

## Phase 0: baseline audit of unmodified FlexSQL

Goal: establish whether real, reproducible FlexSQL failures stem from insufficient *discovery of relevant JSON structure*, rather than SQL syntax, model reasoning, orchestration or a broken setup. No schema-exploration extension is built in this phase.

### A. Upstream audit
- Record SHA, license and run instructions; inspect agent code, prompt templates, tools, SQLite support, model APIs, schema discovery, Python executor and logging.
- Check behaviour on JSON stored as TEXT, SQLite JSON1, nested paths, arrays, missing/null values, and whether the agent can explore recursively with arbitrary SQL or Python.
- Confirm the same agent can be driven over custom local SQLite databases, without weakening its exploration behaviour.
- Smoke tests: environment, one relational question, one JSON question.
- SQLite JSON behaviour is not equated with Snowflake VARIANT/FLATTEN.

### B. Controlled benchmark
Deterministic generator with fixed seeds and documented gold answers; at least 30 questions split across three tiers.

- **Medium (M):** predictable nested objects, arrays, JSON strings, missing keys, numbers as strings, mixed relational and JSON predicates.
- **Hard (H):** versioned payloads with 3–6 alternate paths for one field, type conflicts, mixed arrays/objects, sparse fields, joins, overlapping keys with different meanings, deduplication, partial/malformed JSON.
- **Hardest (X):** rare but consequential variants (0.1–1%), schemas changing by time or source, skew, nested multi-entity arrays, decoy paths, null-versus-absent, exact counts or sums.

Some question pairs share the same wording and task logic and vary only in schema heterogeneity/rarity (the "rarity ladder"), enabling causal diagnosis. Business rules (currency normalization, status semantics, deduplication) are stated explicitly; no answer is hinted in the question, context or metadata.

### C. Runs and recording
Per (case, run, configuration): scenario, tier, paths present, variant counts and rarity, seed, question, gold, final answer, correctness, executed program, errors, explored paths, whether the crucial path was observed and whether it was used, wall time, tool calls, tokens and cost (null where unavailable).

Failure causes are distinguished as schema discovery, path interpretation/mapping, SQL generation, type conversion, query semantics, orchestration, and environment/provider. Metrics: exact accuracy by tier, false-success rate, path recall against an oracle, discover-to-use conversion, and tool/cost budget. Small-n results are reported as counts.

### D. Controls (diagnostic, not the baseline)
For representative discovery failures:
1. unmodified baseline;
2. larger exploration budget via supported configuration;
3. **oracle schema hint**: relevant paths supplied through a documented context route, with no gold answer;
4. **conventional discovery**: an ordinary SQL/Python path enumeration (e.g. `json_tree`) exposed through the same channel.

If the oracle hint does not improve the outcome, the failure is unlikely to be solely missing path discovery. If ordinary enumeration cheaply fixes it, a custom inspector is an engineering opportunity rather than a research contribution.

### E. Decision
- **GO:** multiple reproducible discovery misses with trace evidence, ideally growing with rarity, and oracle hints recover some of them.
- **PIVOT / INCONCLUSIVE:** failures mainly due to SQL generation or semantics, proxy-only harness, or too few repetitions.
- **NO-GO:** few discovery misses, or all fixed cheaply with existing exploration.

Outcome: **PIVOT** (see [phase0/PHASE0_REPORT.md](phase0/PHASE0_REPORT.md)).

## Phase 1: zero-API diagnostic gate

Phase 0 showed that a standard `json_tree` profile exposes every required path, so generic schema inference, recursive key listing and semantic search were dropped. The one remaining candidate: a **reference-free, low-cost diagnostic for silently incomplete JSON queries**. Given a generated program, the database and optionally the question, can likely omission of relevant JSON variants be detected *without* the correct answer or gold SQL?

Constraints: zero LLM/API calls and no paid services; reuse saved programs, traces and frozen fixtures only; do not modify upstream, gold, fixtures, traces or Phase 0 labels. Gold answers and failure labels are read only after the detector is frozen, by a separate scorer. No case-specific heuristics or benchmark-derived alias dictionaries. Valid SQL, non-null values or the existence of another path are not treated as proof of correctness or error.

Prior work to compare before coding: SQLite `json_tree`, Snowflake recursive `FLATTEN`, MRSQLGen (https://doi.org/10.1145/3797146), SpotIt+ (https://arxiv.org/abs/2603.04334), TraceSQL (https://arxiv.org/abs/2608.17795), and FlexSQL itself.

### Stage A: preflight feasibility audit
1. Inventory all 24 saved baseline runs: program kind, path usage, joins/filters, parsing artefacts, local replayability, recoverable lineage.
2. Determine how many of the 9 A/B failures can be assessed without gold answers or creator-supplied field mappings.
3. Identify 8–12 legitimate situations likely to mislead a naive coverage check: optional fields, nulls, irrelevant alternate paths, deliberate filters, array rows, unrelated fields sharing leaf names, valid join restrictions.
4. Write [phase1_offline/PREFLIGHT.md](phase1_offline/PREFLIGHT.md).

**Stop** if fewer than 5 of the 9 A/B failures are eligible, if detection needs gold answers or case-specific aliases, or if the check only reproduces a standard profiling query.

### Stage B: minimal offline diagnostic
Not an agent and not a SQL rewriter. Output per program:
- `SUSPICIOUS`: a specific omitted-path hypothesis with supporting counts and row IDs;
- `NO_EVIDENCE`: no supported warning (not a certificate of correctness);
- `ABSTAIN`: cannot assess safely.

Omitted variants are reported as hypotheses; an identical leaf name in two paths does not prove identical meaning. If the selected row population cannot be reconstructed reliably, the detector abstains.

### Stage C: blind evaluation
1. Freeze detector code and configuration and record hashes ([phase1_offline/FREEZE.sha256](phase1_offline/FREEZE.sha256)). Only then load labels and gold.
2. Score the 9 A/B failures as targets, the 12 correct runs as negative controls, and the 3 E (parsing) failures separately; add independent benign controls.
3. Report detections, false positives and abstentions with denominators.
4. Compare to zero-cost baselines: always warn on any missing JSON path; plain `json_tree` profile / NULL-rate heuristic.
5. Run one held-out schema variation not used during design.
6. Write [phase1_offline/RESULTS.md](phase1_offline/RESULTS.md).

### Decision criteria
- **STOP:** infeasible preflight, obvious false positives, baselines equally effective, need for gold or benchmark aliases, or prior work subsumes the idea.
- **PIVOT:** useful engineering diagnostic without credible novelty.
- **CONDITIONAL GO:** flags a meaningful fraction of A/B omissions, rarely warns on legitimate queries, abstains when uncertain, and beats the simple baselines. Even then, a feasibility result only.

Screening threshold (practical, not statistical): at least 5/9 A/B failures evaluable; at least 4/9 flagged; at most 2 false warnings among the 12 correct runs; no failures on independent negative controls.

Outcome: **STOP** (see [phase1_offline/DECISION.md](phase1_offline/DECISION.md)).
