"""Score Phase 0 runs and extract observable trace evidence.

For every traces/<arm>/<case>/trial_<k>/DONE.json:
  * final answer = upstream majority-vote CSV (utils/major_voting.py, README settings)
  * correctness = Spider2 exec-result comparison, verbatim copy of upstream
    utils/evaluate_passk.py::compare_pandas_table (lines 81-131; that module
    redirects stdout on import, so it is copied rather than imported)
  * per-candidate correctness (pass@k over the run's program_output_*.csv)
  * trace evidence: tool calls by name/stage, tool errors, whether the case's
    critical alternative JSON structures appeared in any data shown to the model
    (tool outputs + system-built example-row sections of prompts) and whether the
    final program references them (regex heuristics; failures are reviewed by hand)
  * tokens/latency/provider errors from the harness trace

Writes results.csv (one row per execution) and traces/<arm>/<case>/trial_k/evidence.json.
Usage: python score_runs.py [--arms baseline,...]
"""
import argparse
import csv
import glob
import json
import math
import os
import re

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
P0 = os.path.dirname(HERE)
CASES = {json.loads(l)["instance_id"]: json.loads(l) for l in open(os.path.join(P0, "fixtures", "cases.jsonl"), encoding="utf-8")}


# ---- verbatim from upstream utils/evaluate_passk.py:81-131 -------------------
def compare_pandas_table(pred, gold, condition_cols=[], ignore_order=False):
    if len(pred) != len(gold):
        return 0
    tolerance = 1e-2

    def normalize(value):
        if pd.isna(value):
            return 0
        return value

    def vectors_match(v1, v2, tol=tolerance, ignore_order_=False):
        v1 = [normalize(x) for x in v1]
        v2 = [normalize(x) for x in v2]
        if ignore_order_:
            v1, v2 = (sorted(v1, key=lambda x: (x is None, str(x), isinstance(x, (int, float)))),
                      sorted(v2, key=lambda x: (x is None, str(x), isinstance(x, (int, float)))))
        if len(v1) != len(v2):
            return False
        for a, b in zip(v1, v2):
            if pd.isna(a) and pd.isna(b):
                continue
            elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
                if not math.isclose(float(a), float(b), abs_tol=tol):
                    return False
            elif a != b:
                return False
        return True

    if condition_cols != []:
        if not isinstance(condition_cols, (list, tuple)):
            condition_cols = [condition_cols]
        gold_cols = gold.iloc[:, condition_cols]
    else:
        gold_cols = gold
    pred_cols = pred
    t_gold_list = gold_cols.transpose().values.tolist()
    t_pred_list = pred_cols.transpose().values.tolist()
    score = 1
    for gold in t_gold_list:
        if not any(vectors_match(gold, pred, ignore_order_=ignore_order) for pred in t_pred_list):
            score = 0
    return score
# -----------------------------------------------------------------------------


def KEY(k):
    """Evidence that JSON key k was shown: dict/JSON key, JSON path, or json_tree markdown cell."""
    # json_tree/json paths quote keys containing '_' (e.g. $."amount_cents"), hence the optional quote.
    return rf"['\"]{k}['\"]\s*:|\$[\w\.\[\]\*\"']*\.[\"']?{k}\b|\|\s*{k}\s*\|"


