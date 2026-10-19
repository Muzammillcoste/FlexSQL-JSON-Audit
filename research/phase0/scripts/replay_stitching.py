"""Diagnose Gemini MALFORMED_FUNCTION_CALL: replay the first logged stitching request
(exact messages + upstream tool definitions) under request-level variants. No agent logic involved."""
import glob, json, os, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); P0 = os.path.dirname(HERE); ROOT = os.path.dirname(os.path.dirname(P0))
sys.path.insert(0, os.path.join(ROOT, "upstream", "FlexSQL", "src")); sys.path.insert(0, os.path.join(P0, "harness"))
from p0_env import provider_env
from tools import get_tools_definition
from openai import OpenAI
rdir = sys.argv[1]; model = sys.argv[2] if len(sys.argv) > 2 else "gemini-2.5-flash"; prov = "gemini" if "gemini" in model else "groq"
recs = sorted([json.loads(l) for p in glob.glob(os.path.join(rdir, "llm_trace_*.jsonl")) for l in open(p, encoding="utf-8")], key=lambda r: r.get("seq", 0))
first = next(r for r in recs if r.get("type") == "llm_call" and r["delta_start"] == 0 and r["messages_delta"][0]["content"].startswith("You are an expert-level data scientist"))
msgs = first["messages_delta"]
tools = get_tools_definition({k: None for k in first["tool_names"]}, db_type="sqlite")
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY") or (provider_env(prov) and os.environ["OPENAI_API_KEY"]), base_url=provider_env(prov))
base = dict(temperature=1.0, top_p=1.0, reasoning_effort="high", tool_choice="auto")
variants = {
  "as_upstream": (base, tools),
  "reasoning_low": (dict(base, reasoning_effort="low"), tools),
  "temp0": (dict(base, temperature=0.0), tools),
  "no_python_tool": (base, [t for t in tools if t["function"]["name"] != "python_interpreter"]),
}
n = int(os.environ.get("N", "3"))
for name, (params, tl) in variants.items():
    c = collections.Counter()
    for _ in range(n):
        try:
            r = client.chat.completions.create(model=model, messages=msgs, tools=tl, **params)
            ch = r.choices[0]
            c[(ch.finish_reason, tuple(t.function.name for t in (ch.message.tool_calls or [])), bool(ch.message.content))] += 1
        except Exception as e:
            c[("EXC", type(e).__name__, str(e)[:120])] += 1
    print(name, dict(c), flush=True)
# --- extra variants (run with EXTRA=1)
if os.environ.get("EXTRA"):
    for name, (params, tl) in {"no_tools": (dict(temperature=1.0, top_p=1.0, reasoning_effort="high"), None),
                               "only_query_database": (base, [t for t in tools if t["function"]["name"] == "query_database"])}.items():
        c = collections.Counter()
        for _ in range(n):
            kw = dict(params)
            if tl: kw["tools"] = tl
            else: kw.pop("tool_choice", None)
            r = client.chat.completions.create(model=model, messages=msgs, **kw)
            ch = r.choices[0]
            c[(ch.finish_reason, tuple(t.function.name for t in (ch.message.tool_calls or [])), bool(ch.message.content))] += 1
        print(name, dict(c), flush=True)
