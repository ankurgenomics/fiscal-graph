"""Checks OpenRouter key validity/remaining credit without spending tokens.
Reads OPENROUTER_API_KEY from .env — never prints the key itself.
"""
import os
import urllib.request
import json
from dotenv import load_dotenv

load_dotenv()
key = os.environ.get("OPENROUTER_API_KEY", "")

if not key:
    print("OPENROUTER_API_KEY not set in .env — add it and rerun.")
    raise SystemExit(1)

req = urllib.request.Request(
    "https://openrouter.ai/api/v1/auth/key",
    headers={"Authorization": f"Bearer {key}"},
)

try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    d = data.get("data", {})
    print("Key is VALID.")
    print("Label:", d.get("label"))
    print("Limit:", d.get("limit"))
    print("Usage so far:", d.get("usage"))
    print("Is free tier:", d.get("is_free_tier"))
    print("Rate limit:", d.get("rate_limit"))
except urllib.error.HTTPError as e:
    print(f"Key check FAILED — HTTP {e.code}: {e.reason}")
    print(e.read().decode(errors='ignore'))
