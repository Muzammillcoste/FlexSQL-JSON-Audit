"""Aggregate results.csv + failure labels (failure_labels.json) into report tables.
Usage: python aggregate.py  -> prints markdown tables and writes diagnostics/aggregate.json
"""
import csv
import json
import os
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
P0 = os.path.dirname(HERE)
rows = [r for r in csv.DictReader(open(os.path.join(P0, "results.csv"), encoding="utf-8")) if r["arm"] == "baseline"]
cases = [json.loads(l) for l in open(os.path.join(P0, "fixtures", "cases.jsonl"), encoding="utf-8")]
labels = json.load(open(os.path.join(P0, "failure_labels.json"), encoding="utf-8")) if os.path.exists(os.path.join(P0, "failure_labels.json")) else {}
by_id = {r["instance_id"]: r for r in rows}
out = []
out.append("| tier | planned | executed | correct | wrong (silent) | no answer / error | not executed |\n|---|---|---|---|---|---|---|")
tot = Counter()
for tier in ("medium", "hard", "hardest"):
    ids = [c["instance_id"] for c in cases if c["tier"] == tier]
    ex = [by_id[i] for i in ids if i in by_id]
    c = Counter(r["status"] for r in ex)
    vals = (len(ids), len(ex), c["correct"], c["wrong_answer"], len(ex) - c["correct"] - c["wrong_answer"], len(ids) - len(ex))
    tot.update(dict(zip(("p", "e", "c", "w", "n", "x"), vals)))
    out.append(f"| {tier} | " + " | ".join(map(str, vals)) + " |")
out.append(f"| **total** | {tot['p']} | {tot['e']} | {tot['c']} | {tot['w']} | {tot['n']} | {tot['x']} |")
# discovery among heterogeneous cases
het = [r for r in rows if r["required_structures"]]
obs = sum(1 for r in het if r["all_required_observed"] == "True")
out.append(f"\nHeterogeneous-structure cases executed: {len(het)}; all required structures observed by the agent: {obs}; "
           f"not all observed: {len(het) - obs}")
out.append("\n| case | tier | rare-rate | status | required observed | used in final program | label |\n|---|---|---|---|---|---|---|")
for r in sorted(het, key=lambda r: r["instance_id"]):
    out.append(f"| {r['instance_id']} | {r['tier']} | {r['alt_structure_rate'] or '-'} | {r['status']} | {r['n_required_observed']}/{len(r['required_structures'].split(';'))} | {r['all_required_used']} | {labels.get(r['instance_id'], {}).get('category', '')} |")
cat = Counter(v["category"] for k, v in labels.items() if by_id.get(k, {}).get("status") != "correct")
out.append("\n| root-cause category | count |\n|---|---|")
for k, v in sorted(cat.items()):
    out.append(f"| {k} | {v} |")
cost = sum(float(json.load(open(os.path.join(P0, "traces", "baseline", r["instance_id"], f"trial_{r['trial']}", "DONE.json")))["est_cost_usd"]) for r in rows)
tok = sum(int(r["total_tokens"]) for r in rows)
out.append(f"\nBaseline runs: {len(rows)}; total tokens {tok:,}; est. cost ${cost:.2f}; mean tokens/run {tok // max(1, len(rows)):,}")
print("\n".join(out))
json.dump({"tables_md": out}, open(os.path.join(P0, "diagnostics", "aggregate.json"), "w"), indent=1)
