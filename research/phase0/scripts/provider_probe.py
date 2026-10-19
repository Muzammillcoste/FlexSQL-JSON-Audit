"""Provider compatibility probe using the UNMODIFIED upstream Chat class.

Runs one tool-calling round trip (query_database tool over a tiny SQLite DB)
through upstream src/chat.py exactly as FlexSQL uses it (default request params
temperature=1.0, top_p=1.0, extra_body.top_k=-1, reasoning_effort=high).
Keys come from env / .env; they are never printed.
Usage: python provider_probe.py <provider:gemini|groq> <model> [--drop-topk]
"""
import os, sys, json, sqlite3, tempfile, time, logging
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
UP = os.path.join(ROOT, "upstream", "FlexSQL", "src")
sys.path.insert(0, UP)
sys.path.insert(0, os.path.join(HERE, "..", "harness"))
from p0_env import provider_env  # noqa
prov, model = sys.argv[1], sys.argv[2]
base_url = provider_env(prov)
if "--thought-sig" in sys.argv:
    os.environ["FLEXSQL_P0_GEMINI_THOUGHT_SIG"] = "1"
if "--drop-topk" in sys.argv:
    os.environ["FLEXSQL_P0_DROP_TOPK"] = "1"
import p0_trace; p0_trace.install()
from chat import Chat
d = tempfile.mkdtemp()
db = os.path.join(d, "probe.sqlite")
c = sqlite3.connect(db); c.execute("create table t(id int, payload text)")
c.executemany("insert into t values(?,?)", [(1, '{"a":{"b":5}}'), (2, '{"a":{"b":7}}')]); c.commit(); c.close()
conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True); cur = conn.cursor()
logging.basicConfig(level=logging.INFO); lg = logging.getLogger("probe")
agent = Chat(model, base_url=base_url)
agent.enable_tools(["query_database"], db_path=d, db_type="sqlite", cursor_getter=lambda: cur)
t0 = time.time()
try:
    r = agent.get_response("Table t(id, payload TEXT JSON). Use the query_database tool to compute the sum of the JSON field a.b over all rows, then reply with just the number.", logger=lg)
    roles = [m["role"] for m in agent.messages]
    ntool = sum(1 for m in agent.messages if m["role"] == "tool")
    print(json.dumps({"ok": True, "model": model, "answer": r["text"][:200], "roles": roles, "tool_msgs": ntool,
                      "tool_outputs": [m["content"][:200] for m in agent.messages if m["role"] == "tool"],
                      "usage": agent.get_usage(), "secs": round(time.time() - t0, 1)}, indent=1))
except Exception as e:
    print(json.dumps({"ok": False, "model": model, "error": f"{type(e).__name__}: {str(e)[:800]}"}, indent=1))
