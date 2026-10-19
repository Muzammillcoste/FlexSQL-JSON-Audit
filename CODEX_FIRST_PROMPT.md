# Codex First Execution Prompt — FlexSQL Phase 0

Read and obey `MASTER.md` in full. This task is **baseline verification and research**, NOT feature development.

## Goal
Set up and run the **actual released FlexSQL agent** against a reproducible set of medium, hard, and hardest semi-structured JSON database questions. Decide whether it exhibits real failures caused by *insufficient exploration of heterogeneous nested JSON schema*, with evidence. If authentic execution is blocked, explicitly mark BLOCKED and explain how to unblock it. Never fake runs or substitute a custom agent.

Upstream: https://github.com/StringNLPLAB/FlexSQL
Paper: https://arxiv.org/pdf/2605.02815 (read section 3 and appendix F: JSON/VARIANT execution already exists, so do not claim lack of JSON support).

## Work steps (execute, not merely plan)

**Step 1 — Inspect and pin:** Clone/fetch upstream if needed; record exact SHA and audit README, license, source entry points, real agent tools, dataset metadata, LLM/provider integrations, and ability to run *custom SQLite cases*. Inspect actual code. Create `research/phase0/UPSTREAM_AUDIT.md` and `ENVIRONMENT.md` with file/line references. Identify the minimum real run command, requirements, credentials and estimated cost. Keep upstream code clean.

**Step 2 — Reproducible setup:** Install prerequisites using documented instructions, prefer existing `uv` environment. Avoid paid cloud/GPU resources without approval. Check SQLite JSON functions. Determine if the model endpoint is configured; do not leak keys. Create `SETUP.md`, `.env.example` if needed, and safe log capture. Run a regular relational and basic JSON smoke case using the real FlexSQL orchestration, not just SQL executed manually.

**Step 3 — Fixture suite:** Build seeded synthetic database fixtures and independent oracle scripts. Create at least 30 distinct benchmark questions if the harness is functional: 10 medium, 10 hard, 10 hardest. Include JSON stored as TEXT, nested keys, array paths, mixed types, aliases across API versions, rare 0.1–1% formats, misleading key names, sparse/null/malformed data, relational joins, exact sum/count tasks and same-query paired scenarios with controlled heterogeneity. Prefer bounded data sizes and fast local setup. Precompute gold without using the tested agent. Freeze case definitions and gold before evaluation.

**Step 4 — Baseline executions:** Actually invoke authentic FlexSQL on the fixtures, respecting the agent's own supported configurations. Start with 2–3 cases; if setup works and cost is acceptable, run the suite. Capture visible tool calls and outputs, SQL/Python, final answers, exact-match scoring, time and token/cost if exposed. Record all failures/timeouts and unknown fields explicitly. Do not claim paper-level replication if model/dialect/harness differs.

**Step 5 — Diagnose:** For reproducible failures, identify whether the necessary nested JSON path was absent from what the agent saw, present but ignored, or correctly mapped but implemented incorrectly. Where possible test documented extra-exploration budget, an explicitly labeled oracle-path hint, and ordinary SQL/Python recursive path enumeration. These are diagnostics, not the primary baseline. If budget or tooling constraints prevent controls, document those limitations.

**Step 6 — Report and stop:** Produce `research/phase0/PHASE0_REPORT.md`, `FAILURE_ANALYSIS.md`, `results.csv`, execution scripts, case/gold definitions and sanitized logs. Conclude with GO / PIVOT / NO-GO and evidence. State exact cases actually executed, not just generated.

## Mandatory reporting format
The final chat response and report should include:

- **Execution status:** REAL_FLEXSQL_RUN / PROXY_ONLY / BLOCKED; pinned commit, entry point, model/provider, dialect, count of completed cases and repeats.
- **Results table:** Medium/Hard/Hardest attempted, completed, correct, wrong-answer, runtime errors, blocked/timeouts.
- **Three trace-backed examples:** at least one successful case and failures when available; show question, gold, answer, crucial paths, tools called and what was missed.
- **Failure attribution:** schema-discovery vs planning/SQL vs environment; report uncertain assignments as uncertain.
- **Control results and conclusion:** did path hints or exhaustive enumeration help? is the problem important and distinct from existing SQL JSON traversal?
- **Next decision:** GO / PIVOT / NO-GO / INCONCLUSIVE, with precise rationale and recommended smallest next experiment.

## Operating rules
- Ask for user intervention only when essential (e.g. model/API credentials, missing authorized compute, costly Snowflake resources). Do not silently burn credits.
- Do not change FlexSQL's core prompts/logic to make it fail or succeed, or label a simplified version "original FlexSQL".
- Never invent results or call unexecuted generated cases tested.
- Do not build any schema exploration extension in this phase.
- If interrupted, leave the work reproducible and state exactly what remains.

**Begin with Step 1 immediately, then work through the remaining steps as resources permit.**
