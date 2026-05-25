#!/usr/bin/env python3.12
"""
Build + publish the "Brubru — Legislative data (API v2)" Postman collection.

The first institution-based v2 collection. Generated FROM the live FastAPI
OpenAPI spec (so request descriptions stay in sync with the code), organised
into source sub-folders that mirror the v2 URL tree:

    Legislative data
    ├── EUR-Lex
    │   ├── Identifiers & resolution
    │   ├── Documents
    │   ├── Search & summaries
    │   ├── Relationships & lifecycle
    │   └── Official Journal
    ├── Legislative Observatory (OEIL)
    ├── Legislative Train
    └── EuroVoc & vocabularies

Every request carries the X-API-Key header ({{api_key}}) and points at
{{baseUrl}} (prod). Requests run end-to-end once the v2 backend is deployed.

Usage:
    python3.12 -m scripts.build_v2_legislative_postman            # build + save JSON only
    python3.12 -m scripts.build_v2_legislative_postman --publish  # also POST to the workspace
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

# Ensure backend/ is importable.
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from main import app  # noqa: E402

PROD_BASE = "https://brubru-production.up.railway.app"
V2_PREFIX = "/api/v2/legislative/"
COLLECTION_NAME = "Brubru API v2: Legislative data"
OUT_PATH = _BACKEND / "data" / "postman_v2_legislative_collection.json"


# (matcher, source folder, sub-folder) — first match wins. matcher tests the
# path tail after /api/v2/legislative/.
_ROUTING = [
    # EUR-Lex sub-groups
    ("eur-lex/identify", "EUR-Lex", "Identifiers & resolution"),
    ("eur-lex/laws/resolve", "EUR-Lex", "Identifiers & resolution"),
    ("eur-lex/xref", "EUR-Lex", "Identifiers & resolution"),
    ("eur-lex/laws/{celex}/xref", "EUR-Lex", "Identifiers & resolution"),
    ("eur-lex/laws/{celex}/views", "EUR-Lex", "Identifiers & resolution"),
    ("eur-lex/verify-citation", "EUR-Lex", "Identifiers & resolution"),
    ("eur-lex/laws/summaries", "EUR-Lex", "Search & summaries"),
    ("eur-lex/resolve-aliases", "EUR-Lex", "Search & summaries"),
    ("eur-lex/resolve-references", "EUR-Lex", "Search & summaries"),
    ("eur-lex/laws/{celex}/relationships", "EUR-Lex", "Relationships & lifecycle"),
    ("eur-lex/laws/{celex}/lifecycle", "EUR-Lex", "Relationships & lifecycle"),
    ("eur-lex/laws/{celex}/consolidated", "EUR-Lex", "Relationships & lifecycle"),
    ("eur-lex/laws/{celex}/languages", "EUR-Lex", "Relationships & lifecycle"),
    ("eur-lex/laws/{celex}/cellar", "EUR-Lex", "Relationships & lifecycle"),
    ("eur-lex/recent", "EUR-Lex", "Relationships & lifecycle"),
    ("eur-lex/oj/", "EUR-Lex", "Official Journal"),
    ("eur-lex/laws/{celex}/text", "EUR-Lex", "Documents"),
    ("eur-lex/laws/{celex}/recital-article-map", "EUR-Lex", "Documents"),
    ("eur-lex/laws/{celex}/defined-terms", "EUR-Lex", "Documents"),
    ("eur-lex/laws/{celex}", "EUR-Lex", "Documents"),
    ("eur-lex/laws", "EUR-Lex", "Documents"),
    ("oeil/", "Legislative Observatory (OEIL)", None),
    ("legislative-train/", "Legislative Train", None),
    ("eurovoc/", "EuroVoc & vocabularies", None),
]

_SOURCE_ORDER = ["EUR-Lex", "Legislative Observatory (OEIL)", "Legislative Train", "EuroVoc & vocabularies"]
_EURLEX_SUBORDER = ["Identifiers & resolution", "Documents", "Search & summaries", "Relationships & lifecycle", "Official Journal"]


def _route(tail: str):
    for needle, source, sub in _ROUTING:
        if tail == needle or tail.startswith(needle) or _match_template(tail, needle):
            return source, sub
    return "EUR-Lex", "Documents"


def _match_template(tail: str, needle: str) -> bool:
    # Compare segment-wise, treating {x} as a wildcard segment.
    t, n = tail.split("/"), needle.split("/")
    if len(t) < len(n):
        return False
    for a, b in zip(t, n):
        if b.startswith("{"):
            continue
        if a != b:
            return False
    return True


# Sensible pre-filled example values so every request runs out of the box.
_PARAM_DEFAULTS = {
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
    "q": "data protection",
    "id": "GDPR",
    "date": "2026-05-01",
    "published_from": "2026-05-01",
    "limit": "10",
    "page": "1",
    "days": "7",
    "lang": "en",
    "language": "en",
    "series": "L",
    "text": "See Regulation (EU) 2016/679 and the AI Act.",
}


def _clean_path(path: str) -> str:
    """Strip FastAPI path converters: {ref:path} -> {ref}."""
    return re.sub(r"\{(\w+):[^}]+\}", r"{\1}", path)


def _to_postman_url(path: str, query_params: list) -> dict:
    clean = _clean_path(path)
    # Postman path variables use :name (NOT {name}, which it sends literally).
    pm_path = re.sub(r"\{(\w+)\}", r":\1", clean)
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
        # Required params enabled; optional ones included-but-disabled for discoverability.
        query.append({"key": p["name"], "value": val, "disabled": not p.get("required", False)})
    if query:
        url["query"] = query
        if any(not q["disabled"] for q in query):
            raw = raw + "?" + "&".join(f"{q['key']}={q['value']}" for q in query if not q["disabled"])
            url["raw"] = raw
    return url


def _query_value(param: dict) -> str:
    if param.get("example") is not None:
        return str(param["example"])
    sch = param.get("schema", {})
    if sch.get("example") is not None:
        return str(sch["example"])
    if sch.get("default") is not None:
        return str(sch["default"])
    return _QUERY_FALLBACKS.get(param["name"], "")


def _build_request(path: str, method: str, op: dict) -> dict:
    name = op.get("summary") or f"{method.upper()} {path}"
    desc = op.get("description") or ""
    query_params = [p for p in op.get("parameters", []) if p.get("in") == "query"]
    req = {
        "name": name,
        "request": {
            "method": method.upper(),
            "header": [{"key": "X-API-Key", "value": "{{api_key}}", "type": "text"}],
            "url": _to_postman_url(path, query_params),
            "description": desc,
        },
        "response": [],
    }
    if method.lower() == "post":
        # Carry an example JSON body for the two free-text resolvers.
        example = {"text": "Article 5 of Regulation (EU) 2022/2065 and the GDPR apply."}
        req["request"]["body"] = {
            "mode": "raw",
            "raw": json.dumps(example, indent=2),
            "options": {"raw": {"language": "json"}},
        }
        req["request"]["header"].append({"key": "Content-Type", "value": "application/json", "type": "text"})
    return req


def build_collection() -> dict:
    spec = app.openapi()
    paths = spec.get("paths", {})

    # source -> sub -> [items];  source -> [items] when sub is None
    tree: dict = {}
    for path, methods in paths.items():
        if V2_PREFIX not in path:
            continue
        tail = path.split("/api/v2/legislative/", 1)[1]
        source, sub = _route(tail)
        for method, op in methods.items():
            if method.lower() not in ("get", "post", "put", "delete"):
                continue
            item = _build_request(path, method, op)
            tree.setdefault(source, {})
            key = sub or "_root"
            tree[source].setdefault(key, []).append(item)

    # Assemble nested folders in a stable order.
    source_items = []
    for source in _SOURCE_ORDER:
        if source not in tree:
            continue
        sub_map = tree[source]
        if list(sub_map.keys()) == ["_root"]:
            folder = {"name": source, "item": sorted(sub_map["_root"], key=lambda i: i["name"])}
        else:
            sub_folders = []
            sub_keys = _EURLEX_SUBORDER if source == "EUR-Lex" else sorted(sub_map.keys())
            for sub in sub_keys:
                if sub not in sub_map:
                    continue
                sub_folders.append({"name": sub, "item": sorted(sub_map[sub], key=lambda i: i["name"])})
            folder = {"name": source, "item": sub_folders}
        source_items.append(folder)

    n_requests = sum(len(m) for s in tree.values() for m in s.values())

    return {
        "info": {
            "name": COLLECTION_NAME,
            "description": (
                "Brubru's institution-based API v2 — first domain: **Legislative data**.\n\n"
                "Grouped by source (EUR-Lex / Legislative Observatory / Legislative Train / "
                "EuroVoc) over domain-rooted `/api/v2/legislative/...` URLs. Same auth, "
                "envelope, error shapes and documentation contract as v1.\n\n"
                "Set the `api_key` collection variable to a `brubru_live_...` key (mint one "
                "at brubru.beresol.eu/api). `baseUrl` defaults to production.\n\n"
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

    # Resolve workspace id.
    req = urllib.request.Request(
        "https://api.getpostman.com/workspaces", headers={"X-Api-Key": api_key}
    )
    ws = json.load(urllib.request.urlopen(req))["workspaces"]
    ws_id = next(w["id"] for w in ws if w["name"] == "Brubru EU Data API")

    # Idempotent: update the existing collection by name if present, else create.
    list_req = urllib.request.Request(
        f"https://api.getpostman.com/collections?workspace={ws_id}",
        headers={"X-Api-Key": api_key},
    )
    existing = json.load(urllib.request.urlopen(list_req)).get("collections", [])
    match = next((c for c in existing if c.get("name") == COLLECTION_NAME), None)

    body = json.dumps({"collection": collection}).encode()
    if match:
        url = f"https://api.getpostman.com/collections/{match['uid']}"
        method = "PUT"
    else:
        url = f"https://api.getpostman.com/collections?workspace={ws_id}"
        method = "POST"
    req = urllib.request.Request(
        url, data=body, method=method,
        headers={"X-Api-Key": api_key, "Content-Type": "application/json"},
    )
    resp = json.load(urllib.request.urlopen(req))
    info = resp.get("collection", {})
    print(f"[OK] {'Updated' if match else 'Created'} collection: {info.get('name')}")
    print(f"     uid: {info.get('uid')}")
    print(f"     Open in workspace: https://www.postman.com/beresol-565660/workspace/brubru-eu-data-api/")


if __name__ == "__main__":
    coll = build_collection()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(coll, indent=2))
    n = sum(
        len(sub.get("item", [])) if isinstance(sub.get("item"), list) and sub.get("item") and "request" in sub["item"][0]
        else sum(len(sf.get("item", [])) for sf in sub.get("item", []))
        for sub in coll["item"]
    )
    print(f"[OK] Built collection JSON -> {OUT_PATH} ({n} requests)")
    if "--publish" in sys.argv:
        publish(coll)
    else:
        print("     Re-run with --publish to POST it to the workspace.")
