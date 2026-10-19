"""jcov: reference-free check for silently incomplete JSON reads in a generated SQL/Python program.

Inputs (inference-time only): the program, its saved sub-queries (Python), the SQLite file, and
optionally the NL question. No gold SQL, gold answer or label is read.

Rule (pre-registered in PREFLIGHT.md §5, no tuned thresholds):
  scope    = rows that reach the program's JSON access (Python: rows passed to json.loads /
             ast.literal_eval at run time; SQL: FROM/JOIN + the relational top-level AND conjuncts)
  read     = the program obtained >=1 value from the row (Python: a key/element access that returned
             a value, or key enumeration; SQL: >=1 referenced JSON path exists in the row)
  unread   = scope rows that are not read
  finding  = a group of unread rows (same structural signature) containing leaf paths that occur in
             NO read row -> SUSPICIOUS(omitted_structure), reported as a hypothesis with counts/ids.
  Valid-JSON rows the program failed to parse -> SUSPICIOUS(parse_failure) (scored separately).
  Unsupported constructs -> ABSTAIN. Otherwise NO_EVIDENCE (not a correctness certificate).

Variant `--anchor` (pre-declared secondary arm): keep an omitted_structure finding only if a question
token (>=3 chars, non-stopword) shares a 4-char prefix with a key name or string value of the
group's novel structure. Lexical; informed by Phase 0 knowledge; reported separately.

Usage:
  python jcov.py --db DB.sqlite --py program.py --subq sub_queries.json [--question TEXT] [--anchor]
  python jcov.py --db DB.sqlite --sql program.sql [--question TEXT] [--anchor]
Prints one JSON object.
"""
import argparse
import ast
import importlib.util
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict

_ORIG_LOADS = json.loads
_ORIG_LITERAL = ast.literal_eval
MAX_IDS = 10


