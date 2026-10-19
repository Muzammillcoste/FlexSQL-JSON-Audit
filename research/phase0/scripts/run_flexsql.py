"""Run UNMODIFIED upstream FlexSQL (src/main.py) on Phase 0 cases, one process per
(case, trial), with checkpointing, tracing and upstream majority voting.

Upstream is invoked exactly as its README describes (python src/main.py ...) with
cwd = upstream checkout. The only things this runner adds are environment:
  - OPENAI_API_KEY from the chosen provider key (never logged)
  - PYTHONPATH=harness  -> sitecustomize.py loads the trace/backoff wrapper
  - FLEXSQL_P0_DROP_TOPK=1 (documented provider-compat transform)
  - PYTHONUTF8=1 (Windows console/file encoding; no logic change)

Usage:
  python run_flexsql.py --arm baseline --cases p0_M01,p0_M02 --trials 1 [--parallel 3]
  python run_flexsql.py --arm baseline --cases all --trials 3
"""
import argparse
import concurrent.futures as cf
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
P0 = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(P0))
UP = os.path.join(ROOT, "upstream", "FlexSQL")
PY = os.path.join(ROOT, ".venv-phase0", "Scripts", "python.exe")
sys.path.insert(0, os.path.join(P0, "harness"))
from p0_env import provider_env  # noqa: E402

import threading
_LOCK = threading.Lock()
_INFLIGHT = [0]
CONFIG = json.load(open(os.path.join(P0, "config", "baseline_config.json"), encoding="utf-8"))


def load_questions(path=None):
    qs = {}
    for line in open(path or os.path.join(P0, "fixtures", "questions.jsonl"), encoding="utf-8"):
        q = json.loads(line)
        qs[q["instance_id"]] = q
    return qs


def trace_usage(rdir):
    u = {"prompt_tokens": 0, "total_tokens": 0, "llm_calls": 0}
    import glob
    for p in glob.glob(os.path.join(rdir, "llm_trace_*.jsonl")):
        for line in open(p, encoding="utf-8"):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("type") == "llm_call" and r.get("usage"):
                u["prompt_tokens"] += r["usage"].get("prompt_tokens") or 0
                u["total_tokens"] += r["usage"].get("total_tokens") or 0
                u["llm_calls"] += 1
    return u


def cost_usd(u):
    pr = CONFIG["pricing_usd_per_1m"]
    return (u["prompt_tokens"] * pr["input"] + (u["total_tokens"] - u["prompt_tokens"]) * pr["output_incl_thinking"]) / 1e6


def spent_usd():
    import glob
    tot = 0.0
    for p in glob.glob(os.path.join(P0, "traces", "*", "*", "trial_*")):
        d = os.path.join(p, "DONE.json")
        if os.path.exists(d):
            tot += json.load(open(d, encoding="utf-8")).get("est_cost_usd", 0) or 0
        else:
            tot += cost_usd(trace_usage(p))  # in-flight or incomplete runs
    return tot


def run_one(arm, q, trial, extra_args, timeout_s):
    cid = q["instance_id"]
    rdir = os.path.join(P0, "traces", arm, cid, f"trial_{trial}")
    if os.path.exists(os.path.join(rdir, "DONE.json")):
        return json.load(open(os.path.join(rdir, "DONE.json"), encoding="utf-8"))
    if os.path.exists(rdir):  # incomplete earlier attempt: keep it, start a fresh numbered attempt dir
        k = 1
        while os.path.exists(rdir + f".incomplete{k}"):
            k += 1
        os.replace(rdir, rdir + f".incomplete{k}")
    per_run = CONFIG["per_run_cost_cap_usd"]
    with _LOCK:  # reserve worst-case cost of every in-flight run before launching another
        if spent_usd() + (_INFLIGHT[0] + 1) * per_run > CONFIG["budget_cap_usd"]:
            return {"case": cid, "trial": trial, "returncode": None, "timed_out": False, "provider_failure": False,
                    "wall_s": 0, "skipped": "budget_cap_reached"}
        _INFLIGHT[0] += 1
    try:
        return _run_one(arm, q, trial, extra_args, timeout_s, rdir, cid, per_run)
    finally:
        with _LOCK:
            _INFLIGHT[0] -= 1


def _kill_tree(pid):
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)


