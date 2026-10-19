# FlexSQL JSON Exploration Gap Study — Master Research Protocol

**Phase:** 0, baseline verification only  
**Research question:** Can uncertainty-aware exploration of heterogeneous JSON columns improve the planning and execution accuracy of FlexSQL-style text-to-SQL agents under constrained exploration budgets?

## Mission and decision rule

First test **unmodified upstream FlexSQL**. We are not authorized to build a new schema-exploration tool during Phase 0. We must establish whether real, reproducible failures stem from missing or insufficient *discovery of relevant JSON structure*, rather than incorrect SQL syntax, model reasoning, orchestration, or a broken setup. A failed easy example is not proof of a new research gap, and success on a small benchmark does not disprove all possible gaps.

Authoritative references:
- Paper: https://arxiv.org/pdf/2605.02815 (especially section 3 and appendix F, pp. 17–18)
- Code: https://github.com/StringNLPLAB/FlexSQL
- Upstream README describes a SQLite/Spider2-Lite option and Snowflake pipeline. The exact runnable harness must be confirmed from inspected code, not assumed.

**Scope:** Semi-structured JSON and JSON-in-text, not semantic search, multimodal data, regex generation, or building a replacement SQL agent. All benchmark data must be synthetic/non-sensitive.

## Non-negotiable scientific integrity

1. Pin upstream commit SHA, environment, code entry point, database dialect, model name/version, inference settings, and prompt/harness configuration. Keep upstream files unchanged when possible. All instrumentation and test fixtures belong under a clearly separated study directory. Save a diff if modification is unavoidable; modified upstream code is not eligible for an "unmodified baseline" claim.
2. Inspect whether the released repository actually implements the paper's agent and tool behaviors. The published experiments use a particular local model/compute setup; a different API model or harness constitutes a **proxy baseline** and must be explicitly labeled, never described as reproduction of published results.
3. If execution is blocked by missing credentials, costly GPU/model access, dataset files, unsupported tools, or inaccessible resources: report **BLOCKED**, document the missing prerequisite and smallest next step. Never invent results, run counts, outputs, tool traces, or paper claims. Do not silently replace FlexSQL with a new agent, plain SQL script, or direct model prompt.
4. No secrets in files or logs. Use environment variables/.env.example only; add secrets to .gitignore. Do not push anything remotely or create cloud spend without explicit permission. No unbounded paid API runs.
5. Ground truth must be calculated deterministically and independently of the agent. Save queries/scripts plus expected results. Freeze test fixtures and labels before viewing results, and identify any later changes to avoid benchmark overfitting.
6. Preserve full observable trace (tool name, sanitized input/output, discovered paths, generated SQL/Python, errors, execution, answer, duration, tokens/cost if reported). Never claim access to hidden model chain-of-thought; collect only visible tool calls, generated plans, and final outputs.
7. Keep failed, incomplete, and timed-out runs. Do not silently retry only failures or cherry-pick successes. Record model variability; at least two/three repeats for diagnostic cases if feasible under approved costs. Single runs are exploratory, not statistically conclusive.

## Phase 0 workflow

### A. Audit the upstream baseline
- Clone/fetch official repo, record SHA/license and instructions; inspect relevant agent code, prompt templates, tool implementations, SQLite compatibility, model APIs, schema discovery, Python executor, and logging options.
- Check actual functionality for JSON string columns, SQLite JSON1 support, nested paths, array traversal, missing/null handling, and ability to explore recursively with arbitrary SQL or Python.
- Determine whether the *same agent* can be driven over our custom local SQLite database. Prefer the real published agent's existing SQLite path. If it requires Spider2-Lite metadata, create compliant fixture metadata without weakening or bypassing its exploration behavior; report all setup differences.
- Run smoke tests: environment, one normal relational question, one JSON question; stop and report setup issues instead of simulating successes.
- If Snowflake is essential for a specific feature, mark SQLite equivalence limitations. Do not equate SQLite JSON behavior with Snowflake VARIANT/FLATTEN/transpilation.

### B. Construct a controlled benchmark
Create a deterministic generator with fixed seeds and documented gold answers. Aim for **at least 30 distinct questions** overall once the harness works, distributed across medium, hard, and hardest cases (e.g. 10 each). Start with 2–3 smoke cases before scaling. Provide both aggregates and row-level examples. Build datasets at manageable sizes first; choose larger data only when feasible and needed to test rare variants.

**Medium (M):** predictable nested objects, arrays, JSON strings, missing keys, number-as-string, multiple straightforward paths; mixed relational and JSON predicates.

**Hard (H):** versioned API payloads with 3–6 alternate paths for the same field; type conflicts; mixed arrays/objects; sparse fields; joins to relational dimensions; overlapping keys with different meanings; repeated records requiring deduplication; partial and malformed JSON where appropriate.

