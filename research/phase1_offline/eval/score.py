"""Score frozen detector/baseline outputs. The ONLY script that reads labels/gold:
results.csv (status), failure_labels.json (A/B/E), cases.jsonl relevant_json_paths (to check whether a
flagged hypothesis names a truly required path), and controls/scenarios/*/EXPECT.json.

Usage: python score.py [outputs/eval_items.jsonl]  -> prints markdown, writes outputs/scores.json
"""
import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.dirname(HERE)
P0 = os.path.join(os.path.dirname(P1), "phase0")
ARMS = ["detector", "detector_anchor", "B1_any_missing", "B2_rare_missing", "B3_profile_het"]


def norm_req(s):
    s = re.sub(r"\[[^\]]*\]", "[]", s.split(" ")[0])
    return re.sub(r"=.*$", "", s)


def active(det, kind):
    return [f for f in det.get("findings", []) if f["kind"] == kind and not f.get("suppressed_by_anchor")]


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(P1, "outputs", "eval_items.jsonl")
    items = [json.loads(l) for l in open(path, encoding="utf-8")]
    res = {r["instance_id"]: r for r in csv.DictReader(open(os.path.join(P0, "results.csv"), encoding="utf-8")) if r["arm"] == "baseline"}
    labels = json.load(open(os.path.join(P0, "failure_labels.json"), encoding="utf-8"))
    req = {json.loads(l)["instance_id"]: [norm_req(p) for p in json.loads(l)["relevant_json_paths"]]
           for l in open(os.path.join(P0, "fixtures", "cases.jsonl"), encoding="utf-8")}
    rows = []
    for it in items:
        if it["set"] == "phase0":
            g = "correct" if res[it["item"]]["status"] == "correct" else labels[it["item"]]["category"]
            group = {"A": "target_AB", "B": "target_AB", "E": "E_artifact", "correct": "benign"}[g]
        else:
            e = json.load(open(os.path.join(P1, "controls", "scenarios", it["item"], "EXPECT.json")))["expect"]
            group = {"benign": "benign", "target": "target_synth", "target_elem": "target_elem"}[e]
        r = {"item": it["item"], "set": it["set"], "group": group, "phase0_label": g if it["set"] == "phase0" else ""}
        for arm in ("detector", "detector_anchor"):
            d = it[arm]
            om, pf = active(d, "omitted_structure"), active(d, "parse_failure")
            r[arm] = bool(om)  # path-coverage warning
            r[arm + "_parse"] = bool(pf)
            r[arm + "_verdict"] = d["verdict"]
            if it["set"] == "phase0" and om:
                novel = {p for f in om for p in f["novel_leaf_paths"]}
                r[arm + "_names_required_path"] = any(q == p or q.endswith("." + p) for q in req[it["item"]] for p in novel)
        for b in ("B1_any_missing", "B2_rare_missing", "B3_profile_het"):
            r[b] = it["baselines"][b]
        rows.append(r)

    def count(sel, arm):
        s = [r for r in rows if sel(r)]
        return sum(1 for r in s if r[arm]), len(s)

    sets = {
        "A/B targets (Phase 0)": lambda r: r["group"] == "target_AB",
        "correct runs (Phase 0)": lambda r: r["set"] == "phase0" and r["group"] == "benign",
        "E artefacts (Phase 0)": lambda r: r["group"] == "E_artifact",
        "benign controls (synthetic)": lambda r: r["set"] == "controls" and r["group"] == "benign",
        "synthetic targets (row-level)": lambda r: r["set"] == "controls" and r["group"] == "target_synth",
        "synthetic target (array-element)": lambda r: r["group"] == "target_elem",
        "held-out targets": lambda r: r["set"] == "heldout" and r["group"] == "target_synth",
        "held-out benign": lambda r: r["set"] == "heldout" and r["group"] == "benign",
    }
    out = ["| set | " + " | ".join(ARMS) + " |", "|---|" + "---|" * len(ARMS)]
    table = {}
    for name, sel in sets.items():
        cells = []
        for arm in ARMS:
            k, n = count(sel, arm)
            cells.append(f"{k}/{n}")
            table.setdefault(name, {})[arm] = [k, n]
        out.append(f"| {name} | " + " | ".join(cells) + " |")
    out.append("\nWarnings = path-coverage warnings (detector: omitted_structure findings only; parse findings listed separately).")
    prec = ["\n| arm | flagged targets (A/B + synth + held-out) | flagged benign (P0 correct + controls + held-out) | precision | recall on A/B |", "|---|---|---|---|---|"]
    for arm in ARMS:
        tp = sum(1 for r in rows if r["group"] in ("target_AB", "target_synth", "target_elem") and r[arm])
        nt = sum(1 for r in rows if r["group"] in ("target_AB", "target_synth", "target_elem"))
        fp = sum(1 for r in rows if r["group"] == "benign" and r[arm])
        nb = sum(1 for r in rows if r["group"] == "benign")
        ab, nab = count(sets["A/B targets (Phase 0)"], arm)
        prec.append(f"| {arm} | {tp}/{nt} | {fp}/{nb} | {tp}/{tp + fp} | {ab}/{nab} |")
    out += prec
    out.append("\n| item | group | label | detector | names required path | parse finding | anchor | B1 | B2 | B3 |")
    out.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        out.append(f"| {r['item']} | {r['group']} | {r['phase0_label']} | {r['detector_verdict']}{'*' if r['detector'] else ''} | "
                   f"{r.get('detector_names_required_path', '')} | {r['detector_parse']} | {r['detector_anchor_verdict']}{'*' if r['detector_anchor'] else ''} | "
                   f"{int(r['B1_any_missing'])} | {int(r['B2_rare_missing'])} | {int(r['B3_profile_het'])} |")
    out.append("\n`*` = path-coverage warning raised (an E item can be SUSPICIOUS from a parse finding alone).")
    print("\n".join(out))
    json.dump({"summary": table, "rows": rows}, open(os.path.join(os.path.dirname(path), "scores.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
