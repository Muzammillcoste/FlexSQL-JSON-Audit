# Upstream FlexSQL audit (Phase 0)

Checkout: `upstream/FlexSQL` @ `0ff2f5107d80ea3bf92b6e12ddf61dfa2a925b68` (2026-09-11, "Change citation format for FlexSQL reference"), remote `https://github.com/StringNLPLAB/FlexSQL.git`. Working tree unmodified (`git status --porcelain` empty; run outputs `inference_res/` and `cache/` are excluded through `.git/info/exclude`, not by editing tracked files). The repository has **no LICENSE file**.

Paper: arXiv 2605.02815 (COLM 2026). Paper tool names map onto code as follows.

| Paper (Sec. 3) | Code | Where | Notes |
|---|---|---|---|
| GetSchema | `list_tables` | `src/tools.py:337` | Skipped for SQLite (`src/chat.py:656`). |
| GetTableCol | `list_columns` | `src/tools.py:415` | Reads the per-table metadata JSON, not the DB. SQLite: shows **2** `column_examples` (`tools.py:539-541`), each passed through `truncate_nested_data`. |
| GetColValues | `get_distinct_values` | `src/tools.py:72` | `SELECT DISTINCT col ... LIMIT 100` (`tools.py:99`). For a JSON column this returns up to 100 whole payloads, untruncated. |
| FindRows | `search_dimension_values` | `src/tools.py:131` | `LIKE` search, `LIMIT 5` (`tools.py:172`). |
| SQLExecutor | `query_database` | `src/tools.py:26` | Arbitrary SQL. Output goes through `execute_and_format_query_result` (`schema_linking.py:94`): the SQL is rewritten by sqlglot (`schema_linking.py:108` → `get_ddl.py:193`), and `LIMIT n_example_rows` is appended when the query has no LIMIT (`schema_linking.py:46-50`). Cells are truncated: JSON values are re-parsed and every string is cut to 200 chars, and lists longer than 3 are shown as `[e0, e1, '...', e_last]`. |
| PythonExecutor | `python_interpreter` | `src/tools.py:280` | Subprocess with pre-loaded `dfs` (the sub-query DataFrames) and a live read-only `conn`. Timeout 120 s (`tools.py:278`). |

## Pipeline as actually executed (`src/main.py`, `--use_2step_batch_planning`)

1. **Plan generation** (`planning.py:333`). The agent gets a table overview (table name and column count) and only `list_columns`; the data tools are removed (`planning.py:378`). It writes `planning_top_k` natural-language plans in batches of `planning_batch_size`.
2. **Plan clarification** (`planning.py:761`). This step has `list_columns`, `query_database`, `get_distinct_values` and `search_dimension_values` (`planning.py:798`), and is where the bulk of schema/data exploration happens. `query_database` uses the registry default `n_example_rows=1` (`chat.py:602`). So a query without its own `LIMIT` returns **one row**, even though the tool description says "20 example rows" (`tools.py:801`). The step outputs `{table: [columns]}`.
3. **Sub-SQL composition** (`planning.py:617`). For each table it builds `SELECT <cols> FROM <table>` (`schema_linking.py:368`). JSON columns are selected whole, with no JSON paths.
4. **Stitching** (`solution_writing.py:230`, hybrid mode). The model sees each sub-query plus **1** truncated example row (`solution_writing.py:140`), and has `python_interpreter` (full `dfs` + `conn`) and the SQL tools (`n_example_rows=20`). It answers with a Python `processing(dfs)` function or one SQL query. SQL is rewritten by sqlglot before execution (`solution_writing.py:571`). Python runs via `utils/program_frame.py` (`solution_writing.py:488`).
5. **Self-evaluation and repair** (`solution_revision.py:15`). An evaluator agent with all tools judges the output. If it rejects, the pipeline re-runs plan clarification or stitching, up to `max_self_eval_rounds`.
6. **Answer selection** (`utils/major_voting.py`). Majority vote over the `planning_top_k × num_programs` candidate CSVs.

## How JSON is handled (SQLite path)

- JSON is plain TEXT. Nothing in the code is JSON-specific for SQLite. The Snowflake VARIANT prompt rules (`prompt_templates.py:362`) are added only when `db_type == "snowflake"` and `db_path == "datasets/Spider2/spider2-snow"` (`solution_writing.py:238`).
- **Structural visibility by default:** two metadata examples per column, then one truncated row per sub-query in the stitching prompt. Anything beyond that requires the agent to issue explicit queries or Python. The agent is fully able to enumerate paths recursively itself (SQLite JSON1 `json_tree`/`json_each` works through `query_database`; SQLite 3.50.4).
- `truncate_nested_data` (`get_ddl.py:646-691`) calls `json.loads` on every string it meets (`get_ddl.py:654`). A **numeric string such as `"5.99"` is therefore displayed as the number `5.99`**, so string-vs-number type information is hidden in every example the agent sees.

## Defects and limitations found (pre-existing, not introduced by us)

1. **sqlglot rewrite changes SQLite JSON semantics.** Every SQL statement the agent runs, in exploration and in final SQL, passes through `quote_identifiers(..., output_dialect="sqlite")` (`get_ddl.py:75-127`). With the pinned sqlglot 28.10.1 this turns `json_extract(col,'$.p')` into `col -> '$.p'`. In SQLite, `->` returns a **JSON-encoded** value: strings keep their quotes and numbers come back as text. Verified directly:
   `json_extract(p,'$.s')='paid'` → 1, but `(p -> '$.s')='paid'` → 0; `CAST(json_extract(p,'$.amt') AS REAL)` → 12.5, but `CAST(p -> '$.amt' AS REAL)` → 0.0 for `"amt":"12.5"`.
   So a correct `json_extract` query can **silently return a wrong answer**, or no rows, both when the agent explores and when it executes. `->>`, `json_each` and `json_tree` are left intact. This is a confound for any SQL-path JSON result and is tracked separately in the analysis (category D/E, not A/B).
2. Usage accounting in `main.py:554` merges only the sub-SQL, stitching and evaluation agents, so the planning agent's tokens are **not** counted. Phase 0 counts tokens from the transport trace instead.
3. The provider request defaults are vLLM-specific (`chat.py:513`): `extra_body.top_k=-1` is rejected with HTTP 400 by both Gemini and Groq.
4. `chat.py:416-426` rebuilds assistant `tool_calls` as `{id,type,function}`. Provider-specific fields (Gemini 3 `extra_content.google.thought_signature`) are dropped, which Gemini 3.x rejects with HTTP 400.
5. `--use_gold_tables` and the similarity reports are Snowflake-oriented. Hierarchical schema linking only applies to Snowflake (`main.py:150`).
6. `pyproject.toml` pins `vllm==0.13.0` and `transformers`. Neither is imported by the agent code paths used here (local model serving only), and neither installs on Windows.

## Can FlexSQL run on arbitrary SQLite DBs and custom questions?

Yes, without code changes. It needs `{db_path}/{db}/{db}.sqlite` plus one Spider2-Lite-style metadata JSON per table (`table_name`, `column_names`, `column_types`, `description`, `column_examples`) in the same folder. Questions are JSONL `{instance_id, db, question, external_knowledge}` (`utils.py:559-580`). Spider2-Lite metadata has `sample_rows` (5 rows) but no `column_examples`. The upstream script that adds them is Snowflake-only (`src/preprocessing/add_example_value.py`), so Phase 0 re-implements its logic on SQLite (`fixtures/generate.py::write_metadata`): examples are the distinct truncated values from the 5 sample rows, with a `SELECT DISTINCT ... LIMIT 10` fallback when there are fewer than 2.
