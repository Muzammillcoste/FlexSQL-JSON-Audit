"""Stage A inventory of the 24 saved Phase 0 baseline runs. Offline only: no LLM/API calls.

For every case and candidate program it:
  * records the program kind (sql / py) and which candidate the upstream majority vote chose;
  * replays the saved program locally against the frozen SQLite fixture, using upstream's own
    `utils/program_frame.py` for Python (same sub-queries, same dfs order) and a read-only sqlite3
    connection for SQL, then compares the replayed output with the saved program_output CSV;
  * extracts static features: JSON path literals (sqlglot AST for SQL, Python AST for .py),
    joins / filters / GROUP BY, parse calls (json.loads / ast.literal_eval), broad try/except,
    defaulting `.get(k, default)` calls, and direct `conn` access outside the saved sub-queries.

It reads Phase 0 status/labels ONLY to group the audit table (A/B targets, E, correct). Nothing here
is a detector; no gold answer is read.

Usage: python inventory.py   -> writes ../preflight/inventory.json and prints a markdown table.
"""
import ast
import csv
import json
import os
import sqlite3
import subprocess
import sys

import pandas as pd
import sqlglot
from sqlglot import exp

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
P0 = os.path.join(ROOT, "research", "phase0")
UP = os.path.join(ROOT, "upstream", "FlexSQL")
OUT = os.path.join(HERE, "replay_out")
PY = sys.executable


def case_dir(c):
    return os.path.join(P0, "traces", "baseline", c, "trial_1")


def sql_features(sql):
    try:
        tree = sqlglot.parse_one(sql, read="sqlite")
    except Exception as e:  # noqa: BLE001
        return {"parse_error": str(e)}
    paths = []
    for node in tree.find_all(exp.JSONExtract, exp.JSONExtractScalar):
        paths.append(node.expression.sql(dialect="sqlite"))
    for fn in tree.find_all(exp.Anonymous):
        if fn.name.lower() in ("json_extract", "json_each", "json_tree"):
            paths.append(fn.sql(dialect="sqlite"))
    return {
        "json_paths": paths,
        "n_joins": len(list(tree.find_all(exp.Join))),
        "has_where": tree.find(exp.Where) is not None,
        "has_group_by": tree.find(exp.Group) is not None,
        "aggregates": sorted({type(a).__name__ for a in tree.find_all(exp.AggFunc)}),
        "uses_json_each": "json_each" in sql.lower() or "json_tree" in sql.lower(),
    }


def py_features(src):
    tree = ast.parse(src)
    keys, gets_with_default, parse_calls, broad_except, conn_use, filters = [], 0, set(), 0, False, 0
    for n in ast.walk(tree):
        if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) and isinstance(n.slice.value, str):
            keys.append(n.slice.value)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            if n.func.attr == "get" and n.args and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
                keys.append(n.args[0].value)
                if len(n.args) > 1:
                    gets_with_default += 1
            if n.func.attr in ("literal_eval", "loads"):
                parse_calls.add(f"{getattr(n.func.value, 'id', '?')}.{n.func.attr}")
            if n.func.attr in ("read_sql_query", "execute", "read_sql"):
                conn_use = True
        if isinstance(n, ast.Name) and n.id in ("conn", "get_cursor", "cursor"):
            conn_use = True
        if isinstance(n, ast.ExceptHandler):
            broad_except += 1
        if isinstance(n, (ast.Compare,)):
            filters += 1
    return {
        "string_keys": sorted(set(keys)),
        "get_with_default": gets_with_default,
        "parse_calls": sorted(parse_calls),
        "n_except_handlers": broad_except,
        "n_comparisons": filters,
        "direct_conn_access": conn_use,
    }


def same_output(a, b):
    try:
        da, db = pd.read_csv(a), pd.read_csv(b)
    except Exception:  # noqa: BLE001
        return False
    return da.shape == db.shape and da.astype(str).values.tolist() == db.astype(str).values.tolist()


