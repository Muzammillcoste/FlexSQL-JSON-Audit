"""Toy unit tests for jcov (development only; no evaluation data is used).
Run: python -m pytest -q test_jcov.py   (or: python test_jcov.py)
"""
import json
import os
import sqlite3
import tempfile

import jcov


def _db(rows):
    d = tempfile.mkdtemp()
    p = os.path.join(d, "t.sqlite")
    con = sqlite3.connect(p)
    con.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, g TEXT, j TEXT)")
    con.executemany("INSERT INTO t VALUES (?,?,?)", [(i, g, json.dumps(o)) for i, (g, o) in enumerate(rows, 1)])
    con.commit()
    con.close()
    return d, p


def _py(d, body, subq='SELECT "g", "j" FROM "t"'):
    prog = os.path.join(d, "prog.py")
    open(prog, "w").write("import json\nimport ast\nimport pandas as pd\n\ndef processing(dfs):\n" + body)
    sq = os.path.join(d, "sq.json")
    json.dump({"t": subq}, open(sq, "w"))
    return prog, sq


def test_tracking_hits_and_misses():
    rec = jcov._Rec({})
    t = jcov._wrap({"a": {"b": 1}, "l": [{"c": 2}]}, rec, "", count=False)
    assert t.get("zz", 5) == 5 and "zz" in rec.missed
    assert t["a"]["b"] == 1 and rec.reads == 2
    assert [x["c"] for x in t["l"]] == [2] and rec.reads == 5
    assert ("q" in t) is False and "q" in rec.missed


def test_py_variant_flagged_and_optional_not():
    rows = [("x", {"v": 1, "k": "a"})] * 20 + [("x", {"v": 2})] * 5 + [("x", {"alt": {"val": 9}})] * 2
    d, db = _db(rows)
    prog, sq = _py(d, "    return pd.DataFrame({'s': [sum(json.loads(s).get('v', 0) for s in dfs[0]['j'])]})\n")
    r = jcov.analyse_python(db, prog, sq)
    assert r["verdict"] == "SUSPICIOUS"
    f = [x for x in r["findings"] if x["kind"] == "omitted_structure"]
    assert len(f) == 1 and f[0]["n_rows"] == 2 and "alt.val" in f[0]["novel_leaf_paths"]


def test_py_optional_only_is_no_evidence():
    rows = [("x", {"v": 1, "k": "a"})] * 20 + [("x", {"k": "b"})] * 5
    d, db = _db(rows)
    prog, sq = _py(d, "    return pd.DataFrame({'s': [sum(json.loads(s).get('v', 0) for s in dfs[0]['j'])]})\n")
    r = jcov.analyse_python(db, prog, sq)
    assert r["verdict"] == "NO_EVIDENCE" and r["n_unread_subset_structure"] == 5


def test_parse_failure_reported():
    rows = [("x", {"v": None})] * 3 + [("x", {"v": 1})] * 3
    d, db = _db(rows)
    body = ("    t = 0\n    for s in dfs[0]['j']:\n        try:\n            t += ast.literal_eval(s)['v'] or 0\n"
            "        except (ValueError, SyntaxError):\n            pass\n    return pd.DataFrame({'t': [t]})\n")
    prog, sq = _py(d, body)
    r = jcov.analyse_python(db, prog, sq)
    assert any(f["kind"] == "parse_failure" and f["n_rows"] == 3 for f in r["findings"])


def test_sql_scope_drops_json_conjunct_keeps_relational():
    rows = [("a", {"v": 1})] * 10 + [("a", {"alt": {"val": 3}})] + [("b", {"alt": {"val": 3}})] * 4
    d, db = _db(rows)
    r = jcov.analyse_sql(db, "SELECT SUM(json_extract(j, '$.v')) FROM t WHERE g = 'a' AND json_extract(j, '$.v') > 0")
    assert r["verdict"] == "SUSPICIOUS" and r["n_scope_rows"] == 11
    assert r["findings"][0]["n_rows"] == 1


def test_sql_or_mixed_abstains():
    d, db = _db([("a", {"v": 1})])
    r = jcov.analyse_sql(db, "SELECT COUNT(*) FROM t WHERE g = 'a' OR json_extract(j, '$.v') = 1")
    assert r["verdict"] == "ABSTAIN"


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
