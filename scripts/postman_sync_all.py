"""
Generalised Postman sync — covers every /api/v1/* path from the live
OpenAPI spec, not just /api/v1/specialised/*. Use this any time an
endpoint changes shape (Pydantic model, description, params).

Pattern: in-place upsert against the existing collection via PUT. Items
are matched by URL path (with placeholders normalised). Existing folder
structure is preserved — items get refreshed in place, brand-new endpoints
go under a top-level "Recently Synced" folder for manual reorganisation.

Run:
    python3.12 scripts/postman_sync_all.py            # dry-run
    python3.12 scripts/postman_sync_all.py --apply    # PUT to Postman
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from copy import deepcopy
from pathlib import Path
from urllib import request as urllib_request

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"

LIVE_OPENAPI = "https://brubru-production.up.railway.app/api/v1/openapi.json"
WORKSPACE_NAME = "Brubru EU Data API"
COLLECTION_NAME_FRAG = "Brubru EU Data API"
NEW_FOLDER_NAME = "Recently Synced"


def get_env(key: str) -> str:
    if not ENV_FILE.exists():
        return os.environ.get(key, "")
    for line in ENV_FILE.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return os.environ.get(key, "")


def fetch_json(url: str, headers: dict | None = None, method: str = "GET", body: bytes | None = None) -> dict:
    req = urllib_request.Request(url, headers=headers or {}, method=method, data=body)
    with urllib_request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def get_postman_ids(api_key: str) -> tuple[str, str]:
    headers = {"X-Api-Key": api_key}
    ws = fetch_json("https://api.getpostman.com/workspaces", headers=headers)
    ws_id = next(w["id"] for w in ws["workspaces"] if w["name"] == WORKSPACE_NAME)
    ws_detail = fetch_json(f"https://api.getpostman.com/workspaces/{ws_id}", headers=headers)
    col_uid = next(c["uid"] for c in ws_detail["workspace"]["collections"]
                   if COLLECTION_NAME_FRAG in c["name"])
    return ws_id, col_uid


# ─────────────────────── OpenAPI → Postman item conversion ──────────────


def normalise_path(p: str) -> str:
    """Strip /api/v1 prefix + normalise path placeholders for matching.
    Treats {x} and :x identically."""
    s = p.replace("/api/v1", "").strip("/")
    s = re.sub(r"\{[^}]+\}", "X", s)
    s = re.sub(r":[A-Za-z_][A-Za-z0-9_]*", "X", s)
    return s


def build_postman_item(path: str, method: str, op: dict, existing: Optional[dict] = None) -> dict:
    """Convert one OpenAPI operation into a Postman item dict.

    `existing` is the previously-saved Postman item (if any) — used to
    preserve hand-edited example values that partners rely on. We only
    overwrite empty placeholder values; non-empty values stay.
    """
    summary = op.get("summary") or f"{method.upper()} {path}"
    description = op.get("description") or ""

    # Index existing path/query var values so we can preserve them
    existing_path: Dict[str, str] = {}
    existing_query: Dict[str, str] = {}
    if existing and existing.get("request"):
        for v in existing["request"].get("url", {}).get("variable", []) or []:
            if v.get("key") and v.get("value"):
                existing_path[v["key"]] = v["value"]
        for v in existing["request"].get("url", {}).get("query", []) or []:
            if v.get("key") and v.get("value"):
                existing_query[v["key"]] = v["value"]

    # Build the URL parts (Postman uses path segments with :param notation)
    raw = path.lstrip("/")
    parts = []
    for seg in raw.split("/"):
        m = re.match(r"^\{([^}]+)\}$", seg)
        parts.append(f":{m.group(1)}" if m else seg)
    raw_url = "{{baseUrl}}/" + raw

    # Extract path + query parameters. Preference order for example value:
    #   1) existing non-empty value in Postman (hand-edited)
    #   2) OpenAPI `example` field on schema
    #   3) OpenAPI `examples` first entry
    #   4) empty string
    def _example_from_op(param: dict) -> str:
        schema = param.get("schema") or {}
        if schema.get("example") not in (None, ""):
            return str(schema["example"])
        if param.get("example") not in (None, ""):
            return str(param["example"])
        examples = param.get("examples") or {}
        for v in examples.values():
            if isinstance(v, dict) and v.get("value") not in (None, ""):
                return str(v["value"])
        return ""

    path_vars = []
    query_vars = []
    for param in op.get("parameters", []) or []:
        name = param["name"]
        if param.get("in") == "path":
            value = existing_path.get(name) or _example_from_op(param)
            path_vars.append({
                "key": name,
                "value": value,
                "description": param.get("description", "") or None,
            })
        elif param.get("in") == "query":
            value = existing_query.get(name) or _example_from_op(param)
            required = bool(param.get("required", False))
            # If required and we still have no value, leave it ENABLED with empty
            # value so partners notice it. If optional and no value, disable it.
            disabled = False if required else (not value)
            query_vars.append({
                "key": name,
                "value": value,
                "description": param.get("description", "") or None,
                "disabled": disabled,
            })

    headers = [{"key": "X-API-Key", "value": "{{api_key}}", "type": "text"}]
    request = {
        "method": method.upper(),
        "header": headers,
        "url": {
            "raw": raw_url,
            "host": ["{{baseUrl}}"],
            "path": parts,
            "variable": path_vars,
            "query": query_vars,
        },
        "description": description,
    }
    return {
        "name": summary,
        "request": request,
        "response": [],
    }


# ─────────────────────── Walking the collection tree ──────────────────


def collect_items(items: list, acc: dict):
    """Build a dict keyed by normalised-path+method → item reference + parent list."""
    for it in items:
        if "request" in it:
            url = it["request"].get("url", {})
            if isinstance(url, dict):
                segs = url.get("path", [])
                p = "/" + "/".join(s if isinstance(s, str) else s.get("value", "") for s in segs)
                key = (normalise_path(p), it["request"].get("method", "GET").upper())
                acc[key] = it
        if "item" in it:
            collect_items(it["item"], acc)


def find_or_create_folder(items: list, name: str, description: str) -> dict:
    for it in items:
        if it.get("name") == name and "item" in it:
            return it
    folder = {"name": name, "description": description, "item": []}
    items.append(folder)
    return folder


# ─────────────────────── Main ──────────────────────────────────────────


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="PUT changes back to Postman.")
    ap.add_argument("--only-prefix", default="/api/v1/",
                    help="Only sync paths starting with this prefix.")
    args = ap.parse_args()

    api_key = get_env("POSTMAN_API_KEY")
    if not api_key:
        print("[FATAL] POSTMAN_API_KEY missing.", file=sys.stderr)
        sys.exit(1)

    print("[INFO] Resolving Postman workspace + collection...")
    ws_id, col_uid = get_postman_ids(api_key)
    print(f"  workspace={ws_id}  collection={col_uid}")

    print(f"[INFO] Loading live OpenAPI spec from {LIVE_OPENAPI}...")
    spec = fetch_json(LIVE_OPENAPI)
    paths = spec.get("paths", {})

    # Pull current collection
    print("[INFO] Fetching current Postman collection...")
    current = fetch_json(
        f"https://api.getpostman.com/collections/{col_uid}",
        headers={"X-Api-Key": api_key},
    )
    collection = deepcopy(current["collection"])

    # Index existing items by (normalised_path, method)
    existing = {}
    collect_items(collection["item"], existing)
    print(f"  current Postman items: {len(existing)}")

    # Walk OpenAPI, build new items
    counts = {"updated": 0, "added": 0, "skipped": 0}
    new_items_for_folder = []

    for path, methods in paths.items():
        if not path.startswith(args.only_prefix):
            continue
        for method, op in methods.items():
            if method not in {"get", "post", "put", "delete", "patch"}:
                continue
            key = (normalise_path(path), method.upper())
            existing_item = existing.get(key)
            new_item = build_postman_item(path, method, op, existing=existing_item)
            if existing_item is not None:
                # Update the existing item in place — keep its parent folder
                # and any saved example responses. build_postman_item already
                # preserved hand-edited query/path values.
                existing_item["name"] = new_item["name"]
                existing_item["request"] = new_item["request"]
                counts["updated"] += 1
            else:
                new_items_for_folder.append(new_item)
                counts["added"] += 1

    if new_items_for_folder:
        folder = find_or_create_folder(
            collection["item"], NEW_FOLDER_NAME,
            "Endpoints added to the API but not yet manually reorganised into a topical folder. "
            "Move them to their proper folder when convenient.",
        )
        for item in new_items_for_folder:
            folder["item"].append(item)

    print(f"\n[INFO] Diff: +{counts['added']} added, ~{counts['updated']} updated.")

    if not args.apply:
        print("[DRY] not pushing back. Re-run with --apply to PUT to Postman.")
        return

    print("[INFO] PUTting modified collection back to Postman...")
    body = json.dumps({"collection": collection}).encode()
    fetch_json(
        f"https://api.getpostman.com/collections/{col_uid}",
        headers={"X-Api-Key": api_key, "Content-Type": "application/json"},
        method="PUT",
        body=body,
    )
    print(f"[OK] Pushed: +{counts['added']} new, ~{counts['updated']} updated.")


if __name__ == "__main__":
    main()
