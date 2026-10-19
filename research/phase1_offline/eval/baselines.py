"""Zero-cost comparison baselines (no program execution, no scope reconstruction, no labels).

B1 any_missing  : warn if any JSON key the program names (static AST / SQL path segments) is absent
                  from >=1 row of the JSON column (keys restricted to ones occurring somewhere in it).
B2 rare_missing : warn if any such key has an absence rate in (0, 0.5] over the full column
                  (raw NULL-rate heuristic).
B3 profile_het  : warn if the column's json_tree path profile (array indices normalised) has any path
                  present in fewer than 100% of rows (plain profile "heterogeneity" warning).
"""
import ast
import json
import re
import sqlite3


def static_keys_py(src):
    keys = set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) and isinstance(n.slice.value, str):
            keys.add(n.slice.value)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("get", "pop", "setdefault") \
                and n.args and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
            keys.add(n.args[0].value)
        if isinstance(n, ast.Compare) and isinstance(n.left, ast.Constant) and isinstance(n.left.value, str) \
                and any(isinstance(o, (ast.In, ast.NotIn)) for o in n.ops):
            keys.add(n.left.value)
    return keys


def static_keys_sql(sql):
    keys = set()
    for p in re.findall(r"'\$((?:\.[^']*)?)'", sql):
        keys |= {k.strip('"') for k in re.split(r"[.\[\]]", p) if k and not k.isdigit()}
    return keys


def _keys_of(obj, acc):
    if isinstance(obj, dict):
        for k, v in obj.items():
            acc.add(k)
            _keys_of(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _keys_of(v, acc)
    return acc


def column_rows(db, table, col):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        out = []
        for (v,) in con.execute(f'SELECT "{col}" FROM "{table}"'):
            try:
                out.append(json.loads(v))
            except Exception:  # noqa: BLE001
                pass
        prof = {}
        n = con.execute(f'SELECT COUNT(*) FROM "{table}" WHERE json_valid("{col}")').fetchone()[0]
        for path, rid in con.execute(
                f'SELECT jt.fullkey, t.rowid FROM "{table}" AS t, json_tree(t."{col}") AS jt WHERE json_valid(t."{col}")'):
            prof.setdefault(re.sub(r"\[\d+\]", "[]", path), set()).add(rid)
        return out, n, {p: len(s) for p, s in prof.items()}
    finally:
        con.close()


def run(db, columns, keys):
    res = {"B1_any_missing": False, "B2_rare_missing": False, "B3_profile_het": False, "detail": {}}
    for table, col in columns:
        rows, n, prof = column_rows(db, table, col)
        per_row = [_keys_of(o, set()) for o in rows]
        universe = set().union(*per_row) if per_row else set()
        rates = {k: sum(1 for s in per_row if k not in s) / len(per_row) for k in keys & universe}
        res["detail"][f"{table}.{col}"] = {"key_absence_rates": {k: round(v, 4) for k, v in sorted(rates.items())},
                                          "n_partial_paths": sum(1 for c in prof.values() if c < n)}
        res["B1_any_missing"] |= any(v > 0 for v in rates.values())
        res["B2_rare_missing"] |= any(0 < v <= 0.5 for v in rates.values())
        res["B3_profile_het"] |= any(c < n for c in prof.values())
    return res