def _run_one(arm, q, trial, extra_args, timeout_s, rdir, cid, per_run):
    os.makedirs(rdir)
    qfile = os.path.join(rdir, "question.jsonl")
    with open(qfile, "w", encoding="utf-8") as f:
        f.write(json.dumps(q, ensure_ascii=False) + "\n")
    exp = f"p0-{arm}-{cid}-t{trial}"
    cfg = CONFIG
    base_url = provider_env(cfg["provider"])
    env = dict(os.environ)
    env.update({
        "PYTHONUTF8": "1",
        "PYTHONPATH": os.path.join(P0, "harness"),
        "FLEXSQL_P0_TRACE": os.path.join(rdir, "llm_trace_{pid}.jsonl"),
        "FLEXSQL_P0_QUOTA_FLAG": os.path.join(rdir, "PROVIDER_FAILURE.txt"),
        "FLEXSQL_P0_DROP_TOPK": "1" if cfg.get("drop_top_k") else "0",
        "FLEXSQL_P0_GEMINI_THOUGHT_SIG": "1" if cfg.get("restore_gemini_thought_signature") else "0",
    })
    env.pop("OPENAI_BASE_URL", None)
    cmd = [PY, "src/main.py", "--model", cfg["model"], "--base_url", base_url, "--dataset", qfile,
           "--db_path", os.path.join(P0, "fixtures", "databases"), "--db_type", "sqlite",
           "--workers", "1", "--custom_exp_name", exp] + cfg["agent_args"] + extra_args
    t0 = time.time()
    with open(os.path.join(rdir, "stdout.txt"), "w", encoding="utf-8") as so, \
         open(os.path.join(rdir, "stderr.txt"), "w", encoding="utf-8") as se:
        proc = subprocess.Popen(cmd, cwd=UP, env=env, stdout=so, stderr=se)
        timed_out, cost_killed = False, False
        while proc.poll() is None:
            time.sleep(5)
            if time.time() - t0 > timeout_s:
                timed_out = True
            elif cost_usd(trace_usage(rdir)) > per_run:
                cost_killed = True
            if timed_out or cost_killed:
                _kill_tree(proc.pid)
                proc.wait()
                break
        rc = proc.returncode
    wall = time.time() - t0
    model_name = os.path.normpath(cfg["model"]).split("/")[-1]
    inf_root = os.path.join(UP, "inference_res")
    src = [d for d in os.listdir(inf_root) if d.startswith(f"{model_name}-{exp}--")] if os.path.isdir(inf_root) else []
    out_dir = os.path.join(rdir, "flexsql_output")
    if src:
        shutil.move(os.path.join(inf_root, src[0]), out_dir)
    cache = os.path.join(UP, "cache", cid)
    if os.path.isdir(cache):
        shutil.copytree(cache, os.path.join(rdir, "upstream_cache"), dirs_exist_ok=True)
    # upstream majority voting over this run's candidates (README settings)
    mv = None
    if os.path.isdir(out_dir):
        mv_out = os.path.join(rdir, "majority")
        r = subprocess.run([PY, "utils/major_voting.py", "--input_dir", out_dir, "--output_dir", mv_out,
                            "--fuzzy_threshold", "0.90", "--allow_superset", "--max_workers", "1"],
                           cwd=UP, env=dict(env, FLEXSQL_P0_TRACE=""), capture_output=True, text=True)
        mv = {"rc": r.returncode, "stdout": r.stdout[-2000:], "stderr": r.stderr[-2000:]}
    done = {"case": cid, "arm": arm, "trial": trial, "returncode": rc, "timed_out": timed_out, "wall_s": round(wall, 1),
            "provider_failure": os.path.exists(os.path.join(rdir, "PROVIDER_FAILURE.txt")),
            "inference_dir_found": bool(src), "majority_vote": mv, "cmd": cmd[1:3] + ["<base_url>"] + cmd[5:],
            "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": cfg["model"],
            "killed_per_run_cost_cap": cost_killed, "per_run_cost_cap_usd": per_run}
    done["usage"] = trace_usage(rdir)
    done["est_cost_usd"] = round(cost_usd(done["usage"]), 4)
    with open(os.path.join(rdir, "DONE.json"), "w", encoding="utf-8") as f:
        json.dump(done, f, indent=1)
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="baseline")
    ap.add_argument("--cases", required=True, help="comma list, 'all', or 'pilot'")
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--trial_start", type=int, default=1)
    ap.add_argument("--parallel", type=int, default=1)
    ap.add_argument("--timeout_min", type=int, default=90)
    ap.add_argument("--extra", default="", help="extra upstream CLI args (diagnostic arms only)")
    ap.add_argument("--questions", default=None, help="alternative question JSONL (diagnostic arms only)")
    a = ap.parse_args()
    qs = load_questions(a.questions)
    if a.cases == "all":
        ids = list(qs)
    elif a.cases == "pilot":
        ids = CONFIG["pilot_cases"]
    else:
        ids = a.cases.split(",")
    # trial-major order: every case gets trial k before any case gets trial k+1 (fair under quota cut-off)
    jobs = [(cid, t) for t in range(a.trial_start, a.trial_start + a.trials) for cid in ids]
    extra = a.extra.split() if a.extra else []
    with cf.ThreadPoolExecutor(max_workers=a.parallel) as ex:
        futs = {ex.submit(run_one, a.arm, qs[c], t, extra, a.timeout_min * 60): (c, t) for c, t in jobs}
        for fu in cf.as_completed(futs):
            c, t = futs[fu]
            try:
                d = fu.result()
                print(f"[{time.strftime('%H:%M:%S')}] {c} t{t}: rc={d['returncode']} timeout={d['timed_out']} "
                      f"provider_failure={d['provider_failure']} costkill={d.get('killed_per_run_cost_cap')} wall={d['wall_s']}s cost=${d.get('est_cost_usd')} {d.get('skipped','')} "
                      f"total_spent=${spent_usd():.2f}", flush=True)
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] {c} t{t}: RUNNER ERROR {e!r}", flush=True)


if __name__ == "__main__":
    main()
