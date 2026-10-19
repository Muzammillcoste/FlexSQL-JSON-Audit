"""Independent local synthetic controls + a held-out schema variation for the Phase 1 diagnostic.

Written BEFORE the detector was run on any evaluation input (see PREFLIGHT.md §3). The programs are
hand-written in the style of FlexSQL `processing(dfs)` / SQL candidates; they are NOT FlexSQL output.
Each scenario has an `expect` label used ONLY by eval/score.py:
  benign  - the program is correct for its question; any warning is a false warning
  target  - the program silently omits a relevant JSON variant (a warning is a detection)
  target_elem - omission happens inside array elements (documented row-level blind spot)

Usage: python build_controls.py  -> controls/{controls,heldout}.sqlite + controls/scenarios/<id>/...
"""
import json
import os
import random
import shutil
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
SCN = os.path.join(HERE, "scenarios")


def mkdb(path, tables):
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    for name, (ddl, rows) in tables.items():
        con.execute(ddl)
        ph = ",".join("?" * len(rows[0]))
        con.executemany(f"INSERT INTO {name} VALUES ({ph})", rows)
    con.commit()
    con.close()


def controls_db(path):
    rnd = random.Random(9001)
    orders = []
    for i in range(1, 401):
        p = {"total": round(rnd.uniform(5, 300), 2), "channel": rnd.choice(["web", "app"])}
        r = rnd.random()
        if r < 0.3:
            p["coupon"] = {"code": f"C{i}", "pct": rnd.choice([5, 10, 15])}
        elif r < 0.5:
            p["coupon"] = None
        if rnd.random() < 0.15:
            p["gift_wrap"] = True
        if rnd.random() < 0.7:
            p["shipping"] = {"method": rnd.choice(["std", "express"]), "cost": str(round(rnd.uniform(2, 20), 2))}
        if rnd.random() < 0.3:
            p["meta"] = {"code": rnd.choice(["A1", "B2"])}  # unrelated 'code'
        orders.append((i, f"2025-0{rnd.randint(1, 6)}-1{rnd.randint(0, 9)}", json.dumps(p)))
    events = []
    for i in range(1, 601):
        r = rnd.random()
        if r < 0.5:
            amt = round(rnd.uniform(1, 99), 2)
            p = {"type": "purchase", "amount": str(amt) if rnd.random() < 0.3 else amt, "currency": "usd"}
        elif r < 0.9:
            p = {"type": "click", "x": rnd.randint(0, 999), "y": rnd.randint(0, 999), "element": "btn"}
        else:
            p = {"kind": "heartbeat", "seq": i, "agent": {"version": "1.2"}}  # irrelevant, disjoint schema
        events.append((i, f"2025-05-{rnd.randint(10, 28)}", json.dumps(p)))
    sensors, sites = [], []
    for i in range(1, 501):
        site = "a" if i % 4 else "b"
        if site == "a":
            p = {"temp_c": round(rnd.uniform(-5, 35), 1), "ok": True}
        else:  # legacy format only at site b
            p = {"t": {"val": round(rnd.uniform(20, 95), 1), "unit": "F"}, "ok": True}
        sensors.append((i, site, json.dumps(p)))
    for s, region in (("a", "west"), ("b", "east")):
        sites.append((s, region))
    baskets = []
    for i in range(1, 301):
        items = []
        for _ in range(rnd.randint(1, 4)):
            if rnd.random() < 0.1:
                items.append({"sku": f"B{rnd.randint(1, 50)}", "bundle": True,
                              "children": [{"sku": f"S{rnd.randint(1, 50)}", "qty": rnd.randint(1, 3)} for _ in range(2)]})
            else:
                it = {"sku": f"S{rnd.randint(1, 50)}", "qty": rnd.randint(1, 5)}
                if rnd.random() < 0.2:
                    it["discount"] = 0.1
                items.append(it)
        baskets.append((i, json.dumps({"items": items})))
    legacy = []
    for i in range(1, 801):
        if rnd.random() < 0.03:
            p = {"ver": 1, "reading": {"pressure_kpa": round(rnd.uniform(90, 110), 2)}}
        else:
            p = {"ver": 2, "pressure": round(rnd.uniform(90, 110), 2), "flags": []}
        legacy.append((i, ["p1", "p2"][i % 2], json.dumps(p)))
    mkdb(path, {
        "orders_c": ("CREATE TABLE orders_c(order_id INTEGER PRIMARY KEY, created_at TEXT, payload TEXT)", orders),
        "events_c": ("CREATE TABLE events_c(event_id INTEGER PRIMARY KEY, ts TEXT, payload TEXT)", events),
        "sensors_c": ("CREATE TABLE sensors_c(sensor_id INTEGER PRIMARY KEY, site TEXT, payload TEXT)", sensors),
        "sites_c": ("CREATE TABLE sites_c(site TEXT PRIMARY KEY, region TEXT)", sites),
        "baskets_c": ("CREATE TABLE baskets_c(basket_id INTEGER PRIMARY KEY, payload TEXT)", baskets),
        "gauges_c": ("CREATE TABLE gauges_c(gauge_id INTEGER PRIMARY KEY, plant TEXT, payload TEXT)", legacy),
    })


