"""
Sync the Brubru EU Data API Postman collection from the live OpenAPI spec.

Why a custom converter (instead of POST /import/openapi):
  - Postman's import-OpenAPI endpoint creates a NEW collection (different UID).
    That breaks any partner who already forked the original collection.
  - We need to PUT the new content onto the EXISTING collection UID so the
    fork chain stays intact.

Behaviour:
  1. Fetch https://brubru-production.up.railway.app/api/v1/openapi.json
  2. Build a Postman v2.1 collection grouped by tag (one folder per tag).
  3. PUT the result to /collections/{uid} preserving info._postman_id.

Usage:
    python3.12 backend/scripts/sync_postman_collection.py [--dry-run]
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, urlencode

import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
OPENAPI_URL = "https://brubru-production.up.railway.app/api/v1/openapi.json"


def get_env(k):
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


def http(url, method="GET", headers=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def slug_to_pretty(s):
    return s.replace("v1-", "").replace("-", " ").title()


def openapi_to_postman_v21(spec, collection_uid):
    """Convert OpenAPI 3.1 to a Postman v2.1 collection that preserves UID."""
    paths = spec.get("paths", {})
    info = spec.get("info", {})
    folders = {}  # tag -> list of items

    for path, methods in sorted(paths.items()):
        for method, op in methods.items():
            if method.lower() not in ("get", "post", "put", "delete", "patch"):
                continue
            tags = op.get("tags") or ["other"]
            tag = tags[0]
            params = op.get("parameters", []) or []
            query_params = []
            path_params = []
            for p in params:
                if p.get("in") == "query":
                    query_params.append(p)
                elif p.get("in") == "path":
                    path_params.append(p)

            # Build URL with {{baseUrl}}
            raw_path = path.lstrip("/")
            postman_url = "{{baseUrl}}/" + raw_path
            url_struct = {
                "raw": postman_url,
                "host": ["{{baseUrl}}"],
                "path": [seg for seg in raw_path.split("/") if seg],
            }
            if query_params:
                url_struct["query"] = [
                    {
                        "key": q["name"],
                        "value": "",
                        "description": q.get("description", "")[:300],
                        "disabled": True,
                    }
                    for q in query_params
                ]
            if path_params:
                url_struct["variable"] = [
                    {
                        "key": pp["name"],
                        "value": "",
                        "description": pp.get("description", "")[:300],
                    }
                    for pp in path_params
                ]

            # Use summary as the request name; fall back to operationId / path.
            name = op.get("summary") or op.get("operationId") or f"{method.upper()} {path}"
            description = (op.get("description") or "").strip()

            request = {
                "name": name,
                "request": {
                    "method": method.upper(),
                    "header": [],
                    "url": url_struct,
                    "description": description,
                },
                "response": [],
            }
            folders.setdefault(tag, []).append(request)

    # Build the collection items: one folder per tag.
    items = []
    for tag in sorted(folders.keys()):
        items.append({
            "name": slug_to_pretty(tag),
            "description": f"Auto-generated from OpenAPI tag: {tag}",
            "item": folders[tag],
        })

    collection = {
        "info": {
            "_postman_id": collection_uid,
            "name": "Brubru EU Data API",
            "description": (
                "Brubru EU Data API v1 — public partner surface.\n\n"
                "Base URL: {{baseUrl}}\n"
                "Auth: Authorization: Bearer {{api_key}} (or X-API-Key header)\n"
                "Rate limit: depends on tier — free 60/min, pro 300/min, enterprise 6000/min.\n"
                "X-RateLimit-Tier header echoes the tier.\n\n"
                "Collection auto-synced from /api/v1/openapi.json. Fork to your own "
                "workspace to add examples or tests.\n\n"
                "Updated: " + spec.get("info", {}).get("version", "v1")
            ),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "auth": {
            "type": "apikey",
            "apikey": [
                {"key": "key", "value": "Authorization", "type": "string"},
                {"key": "value", "value": "Bearer {{api_key}}", "type": "string"},
                {"key": "in", "value": "header", "type": "string"},
            ],
        },
        "item": items,
    }
    return collection


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Build the new collection JSON but don't PUT it")
    ap.add_argument("--out", default="/tmp/brubru_postman_sync.json", help="Where to write the assembled collection JSON for inspection")
    args = ap.parse_args()

    pm_key = get_env("POSTMAN_API_KEY")
    if not pm_key:
        print("[FATAL] POSTMAN_API_KEY missing from .env"); sys.exit(1)

    # Find workspace + collection IDs
    code, body = http("https://api.getpostman.com/workspaces", headers={"X-Api-Key": pm_key})
    workspaces = json.loads(body)["workspaces"]
    ws = next((w for w in workspaces if w["name"] == "Brubru EU Data API"), None)
    if not ws:
        print("[FATAL] Workspace 'Brubru EU Data API' not found"); sys.exit(2)

    code, body = http(f"https://api.getpostman.com/workspaces/{ws['id']}", headers={"X-Api-Key": pm_key})
    ws_data = json.loads(body)["workspace"]
    coll = next((c for c in ws_data["collections"] if "Brubru EU Data API" in c["name"]), None)
    if not coll:
        print("[FATAL] Collection 'Brubru EU Data API' not found"); sys.exit(2)
    coll_uid = coll["uid"]
    coll_id = coll_uid.split("-", 1)[-1]
    print(f"[INFO] Workspace : {ws['id']}")
    print(f"[INFO] Collection: {coll_uid}")

    # Fetch the live OpenAPI spec
    print(f"[INFO] Fetching OpenAPI from {OPENAPI_URL}")
    code, body = http(OPENAPI_URL)
    if code != 200:
        print(f"[FATAL] OpenAPI fetch returned {code}"); sys.exit(2)
    spec = json.loads(body)
    print(f"[INFO] Spec: {len(spec.get('paths', {}))} paths, version {spec.get('info', {}).get('version')}")

    # Build the Postman v2.1 collection
    collection = openapi_to_postman_v21(spec, coll_id)

    n_folders = len(collection["item"])
    n_requests = sum(len(f.get("item", [])) for f in collection["item"])
    print(f"[INFO] Built: {n_folders} folders / {n_requests} requests")

    Path(args.out).write_text(json.dumps({"collection": collection}, indent=2))
    print(f"[INFO] Wrote: {args.out}")

    if args.dry_run:
        print("\n[DRY-RUN] Skipping PUT. Pass without --dry-run to publish.")
        return

    # PUT to Postman
    url = f"https://api.getpostman.com/collections/{coll_uid}"
    payload = {"collection": collection}
    print(f"[INFO] PUT {url}")
    code, resp = http(
        url,
        method="PUT",
        headers={
            "X-Api-Key": pm_key,
            "Content-Type": "application/json",
        },
        body=payload,
    )
    if code in (200, 204):
        print(f"[OK] Postman collection updated ({code})")
        try:
            r = json.loads(resp)
            print(f"     name={r.get('collection', {}).get('name')}  uid={r.get('collection', {}).get('uid')}")
        except Exception:
            pass
    else:
        print(f"[FAIL] PUT returned {code}")
        print(resp.decode(errors="replace")[:500])
        sys.exit(3)


if __name__ == "__main__":
    main()
