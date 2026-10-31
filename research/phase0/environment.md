# Environment, setup and provider compatibility (Phase 0)

## Versions

| Item | Value |
|---|---|
| Host | Windows 11 Pro 10.0.26200 (x64), Git 2.53.0 |
| Upstream | `upstream/FlexSQL` @ `0ff2f5107d80ea3bf92b6e12ddf61dfa2a925b68` (unmodified; see UPSTREAM_AUDIT.md) |
| Python | 3.12.13 (uv-managed venv `.venv-phase0`; upstream requires >=3.12) |
| SQLite | 3.50.4 (JSON1, `json_tree`, `->`/`->>` available) |
| Packages (pinned to upstream `uv.lock`) | openai 1.99.4, openai-harmony 0.0.8, pandas 2.2.3, numpy 2.1.3, sqlglot 28.10.1, snowflake-connector-python 4.4.0, cloudpickle 3.1.2, chardet 7.4.3, parso 0.8.6, python-dateutil 2.9.0.post0, geopandas 1.1.2, networkx 3.6.1, httpx 0.28.1 |
| Not installed | `vllm==0.13.0` and `transformers==4.57.6`. These are used only for local model serving, are not imported by any agent code path, and have no Windows build. `python-dotenv` is not installed either; upstream then falls back to its own minimal `.env` loader, and no `.env` exists in the upstream directory. |
| Model (primary baseline) | `gemini-3.1-flash-lite`, Gemini OpenAI-compatible endpoint `https://generativelanguage.googleapis.com/v1beta/openai/` |
| Request params | upstream defaults (`src/chat.py:513`): temperature 1.0, top_p 1.0, reasoning_effort "high"; `extra_body.top_k=-1` dropped (see below); per-agent gen configs `{"temperature": 1.0}` as in the README |
| Agent config | `--use_2step_batch_planning --planning_top_k 2 --planning_batch_size 2 --num_programs 1 --max_self_eval_rounds 1 --db_type sqlite --workers 1`; answer = upstream `utils/major_voting.py --fuzzy_threshold 0.90 --allow_superset` |
| Budget | 5 USD total, user-imposed. Hard caps in the runner: 2.00 USD for all baseline runs and 0.20 USD per run (the run is killed and recorded as budget-truncated when exceeded). Cost is estimated from traced token usage at list price. |

This is a **proxy baseline**. The paper uses locally served gpt-oss-120b/20b with 8 plans, 3 self-evaluation rounds and majority@8 or more. Phase 0 results are not a reproduction of published numbers.

## Setup (copy-paste)

```bash
cd "FlexSQL Research"
git clone https://github.com/StringNLPLAB/FlexSQL upstream/FlexSQL && git -C upstream/FlexSQL checkout 0ff2f5107d80ea3bf92b6e12ddf61dfa2a925b68
uv venv --python 3.12 .venv-phase0
uv pip install --python .venv-phase0/Scripts/python.exe chardet==7.4.3 cloudpickle==3.1.2 numpy==2.1.3 openai==1.99.4 \
  openai-harmony==0.0.8 pandas==2.2.3 parso==0.8.6 python-dateutil==2.9.0.post0 snowflake-connector-python==4.4.0 \
  sqlglot==28.10.1 geopandas==1.1.2 networkx==3.6.1 httpx==0.28.1
cp .env.example .env        # fill in GEMINI_API_KEY (or GEMINI_KEY); never commit
printf 'cache/\ninference_res/\n' >> upstream/FlexSQL/.git/info/exclude
PY=.venv-phase0/Scripts/python.exe
$PY research/phase0/fixtures/generate.py                     # deterministic fixtures + validated gold
$PY research/phase0/scripts/review_ground_truth.py
$PY research/phase0/scripts/existing_capability_controls.py  # tool-level controls, no LLM
$PY research/phase0/scripts/run_flexsql.py --arm baseline --cases pilot --trials 1
$PY research/phase0/scripts/run_flexsql.py --arm baseline --cases all --trials 1 --parallel 2
$PY research/phase0/scripts/score_runs.py --arms baseline   # -> results.csv + evidence.json per run
```

