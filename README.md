# FlexSQL on heterogeneous JSON: baseline audit and a negative diagnostic result

This study asks whether the FlexSQL text-to-SQL agent ([paper](https://arxiv.org/abs/2605.02815), [code](https://github.com/StringNLPLAB/FlexSQL)) fails silently when the JSON columns it queries contain rare or alternative structures. It also asks whether a cheap, reference-free check could catch those failures.

**Status (2026-10-19):** both phases are complete. The pre-registered protocol and decision criteria for each phase are in [research/PROTOCOL.md](research/PROTOCOL.md).

| Phase | Result |
|---|---|
| Phase 0: baseline evaluation | FlexSQL fails silently on rare JSON variants. The failures get worse as the variant gets rarer. |
| Phase 1: offline diagnostic | Verdict **STOP**. The proposed check fails its own negative controls. |

## Key findings

### Phase 0: baseline audit
Full report: [research/phase0/PHASE0_REPORT.md](research/phase0/PHASE0_REPORT.md).

**Setup**
- Unmodified upstream FlexSQL at commit `0ff2f51`.
- 30 synthetic questions over 7 deterministic SQLite databases, each with an independently validated answer key.
- Proxy model `gemini-3.1-flash-lite`, with reduced planning (2 plans, 1 self-evaluation round).
- Budget-limited: 24 of 30 questions ran, 1 trial each. Total spend about $4.8.

**Results**
- **12 of 24 answers are correct.** All 12 wrong answers are silent: the program runs and returns a plausible number.
- Root causes of the 12 failures:

  | Code | Count | Meaning |
  |---|---|---|
  | A | 7 | required JSON path never observed |
  | B | 2 | path observed but not used |
  | E | 3 | JSON parsing artefact |

- **Rarity ladder.** The same question was asked over identical canonical data with different shares of alternative-format records. It was correct at 0% and 20%, and wrong at 5% and 1%. Both wrong answers equal the naive single-path answer.
- **Discovery tools already exist.** One ordinary SQLite `json_tree` path-frequency query exposes every required structure in 18 of 18 heterogeneous cases. FlexSQL never issued one. Injecting that profile into one failing run did not fix it (n = 1).

**Upstream behaviours that confound JSON results on SQLite** ([UPSTREAM_AUDIT.md](research/phase0/UPSTREAM_AUDIT.md))
- **Python-repr display.** JSON is shown to the model as Python dicts. As a result, 51% of the generated programs parse with `ast.literal_eval`, which fails silently on JSON `null`.
- **sqlglot rewrite.** A rewrite changes `json_extract` into `->`, which alters SQLite comparison semantics.
- **Biased sampling.** `get_distinct_values` sorts before sampling.
- **Tie-break voting.** With 2 candidates, majority voting reduces to a tie-break.

### Phase 1: zero-API diagnostic gate
Documents: [PREFLIGHT.md](research/phase1_offline/PREFLIGHT.md), [RESULTS.md](research/phase1_offline/RESULTS.md), [DECISION.md](research/phase1_offline/DECISION.md).

The candidate check replays each saved program offline, traces which JSON keys it actually reads, and flags in-scope rows that it read nothing from **and** whose structure appears in no row it did read. The detector was frozen (hashes recorded) before evaluation, and labels are read only by a separate scorer.

| | detector | naive baselines (3) |
|---|---|---|
| A/B failures flagged | 9/9 | 9/9 |
| false warnings, Phase 0 correct runs | 0/12 | 5–8/12 |
| false warnings, independent benign controls (synthetic + held-out) | **7/17** | 11–17/17 |

**Why STOP**
1. Every naive baseline also catches all 9 targets.
2. The false warnings come from rows of an *irrelevant* type with a different schema. These produce the same execution trace as a real omission, so telling them apart needs semantic intent.
3. A lexical question-matching variant removes the false warnings but misses the held-out targets.
4. Novelty against three recent papers (MRSQLGen, SpotIt+, TraceSQL) was not verified.

## Repository layout

```
research/
  PROTOCOL.md               study protocol, integrity rules and decision criteria (both phases)
  phase0/
    PHASE0_REPORT.md        main report (GO/PIVOT/NO-GO analysis, verdict PIVOT)
    failures.md             per-failure trace evidence and root-cause labels
    results.csv             one row per executed question
    UPSTREAM_AUDIT.md       upstream code audit and defects
    environment.md          versions, provider compatibility, spend log
    fixtures/               generator, SQLite databases, questions, gold answers + FROZEN.sha256
    harness/                observation/compat shim (tracing, top_k drop, Gemini thought signatures)
    scripts/                runner, scorer, controls, aggregation
    traces/baseline/        saved FlexSQL runs: programs, logs, LLM traces, votes
    diagnostics/            tool-level controls and the single diagnostic run
  phase1_offline/
    PREFLIGHT.md  RESULTS.md  DECISION.md
    preflight/inventory.py  offline replay of all 48 saved candidate programs
    detector/               jcov.py + unit tests
    controls/               synthetic benign/target scenarios and held-out schema variation
    eval/                   run_all.py (no labels), baselines.py, score.py (labels only here)
    FREEZE.sha256           frozen detector/controls hashes
```

## Reproduce

Requirements: Python 3.12 and [uv](https://github.com/astral-sh/uv). Phase 1 needs no API key. Phase 0 runs need a Gemini key in `.env` (see `.env.example`).

```bash
git clone https://github.com/StringNLPLAB/FlexSQL upstream/FlexSQL
git -C upstream/FlexSQL checkout 0ff2f5107d80ea3bf92b6e12ddf61dfa2a925b68
uv venv --python 3.12 .venv-phase0
uv pip install --python .venv-phase0/Scripts/python.exe chardet==7.4.3 cloudpickle==3.1.2 numpy==2.1.3 \
  openai==1.99.4 openai-harmony==0.0.8 pandas==2.2.3 parso==0.8.6 python-dateutil==2.9.0.post0 \
  snowflake-connector-python==4.4.0 sqlglot==28.10.1 geopandas==1.1.2 networkx==3.6.1 httpx==0.28.1
PY=.venv-phase0/Scripts/python.exe; export PYTHONDONTWRITEBYTECODE=1

# Phase 1 (offline, uses the saved Phase 0 traces)
$PY research/phase1_offline/preflight/inventory.py
$PY research/phase1_offline/eval/run_all.py
$PY research/phase1_offline/eval/score.py

# Phase 0 (paid API calls; see research/phase0/environment.md)
$PY research/phase0/fixtures/generate.py
$PY research/phase0/scripts/run_flexsql.py --arm baseline --cases all --trials 1
$PY research/phase0/scripts/score_runs.py --arms baseline
```

## Limitations

- **Proxy setup.** One cheap proxy model and reduced agent settings were used, not the paper's configuration. These results are not a reproduction of the published numbers.
- **Small and synthetic.** 1 trial per question, 24 executed questions, synthetic data.
- **Same author throughout.** The fixtures, labels, controls and detector were all built by the same author. The held-out set is new data, not independent authorship.
- **No end-to-end test.** It was not tested whether detector warnings would change the agent's answers.