**Hardest (X):** rare but consequential variants (e.g. 0.1–1%), schemas that change across time or tenant/source, highly skewed records, nested arrays with multi-entity semantics, decoy paths, null-versus-absent distinctions, and questions requiring *exact* counts or sums in spite of incomplete samples. Balance task complexity and scale; isolate rare-schema discovery from arithmetic or ambiguous user wording.

At least some pairs must share the **same natural language query and task logic** but vary only in schema heterogeneity/rarity, enabling causal diagnosis. A test must not depend on undocumented business rules; explicitly define currency normalization, status semantics, deduplication and ground truth. Make deliberate adversarial cases but do not hardcode an answer into the prompt, agent context, or metadata.

### C. Run and record actual agent tests
Use the real FlexSQL agent and its available tools under fixed model/prompt/budget settings. Randomize or interleave case order when viable. Save outputs per (case, run, configuration). For every case capture:
- scenario, difficulty, size, paths present, variation counts and rarity, seed, question, gold answer
- final answer, correctness (normalized appropriately), executed query, SQL/Python errors, timeout/failure status
- explored tool paths, whether crucial path was observed in a tool result, whether it was used in the final query
- approximate wall time, tool calls, prompt/completion tokens and cost where observable; leave unavailable fields null
- failure reason, citing concrete trace evidence. Distinguish **schema discovery**, **path interpretation/mapping**, **SQL generation**, **type conversion**, **query semantics**, **orchestration**, and **environment/provider**.

Measure exact answer accuracy by tier, plus false-success rate (valid query returning wrong answer), schema coverage/path recall versus oracle, discover-to-use conversion, and tool/cost budget. For tiny n, show counts and avoid over-interpreting percentages.

### D. Essential controls (do not build extension)
For each representative reproducible *schema-discovery* failure, run:
1. **Unmodified baseline** with normal exploration.
2. **More exploration budget** using supported config only, if available.
3. **Oracle schema hint** (diagnostic upper bound): provide the relevant nested JSON paths and meaning through a documented prompt/context route, with no gold answer; clearly mark this as a non-baseline intervention.
4. **Simple conventional discovery control**: a separate existing SQL/Python approach to enumerate paths and counts (e.g. JSON traversal, recursive extraction) and, if permitted, expose its results to the agent via the same documented context channel. Do not present this as a new tool or original baseline.

If the oracle hint does not improve the outcome, the failure is unlikely to be *solely* missing path discovery. If ordinary exhaustive path enumeration cheaply fixes the issue, a custom inspector is an engineering opportunity, but an uncertainty-aware algorithm still needs a distinct budget/accuracy improvement to be research-worthy.

### E. Go/no-go decision
Classify the outcome:
- **GO / INVESTIGATE:** multiple reproducible schema-discovery-related misses with trace evidence, preferably increasing with rarity/heterogeneity, and oracle hints meaningfully recover some errors; simple full scans have costs or budget limitations worth studying.
- **PIVOT / INCONCLUSIVE:** observed failures mainly due to SQL generation/semantics, or only proxy harness accessible, or insufficient repetitions/statistical strength.
- **NO-GO FOR THIS GAP:** few/no meaningful discovery misses, or all failures solved cheaply with existing exploration, or proposed intervention would not offer a measurable advantage. This does not rule out other research.

Do not invent fixed improvement targets as results; propose a threshold for a next-stage intervention only after observing baseline reliability and uncertainty.

## Required repository outputs
Use `research/phase0/` inside study repo/worktree (or a separate study workspace referencing the immutable upstream checkout):

```
research/phase0/
  ENVIRONMENT.md               # commit, model, dependencies, hardware, backend
  UPSTREAM_AUDIT.md            # real tools, entry points, limitations, evidence with file:line
  SETUP.md                     # copy-paste commands, exact run steps
  fixtures/                    # deterministic generator, seeds, schema, databases if small
  cases.jsonl                  # case IDs, questions, metadata, oracle definitions
  gold/                        # independent reference scripts + expected results
  scripts/                     # runnable evaluation and scoring utilities
  runs/                        # raw/sanitized traces; never secrets
  results.csv                  # one row per execution; explicit status and nulls
  FAILURE_ANALYSIS.md          # cause-backed examples, non-failures, confounds
  PHASE0_REPORT.md             # summary, evidence table, limitations, verdict
```

`PHASE0_REPORT.md` must answer:
1. Was **actual upstream FlexSQL** run? Which SHA, entry point, model and dialect? If no, exactly why?
2. How many medium/hard/hardest cases and repeats actually ran vs planned?
3. Which questions failed, and were they errors or silently wrong outputs?
4. Is any failure specifically attributable to undiscovered nested schema paths? Show trace and gold.
5. Do extra-budget/oracle-path/simple-enumeration controls support that diagnosis?
6. What would a next study have to beat, and what is the explicit GO / PIVOT / NO-GO recommendation?

**Stop after Phase 0 and request user review.** Do not implement `ExploreJSONSchema`, uncertainty estimator, semantic search, or other proposed extension. Scientific credibility beats impressive-looking results.