def heldout_db(path):
    """Different domain, different key vocabulary, different variant mechanics (seed 4242)."""
    rnd = random.Random(4242)
    visits, clinics = [], [(1, "north"), (2, "south"), (3, "north")]
    for i in range(1, 1201):
        cl = rnd.choice([1, 2, 3])
        r = rnd.random()
        if r < 0.04:   # rare alternative vitals encoding: observation list, codes + values
            p = {"obs": [{"code": "HR", "val": rnd.randint(50, 120)}, {"code": "SBP", "val": rnd.randint(95, 160)}],
                 "visit_type": rnd.choice(["routine", "urgent"])}
        elif r < 0.10:  # admin-only rows without vitals (legitimately irrelevant for vitals questions)
            p = {"visit_type": "admin", "note": "paperwork"}
        else:
            p = {"vitals": {"hr": rnd.randint(50, 120), "bp": f"{rnd.randint(95, 160)}/{rnd.randint(60, 99)}"},
                 "visit_type": rnd.choice(["routine", "urgent"])}
            if rnd.random() < 0.25:
                p["allergies"] = rnd.choice([[], ["penicillin"], None])
        visits.append((i, cl, f"2025-0{rnd.randint(3, 8)}-{rnd.randint(10, 28)}", json.dumps(p)))
    mkdb(path, {
        "visits": ("CREATE TABLE visits(visit_id INTEGER PRIMARY KEY, clinic_id INTEGER, visit_date TEXT, record TEXT)", visits),
        "clinics": ("CREATE TABLE clinics(clinic_id INTEGER PRIMARY KEY, area TEXT)", clinics),
    })


PY_HEAD = "import pandas as pd\nimport json\n\ndef processing(dfs):\n"

