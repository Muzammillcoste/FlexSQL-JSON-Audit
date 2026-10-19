"""Deterministic generator for the Phase 0 JSON benchmark fixtures.

Produces, under fixtures/databases/<db>/:
  <db>.sqlite          the database (JSON stored as TEXT, as in Spider2-Lite)
  <table>.json         Spider2-Lite-style metadata (sample_rows = 5 random rows,
                       empty descriptions) + `column_examples`, built with the
                       same logic as upstream src/preprocessing/add_example_value.py
                       (that script is Snowflake-only; re-implemented for SQLite).
and under fixtures/:
  questions.jsonl      Spider2-format questions given to FlexSQL (no answers, no schema maps)
  cases.jsonl          per-question metadata (gold, paths, reasoning) -- NEVER given to FlexSQL
  gold/<id>.csv        gold result tables
  gold/<id>.sql        independent ground-truth SQL (validated against the Python gold)

Gold answers are computed from the canonical (pre-serialisation) records in
Python, then cross-checked against hand-written variant-aware SQL. Any
disagreement aborts generation.

Usage: python generate.py      (idempotent; overwrites outputs)
"""
import csv
import datetime as dt
import json
import math
import os
import random
import shutil
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "upstream", "FlexSQL", "src"))
from get_ddl import truncate_nested_data  # upstream helper used by add_example_value.py  # noqa: E402

DB_DIR = os.path.join(HERE, "databases")
GOLD_DIR = os.path.join(HERE, "gold")
METADATA_SEED = 7  # seed for choosing the 5 sample_rows per table

CASES = []      # filled by each builder
QUESTIONS = []


# --------------------------------------------------------------------------- utils
def r2(x):
    return round(x + 1e-12, 2)


def ts(rng, start, end):
    """Uniform random datetime in [start, end)."""
    span = int((end - start).total_seconds())
    return start + dt.timedelta(seconds=rng.randrange(span))


def write_db(db, tables):
    """tables: list of (name, [(col, type)], rows)."""
    d = os.path.join(DB_DIR, db)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    path = os.path.join(d, f"{db}.sqlite")
    conn = sqlite3.connect(path)
    for name, cols, rows in tables:
        conn.execute(f'CREATE TABLE "{name}" (' + ", ".join(f'"{c}" {t}' for c, t in cols) + ")")
        conn.executemany(f'INSERT INTO "{name}" VALUES (' + ",".join("?" * len(cols)) + ")", rows)
    conn.commit()
    for name, cols, rows in tables:
        write_metadata(conn, d, name, cols, rows)
    conn.close()
    return path