# Critical alternative structures per case: name -> (observe regex, use-in-program regex).
# Defined before any baseline results were inspected (see PHASE0_REPORT.md).
S = {
    "fleet_alt_energy": (r"['\"]k['\"]\s*:\s*['\"]energy|['\"]u['\"]\s*:\s*['\"]Wh|data\.readings", r"\$\.data\.readings|\[['\"]data['\"]\]|get\(['\"]data['\"]|['\"]readings['\"]\]|\.get\(['\"]readings['\"]"),
    "fleet_alt_status": (KEY("state") + r"|state\.code|['\"]code['\"]\s*:\s*['\"](FAULT|OK|WARN)", r"\$\.state|\[['\"]state['\"]\]|get\(['\"]state['\"]|state\.code"),
    "pay_v2_amount": (KEY("amount_cents"), r"amount_cents"),
    "pay_v3_amount": (KEY("transaction") + r"|transaction\.value", r"transaction"),
    "pay_v2_status": (KEY("state"), r"\bstate\b"),
    "pay_v3_status": (r"['\"]result['\"]\s*:\s*\{|result\.status|transaction\.result", r"result"),
    "pay_v2_currency": (KEY("currency_code"), r"currency_code"),
    "pay_v2_brand": (KEY("network"), r"network"),
    "pay_v3_brand": (KEY("instrument") + r"|instrument\.details", r"instrument"),
    "pay_wallet_brand": (KEY("card_brand"), r"card_brand"),
    "pay_v2_fees": (KEY("fees") + r"|['\"]type['\"]\s*:\s*['\"]processing", r"\bfees\b"),
    "pay_v3_fees": (KEY("pricing"), r"pricing"),
    "pay_v2_email": (KEY("email"), r"email"),
    "pay_v3_email": (KEY("contact"), r"contact"),
    "pay_connect": (KEY("charges") + r"|['\"]platform['\"]\s*:\s*['\"]connect", r"charges"),
    "log_envelope": (KEY("weight_g") + r"|['\"]type['\"]\s*:\s*['\"]envelope", r"weight_g"),
    "log_pallet": (KEY("gross_weight_kg") + r"|" + KEY("boxes"), r"gross_weight_kg|boxes"),
    "log_pallet_items": (KEY("boxes"), r"boxes"),
    "log_tracking_v2": (KEY("checkpoints") + r"|" + KEY("history"), r"checkpoints|history"),
}
REQUIRED = {
    "p0_H01": ["pay_v2_amount", "pay_v3_amount", "pay_v2_status", "pay_v3_status", "pay_v2_currency"],
    "p0_H02": ["pay_v2_brand", "pay_v3_brand", "pay_wallet_brand", "pay_v2_status", "pay_v3_status"],
    "p0_H03": ["pay_v2_fees", "pay_v3_fees", "pay_v2_status", "pay_v3_status", "pay_v2_currency"],
    "p0_H04": ["pay_v2_email", "pay_v3_email"],
    "p0_H05": ["pay_v2_amount", "pay_v3_amount", "pay_v2_status", "pay_v3_status", "pay_v2_currency"],
    "p0_H06": ["pay_v2_status", "pay_v3_status"],
    "p0_H10": ["pay_v2_amount", "pay_v3_amount", "pay_v2_status", "pay_v3_status", "pay_v2_currency"],
    "p0_X05": ["pay_v2_amount", "pay_v3_amount", "pay_connect", "pay_v2_status", "pay_v3_status", "pay_v2_currency"],
    "p0_X01": ["log_envelope", "log_pallet"],
    "p0_X02": ["log_pallet_items"],
    "p0_X03": ["log_tracking_v2"],
    "p0_X04": ["log_tracking_v2"],
}
for cid, c in CASES.items():
    if c.get("pair_group") and c.get("alt_structure_rate"):
        REQUIRED[cid] = ["fleet_alt_energy"] if c["pair_group"] == "fleet_L1" else ["fleet_alt_status"]


def stage_of(system_prompt):
    s = system_prompt or ""
    if "possible plans" in s:
        return "planning"
    if "Rigorous Data Architect" in s:
        return "clarification"
    if s.startswith("You are an evaluator"):
        return "self_eval"
    if "expert-level data" in s:
        return "stitching"
    return "other"


def load_trace(rdir):
    recs = []
    for p in glob.glob(os.path.join(rdir, "llm_trace_*.jsonl")):
        for line in open(p, encoding="utf-8"):
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    recs.sort(key=lambda r: (r.get("ts", 0), r.get("seq", 0)))
    return recs