`run_flexsql.py` runs `python src/main.py ...` with cwd = the upstream checkout, one process per (case, trial), and checkpoints with `DONE.json`.

## Observation harness (not part of the agent)

`harness/sitecustomize.py` is put on `PYTHONPATH` and loads `harness/p0_trace.py` lazily into every FlexSQL process. The harness wraps `openai...Completions.create` and does four things:

1. **Trace.** Appends every request (message deltas, params, tool names) and response (content, tool calls, finish reason, usage, latency, model) to `llm_trace_<pid>.jsonl`. Key strings are scrubbed. Chain-of-thought is not available from the provider and is not claimed.
2. **Backoff.** Retries 429/5xx/connection errors with exponential backoff and resends the identical request. Daily-quota errors are flagged as provider failures.
3. **Compat transform 1: `top_k`.** Upstream sends `extra_body={"top_k": -1}`, a vLLM-only parameter. Gemini and Groq both reject it with HTTP 400 (`Unknown name "top_k"` / `property 'top_k' is unsupported`). `-1` means "disabled" in vLLM, so dropping the parameter is the closest equivalent.
4. **Compat transform 2: Gemini 3.x thought signatures.** Upstream `chat.py:416-426` rebuilds assistant tool-call messages without Gemini's `extra_content.google.thought_signature`, so Gemini 3.x returns HTTP 400 on the second turn (`Function call is missing a thought_signature`). The harness stores signatures by `tool_call.id` and re-attaches them **to a copy of the outgoing request**. Message content, tools, prompts and the stored conversation are not changed. Each call's trace records `thought_signatures_restored`.

No upstream file is modified (`git -C upstream/FlexSQL status --porcelain` is empty).

## Provider / model compatibility record

| Provider:model | Auth | Tool loop through upstream `Chat` | FlexSQL stitching on JSON | Decision |
|---|---|---|---|---|
| Gemini `gemini-2.5-flash` | OK | OK (after dropping top_k) | **Fails.** All 40 stitching calls of smoke case p0_M02 returned `finish_reason="function_call_filter: MALFORMED_FUNCTION_CALL"` with empty content. Replaying that request reproduced the failure 3/3 times with reasoning_effort=low, with temperature 0, without `python_interpreter`, and with `query_database` as the only tool; it disappears only with no tools at all. The case ended with a single wrong candidate. | Rejected (G: provider incompatibility) |
| Gemini `gemini-2.5-flash-lite` | 404 "no longer available to new users" | – | – | Unavailable (originally planned model) |
| Gemini `gemini-3.x-flash`, `flash-latest`, `flash-lite-latest` | OK | **Fails without shim**: 400 missing thought_signature. Works with compat transform 2. | 3.8-flash, 3.5-flash and 3.1-flash-lite: valid tool calls on the replay | 3.8-flash smoke: p0_M02 correct 4/4, but 196 calls, 1.14M tokens and ≈1.03 USD; p0_M01 ≈1.5 USD before it was stopped. Too expensive for the 5 USD budget. |
| Gemini `gemini-2.5-pro` | OK | OK | valid tool calls on the replay | Not used (cost) |
| Gemini **`gemini-3.1-flash-lite`** | OK | OK with shim (sum query answered "12") | valid `python_interpreter` calls on the replay | **Selected** (cheapest working model; user choice) |
| Groq `openai/gpt-oss-120b` (paper model) | OK | OK (after dropping top_k) | – | **Infeasible.** The account limit is 8,000 tokens/min (`x-ratelimit-limit-tokens: 8000`) and 1,000 requests/day, while a single FlexSQL request is often larger than 8K tokens. |

## Spend log

| Item | Model | Est. USD |
|---|---|---|
| Smoke p0_M01 + p0_M02 (rejected model) | gemini-2.5-flash | 0.15 |
| Smoke p0_M01 (stopped) + p0_M02 | gemini-3.8-flash | 2.57 |
| Probes / request replays (not all traced) | various | ≈0.1–0.2 |
| Baseline: 24 runs | gemini-3.1-flash-lite | 1.91 |
| Diagnostic: 1 run (diag_pathprofile) | gemini-3.1-flash-lite | 0.06 |
| **Total** | | **≈ 4.8 (cap 5.0)** |
