"""Phase 0 observation harness for upstream FlexSQL (NOT part of the agent).

Wraps ``openai.resources.chat.completions.Completions.create`` to:
  1. append every request/response to a JSONL trace (messages logged as deltas
     per message-list object, so the full conversation is reconstructable);
  2. retry transient provider errors (429/5xx/connection) with exponential
     backoff -- infrastructure handling only, the request is resent unchanged;
  3. optionally apply a documented provider-compatibility transform
     (FLEXSQL_P0_DROP_TOPK=1 removes the vLLM-only ``extra_body.top_k``).

It never alters prompts, tool definitions, tool results, or model outputs.
API keys are never written; any key string is scrubbed from logged text.

Env:
  FLEXSQL_P0_TRACE        path of JSONL trace file ("{pid}" is substituted)
  FLEXSQL_P0_DROP_TOPK    "1" to drop extra_body.top_k
  FLEXSQL_P0_QUOTA_FLAG   path of a marker file written when a daily quota is hit
  FLEXSQL_P0_MAX_RETRIES  default 8
"""
import json
import os
import random
import re
import threading
import time

_lock = threading.Lock()
_seen = {}  # id(messages list) -> (n messages logged, fingerprint of last logged message)
_seq = [0]
_thought_sigs = {}  # tool_call id -> extra_content (Gemini thought signature), see FLEXSQL_P0_GEMINI_THOUGHT_SIG
_patched = [False]


def _fp(m):
    try:
        return hash(json.dumps(m, sort_keys=True, default=str))
    except Exception:
        return hash(repr(m))


def _secrets():
    out = []
    for k in ("OPENAI_API_KEY", "GEMINI_API_KEY", "GEMINI_KEY", "GROQ_API_KEY", "GROQ_KEY"):
        v = os.environ.get(k)
        if v and len(v) > 8:
            out.append(v)
    return out


def _scrub(s):
    if not isinstance(s, str):
        s = json.dumps(s, default=str, ensure_ascii=False)
    for sec in _secrets():
        s = s.replace(sec, "<REDACTED>")
    return s


def _write(rec):
    path = os.environ.get("FLEXSQL_P0_TRACE")
    if not path:
        return
    path = path.replace("{pid}", str(os.getpid()))
    line = _scrub(json.dumps(rec, default=str, ensure_ascii=False))
    with _lock:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def _is_daily_quota(err_text):
    t = err_text.lower()
    return any(s in t for s in ("perday", "per day", "requests per day", "tokens per day", "(rpd)", "(tpd)", "daily"))


def _retry_after(err):
    try:
        h = err.response.headers
        if h.get("retry-after"):
            return float(h["retry-after"])
    except Exception:
        pass
    m = re.search(r"retry(?:Delay| in)[\"': ]+([0-9.]+)s", str(err))
    if m:
        return float(m.group(1))
    return None