def analyse_trace(recs):
    calls = [r for r in recs if r.get("type") == "llm_call"]
    perr = [r for r in recs if r.get("type") == "provider_error"]
    sys_by_list = {}
    tool_calls = {}   # id -> dict
    shown = []        # (stage, source, text) data shown to the model
    for r in calls:
        lid = r["msg_list_id"]
        for m in r.get("messages_delta", []):
            if m.get("role") == "system":
                sys_by_list[lid] = m.get("content", "")
        stage = stage_of(sys_by_list.get(lid))
        for m in r.get("messages_delta", []):
            if m.get("role") == "tool":
                tc = tool_calls.get(m.get("tool_call_id"))
                if tc is not None:
                    tc["output"] = m.get("content", "")
                shown.append((stage, f"tool:{m.get('name')}", m.get("content", "") or ""))
            elif m.get("role") == "user":
                txt = m.get("content", "") or ""
                mm = re.search(r"### SQL QUERIES AND EXAMPLE ROWS:(.*?)### User's Question", txt, re.S)
                if mm:
                    shown.append((stage, "prompt:sub_sql_example_rows", mm.group(1)))
        resp = r.get("response") or {}
        for tc in resp.get("tool_calls") or []:
            fn = (tc.get("function") or {})
            tool_calls[tc.get("id") or f"anon{len(tool_calls)}"] = {"seq": r["seq"], "stage": stage, "name": fn.get("name"),
                                                                     "arguments": fn.get("arguments"), "output": None}
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for r in calls:
        u = r.get("usage") or {}
        for k in usage:
            usage[k] += (u.get(k) or 0)
    return {
        "n_llm_calls": len(calls), "n_llm_errors": sum(1 for r in calls if r.get("error")),
        "n_provider_retries": len(perr), "provider_errors": [p["error"][:300] for p in perr][:20],
        "llm_latency_s": round(sum(r.get("latency_s", 0) or 0 for r in calls), 1),
        "usage": usage, "models": sorted({r.get("response_model") for r in calls if r.get("response_model")}),
        "tool_calls": list(tool_calls.values()), "shown": shown,
    }


