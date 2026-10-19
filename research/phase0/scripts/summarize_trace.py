"""Human-readable summary of one run's observable trace (for manual root-cause review).

Prints, in order: every tool call (stage, tool, arguments) with a truncated output,
the final chosen program, the answer vs gold and the discovery flags from evidence.json.
Usage: python summarize_trace.py <run_dir> [--out file.md] [--maxout 600]
"""
import argparse
import json
import os

ap = argparse.ArgumentParser()
ap.add_argument("rdir")
ap.add_argument("--out")
ap.add_argument("--maxout", type=int, default=600)
a = ap.parse_args()
ev = json.load(open(os.path.join(a.rdir, "evidence.json"), encoding="utf-8"))
L = [f"# Trace summary: {a.rdir}", f"status={ev['status']}  final={ev['final_answer']}  gold={ev['gold']}",
     f"candidates={ev['candidate_scores']}  majority={ev['majority_summary'].get('groups')}",
     f"required={ev['required_structures']}", f"observed={json.dumps(ev['observed'])}",
     f"used_in_final_program={ev['used_in_final_program']}", f"tool_calls_by_stage={ev['tool_calls_by_stage']}",
     f"trace={json.dumps(ev['trace'])}", "", "## Tool calls"]
for i, t in enumerate(ev["tool_calls"], 1):
    args = t.get("arguments") or ""
    try:
        aj = json.loads(args)
        args = aj.get("query") or aj.get("code") or json.dumps(aj)
    except Exception:
        pass
    out = (t.get("output") or "")
    L.append(f"### {i}. [{t['stage']}] {t['name']} (seq {t['seq']})\n```\n{args[:1500]}\n```\n→\n```\n{out[:a.maxout]}{' …' if len(out) > a.maxout else ''}\n```")
L.append(f"## Final program ({ev['chosen_program']}, {ev['program_lang']})\n```\n{ev['program']}\n```")
txt = "\n".join(L)
if a.out:
    open(a.out, "w", encoding="utf-8").write(txt)
else:
    print(txt)
