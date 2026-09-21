"""API providers for run_ladder.py (OpenAI-compatible chat completions).

Credentials come from an environment variable first, then from a plain-text file holding only the key.
The key is never echoed, never passed on a command line, and never enters a result record; only the
provider name does.  Local vLLM servers need no credential.
"""
import json, os, sys

PROVIDERS = {
    "opencode": {
        "url": "https://opencode.ai/zen/go/v1/chat/completions",
        "headers": {"User-Agent": "endless-exam/1.0"},
        "key_env": "OPENCODE_API_KEY", "key_file": ("~/.config/opencode/zen_api_key", None),
        "fingerprint": False,
    },
    "deepseek": {
        "url": "https://api.deepseek.com/chat/completions",
        "headers": {},
        "key_env": "DEEPSEEK_API_KEY",
        "key_file": ("~/.config/deepseek/api_key", None),
        "fingerprint": True,           # the API returns a system_fingerprint; recorded per row
    },
    "gemini": {                        # Google's OpenAI-compatible layer (AI Studio key)
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "headers": {},
        "key_env": "GEMINI_API_KEY",
        "key_file": ("~/.config/gemini/api_key", None),
        "fingerprint": False,
    },
    "openrouter": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "headers": {"X-Title": "endless-exam"},
        "key_env": "OPENROUTER_API_KEY",
        "key_file": ("~/.config/openrouter/api_key", None),
        "fingerprint": False,
    },
    # local OpenAI-compatible server (vLLM); no credential, no fingerprint.  QWEN_LOCAL_URL selects the replica.
    "qwen_local": {
        "url": os.environ.get("QWEN_LOCAL_URL", "http://127.0.0.1:8000/v1/chat/completions"),
        "headers": {},
        "key_env": "QWEN_LOCAL_KEY",
        "key_file": None,
        "fingerprint": False,
        "no_auth": True,
    },
    # same route for models with thinking on/off only (no reasoning_effort)
    "qwen35_local": {
        "url": os.environ.get("QWEN_LOCAL_URL", "http://127.0.0.1:8000/v1/chat/completions"),
        "headers": {},
        "key_env": "QWEN_LOCAL_KEY",
        "key_file": None,
        "fingerprint": False,
        "no_auth": True,
    },
}


def api_key(provider="deepseek"):
    p = PROVIDERS[provider]
    if p.get("no_auth"):
        return "EMPTY"
    key = os.environ.get(p["key_env"])
    if key:
        return key
    if p["key_file"]:
        path, field = p["key_file"]
        try:
            if field is None:
                key = open(os.path.expanduser(path)).read().strip()
                if key:
                    return key
            else:
                return json.load(open(os.path.expanduser(path)))[field]["key"]
        except (OSError, KeyError, ValueError):
            pass
    sys.exit(f"no credential for provider {provider!r}: set {p['key_env']}"
             + (f" or populate {p['key_file'][0]}" if p["key_file"] else ""))
