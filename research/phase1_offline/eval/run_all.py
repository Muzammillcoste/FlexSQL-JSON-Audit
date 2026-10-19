"""Apply the FROZEN detector (primary + anchor arm) and the three baselines to every evaluation input.
Reads only inference-time inputs: programs, sub-queries, SQLite files, question text.
Does NOT read gold, results.csv, failure_labels.json or EXPECT.json.

Inputs: 24 Phase 0 baseline runs (the majority-vote-chosen program) + controls/scenarios/*.
Output: outputs/eval_items.jsonl (one line per item).
Usage:  python run_all.py
"""
import json
import os
import sqlite3
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(P1, "..", ".."))
P0 = os.path.join(ROOT, "research", "phase0")
sys.path.insert(0, os.path.join(P1, "detector"))
sys.path.insert(0, HERE)
import baselines  # noqa: E402
import jcov  # noqa: E402

JCOV = os.path.join(P1, "detector", "jcov.py")
WORK = os.path.join(P1, "outputs", "_work")


def items():
    qs = {json.loads(l)["instance_id"]: json.loads(l) for l in open(os.path.join(P0, "fixtures", "questions.jsonl"), encoding="utf-8")}
    base = os.path.join(P0, "traces", "baseline")
    for case in sorted(os.listdir(base)):
        t = os.path.join(base, case, "trial_1")
        chosen = json.load(open(os.path.join(t, "majority", "majority_vote_summary.json")))[case]["chosen_file"]
        prog = chosen.replace("program_output_", "").replace(".csv", "")
        d = os.path.join(t, "flexsql_output", case)
        q = qs[case]
        question = q["question"] + (" " + q["external_knowledge"] if q.get("external_knowledge") else "")
        db = os.path.join(P0, "fixtures", "databases", q["db"], f"{q['db']}.sqlite")
        kind = "sql" if os.path.exists(os.path.join(d, f"program_{prog}.sql")) else "py"
        yield {"item": case, "set": "phase0", "db": db, "kind": kind, "program": os.path.join(d, f"program_{prog}.{kind}"),
               "subq": os.path.join(d, f"sub_queries_plan_{prog.split('_')[0]}.json"), "question": question}
    scn = os.path.join(P1, "controls", "scenarios")
    for m in json.load(open(os.path.join(scn, "manifest.json"))):
        d = os.path.join(scn, m["id"])
        yield {"item": m["id"], "set": "heldout" if m["id"].startswith("HO") else "controls",
               "db": os.path.join(P1, "controls", m["db"]), "kind": m["kind"],
               "program": os.path.join(d, f"program.{m['kind']}"), "subq": os.path.join(d, "sub_queries.json"),
               "question": open(os.path.join(d, "question.txt"), encoding="utf-8").read()}


def detect(it, anchor):
    cmd = [sys.executable, JCOV, "--db", it["db"], "--question", it["question"]]
    cmd += ["--sql", it["program"]] if it["kind"] == "sql" else ["--py", it["program"], "--subq", it["subq"]]
    if anchor:
        cmd.append("--anchor")
    os.makedirs(WORK, exist_ok=True)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=WORK)
    if r.returncode != 0:
        return {"verdict": "ABSTAIN", "reason": f"detector crashed: {r.stderr.strip().splitlines()[-1] if r.stderr else r.returncode}"}
    return json.loads(r.stdout.strip().splitlines()[-1])


def json_columns(it):
    if it["kind"] == "sql":
        import sqlglot
        from sqlglot import exp
        tree = sqlglot.parse_one(open(it["program"], encoding="utf-8").read(), read="sqlite")
        amap = {t.alias_or_name: t.name for t in tree.find_all(exp.Table)}
        cols = set()
        for a, c, _ in jcov._json_refs(tree):
            cols.add((amap.get(a, a) if a else next(iter(amap.values())), c))
        return sorted(cols)
    con = sqlite3.connect(f"file:{it['db']}?mode=ro", uri=True)
    cols = []
    try:
        for table, q in json.load(open(it["subq"], encoding="utf-8")).items():
            cur = con.execute(q)
            names = [d[0] for d in cur.description]
            data = cur.fetchall()
            for i, n in enumerate(names):
                if jcov._is_json_col([r[i] for r in data]):
                    cols.append((table, n))
    finally:
        con.close()
    return cols


def main():
    os.makedirs(os.path.join(P1, "outputs"), exist_ok=True)
    out = open(os.path.join(P1, "outputs", "eval_items.jsonl"), "w", encoding="utf-8")
    for it in items():
        src = open(it["program"], encoding="utf-8").read()
        keys = baselines.static_keys_sql(src) if it["kind"] == "sql" else baselines.static_keys_py(src)
        rec = dict(it, detector=detect(it, False), detector_anchor=detect(it, True),
                   baselines=baselines.run(it["db"], json_columns(it), keys))
        out.write(json.dumps(rec, default=str) + "\n")
        print(it["item"], rec["detector"]["verdict"], rec["detector_anchor"]["verdict"],
              {k: v for k, v in rec["baselines"].items() if k != "detail"})
    out.close()


if __name__ == "__main__":
    main()