def _wrap(orig):
    import openai

    transient = (openai.RateLimitError, openai.APIConnectionError, openai.APITimeoutError,
                 openai.InternalServerError)

    def create(self, *args, **kwargs):
        msgs = kwargs.get("messages", [])
        n_sig_restored = 0
        if os.environ.get("FLEXSQL_P0_GEMINI_THOUGHT_SIG") == "1":
            # Transport-level compat (Gemini 3.x): upstream chat.py rebuilds assistant tool_call
            # dicts as {id,type,function}, dropping Gemini's extra_content.google.thought_signature,
            # which the API requires on replay. Re-attach it by tool_call id in a COPY of the
            # outgoing messages; upstream's stored conversation and all content are untouched.
            out = []
            for m in msgs:
                if isinstance(m, dict) and m.get("role") == "assistant" and m.get("tool_calls"):
                    tcs = []
                    for tc in m["tool_calls"]:
                        sig = _thought_sigs.get(tc.get("id"))
                        if sig is not None and "extra_content" not in tc:
                            tc = dict(tc, extra_content=sig)
                            n_sig_restored += 1
                        tcs.append(tc)
                    m = dict(m, tool_calls=tcs)
                out.append(m)
            kwargs["messages"] = out
        if os.environ.get("FLEXSQL_P0_DROP_TOPK") == "1":
            eb = kwargs.get("extra_body")
            if isinstance(eb, dict) and "top_k" in eb:
                eb = {k: v for k, v in eb.items() if k != "top_k"}
                if eb:
                    kwargs["extra_body"] = eb
                else:
                    kwargs.pop("extra_body")
        with _lock:
            _seq[0] += 1
            seq = _seq[0]
            lid = id(msgs)
            start, fp = _seen.get(lid, (0, None))
            # id() can be reused after a list is garbage-collected: verify the last
            # message we logged for this id is still at the same position.
            if start > len(msgs) or (start and _fp(msgs[start - 1]) != fp):
                start = 0
            _seen[lid] = (len(msgs), _fp(msgs[-1]) if msgs else None)
        params = {k: v for k, v in kwargs.items() if k not in ("messages", "tools")}
        rec = {
            "type": "llm_call", "seq": seq, "pid": os.getpid(), "ts": time.time(),
            "model": kwargs.get("model"), "params": params,
            "tool_names": [t["function"]["name"] for t in kwargs.get("tools", []) or []],
            "msg_list_id": lid, "n_messages": len(msgs), "delta_start": start,
            "messages_delta": msgs[start:],
        }
        max_retries = int(os.environ.get("FLEXSQL_P0_MAX_RETRIES", "8"))
        attempt = 0
        t0 = time.time()
        while True:
            try:
                resp = orig(self, *args, **kwargs)
                break
            except transient as e:
                attempt += 1
                txt = str(e)
                daily = isinstance(e, openai.RateLimitError) and _is_daily_quota(txt)
                _write({"type": "provider_error", "seq": seq, "pid": os.getpid(), "ts": time.time(),
                        "attempt": attempt, "error": f"{type(e).__name__}: {txt[:1500]}", "daily_quota": daily})
                if daily or attempt > max_retries:
                    flag = os.environ.get("FLEXSQL_P0_QUOTA_FLAG")
                    if flag:
                        with open(flag, "a", encoding="utf-8") as f:
                            f.write(_scrub(f"{time.time()} seq={seq} daily={daily} {type(e).__name__}: {txt[:500]}") + "\n")
                    rec["error"] = f"{type(e).__name__}: {txt[:1500]}"
                    rec["latency_s"] = time.time() - t0
                    _write(rec)
                    raise
                ra = _retry_after(e)
                delay = min(120.0, ra if ra else 5.0 * (2 ** (attempt - 1))) + random.uniform(0, 2)
                time.sleep(delay)
            except Exception as e:  # non-transient: log and propagate unchanged
                rec["error"] = f"{type(e).__name__}: {str(e)[:1500]}"
                rec["latency_s"] = time.time() - t0
                _write(rec)
                raise
        rec["latency_s"] = time.time() - t0
        rec["retries"] = attempt
        rec["thought_signatures_restored"] = n_sig_restored
        try:
            for tc in resp.choices[0].message.tool_calls or []:
                ec = getattr(tc, "extra_content", None)
                if ec is None and getattr(tc, "model_extra", None):
                    ec = tc.model_extra.get("extra_content")
                if ec is not None:
                    _thought_sigs[tc.id] = ec
        except Exception:
            pass
        rec["response_model"] = getattr(resp, "model", None)
        rec["response_id"] = getattr(resp, "id", None)
        try:
            ch = resp.choices[0]
            m = ch.message.model_dump()
            rec["finish_reason"] = ch.finish_reason
            rec["response"] = m
        except Exception as e:
            rec["response_parse_error"] = repr(e)
        try:
            rec["usage"] = resp.usage.model_dump() if resp.usage else None
        except Exception:
            rec["usage"] = None
        _write(rec)
        return resp

    create._p0_wrapped = True
    return create


def patch_class(cls):
    if getattr(cls.create, "_p0_wrapped", False):
        return
    cls.create = _wrap(cls.create)
    _patched[0] = True


def install():
    from openai.resources.chat.completions import completions as _c
    patch_class(_c.Completions)
