"""Map provider credentials (from process env or the gitignored .env) onto the
OpenAI-compatible env vars that upstream chat.py reads (OPENAI_API_KEY).
Never prints or logs key values."""
import os
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
ENDPOINTS = {
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", ("GEMINI_API_KEY", "GEMINI_KEY")),
    "groq": ("https://api.groq.com/openai/v1", ("GROQ_API_KEY", "GROQ_KEY")),
}
def _load_dotenv(path=os.path.join(ROOT, ".env")):
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
def provider_env(provider):
    _load_dotenv()
    url, names = ENDPOINTS[provider]
    key = next((os.environ[n] for n in names if os.environ.get(n)), None)
    if not key:
        raise SystemExit(f"Missing API key: set one of {names}")
    os.environ["OPENAI_API_KEY"] = key
    os.environ["FLEXSQL_P0_PROVIDER"] = provider
    return url