# ---------------------------------------------------------------- structure helpers
def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def walk(obj, path=""):
    """Yield (path, is_leaf, value) for every node; array indices normalised to []."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else str(k)
            yield p, False if isinstance(v, (dict, list)) else True, v
            yield from walk(v, p)
    elif isinstance(obj, list):
        for v in obj:
            p = f"{path}[]"
            if not isinstance(v, (dict, list)):
                yield p, True, v
            yield from walk(v, p)


def signature(obj):
    return frozenset(p for p, _, _ in walk(obj))


def jtype(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, (int, float)):
        return "number"
    if isinstance(v, str):
        return "numeric_string" if re.fullmatch(r"-?\d+(\.\d+)?", v.strip()) else "string"
    return type(v).__name__


STOP = set("the and for with from that this what which how many much total number are was were has have "
           "into per all any only its their than then when where whose who rounded decimal places note "
           "used include ignore values value case insensitive".split())


def q_tokens(question):
    return {t for t in re.findall(r"[a-z0-9]+", (question or "").lower()) if len(t) >= 3 and t not in STOP}


def text_tokens(s):
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", str(s))
    return {t for t in re.findall(r"[a-z0-9]+", s.lower()) if len(t) >= 3}


def anchored(qtok, group_rows, novel):
    toks = set()
    for p in novel:
        toks |= text_tokens(p.replace("[]", " ").replace(".", " "))
    for obj in group_rows:
        for p, leaf, v in walk(obj):
            if leaf and p in novel and isinstance(v, str):
                toks |= text_tokens(v)
    hits = sorted(q for q in qtok for t in toks if q[:4] == t[:4])
    return sorted(set(hits))


# ---------------------------------------------------------------- shared analysis
def analyse(rows, read_ids, failed_ids, missed, question=None, anchor=False):
    """rows: {row_key: obj} for scope rows; read_ids: set of read row keys."""
    read_union = set()
    for k in read_ids:
        read_union |= signature(rows[k])
    unread = [k for k in rows if k not in read_ids and k not in failed_ids]
    groups = defaultdict(list)
    for k in unread:
        groups[signature(rows[k])].append(k)
    findings, benign_unread = [], 0
    qtok = q_tokens(question)
    for sig, keys in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        novel_all = sig - read_union
        leaves = {}
        for k in keys:
            for p, leaf, v in walk(rows[k]):
                if leaf and p in novel_all:
                    leaves.setdefault(p, {"types": set(), "examples": []})
                    leaves[p]["types"].add(jtype(v))
                    if len(leaves[p]["examples"]) < 3 and v not in leaves[p]["examples"]:
                        leaves[p]["examples"].append(v)
        if not leaves:
            benign_unread += len(keys)
            continue
        f = {"kind": "omitted_structure", "n_rows": len(keys), "n_scope_rows": len(rows),
             "row_ids": [list(k) for k in keys[:MAX_IDS]],
             "missed_accesses": sorted({m for k in keys for m in missed.get(k, ())})[:20],
             "novel_leaf_paths": {p: {"types": sorted(d["types"]), "examples": d["examples"]} for p, d in sorted(leaves.items())[:25]},
             "hypothesis": (f"{len(keys)} of {len(rows)} in-scope rows yielded no value to the program and contain "
                            f"structure absent from every row it read; possible omitted variant (not a proven equivalent).")}
        if anchor:
            f["anchor_tokens"] = anchored(qtok, [rows[k] for k in keys], set(leaves))
            if not f["anchor_tokens"]:
                f["suppressed_by_anchor"] = True
        findings.append(f)
    if failed_ids:
        findings.append({"kind": "parse_failure", "n_rows": len(failed_ids), "n_scope_rows": len(rows),
                         "row_ids": [list(k) for k in sorted(failed_ids)[:MAX_IDS]],
                         "hypothesis": "valid JSON rows that the program's parser rejected (silently, if caught)."})
    active = [f for f in findings if not f.get("suppressed_by_anchor")]
    return {"verdict": "SUSPICIOUS" if active else "NO_EVIDENCE",
            "n_scope_rows": len(rows), "n_read_rows": len(read_ids), "n_unread_rows": len(unread),
            "n_unread_subset_structure": benign_unread, "findings": findings}


# ---------------------------------------------------------------- Python tracing
class _Rec:
    __slots__ = ("obj", "reads", "missed")

    def __init__(self, obj):
        self.obj, self.reads, self.missed = obj, 0, set()


def _wrap(v, rec, path, count=True):
    # v2: any value returned by an access counts as a read, containers included (pre-registered rule);
    # v1 counted scalars only. The root object returned by the parser itself is not a read.
    if count:
        rec.reads += 1
    if isinstance(v, dict):
        return TDict(v, rec, path)
    if isinstance(v, list):
        return TList(v, rec, path)
    return v


class TDict(dict):
    def __init__(self, d, rec, path):
        super().__init__(d)
        self._r, self._p = rec, path

    def _sub(self, k):
        return f"{self._p}.{k}" if self._p else str(k)

    def __getitem__(self, k):
        if dict.__contains__(self, k):
            return _wrap(dict.__getitem__(self, k), self._r, self._sub(k))
        self._r.missed.add(self._sub(k))
        raise KeyError(k)

    def get(self, k, default=None):
        if dict.__contains__(self, k):
            return _wrap(dict.__getitem__(self, k), self._r, self._sub(k))
        self._r.missed.add(self._sub(k))
        return default

    def __contains__(self, k):
        if not dict.__contains__(self, k):
            self._r.missed.add(self._sub(k))
            return False
        return True

    def setdefault(self, k, default=None):
        return self.get(k, default)

    def pop(self, k, *a):
        return self.get(k, *(a or (None,)))

    def items(self):
        self._r.reads += 1
        return [(k, _wrap(v, self._r, self._sub(k))) for k, v in dict.items(self)]

    def values(self):
        self._r.reads += 1
        return [_wrap(v, self._r, self._sub(k)) for k, v in dict.items(self)]

    def keys(self):
        self._r.reads += 1
        return dict.keys(self)

    def __iter__(self):
        self._r.reads += 1
        return dict.__iter__(self)


class TList(list):
    def __init__(self, l, rec, path):
        super().__init__(l)
        self._r, self._p = rec, path

    def __getitem__(self, i):
        v = list.__getitem__(self, i)
        if isinstance(i, slice):
            return [_wrap(x, self._r, self._p + "[]") for x in v]
        return _wrap(v, self._r, self._p + "[]")

    def __iter__(self):
        for x in list.__iter__(self):
            yield _wrap(x, self._r, self._p + "[]")


def _is_json_col(values):
    vals = [v for v in values if isinstance(v, str)][:200]
    if not vals:
        return False
    ok = 0
    for v in vals:
        try:
            ok += isinstance(_ORIG_LOADS(v), (dict, list))
        except Exception:  # noqa: BLE001
            pass
    return ok >= 0.9 * len(vals)


def analyse_python(db, prog_path, subq_path, question=None, anchor=False):
    import pandas as pd
    src = open(prog_path, encoding="utf-8").read()
    tree = ast.parse(src)
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    calls = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    if names & {"conn", "get_cursor", "cursor"}:
        return {"verdict": "ABSTAIN", "reason": "program queries the database directly (lineage not recoverable)"}
    if calls & {"eval", "exec"}:
        return {"verdict": "ABSTAIN", "reason": "eval/exec in program"}
    subq = json.load(open(subq_path, encoding="utf-8"))
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    dfs, index, json_cols = [], {}, []
    for table, q in subq.items():
        cur = con.execute(q)
        df = pd.DataFrame(cur.fetchall(), columns=[d[0] for d in cur.description])
        dfs.append(df)
        for col in df.columns:
            if df[col].dtype == object and _is_json_col(df[col].tolist()):
                json_cols.append((table, col))
                try:
                    for rid, v in con.execute(f'SELECT rowid, "{col}" FROM "{table}"'):
                        try:
                            index.setdefault(canon(_ORIG_LOADS(v)), []).append((table, col, rid))
                        except Exception:  # noqa: BLE001
                            pass
                except sqlite3.Error:
                    pass
    if not json_cols:
        return {"verdict": "NO_EVIDENCE", "reason": "no JSON column in the program's inputs", "findings": []}
    recs, fails = [], []
    prog_abs = os.path.abspath(prog_path)

    def _from_program():
        f = sys._getframe(2)
        while f is not None:
            if os.path.abspath(f.f_code.co_filename) == prog_abs:
                return True
            f = f.f_back
        return False

    def _wrap_parser(orig):
        def parser(s, *a, **k):
            if not _from_program():
                return orig(s, *a, **k)
            try:
                res = orig(s, *a, **k)
            except Exception:
                fails.append(s)
                raise
            if isinstance(res, (dict, list)):
                r = _Rec(res)
                recs.append(r)
                return _wrap(res, r, "", count=False)
            return res
        return parser

    json.loads = _wrap_parser(_ORIG_LOADS)
    ast.literal_eval = _wrap_parser(_ORIG_LITERAL)
    try:
        spec = importlib.util.spec_from_file_location("jcov_prog", prog_path)
        mod = importlib.util.module_from_spec(spec)
        mod.pd = pd
        spec.loader.exec_module(mod)
        mod.processing(dfs)
    except Exception as e:  # noqa: BLE001
        return {"verdict": "ABSTAIN", "reason": f"program failed to replay: {type(e).__name__}: {e}"}
    finally:
        json.loads, ast.literal_eval = _ORIG_LOADS, _ORIG_LITERAL
        con.close()
    if not recs and not fails:
        return {"verdict": "ABSTAIN", "reason": "JSON columns present but no interceptable parse call ran"}
    rows, read, missed, failed, unmatched = {}, set(), defaultdict(set), set(), 0
    for r in recs:
        ids = index.get(canon(r.obj))
        if not ids:
            unmatched += 1
            continue
        for rid in ids:
            rows[rid] = r.obj
            missed[rid] |= r.missed
            if r.reads:
                read.add(rid)
    for s in fails:
        try:
            obj = _ORIG_LOADS(s)
        except Exception:  # noqa: BLE001
            continue
        for rid in index.get(canon(obj), []):
            if rid not in rows:  # v2: a row parsed successfully by any call (e.g. a fallback) is not a parse failure
                rows[rid] = obj
                failed.add(rid)
    if not rows:
        return {"verdict": "ABSTAIN", "reason": f"parsed objects could not be mapped to DB rows ({unmatched} unmatched)"}
    out = analyse(rows, read, failed, missed, question, anchor)
    out.update({"program_kind": "py", "json_columns": [list(c) for c in json_cols], "unmatched_parses": unmatched})
    return out


# ---------------------------------------------------------------- SQL scope reconstruction
def _json_refs(node):
    from sqlglot import exp
    refs = []
    for n in node.find_all(exp.JSONExtract, exp.JSONExtractScalar):
        col = n.this
        path = n.expression.sql(dialect="sqlite").strip("'")
        if isinstance(col, exp.Column):
            refs.append((col.table, col.name, path))
    return refs


def analyse_sql(db, sql, question=None, anchor=False):
    import sqlglot
    from sqlglot import exp
    try:
        tree = sqlglot.parse_one(sql, read="sqlite")
    except Exception as e:  # noqa: BLE001
        return {"verdict": "ABSTAIN", "reason": f"SQL parse error: {e}"}
    if not isinstance(tree, exp.Select) or tree.find(exp.With) or tree.find(exp.Union) or tree.find(exp.Subquery) \
            or any(isinstance(s, exp.Select) for s in tree.find_all(exp.Select) if s is not tree):
        return {"verdict": "ABSTAIN", "reason": "unsupported SQL shape (CTE/subquery/UNION)"}
    if re.search(r"json_(each|tree)", sql, re.I):
        return {"verdict": "ABSTAIN", "reason": "json_each/json_tree scope not reconstructed"}
    refs = _json_refs(tree)
    if not refs:
        return {"verdict": "NO_EVIDENCE", "reason": "no JSON access", "findings": []}
    for j in tree.args.get("joins") or []:
        if j.args.get("on") is not None and _json_refs(j.args["on"]):
            return {"verdict": "ABSTAIN", "reason": "JSON predicate in JOIN condition"}
    if tree.args.get("having") is not None and _json_refs(tree.args["having"]):
        return {"verdict": "ABSTAIN", "reason": "JSON predicate in HAVING"}
    kept = []
    where = tree.args.get("where")
    if where is not None:
        for c in where.this.flatten() if isinstance(where.this, exp.And) else [where.this]:
            has_json = bool(_json_refs(c))
            if has_json and c.find(exp.Or):
                return {"verdict": "ABSTAIN", "reason": "JSON predicate mixed into OR"}
            if not has_json:
                kept.append(c)
    alias_tbl = {}
    for t in tree.find_all(exp.Table):
        alias_tbl[t.alias_or_name] = t.name
    cols = sorted({(a, c) for a, c, _ in refs})
    if len({c for _, c in cols}) != 1 or len(cols) != 1:
        return {"verdict": "ABSTAIN", "reason": "JSON paths over more than one column"}
    alias, col = cols[0]
    if not alias:
        if len(alias_tbl) != 1:
            return {"verdict": "ABSTAIN", "reason": "unqualified JSON column with several tables"}
        alias = next(iter(alias_tbl))
    paths = sorted({p for _, _, p in refs})
    scope = exp.select(exp.column("rowid", table=alias), exp.column(col, table=alias))
    scope = scope.from_((tree.args.get("from_") or tree.args.get("from")).this.copy())
    for j in tree.args.get("joins") or []:
        scope = scope.join(j.copy())
    if kept:
        scope = scope.where(exp.and_(*[k.copy() for k in kept]))
    q = scope.sql(dialect="sqlite")
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        data = con.execute(q).fetchall()
        rows, read = {}, set()
        for rid, v in data:
            key = (alias_tbl.get(alias, alias), col, rid)
            try:
                obj = _ORIG_LOADS(v)
            except Exception:  # noqa: BLE001
                continue
            rows[key] = obj
            if any(con.execute("SELECT json_type(?, ?)", (v, p)).fetchone()[0] is not None for p in paths):
                read.add(key)
    except sqlite3.Error as e:
        return {"verdict": "ABSTAIN", "reason": f"scope query failed: {e}"}
    finally:
        con.close()
    out = analyse(rows, read, set(), {k: {f"(paths) {', '.join(paths)}"} for k in rows if k not in read}, question, anchor)
    out.update({"program_kind": "sql", "json_columns": [[alias_tbl.get(alias, alias), col]], "json_paths": paths, "scope_query": q})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--py")
    ap.add_argument("--subq")
    ap.add_argument("--sql")
    ap.add_argument("--question")
    ap.add_argument("--anchor", action="store_true")
    a = ap.parse_args()
    if a.sql:
        res = analyse_sql(a.db, open(a.sql, encoding="utf-8").read(), a.question, a.anchor)
    else:
        sys.path.insert(0, os.path.dirname(os.path.abspath(a.py)))
        res = analyse_python(a.db, a.py, a.subq, a.question, a.anchor)
    print(json.dumps(res, default=str))


if __name__ == "__main__":
    main()
