"""Phase 6 tool-level diagnostic controls (NO LLM, NO new tool).

Runs conventional exploration queries through the *unmodified upstream*
query_database tool (tools.create_query_database_tool, the paper's SQLExecutor),
exactly as the agent would receive them (including upstream's sqlglot rewrite and
truncation), and checks whether the output reveals each case's critical structures.

Controls:
  C1_more_examples_k : SELECT <json_col> FROM t LIMIT k          (k = 5, 20, 100; first rows)
  C1r_random_k       : ... ORDER BY RANDOM() LIMIT k             (k = 20, 100; 20 seeds -> discovery rate)
  C2_path_enum       : distinct normalised JSON paths via json_tree (arrays collapsed to [*])
  C3_path_freq       : the same with row counts per path (reveals rare variants + frequency)

Note: the upstream tool appends "LIMIT <n_example_rows>" only when the query has
no LIMIT; with the planning-stage default (n_example_rows=1) a query without an
explicit LIMIT returns ONE row. Controls therefore include an explicit LIMIT, which
an agent can equally write.

Output: research/phase0/diagnostics/existing_capability_controls.{json,md}
"""
import json
import os
import random
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
P0 = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(P0))
sys.path.insert(0, os.path.join(ROOT, "upstream", "FlexSQL", "src"))
sys.path.insert(0, HERE)
from tools import create_query_database_tool  # noqa: E402
from score_runs import S, REQUIRED, CASES  # noqa: E402

DBS = os.path.join(P0, "fixtures", "databases")
JSON_COLS = {"retail": [("orders", "details")], "payments": [("payment_events", "payload")],
             "logistics": [("shipments", "manifest"), ("shipments", "tracking")]}
for r in ("r00", "r01", "r05", "r20"):
    JSON_COLS[f"fleet_{r}"] = [("readings", "payload")]

_NORM = "j.fullkey"
for _i in range(10):
    _NORM = f"REPLACE({_NORM}, '[{_i}]', '[*]')"
PATH_SQL = ("SELECT p AS json_path, COUNT(DISTINCT rid) AS n_rows FROM (SELECT t.rowid AS rid, " + _NORM +
            " AS p FROM {t} t, json_tree(t.{c}) j WHERE j.type NOT IN ('object','array')) GROUP BY p ORDER BY n_rows DESC LIMIT 500")
ENUM_SQL = PATH_SQL.replace("p AS json_path, COUNT(DISTINCT rid) AS n_rows", "DISTINCT p AS json_path").replace("GROUP BY p ORDER BY n_rows DESC", "ORDER BY p")


def run_tool(db, sql, n_example_rows=1):
    conn = sqlite3.connect(f"file:{os.path.join(DBS, db, db + '.sqlite')}?mode=ro", uri=True)
    cur = conn.cursor()
    tool = create_query_database_tool(db_path=DBS, db_type="sqlite", cursor_getter=lambda: cur, n_example_rows=n_example_rows)
    out = tool(sql)
    conn.close()
    return out


def reveals(out, cid):
    return {s: bool(re.search(S[s][0], out)) for s in REQUIRED.get(cid, [])}


def main():
    res = {"controls": {}, "per_case": {}}
    for db, cols in JSON_COLS.items():
        for t, c in cols:
            key = f"{db}.{t}.{c}"
            res["controls"][key] = {}
            for k in (5, 20, 100):
                res["controls"][key][f"C1_first_{k}"] = run_tool(db, f"SELECT {c} FROM {t} LIMIT {k}")
            res["controls"][key]["C2_path_enum"] = run_tool(db, ENUM_SQL.format(t=t, c=c))
            res["controls"][key]["C3_path_freq"] = run_tool(db, PATH_SQL.format(t=t, c=c))
            # random samples: rowid-based deterministic sampling (SQLite RANDOM() is unseeded)
            conn = sqlite3.connect(os.path.join(DBS, db, db + ".sqlite"))
            n = conn.execute(f"SELECT MAX(rowid) FROM {t}").fetchone()[0]
            conn.close()
            for k in (20, 100):
                outs = []
                for seed in range(20):
                    ids = random.Random(seed).sample(range(1, n + 1), k)
                    outs.append(run_tool(db, f"SELECT {c} FROM {t} WHERE rowid IN ({','.join(map(str, ids))}) LIMIT {k}"))
                res["controls"][key][f"C1r_random_{k}"] = outs
    for cid, case in CASES.items():
        req = REQUIRED.get(cid)
        if not req:
            continue
        db = case["db"]
        row = {}
        for key, ctl in res["controls"].items():
            if not key.startswith(db + "."):
                continue
            for name, out in ctl.items():
                if isinstance(out, list):
                    hits = [reveals(o, cid) for o in out]
                    row.setdefault(name, {})
                    for s in req:
                        row[name][s] = max(row[name].get(s, 0), sum(h[s] for h in hits) / len(hits))
                    row[name]["_chars"] = sum(len(o) for o in out) // len(out)
                else:
                    h = reveals(out, cid)
                    row.setdefault(name, {})
                    for s in req:
                        row[name][s] = max(row[name].get(s, 0), int(h[s]))
                    row[name]["_chars"] = row[name].get("_chars", 0) + len(out)
        res["per_case"][cid] = row
    os.makedirs(os.path.join(P0, "diagnostics"), exist_ok=True)
    json.dump(res, open(os.path.join(P0, "diagnostics", "existing_capability_controls.json"), "w", encoding="utf-8"), indent=1)
    names = ["C1_first_5", "C1_first_20", "C1_first_100", "C1r_random_20", "C1r_random_100", "C2_path_enum", "C3_path_freq"]
    md = ["# Existing-capability controls (tool level, no LLM)\n",
          "Each cell: fraction of the case's required alternative structures revealed by the upstream `query_database` "
          "output (random-sample controls: mean over 20 seeds of the per-structure discovery indicator, worst structure shown); "
          "in brackets the output size in characters (~chars/4 tokens).\n",
          "| case | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for cid, row in res["per_case"].items():
        cells = []
        for n in names:
            r = row.get(n, {})
            vals = [v for k, v in r.items() if k != "_chars"]
            cells.append(f"{min(vals) if vals else 0:.2f} [{r.get('_chars', 0)}]")
        md.append(f"| {cid} | " + " | ".join(cells) + " |")
    md.append("\n## Example: C3 path-frequency output for fleet_r01.readings.payload (as the agent would see it)\n```\n"
              + res["controls"]["fleet_r01.readings.payload"]["C3_path_freq"] + "\n```")
    md.append("\n## Example: C3 path-frequency output for payments.payment_events.payload\n```\n"
              + res["controls"]["payments.payment_events.payload"]["C3_path_freq"] + "\n```")
    open(os.path.join(P0, "diagnostics", "existing_capability_controls.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md[:len(res['per_case']) + 4]))


if __name__ == "__main__":
    main()