def read_csv(path):
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def score_dir(rdir, case):
    gold = pd.read_csv(os.path.join(P0, "fixtures", "gold", f"{case['instance_id']}.csv"))
    done = json.load(open(os.path.join(rdir, "DONE.json"), encoding="utf-8"))
    qdir = os.path.join(rdir, "flexsql_output", case["instance_id"])
    cands = sorted(glob.glob(os.path.join(qdir, "program_output_*.csv")))
    cand_scores = {}
    for c in cands:
        df = read_csv(c)
        cand_scores[os.path.basename(c)] = int(compare_pandas_table(df, gold, ignore_order=True)) if not df.empty else 0
    maj = os.path.join(rdir, "majority", f"{case['instance_id']}.csv")
    summ_p = os.path.join(rdir, "majority", "majority_vote_summary.json")
    summ = json.load(open(summ_p, encoding="utf-8")).get(case["instance_id"], {}) if os.path.exists(summ_p) else {}
    final_df = read_csv(maj) if os.path.exists(maj) else None
    correct = None if final_df is None else int(compare_pandas_table(final_df, gold, ignore_order=True))
    chosen = summ.get("chosen_file")
    prog_text, prog_lang = "", None
    if chosen:
        stem = chosen.replace("_output", "", 1).replace(".csv", "")
        for ext in ("sql", "py"):
            p = os.path.join(qdir, f"{stem}.{ext}")
            if os.path.exists(p):
                prog_text, prog_lang = open(p, encoding="utf-8").read(), ext
                break
    tr = analyse_trace(load_trace(rdir))
    log = open(os.path.join(qdir, "log.txt"), encoding="utf-8", errors="replace").read() if os.path.exists(os.path.join(qdir, "log.txt")) else ""
    exec_errs = len(re.findall(r"The SQL query got the following error|The model got the following error", log))
    tool_err = sum(1 for t in tr["tool_calls"] if (t.get("output") or "").startswith(("Error", "Traceback")) or "Error executing query" in (t.get("output") or "") or "Traceback (most recent call last)" in (t.get("output") or ""))
    req = REQUIRED.get(case["instance_id"], [])
    observed, used = {}, {}
    for s in req:
        o_re, u_re = S[s]
        hits = [(st, src) for st, src, txt in tr["shown"] if re.search(o_re, txt)]
        observed[s] = sorted({f"{st}/{src}" for st, src in hits})
        used[s] = bool(re.search(u_re, prog_text)) if prog_text else False
    # status
    if done.get("timed_out"):
        status = "timeout"
    elif final_df is None:
        status = "provider_failure_no_answer" if done.get("provider_failure") else "no_answer"
    elif correct:
        status = "correct"
    else:
        status = "wrong_answer"
    tools_by = {}
    for t in tr["tool_calls"]:
        k = f"{t['stage']}:{t['name']}"
        tools_by[k] = tools_by.get(k, 0) + 1
    ev = {
        "status": status, "correct": correct, "final_answer": None if final_df is None else final_df.head(10).to_dict(orient="split"),
        "gold": gold.to_dict(orient="split"), "chosen_program": chosen, "program_lang": prog_lang, "program": prog_text,
        "majority_summary": summ, "candidate_scores": cand_scores, "exec_error_retries_in_log": exec_errs,
        "tool_error_outputs": tool_err, "tool_calls_by_stage": tools_by, "required_structures": req,
        "observed": observed, "used_in_final_program": used, "trace": {k: v for k, v in tr.items() if k not in ("shown", "tool_calls")},
        "tool_calls": tr["tool_calls"], "done": done,
    }
    with open(os.path.join(rdir, "evidence.json"), "w", encoding="utf-8") as f:
        json.dump(ev, f, indent=1, ensure_ascii=False, default=str)
    row = {
        "arm": done["arm"], "instance_id": case["instance_id"], "trial": done["trial"], "tier": case["tier"], "db": case["db"],
        "alt_structure_rate": case.get("alt_structure_rate"), "positive_control": case.get("positive_control"),
        "status": status, "correct": correct,
        "final_answer": None if final_df is None else json.dumps(final_df.head(5).values.tolist(), default=str),
        "gold": json.dumps(case["gold_rows"]), "n_candidates": len(cands), "n_candidates_correct": sum(cand_scores.values()),
        "pass_at_k": int(any(cand_scores.values())) if cands else None, "majority_vote_count": summ.get("vote_count"),
        "final_program_lang": prog_lang, "exec_error_retries": exec_errs, "tool_error_outputs": tool_err,
        "n_tool_calls": len(tr["tool_calls"]),
        "n_explore_calls": sum(v for k, v in tools_by.items() if k.split(":")[0] in ("planning", "clarification")),
        "required_structures": ";".join(req) or None,
        "all_required_observed": (all(observed[s] for s in req) if req else None),
        "n_required_observed": (sum(1 for s in req if observed[s]) if req else None),
        "all_required_used": (all(used.values()) if req and prog_text else (None if not req else False)),
        "n_llm_calls": tr["n_llm_calls"], "prompt_tokens": tr["usage"]["prompt_tokens"],
        "completion_tokens": tr["usage"]["completion_tokens"], "total_tokens": tr["usage"]["total_tokens"],
        "llm_latency_s": tr["llm_latency_s"], "wall_s": done.get("wall_s"), "provider_retries": tr["n_provider_retries"],
        "provider_failure": done.get("provider_failure"), "timed_out": done.get("timed_out"),
        "model_versions": ";".join(tr["models"]) or None,
    }
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default=None)
    ap.add_argument("--root", default="traces")
    ap.add_argument("--out", default=os.path.join(P0, "results.csv"))
    a = ap.parse_args()
    arms = a.arms.split(",") if a.arms else sorted(os.listdir(os.path.join(P0, a.root)))
    rows = []
    for arm in arms:
        for done in sorted(glob.glob(os.path.join(P0, a.root, arm, "*", "trial_*", "DONE.json"))):
            rdir = os.path.dirname(done)
            cid = os.path.basename(os.path.dirname(rdir))
            rows.append(score_dir(rdir, CASES[cid]))
    if rows:
        with open(a.out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    for r in rows:
        print(f"{r['arm']:10s} {r['instance_id']:14s} t{r['trial']} {r['status']:13s} cand={r['n_candidates_correct']}/{r['n_candidates']} "
              f"obs={r['n_required_observed']}/{len(r['required_structures'].split(';')) if r['required_structures'] else 0} "
              f"tok={r['total_tokens']} calls={r['n_llm_calls']} wall={r['wall_s']}")


if __name__ == "__main__":
    main()
