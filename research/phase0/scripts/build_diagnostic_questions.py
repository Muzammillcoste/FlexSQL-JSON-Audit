"""Build question files for Phase 6 *agent-level* diagnostic arms (NOT baseline).

Context reaches the unmodified agent through upstream's own BIRD-style `evidence`
field (planning.py:500-501, :1182-1183). It is injected verbatim as "External
Knowledge" into the planning, clarification, stitching and evaluation prompts.
No upstream code is changed, and no gold answers are included.

Arms:
  diag_pathprofile : evidence = generic JSON path-frequency profile of every JSON column
                     in the question's database, i.e. the output of ONE conventional
                     json_tree GROUP BY query per column (control C3) run through the
                     upstream query_database tool. Same text for every question on a DB.
  diag_oracle      : evidence = the question's relevant JSON paths and their meaning
                     (from cases.jsonl `relevant_json_paths`). Diagnostic upper bound.

Writes diagnostics/questions_<arm>.jsonl
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
P0 = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from existing_capability_controls import JSON_COLS, PATH_SQL, run_tool  # noqa: E402

QS = [json.loads(l) for l in open(os.path.join(P0, "fixtures", "questions.jsonl"), encoding="utf-8")]
CASES = {json.loads(l)["instance_id"]: json.loads(l) for l in open(os.path.join(P0, "fixtures", "cases.jsonl"), encoding="utf-8")}


def profile(db):
    parts = [f"JSON path profile of database '{db}' (one json_tree path-frequency query per JSON column; "
             "n_rows = number of rows in which the path occurs):"]
    for t, c in JSON_COLS[db]:
        out = run_tool(db, PATH_SQL.format(t=t, c=c)).replace("1 example rows:\n", "")
        parts.append(f"Table {t}, column {c}:\n{out}")
    return "\n".join(parts)


def oracle(cid):
    paths = CASES[cid]["relevant_json_paths"]
    if not paths:
        return ""
    return ("Relevant JSON paths for this question (all variants that occur in the data; path notation "
            "table.column.key...):\n- " + "\n- ".join(paths))


def main():
    os.makedirs(os.path.join(P0, "diagnostics"), exist_ok=True)
    for arm, fn in (("diag_pathprofile", lambda q: profile(q["db"])), ("diag_oracle", lambda q: oracle(q["instance_id"]))):
        with open(os.path.join(P0, "diagnostics", f"questions_{arm}.jsonl"), "w", encoding="utf-8") as f:
            for q in QS:
                q2 = dict(q)
                ev = fn(q)
                if ev:
                    q2["evidence"] = ev
                f.write(json.dumps(q2, ensure_ascii=False) + "\n")
        print("wrote", arm)


if __name__ == "__main__":
    main()
