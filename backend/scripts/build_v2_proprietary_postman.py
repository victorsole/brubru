#!/usr/bin/env python3.12
"""
Build + publish the "Brubru API v2: Proprietary Databases" Postman collection.

The second institution-/source-based v2 collection (after "Legislative data").
Generated FROM the live FastAPI OpenAPI spec so request descriptions stay in
sync with the code. Organised into source sub-folders that mirror the v2 URL
tree:

    Proprietary Databases
    ├── Knowledge Guides       /api/v2/proprietary/guides
    ├── Catalan Translations   /api/v2/proprietary/catalan
    └── Canon & Deep-Dives     /api/v2/proprietary/canon

Each folder leads with a "show everything" list request (no filters) so it
runs out of the box. Every request carries X-API-Key ({{api_key}}) and points
at {{baseUrl}} (prod). Mirrors build_v2_legislative_postman.py.

Usage:
    python3.12 -m scripts.build_v2_proprietary_postman            # build + save JSON only
    python3.12 -m scripts.build_v2_proprietary_postman --publish  # also publish to the workspace
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from main import app  # noqa: E402

PROD_BASE = "https://brubru-production.up.railway.app"
V2_PREFIX = "/api/v2/proprietary/"
COLLECTION_NAME = "Brubru API v2: Proprietary Databases"
OUT_PATH = _BACKEND / "data" / "postman_v2_proprietary_collection.json"

# path tail (after /api/v2/proprietary/) -> source folder. First match wins.
_ROUTING = [
    ("guides", "Knowledge Guides"),
    ("catalan", "Catalan Translations"),
    ("canon", "Canon & Deep-Dives"),
]
_SOURCE_ORDER = ["Knowledge Guides", "Catalan Translations", "Canon & Deep-Dives"]

# Pre-filled example values so every request runs out of the box.
_PARAM_DEFAULTS = {
    "guide_id": "ai_act_regulation",
    "celex": "32016R0679",      # GDPR — stable, large Catalan translation
    "slug": "2024-1689_aiact",  # AI Act canon deep-dive
}
_QUERY_FALLBACKS = {
    "q": "AI Act",
    "limit": "10",
    "page": "1",
    "detail_level": "Summary",
    "report_type": "canon",
    "legal_family": "eu_pharmaceutical",
    "language": "en",
    "lang": "en",
    "include_body": "false",
    "body": "html",
}
# List endpoints that should show EVERYTHING by default: leave their optional
# filters disabled so the request returns the whole catalogue out of the box.
_SHOW_ALL_TAILS = {"guides", "catalan", "canon"}


def _route(tail: str) -> str:
    for needle, source in _ROUTING:
        if tail == needle or tail.startswith(needle):
            return source
    return "Knowledge Guides"


def _clean_path(path: str) -> str:
    return re.sub(r"\{(\w+):[^}]+\}", r"{\1}", path)


def _query_value(param: dict) -> str:
    if param.get("example") is not None:
        return str(param["example"])
    sch = param.get("schema", {})
    if sch.get("example") is not None:
        return str(sch["example"])
    if sch.get("default") is not None:
        return str(sch["default"])
    return _QUERY_FALLBACKS.get(param["name"], "")


def _to_postman_url(path: str, query_params: list) -> dict:
    clean = _clean_path(path)
    pm_path = re.sub(r"\{(\w+)\}", r":\1", clean)  # Postman path vars use :name
    raw = "{{baseUrl}}" + pm_path
    url = {"raw": raw, "host": ["{{baseUrl}}"], "path": pm_path.strip("/").split("/")}

    variables = []
    for m in re.finditer(r"\{(\w+)\}", clean):
        name = m.group(1)
        variables.append({"key": name, "value": _PARAM_DEFAULTS.get(name, ""), "description": "(path variable)"})
    if variables:
        url["variable"] = variables

    query = []
    for p in query_params:
        val = _query_value(p)
        query.append({"key": p["name"], "value": val, "disabled": not p.get("required", False)})
    if query:
        url["query"] = query
        enabled = [q for q in query if not q["disabled"]]
        if enabled:
            raw = raw + "?" + "&".join(f"{q['key']}={q['value']}" for q in enabled)
            url["raw"] = raw
    return url


def _build_request(path: str, method: str, op: dict) -> dict:
    name = op.get("summary") or f"{method.upper()} {path}"
    query_params = [p for p in op.get("parameters", []) if p.get("in") == "query"]
    return {
        "name": name,
        "request": {
            "method": method.upper(),
            "header": [{"key": "X-API-Key", "value": "{{api_key}}", "type": "text"}],
            "url": _to_postman_url(path, query_params),
            "description": op.get("description") or "",
        },
        "response": [],
    }


def _sort_key(item: dict) -> tuple:
    """Order within a folder: the 'show everything' list first, then literal
    sub-routes (e.g. /stats), then path-variable detail routes, each by name."""
    segs = item["request"]["url"]["path"]  # e.g. ['api','v2','proprietary','catalan','stats']
    after = segs[3:]  # drop api/v2/proprietary
    if len(after) == 1:
        rank = 0  # bare list — show everything
    elif any(s.startswith(":") for s in after):
        rank = 2  # detail (path variable)
    else:
        rank = 1  # literal sub-route (e.g. stats)
    return (rank, item["name"])


def build_collection() -> dict:
    spec = app.openapi()
    paths = spec.get("paths", {})

    tree: dict[str, list] = {}
    for path, methods in paths.items():
        if V2_PREFIX not in path:
            continue
        tail = path.split(V2_PREFIX, 1)[1]
        source = _route(tail)
        for method, op in methods.items():
            if method.lower() not in ("get", "post"):
                continue
            tree.setdefault(source, []).append(_build_request(path, method, op))

    source_items = []
    for source in _SOURCE_ORDER:
        if source in tree:
            source_items.append({"name": source, "item": sorted(tree[source], key=_sort_key)})

    n_requests = sum(len(v) for v in tree.values())

    return {
        "info": {
            "name": COLLECTION_NAME,
            "description": (
                "Brubru's institution-/source-based API v2 — domain: **Proprietary Databases**.\n\n"
                "Brubru's own data products (not mirrored EU institutional sources), grouped by source "
                "over domain-rooted `/api/v2/proprietary/...` URLs:\n\n"
                "- **Knowledge Guides** — the curated EU-policy guides the chatbot uses to ground answers.\n"
                "- **Catalan Translations** — the EU binding-law acquis translated into Catalan (MIT).\n"
                "- **Canon & Deep-Dives** — Brubru's article-by-article HTML reports (EU Canon + law deep-dives).\n\n"
                "Same auth, envelope, error shapes and documentation contract as v1. Each folder's first "
                "request lists the whole catalogue; detail requests are pre-filled with a working example.\n\n"
                "Set the `api_key` collection variable to a `brubru_live_...` key (mint one at "
                "brubru.beresol.eu/api) with scopes `read:knowledge` (guides, canon) and `read:laws` "
                "(catalan). `baseUrl` defaults to production.\n\n"
                f"{n_requests} requests across {len(source_items)} sources."
            ),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": source_items,
        "variable": [
            {"key": "baseUrl", "value": PROD_BASE, "type": "string"},
            {"key": "api_key", "value": "", "type": "string"},
        ],
    }


def publish(collection: dict) -> None:
    api_key = None
    env_path = _BACKEND.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("POSTMAN_API_KEY="):
                api_key = line.split("=", 1)[1].strip()
                break
    api_key = api_key or os.environ.get("POSTMAN_API_KEY")
    if not api_key:
        print("[ERROR] POSTMAN_API_KEY not found in .env")
        sys.exit(1)

    req = urllib.request.Request("https://api.getpostman.com/workspaces", headers={"X-Api-Key": api_key})
    ws = json.load(urllib.request.urlopen(req))["workspaces"]
    ws_id = next(w["id"] for w in ws if w["name"] == "Brubru EU Data API")

    list_req = urllib.request.Request(
        f"https://api.getpostman.com/collections?workspace={ws_id}", headers={"X-Api-Key": api_key}
    )
    existing = json.load(urllib.request.urlopen(list_req)).get("collections", [])
    match = next((c for c in existing if c.get("name") == COLLECTION_NAME), None)

    body = json.dumps({"collection": collection}).encode()
    if match:
        url, method = f"https://api.getpostman.com/collections/{match['uid']}", "PUT"
    else:
        url, method = f"https://api.getpostman.com/collections?workspace={ws_id}", "POST"
    req = urllib.request.Request(
        url, data=body, method=method,
        headers={"X-Api-Key": api_key, "Content-Type": "application/json"},
    )
    resp = json.load(urllib.request.urlopen(req))
    info = resp.get("collection", {})
    print(f"[OK] {'Updated' if match else 'Created'} collection: {info.get('name')}")
    print(f"     uid: {info.get('uid')}")
    print(f"     Open: https://www.postman.com/beresol-565660/workspace/brubru-eu-data-api/")


if __name__ == "__main__":
    coll = build_collection()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(coll, indent=2))
    n = sum(len(folder.get("item", [])) for folder in coll["item"])
    print(f"[OK] Built collection JSON -> {OUT_PATH} ({n} requests across {len(coll['item'])} sources)")
    for folder in coll["item"]:
        print(f"  {folder['name']}: {len(folder['item'])} requests")
        for it in folder["item"]:
            print(f"      - {it['request']['method']:4s} {it['request']['url']['raw']}")
    if "--publish" in sys.argv:
        publish(coll)
    else:
        print("     Re-run with --publish to push it to the workspace.")