SCENARIOS = [
    # ---- benign controls (situations from PREFLIGHT.md §3) ----
    ("C01_null_vs_absent", "controls", "benign", "py",
     {"orders_c": 'SELECT "payload" FROM "orders_c"'},
     PY_HEAD + "    n = 0\n    for s in dfs[0]['payload']:\n        p = json.loads(s)\n        if isinstance(p.get('coupon'), dict):\n            n += 1\n    return pd.DataFrame({'n': [n]})\n",
     "How many orders used a coupon (coupon present and not null)?"),
    ("C02_optional_bool", "controls", "benign", "py",
     {"orders_c": 'SELECT "payload" FROM "orders_c"'},
     PY_HEAD + "    n = sum(1 for s in dfs[0]['payload'] if json.loads(s).get('gift_wrap') is True)\n    return pd.DataFrame({'n': [n]})\n",
     "How many orders requested gift wrapping?"),
    ("C03_optional_object", "controls", "benign", "py",
     {"orders_c": 'SELECT "payload" FROM "orders_c"'},
     PY_HEAD + "    costs = []\n    for s in dfs[0]['payload']:\n        sh = json.loads(s).get('shipping')\n        if sh and sh.get('method') == 'express':\n            costs.append(float(sh['cost']))\n    return pd.DataFrame({'avg': [round(sum(costs) / len(costs), 2)]})\n",
     "Average shipping cost of express orders (pickup orders have no shipping)."),
    ("C04_irrelevant_type_guarded", "controls", "benign", "py",
     {"events_c": 'SELECT "payload" FROM "events_c"'},
     PY_HEAD + "    t = 0.0\n    for s in dfs[0]['payload']:\n        p = json.loads(s)\n        if p.get('type') == 'purchase':\n            t += float(p['amount'])\n    return pd.DataFrame({'total': [round(t, 2)]})\n",
     "Total purchase amount."),
    ("C05_irrelevant_type_default", "controls", "benign", "py",
     {"events_c": 'SELECT "payload" FROM "events_c"'},
     PY_HEAD + "    t = sum(float(json.loads(s).get('amount', 0)) for s in dfs[0]['payload'])\n    return pd.DataFrame({'total': [round(t, 2)]})\n",
     "Total purchase amount (only purchases carry an amount)."),
    ("C06_filtered_before_parse", "controls", "benign", "py",
     {"sensors_c": 'SELECT "site", "payload" FROM "sensors_c"'},
     PY_HEAD + "    df = dfs[0][dfs[0]['site'] == 'a']\n    v = [json.loads(s)['temp_c'] for s in df['payload']]\n    return pd.DataFrame({'avg_temp_c': [round(sum(v) / len(v), 2)]})\n",
     "Average temperature at site a."),
    ("C07_filtered_after_parse", "controls", "benign", "py",
     {"sensors_c": 'SELECT "site", "payload" FROM "sensors_c"'},
     PY_HEAD + "    df = dfs[0].copy()\n    df['t'] = df['payload'].apply(lambda s: json.loads(s).get('temp_c'))\n    df = df[df['site'] == 'a']\n    return pd.DataFrame({'avg_temp_c': [round(df['t'].mean(), 2)]})\n",
     "Average temperature at site a (filter applied after parsing)."),
    ("C08_join_restriction", "controls", "benign", "py",
     {"sensors_c": 'SELECT "site", "payload" FROM "sensors_c"', "sites_c": 'SELECT "site", "region" FROM "sites_c"'},
     PY_HEAD + "    df = dfs[0].merge(dfs[1][dfs[1]['region'] == 'west'], on='site')\n    v = [json.loads(s)['temp_c'] for s in df['payload']]\n    return pd.DataFrame({'avg_temp_c': [round(sum(v) / len(v), 2)]})\n",
     "Average temperature of sensors in the west region."),
    ("C09_same_leaf_name", "controls", "benign", "py",
     {"orders_c": 'SELECT "payload" FROM "orders_c"'},
     PY_HEAD + "    n = 0\n    for s in dfs[0]['payload']:\n        c = json.loads(s).get('coupon')\n        if isinstance(c, dict) and c.get('code', '').startswith('C1'):\n            n += 1\n    return pd.DataFrame({'n': [n]})\n",
     "How many coupons have a code starting with C1?"),
    ("C10_array_optional_elem_key", "controls", "benign", "py",
     {"baskets_c": 'SELECT "payload" FROM "baskets_c"'},
     PY_HEAD + "    n = 0\n    for s in dfs[0]['payload']:\n        for it in json.loads(s)['items']:\n            if it.get('discount'):\n                n += 1\n    return pd.DataFrame({'n_discounted_items': [n]})\n",
     "How many basket items carry a discount?"),
    ("C11_numeric_strings", "controls", "benign", "py",
     {"events_c": 'SELECT "payload" FROM "events_c"'},
     PY_HEAD + "    v = [float(p['amount']) for p in map(json.loads, dfs[0]['payload']) if p.get('type') == 'purchase']\n    return pd.DataFrame({'max': [max(v)]})\n",
     "Largest purchase amount (amounts may be numeric strings)."),
    ("C12_sql_optional", "controls", "benign", "sql", None,
     "SELECT COUNT(*) AS n FROM orders_c WHERE json_extract(payload, '$.gift_wrap') = 1",
     "How many orders requested gift wrapping?"),
    ("C13_sql_irrelevant_type_filter", "controls", "benign", "sql", None,
     "SELECT ROUND(SUM(CAST(json_extract(payload, '$.amount') AS REAL)), 2) AS total FROM events_c WHERE json_extract(payload, '$.type') = 'purchase'",
     "Total purchase amount."),
    ("C14_sql_filtered_scope", "controls", "benign", "sql", None,
     "SELECT ROUND(AVG(json_extract(s.payload, '$.temp_c')), 2) AS avg_t FROM sensors_c AS s JOIN sites_c AS z ON s.site = z.site WHERE z.region = 'west'",
     "Average temperature of sensors in the west region."),
    # ---- synthetic targets (sensitivity outside Phase 0) ----
    ("T01_py_rare_legacy", "controls", "target", "py",
     {"gauges_c": 'SELECT "plant", "payload" FROM "gauges_c"'},
     PY_HEAD + "    df = dfs[0][dfs[0]['plant'] == 'p1']\n    v = [json.loads(s).get('pressure') for s in df['payload']]\n    v = [x for x in v if x is not None]\n    return pd.DataFrame({'avg_kpa': [round(sum(v) / len(v), 2)]})\n",
     "Average pressure (kPa) of gauges at plant p1."),
    ("T02_sql_rare_legacy", "controls", "target", "sql", None,
     "SELECT ROUND(AVG(json_extract(payload, '$.pressure')), 2) AS avg_kpa FROM gauges_c WHERE plant = 'p1'",
     "Average pressure (kPa) of gauges at plant p1."),
    ("T03_array_element_variant", "controls", "target_elem", "py",
     {"baskets_c": 'SELECT "payload" FROM "baskets_c"'},
     PY_HEAD + "    q = 0\n    for s in dfs[0]['payload']:\n        for it in json.loads(s)['items']:\n            q += it.get('qty', 0)\n    return pd.DataFrame({'units': [q]})\n",
     "Total units across all basket items (bundles contain child items)."),
    # ---- held-out schema variation (different domain, seed 4242) ----
    ("HO1_rare_obs_list", "heldout", "target", "py",
     {"visits": 'SELECT "clinic_id", "visit_date", "record" FROM "visits"', "clinics": 'SELECT "clinic_id", "area" FROM "clinics"'},
     PY_HEAD + "    df = dfs[0].merge(dfs[1], on='clinic_id')\n    df = df[(df['area'] == 'north') & df['visit_date'].str.startswith('2025-05')]\n    hr = []\n    for s in df['record']:\n        try:\n            hr.append(json.loads(s)['vitals']['hr'])\n        except (KeyError, TypeError):\n            pass\n    return pd.DataFrame({'avg_hr': [round(sum(hr) / len(hr), 1)]})\n",
     "Average heart rate of north-area visits in May 2025."),
    ("HO2_complete_handling", "heldout", "benign", "py",
     {"visits": 'SELECT "visit_date", "record" FROM "visits"'},
     PY_HEAD + "    hr = []\n    for s in dfs[0][dfs[0]['visit_date'].str.startswith('2025-05')]['record']:\n        p = json.loads(s)\n        if 'vitals' in p:\n            hr.append(p['vitals']['hr'])\n        else:\n            hr += [o['val'] for o in p.get('obs', []) if o['code'] == 'HR']\n    return pd.DataFrame({'avg_hr': [round(sum(hr) / len(hr), 1)]})\n",
     "Average heart rate of visits in May 2025 (admin visits have no vitals)."),
    ("HO3_optional_allergies", "heldout", "benign", "py",
     {"visits": 'SELECT "record" FROM "visits"'},
     PY_HEAD + "    n = 0\n    for s in dfs[0]['record']:\n        a = json.loads(s).get('allergies')\n        if a:\n            n += 1\n    return pd.DataFrame({'n': [n]})\n",
     "How many visits record at least one allergy?"),
    ("HO4_sql_rare_obs", "heldout", "target", "sql", None,
     "SELECT COUNT(*) AS n FROM visits WHERE json_extract(record, '$.vitals.hr') > 100 AND visit_date LIKE '2025-06%'",
     "How many June 2025 visits had a heart rate above 100?"),
    ("HO5_visit_type_counts", "heldout", "benign", "py",
     {"visits": 'SELECT "record" FROM "visits"'},
     PY_HEAD + "    c = {}\n    for s in dfs[0]['record']:\n        t = json.loads(s).get('visit_type')\n        c[t] = c.get(t, 0) + 1\n    return pd.DataFrame({'visit_type': list(c), 'n': list(c.values())})\n",
     "Number of visits per visit type."),
]


def main():
    controls_db(os.path.join(HERE, "controls.sqlite"))
    heldout_db(os.path.join(HERE, "heldout.sqlite"))
    if os.path.exists(SCN):
        shutil.rmtree(SCN)
    manifest = []
    for sid, dbn, expect, kind, subq, prog, question in SCENARIOS:
        d = os.path.join(SCN, sid)
        os.makedirs(d)
        open(os.path.join(d, f"program.{kind}"), "w", encoding="utf-8").write(prog)
        if subq:
            json.dump(subq, open(os.path.join(d, "sub_queries.json"), "w"), indent=1)
        open(os.path.join(d, "question.txt"), "w", encoding="utf-8").write(question)
        manifest.append({"id": sid, "db": f"{dbn}.sqlite", "kind": kind})
        json.dump({"expect": expect}, open(os.path.join(d, "EXPECT.json"), "w"))  # scorer-only
    json.dump(manifest, open(os.path.join(SCN, "manifest.json"), "w"), indent=1)
    print(f"{len(manifest)} scenarios written")


if __name__ == "__main__":
    main()
