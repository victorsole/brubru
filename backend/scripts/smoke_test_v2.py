#!/usr/bin/env python3.12
"""
Smoke-test EVERY /api/v2/legislative/* endpoint against a running server with
real example parameters, and report exact HTTP status + error per endpoint.

Unlike the pytest "reach-handler" checks (which only assert not-401/402/403),
this asserts a genuine 2xx and surfaces 4xx/5xx bodies so real bugs show up.

Usage:
    python3.12 -m scripts.smoke_test_v2 [BASE_URL]
    (default BASE_URL = https://brubru-production.up.railway.app)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import httpx

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from main import app  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://brubru-production.up.railway.app"

# Read the API key from .env
KEY = ""
env = _BACKEND.parent / ".env"
for line in env.read_text().splitlines():
    if line.startswith("BRUBRU_API_KEY="):
        KEY = line.split("=", 1)[1].strip()
        break

_PATH_DEFAULTS = {
    "celex": "32016R0679",
    "ref": "32016R0679",
    "reference": "2022/0047(COD)",
    "concept_id": "3030",
    "table": "corporate-bodies",
    "summary_id": "32016R0679",
    "carriage_id": "2022/0047(COD)",
    "series": "L",
    "year": "2016",
    "number": "119",
}
_QUERY_FALLBACKS = {
    "q": "data protection", "id": "GDPR", "date": "2026-05-01",
    "published_from": "2026-05-01", "limit": "5", "page": "1", "days": "7",
    "lang": "en", "language": "en", "series": "L", "text": "the GDPR applies",
}


def _clean(path: str) -> str:
    return re.sub(r"\{(\w+):[^}]+\}", r"{\1}", path)


def _qval(p: dict) -> str:
    if p.get("example") is not None:
        return str(p["example"])
    s = p.get("schema", {})
    if s.get("example") is not None:
        return str(s["example"])
    if s.get("default") is not None:
        return str(s["default"])
    return _QUERY_FALLBACKS.get(p["name"], "x")


def main() -> int:
    spec = app.openapi()
    rows = []
    for path, methods in spec.get("paths", {}).items():
        if "/api/v2/legislative/" not in path:
            continue
        for method, op in methods.items():
            if method.lower() not in ("get", "post"):
                continue
            url_path = _clean(path)
            for m in re.finditer(r"\{(\w+)\}", _clean(path)):
                url_path = url_path.replace("{" + m.group(1) + "}", _PATH_DEFAULTS.get(m.group(1), "x"))
            params = {}
            for p in op.get("parameters", []):
                if p.get("in") == "query" and p.get("required"):
                    params[p["name"]] = _qval(p)
            body = None
            if method.lower() == "post":
                body = {"text": "Article 5 of Regulation (EU) 2016/679 and the GDPR apply."}
            rows.append((method.upper(), path, url_path, params, body))

    headers = {"X-API-Key": KEY}
    results = []
    with httpx.Client(base_url=BASE, headers=headers, timeout=90.0) as client:
        for method, orig, url_path, params, body in rows:
            try:
                if method == "POST":
                    r = client.post(url_path, params=params, json=body)
                else:
                    r = client.get(url_path, params=params)
                code = r.status_code
                note = ""
                if code >= 400:
                    try:
                        j = r.json()
                        note = j.get("reason_code") or j.get("error") or str(j)[:120]
                    except Exception:
                        note = r.text[:120]
                else:
                    # sanity: is the body shaped right?
                    try:
                        j = r.json()
                        if "data" in j:
                            note = f"list total={j.get('total')}"
                        elif "celex" in j:
                            note = f"celex={j.get('celex')}"
                        elif "input" in j:
                            note = f"resolved={j.get('celex')}"
                    except Exception:
                        note = "non-json 200"
                results.append((code, method, orig, note))
            except Exception as e:
                results.append((-1, method, orig, f"{type(e).__name__}: {str(e)[:100]}"))

    print(f"\nSmoke test vs {BASE} — {len(results)} endpoints\n" + "=" * 90)
    ok = warn = fail = 0
    for code, method, path, note in results:
        short = path.replace("/api/v2/legislative/", "")
        if 200 <= code < 300:
            tag = "OK  "; ok += 1
        elif code in (404,) and "{" not in path:
            tag = "WARN"; warn += 1
        else:
            tag = "FAIL"; fail += 1
        print(f"[{tag}] {code:>4} {method:<4} {short:<48} {note}")
    print("=" * 90)
    print(f"OK={ok}  WARN={warn}  FAIL={fail}  (of {len(results)})")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
