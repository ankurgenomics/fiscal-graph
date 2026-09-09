"""Checks every OPENROUTER_API_KEY found across known project .env files.
Never prints key values — only labels (already masked by OpenRouter) and balances.
"""
import re
import urllib.request
import json

CANDIDATE_ENV_FILES = [
    r"C:\Users\RupRa\Downloads\ATG\ankur-career-ops\ankur-career-ops\Interview_slides\HTX\assignment\htx-ai-engineering-test\.env",
    r"C:\Users\RupRa\Downloads\ATG\ankur-career-ops\GitHub_rep\NEW_projects_github\enterprise-doc-intelligence\.env",
    r"C:\Users\RupRa\Downloads\ATG\ankur-career-ops\GitHub_rep\NEW_projects_github\adaptive-research-swarm\.env",
    r"C:\Users\RupRa\Downloads\ATG\ankur-career-ops\ankur-career-ops\.env",
]

def extract_key(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except FileNotFoundError:
        return None
    m = re.search(r"^OPENROUTER_API_KEY=(.+)$", content, re.MULTILINE)
    return m.group(1).strip() if m else None

seen = set()
for path in CANDIDATE_ENV_FILES:
    key = extract_key(path)
    if not key or key in seen:
        continue
    seen.add(key)
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/auth/key",
        headers={"Authorization": f"Bearer {key}"},
    )
    print(f"--- {path} ---")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())["data"]
        print("  label:", data.get("label"))
        print("  limit:", data.get("limit"))
        print("  usage:", data.get("usage"))
        print("  limit_remaining:", data.get("limit_remaining"))
        print("  is_free_tier:", data.get("is_free_tier"))
    except Exception as e:
        print("  FAILED:", e)