def write_metadata(conn, d, name, cols, rows):
    """Spider2-Lite table JSON + column_examples (logic of upstream add_example_value.py)."""
    # Ladder DBs (fleet_rXX) share the seed so the SAME row positions are sampled at every rarity level.
    family = os.path.basename(d).split("_r")[0] if os.path.basename(d).startswith("fleet_") else os.path.basename(d)
    rng = random.Random(f"{METADATA_SEED}-{family}-{name}")
    sample = rng.sample(rows, min(5, len(rows)))
    col_names = [c for c, _ in cols]
    sample_rows = [dict(zip(col_names, r)) for r in sample]
    # --- add_example_value.process_table_metadata, verbatim logic ---
    existing = {c: [] for c in col_names}
    for row in sample_rows:
        for c in col_names:
            val = row.get(c)
            if val is not None:
                val = truncate_nested_data(val)
                if val not in existing[c]:
                    existing[c].append(val)
    for c in col_names:
        if len(existing[c]) < 2:  # fetch_single_column_example
            q = f'SELECT DISTINCT CAST("{c}" AS TEXT) FROM "{name}" WHERE "{c}" IS NOT NULL LIMIT 10'
            ex = []
            for (v,) in conn.execute(q).fetchall():
                if isinstance(v, str):
                    try:
                        if v.strip().startswith(("[", "{")):
                            v = json.loads(v)
                    except Exception:
                        pass
                ex.append(truncate_nested_data(v))
            if ex:
                existing[c] = ex
    meta = {
        "sample_rows": sample_rows,
        "table_name": name,
        "table_fullname": name,
        "column_names": col_names,
        "column_types": [t for _, t in cols],
        "description": ["" for _ in cols],
        "column_examples": existing,
    }
    with open(os.path.join(d, f"{name}.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=4, ensure_ascii=False)


def add_case(cid, tier, db, question, gold_cols, gold_rows, gold_sql, paths, reasoning, seed, notes="",
             control=False, alt_rate=None, pair_group=None):
    QUESTIONS.append({"instance_id": cid, "db": db, "question": question, "external_knowledge": None})
    CASES.append({
        "instance_id": cid, "tier": tier, "db": db, "seed": seed, "question": question,
        "gold_columns": gold_cols, "gold_rows": gold_rows, "gold_sql_file": f"gold/{cid}.sql",
        "relevant_json_paths": paths, "required_reasoning": reasoning, "positive_control": control,
        "alt_structure_rate": alt_rate, "pair_group": pair_group, "notes": notes,
    })
    os.makedirs(GOLD_DIR, exist_ok=True)
    with open(os.path.join(GOLD_DIR, f"{cid}.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(gold_cols)
        w.writerows(gold_rows)
    with open(os.path.join(GOLD_DIR, f"{cid}.sql"), "w", encoding="utf-8") as f:
        f.write(gold_sql.strip() + "\n")


def check_sql(db_path, cid, sql, expected_rows, ordered=False):
    conn = sqlite3.connect(db_path)
    got = conn.execute(sql).fetchall()
    conn.close()
    exp = [tuple(r) for r in expected_rows]
    norm = lambda rows: [tuple(round(v, 6) if isinstance(v, float) else v for v in r) for r in rows]
    a, b = norm(got), norm(exp)
    if not ordered:
        a, b = sorted(a, key=str), sorted(b, key=str)
    ok = len(a) == len(b) and all(
        len(x) == len(y) and all((abs(p - q) < 1e-6) if isinstance(p, (int, float)) and isinstance(q, (int, float)) else p == q
                                  for p, q in zip(x, y)) for x, y in zip(a, b))
    if not ok:
        raise SystemExit(f"[{cid}] gold SQL disagrees with Python gold:\n SQL={got}\n PY ={exp}")


# --------------------------------------------------------------------------- retail (MEDIUM)
def build_retail():
    seed = 101
    rng = random.Random(seed)
    db = "retail"
    first = ["Ana", "Ben", "Chloe", "Dev", "Emil", "Fatima", "Gus", "Hana", "Ivo", "Jun", "Kai", "Lea", "Mara", "Nils", "Omar", "Pia"]
    last = ["Rossi", "Muller", "Dubois", "Smith", "Tanaka", "Garcia", "Novak", "Okafor", "Silva", "Kim", "Berg", "Moreau"]
    countries = ["US", "DE", "FR", "GB", "JP"]
    cities = {"US": ["Boston", "Austin", "Denver", "Seattle"], "DE": ["Berlin", "Munich", "Hamburg"],
              "FR": ["Paris", "Lyon", "Marseille", "Lille"], "GB": ["London", "Leeds", "Bristol"],
              "JP": ["Tokyo", "Osaka", "Kyoto"]}
    customers = []
    for cid in range(1, 301):
        customers.append(dict(
            customer_id=cid, full_name=f"{rng.choice(first)} {rng.choice(last)}",
            country=rng.choices(countries, [35, 20, 15, 15, 15])[0],
            segment=rng.choices(["consumer", "smb", "enterprise"], [60, 25, 15])[0],
            signup_date=(dt.date(2023, 1, 1) + dt.timedelta(days=rng.randrange(730))).isoformat()))
    cats = ["electronics", "books", "home", "toys", "grocery"]
    catalog = {}
    for i in range(1000, 1200):
        c = rng.choice(cats)
        base = {"electronics": (40, 400), "books": (8, 40), "home": (15, 150), "toys": (10, 80), "grocery": (2, 20)}[c]
        catalog[f"SKU-{i}"] = (c, round(rng.uniform(*base), 2))
    skus = sorted(catalog)
    orders = []
    for k in range(1500):
        cust = rng.choice(customers)
        od = dt.date(2025, 1, 1) + dt.timedelta(days=rng.randrange(181))
        status = rng.choices(["delivered", "shipped", "cancelled", "returned"], [60, 20, 10, 10])[0]
        items = []
        for sku in rng.sample(skus, rng.randint(1, 5)):
            items.append({"sku": sku, "category": catalog[sku][0], "qty": rng.choices([1, 2, 3, 4], [55, 25, 12, 8])[0],
                          "unit_price": catalog[sku][1]})
        method = rng.choices(["standard", "express", "pickup"], [60, 25, 15])[0]
        cost = {"standard": rng.choice([4.99, 5.99, 6.49]), "express": rng.choice([12.99, 14.99, 19.99]), "pickup": 0.0}[method]
        shipping = {"method": method, "cost": f"{cost:.2f}"}
        if method == "pickup":
            shipping["store_id"] = f"ST-{rng.randint(1, 30):03d}"
        else:
            ctry = cust["country"] if rng.random() < 0.92 else rng.choice(countries)
            shipping["address"] = {"city": rng.choice(cities[ctry]), "country": ctry, "postal_code": str(rng.randint(10000, 99999))}
        details = {"channel": rng.choices(["web", "mobile", "store"], [55, 35, 10])[0], "shipping": shipping, "items": items}
        u = rng.random()
        if u < 0.25:
            details["coupon"] = {"code": rng.choice(["SPRING10", "WELCOME5", "VIP15", "FLASH20"]), "discount_pct": rng.choice([5, 10, 15, 20])}
        elif u < 0.60:
            details["coupon"] = None
        if rng.random() < 0.10:
            details["gift_wrap"] = True
        details["notes"] = None if rng.random() < 0.7 else rng.choice(["leave at door", "call before delivery", "fragile"])
        orders.append(dict(order_id=10001 + k, customer_id=cust["customer_id"], order_date=od.isoformat(), status=status, details=details))
    path = write_db(db, [
        ("customers", [("customer_id", "INTEGER"), ("full_name", "TEXT"), ("country", "TEXT"), ("segment", "TEXT"), ("signup_date", "TEXT")],
         [(c["customer_id"], c["full_name"], c["country"], c["segment"], c["signup_date"]) for c in customers]),
        ("orders", [("order_id", "INTEGER"), ("customer_id", "INTEGER"), ("order_date", "TEXT"), ("status", "TEXT"), ("details", "TEXT")],
         [(o["order_id"], o["customer_id"], o["order_date"], o["status"], json.dumps(o["details"])) for o in orders]),
    ])
    cust = {c["customer_id"]: c for c in customers}

    # M01 positive control (relational only)
    g = sum(1 for c in customers if c["segment"] == "enterprise" and c["country"] == "DE")
    sql = "SELECT COUNT(*) FROM customers WHERE segment='enterprise' AND country='DE'"
    check_sql(path, "M01", sql, [(g,)])
    add_case("p0_M01", "medium", db, "How many customers in the 'enterprise' segment are located in Germany (country code 'DE')?",
             ["n_customers"], [[g]], sql, [], "Relational filter on customers only.", seed, control=True)
    # M02 arrays of objects
    g = sum(it["qty"] for o in orders if o["status"] == "delivered" for it in o["details"]["items"] if it["category"] == "electronics")
    sql = """SELECT SUM(json_extract(i.value,'$.qty')) FROM orders o, json_each(o.details,'$.items') i
WHERE o.status='delivered' AND json_extract(i.value,'$.category')='electronics'"""
    check_sql(path, "M02", sql, [(g,)])
    add_case("p0_M02", "medium", db, "What is the total number of units (sum of item quantities) of products in the 'electronics' category across all orders with status 'delivered'?",
             ["total_units"], [[g]], sql, ["orders.details.items[*].category", "orders.details.items[*].qty"],
             "Unnest the items array, filter by category, sum qty.", seed)
    # M03 number stored as string
    xs = [float(o["details"]["shipping"]["cost"]) for o in orders if o["details"]["shipping"]["method"] == "express"]
    g = r2(sum(xs) / len(xs))
    sql = "SELECT ROUND(AVG(CAST(json_extract(details,'$.shipping.cost') AS REAL)),2) FROM orders WHERE json_extract(details,'$.shipping.method')='express'"
    check_sql(path, "M03", sql, [(g,)])
    add_case("p0_M03", "medium", db, "What is the average shipping cost, in USD rounded to 2 decimal places, of orders shipped with the 'express' shipping method? All shipping costs are in USD.",
             ["avg_shipping_cost_usd"], [[g]], sql, ["orders.details.shipping.method", "orders.details.shipping.cost (string)"],
             "Nested path; cost is a numeric string that must be cast.", seed)
    # M04 missing vs null coupon
    g = sum(1 for o in orders if o["details"].get("coupon") is not None)
    sql = "SELECT COUNT(*) FROM orders WHERE json_type(details,'$.coupon')='object'"
    check_sql(path, "M04", sql, [(g,)])
    add_case("p0_M04", "medium", db, "How many orders used a coupon? An order used a coupon only if its coupon information is present and not null.",
             ["n_orders"], [[g]], sql, ["orders.details.coupon (object | null | absent)"],
             "Coupon key is absent, explicit null, or an object; count objects only.", seed)
    # M05 nested address
    g = sum(1 for o in orders if o["status"] == "delivered" and o["details"]["shipping"].get("address", {}).get("city") == "Lyon")
    sql = "SELECT COUNT(*) FROM orders WHERE status='delivered' AND json_extract(details,'$.shipping.address.city')='Lyon'"
    check_sql(path, "M05", sql, [(g,)])
    add_case("p0_M05", "medium", db, "How many orders with status 'delivered' were shipped to the city of Lyon?",
             ["n_orders"], [[g]], sql, ["orders.details.shipping.address.city"], "Nested object path (absent for pickup orders).", seed)
    # M06 GMV March
    g = r2(sum(it["qty"] * it["unit_price"] for o in orders if o["order_date"].startswith("2025-03") for it in o["details"]["items"]))
    sql = """SELECT ROUND(SUM(json_extract(i.value,'$.qty')*json_extract(i.value,'$.unit_price')),2)
FROM orders o, json_each(o.details,'$.items') i WHERE o.order_date LIKE '2025-03-%'"""
    check_sql(path, "M06", sql, [(g,)])
    add_case("p0_M06", "medium", db, "What is the gross merchandise value of orders placed in March 2025, i.e. the sum over all ordered items of quantity times unit price (in USD, before any discount, all order statuses included), rounded to 2 decimal places?",
             ["gmv_usd"], [[g]], sql, ["orders.details.items[*].qty", "orders.details.items[*].unit_price"],
             "Array unnest + per-item product + date filter on relational column.", seed)
    # M07 join + array distinct
    g = len({it["sku"] for o in orders if cust[o["customer_id"]]["segment"] == "enterprise" for it in o["details"]["items"]})
    sql = """SELECT COUNT(DISTINCT json_extract(i.value,'$.sku')) FROM orders o JOIN customers c ON c.customer_id=o.customer_id,
json_each(o.details,'$.items') i WHERE c.segment='enterprise'"""
    check_sql(path, "M07", sql, [(g,)])
    add_case("p0_M07", "medium", db, "How many distinct product SKUs were purchased by customers in the 'enterprise' segment (orders of any status)?",
             ["n_skus"], [[g]], sql, ["orders.details.items[*].sku"], "Join relational customers to JSON array elements.", seed)
    # M08 key present only when true
    g = sum(1 for o in orders if o["details"].get("gift_wrap") is True)
    sql = "SELECT COUNT(*) FROM orders WHERE json_extract(details,'$.gift_wrap')=1"
    check_sql(path, "M08", sql, [(g,)])
    add_case("p0_M08", "medium", db, "How many orders requested gift wrapping?",
             ["n_orders"], [[g]], sql, ["orders.details.gift_wrap (true | absent)"], "Optional boolean key present only when true.", seed)


# --------------------------------------------------------------------------- fleet ladder
def build_fleet_ladder():
    seed = 202
    rng = random.Random(seed)
    devices = []
    for i in range(1, 61):
        devices.append(dict(device_id=f"D-{i:03d}", site=rng.choice(["north", "south", "east", "west"]),
                            model=rng.choice(["TX-100", "TX-200", "TX-300"]),
                            installed_on=(dt.date(2024, 1, 1) + dt.timedelta(days=rng.randrange(365))).isoformat()))
    dev = {d["device_id"]: d for d in devices}
    readings = []
    for _ in range(4000):
        d = rng.choice(devices)
        t = ts(rng, dt.datetime(2025, 5, 1), dt.datetime(2025, 8, 1))
        readings.append(dict(device_id=d["device_id"], recorded_at=t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                             energy_kwh=round(rng.uniform(0.2, 3.0), 3), temp_c=round(rng.uniform(15, 35), 1),
                             humidity=rng.randint(20, 70),
                             status=rng.choices(["ok", "warn", "fault"], [82, 10, 8])[0],
                             fw=rng.choice(["4.2.1", "4.3.0"])))
    readings.sort(key=lambda r: r["recorded_at"])
    for i, r in enumerate(readings, 1):
        r["reading_id"] = i
    in_l1 = lambda r: dev[r["device_id"]]["site"] == "north" and r["recorded_at"].startswith("2025-06")
    in_l2 = lambda r: dev[r["device_id"]]["model"] == "TX-200" and r["recorded_at"].startswith("2025-07") and r["status"] == "fault"
    # Nested alternative-format sets: alt(1%) subset alt(5%) subset alt(20%).
    # Guarantee the rare variant touches each question's slice at every rate (documented).
    prng = random.Random(seed + 1)
    idx = list(range(len(readings)))
    prng.shuffle(idx)
    forced = [i for i in idx if in_l1(readings[i])][:2] + [i for i in idx if in_l2(readings[i])][:1]
    order = forced + [i for i in idx if i not in forced]
    gold_l1 = r2(sum(r["energy_kwh"] for r in readings if in_l1(r)))
    gold_l2 = sum(1 for r in readings if in_l2(r))
    tiers = {"r00": ("medium", 0.0), "r20": ("hard", 0.20), "r05": ("hardest", 0.05), "r01": ("hardest", 0.01)}
    for tag, (tier, rate) in tiers.items():
        db = f"fleet_{tag}"
        alt = set(order[:int(round(rate * len(readings)))])
        rows = []
        for i, r in enumerate(readings):
            if i in alt:
                payload = {"fw": "2.9.0", "data": {"readings": [
                    {"k": "energy", "v": int(round(r["energy_kwh"] * 1000)), "u": "Wh"},
                    {"k": "temp", "v": round(r["temp_c"] * 9 / 5 + 32, 1), "u": "F"},
                    {"k": "hum", "v": r["humidity"], "u": "%"}]},
                    "state": {"code": r["status"].upper()}}
            else:
                payload = {"fw": r["fw"], "metrics": {"energy_kwh": r["energy_kwh"], "temp_c": r["temp_c"], "humidity_pct": r["humidity"]},
                           "status": r["status"]}
            rows.append((r["reading_id"], r["device_id"], r["recorded_at"], json.dumps(payload)))
        path = write_db(db, [
            ("devices", [("device_id", "TEXT"), ("site", "TEXT"), ("model", "TEXT"), ("installed_on", "TEXT")],
             [(d["device_id"], d["site"], d["model"], d["installed_on"]) for d in devices]),
            ("readings", [("reading_id", "INTEGER"), ("device_id", "TEXT"), ("recorded_at", "TEXT"), ("payload", "TEXT")], rows),
        ])
        n_alt_l1 = sum(1 for i in alt if in_l1(readings[i]))
        n_alt_l2 = sum(1 for i in alt if in_l2(readings[i]))
        sql1 = """SELECT ROUND(SUM(COALESCE(json_extract(r.payload,'$.metrics.energy_kwh'),
  (SELECT json_extract(x.value,'$.v')/1000.0 FROM json_each(r.payload,'$.data.readings') x WHERE json_extract(x.value,'$.k')='energy'))),2)
FROM readings r JOIN devices d ON d.device_id=r.device_id
WHERE d.site='north' AND r.recorded_at >= '2025-06-01' AND r.recorded_at < '2025-07-01'"""
        check_sql(path, db, sql1, [(gold_l1,)])
        sql2 = """SELECT COUNT(*) FROM readings r JOIN devices d ON d.device_id=r.device_id
WHERE d.model='TX-200' AND r.recorded_at >= '2025-07-01' AND r.recorded_at < '2025-08-01'
AND LOWER(COALESCE(json_extract(r.payload,'$.status'), json_extract(r.payload,'$.state.code')))='fault'"""
        check_sql(path, db, sql2, [(gold_l2,)])
        ctl = rate == 0.0
        add_case(f"p0_{'M' if tier=='medium' else 'H' if tier=='hard' else 'X'}_L1_{tag}", tier, db,
                 "What is the total energy consumed, in kWh rounded to 2 decimal places, by devices located at the 'north' site, based on readings recorded in June 2025 (UTC)? Note: 1 kWh = 1000 Wh.",
                 ["total_energy_kwh"], [[gold_l1]], sql1,
                 ["readings.payload.metrics.energy_kwh"] + ([] if ctl else ["readings.payload.data.readings[k='energy'].v (Wh, legacy fw 2.9.0)"]),
                 "Join devices; sum energy across both payload formats, converting Wh to kWh." if not ctl else "Join devices; sum metrics.energy_kwh.",
                 seed, control=ctl, alt_rate=rate, pair_group="fleet_L1",
                 notes=f"alt-format readings in this question's slice: {n_alt_l1}; total alt readings: {len(alt)}")
        add_case(f"p0_{'M' if tier=='medium' else 'H' if tier=='hard' else 'X'}_L2_{tag}", tier, db,
                 "How many readings from devices of model 'TX-200', recorded in July 2025 (UTC), reported a 'fault' status? Status values are case-insensitive.",
                 ["n_fault_readings"], [[gold_l2]], sql2,
                 ["readings.payload.status"] + ([] if ctl else ["readings.payload.state.code (legacy fw 2.9.0)"]),
                 "Join devices; status lives at different paths/casing across formats." if not ctl else "Join devices; filter payload.status.",
                 seed, control=ctl, alt_rate=rate, pair_group="fleet_L2",
                 notes=f"alt-format fault readings in this question's slice: {n_alt_l2}")


# --------------------------------------------------------------------------- payments (HARD + 1 hardest)
def build_payments():
    seed = 303
    rng = random.Random(seed)
    db = "payments"
    merchants = []
    for i in range(1, 41):
        merchants.append(dict(merchant_id=f"M-{i:02d}", merchant_name=f"{rng.choice(['Acme','Blue','Nova','Peak','Urban','Lumen','Atlas','Zen'])} {rng.choice(['Goods','Labs','Retail','Travel','Foods','Studio'])} {i}",
                              region=rng.choices(["NA", "EMEA", "APAC"], [40, 35, 25])[0],
                              tier=rng.choices(["gold", "silver", "bronze"], [20, 35, 45])[0]))
    mer = {m["merchant_id"]: m for m in merchants}
    ev = []
    for _ in range(2500):
        t = ts(rng, dt.datetime(2025, 1, 1), dt.datetime(2025, 7, 1))
        mo = t.month
        ver = rng.choices(["2023-01", "2024-06", "2025-03"], {1: [70, 30, 0], 2: [70, 30, 0], 3: [40, 45, 15], 4: [40, 45, 15]}.get(mo, [20, 40, 40]))[0]
        cur = rng.choices(["USD", "EUR"], [70, 30])[0]
        amt = round(math.exp(rng.uniform(math.log(5), math.log(500))), 2)
        if ver == "2025-03":
            amt = min(amt, 399.0)
        status = rng.choices(["succeeded", "failed", "refunded"], [80, 12, 8])[0]
        if ver == "2025-03" and rng.random() < 0.25:
            method = {"kind": "wallet", "provider": rng.choice(["apple_pay", "google_pay"]), "brand": rng.choice(["visa", "mastercard"])}
        else:
            method = {"kind": "card", "brand": rng.choices(["visa", "mastercard", "amex"], [50, 35, 15])[0]}
        proc = r2(amt * 0.029 + 0.30)
        fx = r2(amt * 0.01) if cur == "EUR" else 0.0
        if ver == "2023-01":
            email = "not_collected"
        elif ver == "2024-06":
            email = rng.choices(["provided", "declined"], [70, 30])[0]
        else:
            email = rng.choices(["provided", "declined", "not_collected"], [60, 25, 15])[0]
        ev.append(dict(created_at=t, merchant_id=rng.choice(merchants)["merchant_id"], ver=ver, cur=cur, amt=amt, status=status,
                       method=method, proc=proc, fx=fx, email=email, connect=False,
                       last4=f"{rng.randint(0, 9999):04d}", cus=f"cus_{rng.randint(10**7, 10**8 - 1)}"))
    ev.sort(key=lambda e: e["created_at"])
    # H10: guarantee the true maximum USD succeeded amount is a numeric (v1) value.
    v1_usd = [e for e in ev if e["ver"] == "2023-01" and e["cur"] == "USD" and e["status"] == "succeeded"]
    top = max(v1_usd, key=lambda e: e["amt"])
    top["amt"] = 499.99
    top["proc"] = r2(499.99 * 0.029 + 0.30)
    # X05: rare (1%) "connect" variant of 2024-06 payloads; EUR only, amount nested in charges.data[].
    v2_eur = [e for e in ev if e["ver"] == "2024-06" and e["cur"] == "EUR"]
    crng = random.Random(seed + 5)
    q2_succ = [e for e in v2_eur if e["status"] == "succeeded" and e["created_at"].month >= 4]
    chosen = crng.sample(q2_succ, 6)
    rest = [e for e in v2_eur if e not in chosen]
    chosen += crng.sample(rest, 25 - len(chosen))
    for e in chosen:
        e["connect"] = True
    rows = []
    for i, e in enumerate(ev, 1):
        e["event_id"] = f"evt_{i:05d}"
        b = e["method"]["brand"]
        if e["ver"] == "2023-01":
            p = {"object": "charge", "amount": e["amt"], "currency": e["cur"], "status": e["status"],
                 "card": {"brand": b, "last4": e["last4"]}, "fee": r2(e["proc"] + e["fx"]), "customer": {"id": e["cus"]}}
        elif e["ver"] == "2024-06":
            cents = int(round(e["amt"] * 100))
            p = {"object": "payment_intent"}
            if e["connect"]:
                p["charges"] = {"data": [{"amount_cents": cents, "captured": True}]}
                p["platform"] = "connect"
            else:
                p["amount_cents"] = cents
            p["currency_code"] = e["cur"].lower()
            p["state"] = e["status"].upper()
            p["payment_method"] = {"type": "card", "card": {"network": b.upper(), "last4": e["last4"]}}
            fees = [{"type": "processing", "amount_cents": int(round(e["proc"] * 100))}]
            if e["fx"]:
                fees.append({"type": "fx", "amount_cents": int(round(e["fx"] * 100))})
            p["fees"] = fees
            p["customer"] = {"id": e["cus"], "email": (f"user{i}@example.com" if e["email"] == "provided" else None)}
        else:
            if e["method"]["kind"] == "card":
                inst = {"kind": "card", "details": {"brand": b.capitalize() if b != "amex" else "AmEx", "last4": e["last4"]}}
            else:
                inst = {"kind": "wallet", "details": {"provider": e["method"]["provider"], "card_brand": b}}
            contact = {}
            if e["email"] == "provided":
                contact["email"] = f"user{i}@example.com"
            elif e["email"] == "declined":
                contact["email"] = None
            contact["locale"] = rng.choice(["en-US", "de-DE", "fr-FR", "ja-JP"])
            p = {"transaction": {"value": {"amount": f"{e['amt']:.2f}", "currency": e["cur"]}, "result": {"status": e["status"]}},
                 "instrument": inst, "pricing": {"fees": {"processing": f"{e['proc']:.2f}", "fx": f"{e['fx']:.2f}"}},
                 "customer": {"ref": e["cus"], "contact": contact}}
        rows.append((e["event_id"], e["merchant_id"], e["created_at"].strftime("%Y-%m-%d %H:%M:%S"), e["ver"], json.dumps(p)))
    path = write_db(db, [
        ("merchants", [("merchant_id", "TEXT"), ("merchant_name", "TEXT"), ("region", "TEXT"), ("tier", "TEXT")],
         [(m["merchant_id"], m["merchant_name"], m["region"], m["tier"]) for m in merchants]),
        ("payment_events", [("event_id", "TEXT"), ("merchant_id", "TEXT"), ("created_at", "TEXT"), ("api_version", "TEXT"), ("payload", "TEXT")], rows),
    ])
    AMT = """COALESCE(json_extract(p.payload,'$.amount'), json_extract(p.payload,'$.amount_cents')/100.0,
  json_extract(p.payload,'$.charges.data[0].amount_cents')/100.0, CAST(json_extract(p.payload,'$.transaction.value.amount') AS REAL))"""
    CUR = "UPPER(COALESCE(json_extract(p.payload,'$.currency'), json_extract(p.payload,'$.currency_code'), json_extract(p.payload,'$.transaction.value.currency')))"
    ST = "LOWER(COALESCE(json_extract(p.payload,'$.status'), json_extract(p.payload,'$.state'), json_extract(p.payload,'$.transaction.result.status')))"
    succ_usd = lambda e: e["status"] == "succeeded" and e["cur"] == "USD"
    V = ["payment_events.payload.amount (v2023-01, number)", "payment_events.payload.amount_cents (v2024-06, int cents)",
         "payment_events.payload.transaction.value.amount (v2025-03, string)"]
    C = ["payload.currency", "payload.currency_code (lowercase)", "payload.transaction.value.currency"]
    S = ["payload.status", "payload.state (uppercase)", "payload.transaction.result.status"]
    # H01
    g = r2(sum(e["amt"] for e in ev if succ_usd(e) and mer[e["merchant_id"]]["region"] == "EMEA"))
    sql = f"SELECT ROUND(SUM({AMT}),2) FROM payment_events p JOIN merchants m ON m.merchant_id=p.merchant_id WHERE m.region='EMEA' AND {ST}='succeeded' AND {CUR}='USD'"
    check_sql(path, "H01", sql, [(g,)])
    add_case("p0_H01", "hard", db, "What is the total amount, in US dollars rounded to 2 decimal places, of succeeded payments denominated in US dollars (USD) received by merchants in the 'EMEA' region? Ignore payments in other currencies. Payment status and currency codes are case-insensitive.",
             ["total_usd"], [[g]], sql, V + C + S, "Coalesce amount/currency/status across 3 API versions (types: number, int cents, string); join merchants.", seed)
    # H02
    g = sum(1 for e in ev if e["status"] == "succeeded" and e["method"]["brand"] == "visa")
    sql = f"""SELECT COUNT(*) FROM payment_events p WHERE {ST}='succeeded' AND LOWER(COALESCE(json_extract(p.payload,'$.card.brand'),
 json_extract(p.payload,'$.payment_method.card.network'), json_extract(p.payload,'$.instrument.details.brand'),
 json_extract(p.payload,'$.instrument.details.card_brand')))='visa'"""
    check_sql(path, "H02", sql, [(g,)])
    add_case("p0_H02", "hard", db, "How many succeeded payments were paid with a Visa card? Include Visa cards used through digital wallets. Card brand and payment status values are case-insensitive.",
             ["n_payments"], [[g]], sql, ["payload.card.brand", "payload.payment_method.card.network", "payload.instrument.details.brand",
                                         "payload.instrument.details.card_brand (wallet)"] + S,
             "Equivalent values under different names/casing; wallet payments carry the brand in a different key.", seed)
    # H03
    g = r2(sum(e["proc"] for e in ev if succ_usd(e) and e["created_at"].month <= 3))
    sql = f"""SELECT ROUND(SUM(COALESCE(json_extract(p.payload,'$.fee'),
 (SELECT json_extract(f.value,'$.amount_cents')/100.0 FROM json_each(p.payload,'$.fees') f WHERE json_extract(f.value,'$.type')='processing'),
 CAST(json_extract(p.payload,'$.pricing.fees.processing') AS REAL))),2)
FROM payment_events p WHERE {ST}='succeeded' AND {CUR}='USD' AND p.created_at < '2025-04-01'"""
    check_sql(path, "H03", sql, [(g,)])
    add_case("p0_H03", "hard", db, "What is the total processing fee, in US dollars rounded to 2 decimal places, charged on succeeded USD-denominated payments created in the first quarter of 2025 (January to March)? Exclude foreign-exchange (FX) fees. Status and currency codes are case-insensitive.",
             ["total_processing_fee_usd"], [[g]], sql, ["payload.fee (v2023-01; equals processing fee for USD)", "payload.fees[type='processing'].amount_cents",
                                                       "payload.pricing.fees.processing (string)"] + C + S,
             "Fee representation differs per version: scalar, typed array in cents, nested string map.", seed,
             notes="For USD payments the 2023-01 'fee' contains no FX component, so it equals the processing fee.")
    # H04 missing vs null
    g = sum(1 for e in ev if e["email"] == "declined")
    sql = """SELECT COUNT(*) FROM payment_events p WHERE json_type(p.payload,'$.customer.email')='null' OR json_type(p.payload,'$.customer.contact.email')='null'"""
    check_sql(path, "H04", sql, [(g,)])
    add_case("p0_H04", "hard", db, "How many payment events explicitly record that the customer's email address is unknown, i.e. the email field is present but its value is null? Events in which no email field exists at all must not be counted.",
             ["n_events"], [[g]], sql, ["payload.customer.email (v2024-06)", "payload.customer.contact.email (v2025-03)"],
             "Distinguish JSON null from absent key across two nesting depths.", seed)
    # H05 per tier
    rows_g = []
    for tier in ["bronze", "gold", "silver"]:
        xs = [e["amt"] for e in ev if succ_usd(e) and mer[e["merchant_id"]]["tier"] == tier]
        rows_g.append([tier, r2(sum(xs) / len(xs))])
    sql = f"SELECT m.tier, ROUND(AVG({AMT}),2) FROM payment_events p JOIN merchants m ON m.merchant_id=p.merchant_id WHERE {ST}='succeeded' AND {CUR}='USD' GROUP BY m.tier"
    check_sql(path, "H05", sql, rows_g)
    add_case("p0_H05", "hard", db, "For each merchant tier, what is the average amount, in US dollars rounded to 2 decimal places, of succeeded USD-denominated payments? Return the tier and the average. Status and currency codes are case-insensitive.",
             ["tier", "avg_amount_usd"], rows_g, sql, V + C + S, "Join + group by + cross-version amount normalisation.", seed)
    # H06
    g = sum(1 for e in ev if e["status"] == "refunded")
    sql = f"SELECT COUNT(*) FROM payment_events p WHERE {ST}='refunded'"
    check_sql(path, "H06", sql, [(g,)])
    add_case("p0_H06", "hard", db, "How many payments were refunded? Payment status values are case-insensitive.",
             ["n_payments"], [[g]], sql, S, "Status stored under three different paths/casings.", seed)
    # H09 positive control
    g = sum(1 for e in ev if e["created_at"].month == 2 and mer[e["merchant_id"]]["region"] == "APAC")
    sql = "SELECT COUNT(*) FROM payment_events p JOIN merchants m ON m.merchant_id=p.merchant_id WHERE m.region='APAC' AND p.created_at LIKE '2025-02-%'"
    check_sql(path, "H09", sql, [(g,)])
    add_case("p0_H09", "hard", db, "How many payment events were created in February 2025 for merchants in the 'APAC' region?",
             ["n_events"], [[g]], sql, [], "Relational join + date filter only.", seed, control=True)
    # H10 type inconsistency
    g = max(e["amt"] for e in ev if succ_usd(e))
    sql = f"SELECT MAX({AMT}) FROM payment_events p WHERE {ST}='succeeded' AND {CUR}='USD'"
    check_sql(path, "H10", sql, [(g,)])
    add_case("p0_H10", "hard", db, "What is the largest single succeeded payment amount among USD-denominated payments, in US dollars? Status and currency codes are case-insensitive.",
             ["max_amount_usd"], [[g]], sql, V + C + S,
             "Amount types differ (number / int cents / string); naive MAX over mixed types in SQLite returns a TEXT value.", seed)
    # X05 rare connect variant
    g = r2(sum(e["amt"] for e in ev if e["status"] == "succeeded" and e["cur"] == "EUR" and e["created_at"].month >= 4))
    sql = f"SELECT ROUND(SUM({AMT}),2) FROM payment_events p WHERE {ST}='succeeded' AND {CUR}='EUR' AND p.created_at >= '2025-04-01'"
    check_sql(path, "X05", sql, [(g,)])
    n_conn = sum(1 for e in ev if e["connect"] and e["status"] == "succeeded" and e["cur"] == "EUR" and e["created_at"].month >= 4)
    add_case("p0_X05", "hardest", db, "What is the total amount, in euros rounded to 2 decimal places, of succeeded euro-denominated (EUR) payments created in the second quarter of 2025 (April to June)? Status and currency codes are case-insensitive.",
             ["total_eur"], [[g]], sql, V + ["payload.charges.data[0].amount_cents (rare 'connect' variant of v2024-06, 1% of events)"] + C + S,
             "All version paths plus a rare (1%) sub-variant of 2024-06 that has no top-level amount_cents.", seed, alt_rate=0.01,
             notes=f"connect-variant events in this question's slice: {n_conn} of 25 total")


# --------------------------------------------------------------------------- logistics (HARDEST)
def build_logistics():
    seed = 404
    rng = random.Random(seed)
    db = "logistics"
    carriers = [("FF", "FastFreight", "road"), ("BX", "BoxRoad", "road"), ("SA", "SkyAir", "air"),
                ("QX", "QuickExpress", "air"), ("OC", "OceanCargo", "sea"), ("RL", "RailLink", "rail")]
    mode = {c: m for c, _, m in carriers}
    skus = [f"P-{i:04d}" for i in range(1, 400)]
    items = lambda n: [{"sku": s, "qty": rng.randint(1, 6)} for s in rng.sample(skus, n)]
    ships = []
    for _ in range(1800):
        cc = rng.choices([c for c, _, _ in carriers], [25, 15, 15, 15, 15, 15])[0]
        created = ts(rng, dt.datetime(2025, 1, 1), dt.datetime(2025, 7, 1))
        pk = []
        for _ in range(rng.choices([1, 2, 3, 4], [50, 30, 15, 5])[0]):
            u = rng.random()
            if u < 0.035 and mode[cc] in ("road", "rail", "sea"):
                boxes = [{"weight_kg": round(rng.uniform(5, 30), 2), "items": items(rng.randint(1, 3))} for _ in range(rng.randint(3, 8))]
                pk.append({"type": "pallet", "gross_weight_kg": round(sum(b["weight_kg"] for b in boxes), 2), "boxes": boxes})
            elif u < 0.105:
                pk.append({"type": "envelope", "weight_g": rng.randint(50, 900), "items": items(1)})
            else:
                dims = [rng.randint(10, 80) for _ in range(3)]
                pk.append({"type": "box", "weight_kg": round(rng.uniform(0.5, 25), 2), "dims_cm": dims, "items": items(rng.randint(1, 4))})
        actual = sum(p.get("weight_kg", 0) or p.get("gross_weight_kg", 0) or p.get("weight_g", 0) / 1000 for p in pk)
        vol = sum((p["dims_cm"][0] * p["dims_cm"][1] * p["dims_cm"][2]) / 5000 for p in pk if p["type"] == "box")
        manifest = {"billable_weight_kg": round(max(actual, vol), 2), "declared_value_usd": round(rng.uniform(20, 5000), 2), "packages": pk}
        # tracking: delivered with prob .85; transit hours depend on mode
        delivered = rng.random() < 0.85
        hrs = {"air": rng.uniform(12, 60), "road": rng.uniform(24, 120), "rail": rng.uniform(48, 160), "sea": rng.uniform(300, 700)}[mode[cc]]
        pick = created + dt.timedelta(hours=rng.uniform(1, 6))
        deliv = created + dt.timedelta(hours=hrs) if delivered else None
        ships.append(dict(cc=cc, created=created, manifest=manifest, pick=pick, deliv=deliv, ref=f"TRK{rng.randint(10**8, 10**9-1)}"))
    ships.sort(key=lambda s: s["created"])
    drift = dt.datetime(2025, 6, 10)
    rows = []
    for i, s in enumerate(ships, 1):
        s["id"] = f"SHP-{i:06d}"
        if s["created"] < drift:
            evs = [{"code": "PICKED_UP", "at": s["pick"].strftime("%Y-%m-%dT%H:%M:%SZ")},
                   {"code": "IN_TRANSIT", "at": (s["pick"] + dt.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")}]
            if s["deliv"]:
                evs.append({"code": "DELIVERED", "at": s["deliv"].strftime("%Y-%m-%dT%H:%M:%SZ")})
            tracking = {"carrier_ref": s["ref"], "events": evs}
        else:
            epoch = lambda d: int(d.replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
            cps = [{"status": "picked_up", "ts": epoch(s["pick"])}, {"status": "in_transit", "ts": epoch(s["pick"] + dt.timedelta(hours=2))}]
            if s["deliv"]:
                cps.append({"status": "delivered", "ts": epoch(s["deliv"])})
            tracking = {"ref": s["ref"], "history": {"checkpoints": cps}}
        s["fmt"] = "events" if s["created"] < drift else "history"
        rows.append((s["id"], s["cc"], s["created"].strftime("%Y-%m-%d %H:%M:%S"), json.dumps(s["manifest"]), json.dumps(tracking)))
    path = write_db(db, [
        ("carriers", [("carrier_code", "TEXT"), ("carrier_name", "TEXT"), ("transport_mode", "TEXT")], carriers),
        ("shipments", [("shipment_id", "TEXT"), ("carrier_code", "TEXT"), ("created_at", "TEXT"), ("manifest", "TEXT"), ("tracking", "TEXT")], rows),
    ])
    # X01
    def pw(p):
        return p["weight_kg"] if p["type"] == "box" else p["gross_weight_kg"] if p["type"] == "pallet" else p["weight_g"] / 1000
    g = round(sum(pw(p) for s in ships if s["created"].month == 5 for p in s["manifest"]["packages"]) + 1e-9, 1)
    sql = """SELECT ROUND(SUM(COALESCE(json_extract(k.value,'$.weight_kg'), json_extract(k.value,'$.gross_weight_kg'),
 json_extract(k.value,'$.weight_g')/1000.0)),1) FROM shipments s, json_each(s.manifest,'$.packages') k WHERE s.created_at LIKE '2025-05-%'"""
    check_sql(path, "X01", sql, [(g,)])
    add_case("p0_X01", "hardest", db, "What is the total actual (physical) weight, in kilograms rounded to 1 decimal place, of all packages in shipments created in May 2025? Use the physical weight of the packages, not the billable weight. Note: 1 kg = 1000 g.",
             ["total_weight_kg"], [[g]], sql, ["shipments.manifest.packages[type='box'].weight_kg", "shipments.manifest.packages[type='envelope'].weight_g",
                                              "shipments.manifest.packages[type='pallet'].gross_weight_kg", "decoy: shipments.manifest.billable_weight_kg"],
             "Mixed-structure package array (box/envelope/pallet) with different weight keys/units; decoy billable weight.", seed,
             notes="A pallet's gross_weight_kg equals the sum of its boxes' weights, so summing either gives the same physical weight (no double counting).")
    # X02
    def units(p):
        if p["type"] == "pallet":
            return sum(it["qty"] for b in p["boxes"] for it in b["items"])
        return sum(it["qty"] for it in p["items"])
    g = sum(units(p) for s in ships if s["cc"] == "FF" for p in s["manifest"]["packages"])
    sql = """SELECT (SELECT COALESCE(SUM(json_extract(i.value,'$.qty')),0) FROM shipments s JOIN carriers c ON c.carrier_code=s.carrier_code,
  json_each(s.manifest,'$.packages') k, json_each(k.value,'$.items') i WHERE c.carrier_name='FastFreight')
 + (SELECT COALESCE(SUM(json_extract(i.value,'$.qty')),0) FROM shipments s JOIN carriers c ON c.carrier_code=s.carrier_code,
  json_each(s.manifest,'$.packages') k, json_each(k.value,'$.boxes') b, json_each(b.value,'$.items') i WHERE c.carrier_name='FastFreight')"""
    check_sql(path, "X02", sql, [(g,)])
    npal = sum(1 for s in ships if s["cc"] == "FF" for p in s["manifest"]["packages"] if p["type"] == "pallet")
    add_case("p0_X02", "hardest", db, "How many item units in total (the sum of item quantities across all packages) were shipped by the carrier named 'FastFreight'?",
             ["total_units"], [[g]], sql, ["shipments.manifest.packages[*].items[*].qty", "shipments.manifest.packages[type='pallet'].boxes[*].items[*].qty"],
             "Pallet packages nest items one level deeper (boxes[].items[]); naive unnest silently omits them.", seed,
             notes=f"FastFreight pallet packages: {npal}")
    # X03
    june = [s for s in ships if s["created"].month == 6]
    g = sum(1 for s in june if s["deliv"])
    sql = """SELECT COUNT(*) FROM shipments s WHERE s.created_at LIKE '2025-06-%' AND (
 EXISTS (SELECT 1 FROM json_each(s.tracking,'$.events') e WHERE json_extract(e.value,'$.code')='DELIVERED') OR
 EXISTS (SELECT 1 FROM json_each(s.tracking,'$.history.checkpoints') c WHERE json_extract(c.value,'$.status')='delivered'))"""
    check_sql(path, "X03", sql, [(g,)])
    add_case("p0_X03", "hardest", db, "How many shipments created in June 2025 have been delivered, i.e. their tracking history contains a delivery event?",
             ["n_delivered"], [[g]], sql, ["shipments.tracking.events[*].code='DELIVERED' (created before 2025-06-10)",
                                          "shipments.tracking.history.checkpoints[*].status='delivered' (created on/after 2025-06-10)"],
             "Schema drift by time without a version column; new format only in the last ~11% of rows.", seed,
             notes=f"June shipments: {len(june)}, of which new-format: {sum(1 for s in june if s['fmt']=='history')}")
    # X04
    air = [s for s in ships if mode[s["cc"]] == "air" and s["deliv"]]
    hours = [(s["deliv"].replace(microsecond=0) - s["created"].replace(microsecond=0)).total_seconds() / 3600 for s in air]
    g = round(sum(hours) / len(hours) + 1e-9, 1)
    sql = """SELECT ROUND(AVG((COALESCE(
  (SELECT unixepoch(json_extract(e.value,'$.at')) FROM json_each(s.tracking,'$.events') e WHERE json_extract(e.value,'$.code')='DELIVERED'),
  (SELECT json_extract(c.value,'$.ts')/1000 FROM json_each(s.tracking,'$.history.checkpoints') c WHERE json_extract(c.value,'$.status')='delivered'))
  - unixepoch(s.created_at))/3600.0),1)
FROM shipments s JOIN carriers c ON c.carrier_code=s.carrier_code WHERE c.transport_mode='air'
AND COALESCE((SELECT 1 FROM json_each(s.tracking,'$.events') e WHERE json_extract(e.value,'$.code')='DELIVERED'),
             (SELECT 1 FROM json_each(s.tracking,'$.history.checkpoints') c WHERE json_extract(c.value,'$.status')='delivered')) = 1"""
    check_sql(path, "X04", sql, [(g,)])
    add_case("p0_X04", "hardest", db, "For delivered shipments handled by carriers whose transport mode is 'air', what is the average transit time in hours, measured from the shipment's created_at timestamp (UTC) to its delivery event, rounded to 1 decimal place?",
             ["avg_transit_hours"], [[g]], sql, ["shipments.tracking.events[code='DELIVERED'].at (ISO-8601 string)",
                                                "shipments.tracking.history.checkpoints[status='delivered'].ts (epoch milliseconds)"],
             "Time drift: delivery timestamp format changes from ISO string to epoch ms; join carriers.", seed)
    # X06 positive control
    g = sum(1 for s in ships if mode[s["cc"]] == "sea")
    sql = "SELECT COUNT(*) FROM shipments s JOIN carriers c ON c.carrier_code=s.carrier_code WHERE c.transport_mode='sea'"
    check_sql(path, "X06", sql, [(g,)])
    add_case("p0_X06", "hardest", db, "How many shipments were handled by carriers whose transport mode is 'sea'?",
             ["n_shipments"], [[g]], sql, [], "Relational join only.", seed, control=True)


def main():
    os.makedirs(DB_DIR, exist_ok=True)
    if os.path.exists(GOLD_DIR):
        shutil.rmtree(GOLD_DIR)
    build_retail()
    build_fleet_ladder()
    build_payments()
    build_logistics()
    order = {"medium": 0, "hard": 1, "hardest": 2}
    CASES.sort(key=lambda c: (order[c["tier"]], c["instance_id"]))
    qmap = {q["instance_id"]: q for q in QUESTIONS}
    with open(os.path.join(HERE, "questions.jsonl"), "w", encoding="utf-8") as f:
        for c in CASES:
            f.write(json.dumps(qmap[c["instance_id"]], ensure_ascii=False) + "\n")
    with open(os.path.join(HERE, "cases.jsonl"), "w", encoding="utf-8") as f:
        for c in CASES:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    from collections import Counter
    print("cases:", len(CASES), dict(Counter(c["tier"] for c in CASES)))
    for c in CASES:
        print(f'{c["instance_id"]:16s} {c["tier"]:8s} {c["db"]:11s} gold={c["gold_rows"]} {c["notes"]}')


if __name__ == "__main__":
    main()