def replay(case, db, prog, kind, plan):
    d = os.path.join(case_dir(case), "flexsql_output", case)
    dbfile = os.path.join(P0, "fixtures", "databases", db, f"{db}.sqlite")
    os.makedirs(os.path.join(OUT, case), exist_ok=True)
    out = os.path.join(OUT, case, f"replay_{prog}.csv")
    saved = os.path.join(d, f"program_output_{prog}.csv")
    if kind == "sql":
        conn = sqlite3.connect(f"file:{dbfile}?mode=ro", uri=True)
        try:
            cur = conn.execute(open(os.path.join(d, f"program_{prog}.sql"), encoding="utf-8").read())
            pd.DataFrame(cur.fetchall(), columns=[x[0] for x in cur.description]).to_csv(out, index=False)
        except Exception as e:  # noqa: BLE001
            return {"replay_ok": False, "error": str(e)}
        finally:
            conn.close()
    else:
        sq = os.path.join(d, f"sub_queries_plan_{plan}.json")
        r = subprocess.run([PY, "utils/program_frame.py", dbfile, case, os.path.join(d, f"program_{prog}.py"), sq, out],
                           cwd=UP, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            return {"replay_ok": False, "error": r.stderr.strip().splitlines()[-1] if r.stderr else "rc!=0"}
    return {"replay_ok": True, "matches_saved_output": same_output(out, saved)}


def main():
    cases = {json.loads(l)["instance_id"]: json.loads(l) for l in open(os.path.join(P0, "fixtures", "cases.jsonl"), encoding="utf-8")}
    res = {r["instance_id"]: r for r in csv.DictReader(open(os.path.join(P0, "results.csv"), encoding="utf-8")) if r["arm"] == "baseline"}
    labels = json.load(open(os.path.join(P0, "failure_labels.json"), encoding="utf-8"))
    inv = {}
    for case in sorted(res):
        db = cases[case]["db"]
        d = os.path.join(case_dir(case), "flexsql_output", case)
        chosen = json.load(open(os.path.join(case_dir(case), "majority", "majority_vote_summary.json")))[case]["chosen_file"]
        chosen_prog = chosen.replace("program_output_", "").replace(".csv", "")
        progs = {}
        for f in sorted(os.listdir(d)):
            if f.startswith("program_") and f.endswith((".py", ".sql")) and "output" not in f:
                prog, kind = f[len("program_"):].rsplit(".", 1)
                src = open(os.path.join(d, f), encoding="utf-8").read()
                feats = sql_features(src) if kind == "sql" else py_features(src)
                sq = json.load(open(os.path.join(d, f"sub_queries_plan_{prog.split('_')[0]}.json"), encoding="utf-8"))
                progs[prog] = {"kind": kind, "features": feats, "sub_queries": sq,
                               **replay(case, db, prog, kind, prog.split("_")[0])}
        group = "correct" if res[case]["status"] == "correct" else labels.get(case, {}).get("category", "?")
        inv[case] = {"db": db, "group": group, "chosen": chosen_prog, "programs": progs}
    json.dump(inv, open(os.path.join(HERE, "inventory.json"), "w", encoding="utf-8"), indent=1)
    print("| case | group | chosen kind | replay ok | matches saved | json parse | direct conn | joins/filters (chosen) |")
    print("|---|---|---|---|---|---|---|---|")
    for case, v in inv.items():
        p = v["programs"][v["chosen"]]
        f = p["features"]
        jf = (f"joins={f.get('n_joins')} where={f.get('has_where')}" if p["kind"] == "sql"
              else f"cmp={f.get('n_comparisons')} except={f.get('n_except_handlers')} get_default={f.get('get_with_default')}")
        print(f"| {case} | {v['group']} | {p['kind']} | {p['replay_ok']} | {p.get('matches_saved_output')} | "
              f"{','.join(f.get('parse_calls', [])) or ('->' if f.get('json_paths') else '-')} | {f.get('direct_conn_access', '-')} | {jf} |")


if __name__ == "__main__":
    main()
