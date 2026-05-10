#!/usr/bin/env python3.12
"""
Sync Brubru's "Specialised EC Databases" Postman folder from the live
OpenAPI spec.

Reusable across every wave of the rollout: re-run after each deploy and
this script will add (or update) every new /api/v1/specialised/* path
under the corresponding sub-folder.

Sub-folder = the cluster name from
docs/applications/specialised_ec_databases.md.

URL prefix → cluster mapping is hard-coded below; new prefixes raise so
we don't accidentally drop something into the wrong folder.

Run:
    POSTMAN_API_KEY=$(grep '^POSTMAN_API_KEY=' .env | cut -d= -f2-) \
    python3.12 scripts/postman_sync_specialised.py            # dry-run, prints diff
    POSTMAN_API_KEY=... python3.12 scripts/postman_sync_specialised.py --apply
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"

LIVE_OPENAPI = "https://brubru-production.up.railway.app/api/v1/openapi.json"
LIVE_BASEURL = "https://brubru-production.up.railway.app"
WORKSPACE_NAME = "Brubru EU Data API"
COLLECTION_NAME_FRAG = "Brubru EU Data API"
TOP_FOLDER = "Specialised EC Databases"

# Each row: prefix → (sub-folder, plain-English short title, sub-folder description)
CLUSTER_MAP = {
    "/api/v1/specialised/fta": (
        "Trade & Customs",
        "EU international agreements (FTA-equivalent surface, table-backed)",
        "Wave 1. Trade & customs registries — TARIC tariff measures, EU international agreements (FTAs/EPAs/AAs/PCAs/Fisheries/Aviation/Exchange-of-Letters), CIRCABC document collaboration, trade-defence cases, Access2Markets / SEP, EU restrictive measures (CFSP sanctions). New endpoints land here as each upstream source is wired up.",
    ),
    "/api/v1/specialised/sanctions": (
        "Trade & Customs",
        "EU restrictive measures (CFSP sanctions consolidated list)",
        "Wave 1. Trade & customs registries — EU international agreements (FTAs/EPAs/AAs/PCAs/Fisheries/Aviation/Exchange-of-Letters), restrictive measures (CFSP sanctions), trade-defence regulations (anti-dumping / countervailing / safeguard). New endpoints land here as each upstream source is wired up.",
    ),
    "/api/v1/specialised/trade-defence": (
        "Trade & Customs",
        "EU anti-dumping, countervailing and safeguard regulations (Cellar-backed)",
        "Wave 1. Trade & customs registries — EU international agreements (FTAs/EPAs/AAs/PCAs/Fisheries/Aviation/Exchange-of-Letters), restrictive measures (CFSP sanctions), trade-defence regulations (anti-dumping / countervailing / safeguard). New endpoints land here as each upstream source is wired up.",
    ),
    "/api/v1/specialised/gi": (
        "Food, Feed & Plant Health",
        "EU Geographical Indications (PDOs, PGIs, TSGs, craft and industrial GIs)",
        "Wave 3. Food, feed and plant-health registries — eAmbrosia + GIview merged Geographical Indications dataset (PDOs / PGIs / TSGs / wine GIs / spirit GIs / aromatised GIs / craft + industrial GIs from Reg 2023/2411), RASFF, TRACES, EU Pesticides Database, EUROPHYT, ADIS, Plant Variety Portal, FOREMATIS, Food and Feed Information Portal sub-screens.",
    ),
}

DEFAULT_FOLDER_DESCRIPTIONS = {
    "Trade & Customs": (
        "Wave 1. Trade & customs registries — TARIC tariff measures, EU international "
        "agreements (treaties), CIRCABC document collaboration, trade-defence cases, "
        "Access2Markets / SEP. New endpoints land here as each upstream source is wired up."
    ),
    "Chemicals (ECHA)": (
        "Wave 2. ECHA-led chemical registries — REACH registered substances, CLP "
        "inventory, biocidal products, SCIP, candidate list (SVHC), Annex XVII restrictions, "
        "PIC export consents."
    ),
    "Food, Feed & Plant Health": (
        "Wave 3. DG SANTE registries — eAmbrosia (geographical indications), RASFF Window, "
        "TRACES NT, EUROPHYT, ADIS animal disease, EU Pesticides DB, Plant Variety Portal, "
        "FOREMATIS, Food & Feed Information Portal sub-screens."
    ),
    "Health & Medical Devices": (
        "Wave 3+. EUDAMED, COSING cosmetic ingredients, EU-CEG tobacco, EU Vaccines, "
        "Substances of Human Origin (SoHO)."
    ),
    "Competition & State Aid": (
        "Wave 4. DG COMP — antitrust + merger + state-aid case search, Transparency Award Module."
    ),
    "Research & Knowledge (JRC)": (
        "Wave 5. JRC + R&I — JRC Data Catalogue, Knowledge4Policy hubs (Bioeconomy, "
        "Disaster Risk, Food Fraud, Migration & Demography, Territorial, Cancer, Biodiversity), "
        "DataM, ESDAC, EFFIS, LUISA, INSPIRE, EOSC."
    ),
    "Marine & Environment": (
        "Wave 6. EMODnet, WISE, BISE, EEA datasets, Copernicus services."
    ),
    "Economy & Finance (DG ECFIN)": (
        "Wave 7. AMECO, Fiscal Governance, CeSaR, euro-area indicators, Price & Cost "
        "Competitiveness, Stability & Convergence Programmes, EU KLEMS, Tax & Benefits."
    ),
    "Transparency & Decision-Making": (
        "Wave 8. Transparency Register (lobbyists), Comitology Register, Expert Group Register, "
        "RegDoc, Commissioners' Meetings register."
    ),
    "Energy / Education / Regional": (
        "Wave 9. ENTSO-E, ENTSOG, ESCO, Eurydice, EQAVET, Cohesion Open Data, Inforegio."
    ),
}


def get_env(key: str) -> str:
    if not ENV_FILE.exists():
        return os.environ.get(key, "")
    for line in ENV_FILE.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return os.environ.get(key, "")


def fetch_json(url: str, headers: dict | None = None, method: str = "GET", body: bytes | None = None) -> dict:
    req = urllib.request.Request(url, headers=headers or {}, method=method, data=body)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def get_postman_ids(api_key: str) -> tuple[str, str]:
    ws = fetch_json("https://api.getpostman.com/workspaces", headers={"X-Api-Key": api_key})
    ws_id = next(w["id"] for w in ws["workspaces"] if w["name"] == WORKSPACE_NAME)
    ws_detail = fetch_json(f"https://api.getpostman.com/workspaces/{ws_id}", headers={"X-Api-Key": api_key})
    col_uid = next(c["uid"] for c in ws_detail["workspace"]["collections"] if COLLECTION_NAME_FRAG in c["name"])
    return ws_id, col_uid


def load_openapi() -> dict:
    return fetch_json(LIVE_OPENAPI)


# --------------------------------------------------------------------------
# Postman item construction
# --------------------------------------------------------------------------


def build_postman_item(path: str, method: str, op: dict) -> dict:
    """Convert one OpenAPI operation into a Postman v2.1 item."""
    method = method.upper()
    summary = op.get("summary") or path
    description = op.get("description") or ""

    # Path → URL with {{baseUrl}} prefix and {var} → {{var}}
    raw_path = path.replace("{", "{{").replace("}", "}}")
    raw_url = f"{{{{baseUrl}}}}{raw_path}"

    # Path components (Postman parses URL into segments)
    segments = [s for s in path.lstrip("/").split("/") if s]
    postman_segments = []
    for s in segments:
        if s.startswith("{") and s.endswith("}"):
            postman_segments.append(":" + s[1:-1])
        else:
            postman_segments.append(s)

    # Path variables list
    path_vars = [
        {"key": s[1:-1], "value": "", "description": ""}
        for s in segments
        if s.startswith("{") and s.endswith("}")
    ]

    # Query parameters from OpenAPI parameter list (filter to query params,
    # default disabled=true so the user opts in; mirror the existing pattern).
    query_params = []
    for p in op.get("parameters", []) or []:
        if p.get("in") != "query":
            continue
        schema = p.get("schema", {}) or {}
        default_val = schema.get("default", "")
        query_params.append({
            "key": p["name"],
            "value": str(default_val) if default_val != "" else "",
            "description": p.get("description") or schema.get("description") or "",
            "disabled": True,
        })

    item = {
        "name": summary,
        "request": {
            "method": method,
            "header": [],
            "url": {
                "raw": raw_url + ("?" + "&".join(f"{q['key']}=" for q in query_params) if query_params else ""),
                "host": ["{{baseUrl}}"],
                "path": postman_segments,
                "query": query_params,
                "variable": path_vars,
            },
            "description": description,
        },
        "response": [],
    }
    return item


# --------------------------------------------------------------------------
# Folder graft logic
# --------------------------------------------------------------------------


def find_folder(items: list, name: str) -> dict | None:
    for it in items:
        if it.get("name") == name and "item" in it:
            return it
    return None


def upsert_folder(items: list, name: str, description: str) -> dict:
    folder = find_folder(items, name)
    if folder is None:
        folder = {
            "name": name,
            "description": description,
            "item": [],
        }
        items.append(folder)
    elif description and not folder.get("description"):
        folder["description"] = description
    return folder


def upsert_item(folder: dict, item: dict) -> str:
    """Insert `item` under `folder` by name. Returns 'added' or 'updated'."""
    existing = next((x for x in folder["item"] if x.get("name") == item["name"]), None)
    if existing:
        # Preserve any existing _postman_id but replace request + response.
        existing["request"] = item["request"]
        # Don't wipe any existing example responses — keep them.
        if "response" not in existing:
            existing["response"] = []
        return "updated"
    folder["item"].append(item)
    return "added"


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="PUT changes back to Postman.")
    args = ap.parse_args()

    api_key = get_env("POSTMAN_API_KEY")
    if not api_key:
        print("[FATAL] POSTMAN_API_KEY missing. Set in .env or env.", file=sys.stderr)
        sys.exit(1)

    print("[INFO] Resolving Postman workspace + collection...")
    ws_id, col_uid = get_postman_ids(api_key)
    print(f"  workspace={ws_id}  collection={col_uid}")

    print("[INFO] Loading live OpenAPI spec from Railway...")
    spec = load_openapi()

    # Find every /api/v1/specialised/* operation.
    new_items_by_cluster: dict[str, list[dict]] = {}
    for path, methods in spec["paths"].items():
        if not path.startswith("/api/v1/specialised"):
            continue
        # Strip the global /api/v1 prefix that Postman appends via baseUrl.
        # Actually leave it in — the Postman items in this collection use the full
        # /api/v1/* path under {{baseUrl}}.
        cluster = None
        for prefix, (folder_name, _, _) in CLUSTER_MAP.items():
            if path.startswith(prefix):
                cluster = folder_name
                break
        if cluster is None:
            print(f"[WARN] no cluster mapping for {path}, skipping.", file=sys.stderr)
            continue
        for method, op in methods.items():
            if method not in {"get", "post", "put", "delete", "patch"}:
                continue
            item = build_postman_item(path, method, op)
            new_items_by_cluster.setdefault(cluster, []).append(item)

    if not new_items_by_cluster:
        print("[INFO] No /api/v1/specialised/* paths found in live spec — nothing to do.")
        return

    # Pull current collection.
    print("[INFO] Fetching current Postman collection...")
    current = fetch_json(
        f"https://api.getpostman.com/collections/{col_uid}",
        headers={"X-Api-Key": api_key},
    )
    collection = deepcopy(current["collection"])

    # Find or create the top "Specialised EC Databases" folder.
    top = find_folder(collection["item"], TOP_FOLDER)
    if top is None:
        top = {
            "name": TOP_FOLDER,
            "description": (
                "Specialised European Commission databases — registries, lookup tools and "
                "data portals managed by individual DGs and agencies. Each sub-folder maps "
                "to one wave of the rollout (see docs/applications/specialised_ec_databases.md)."
            ),
            "item": [],
        }
        collection["item"].append(top)
        print(f"[INFO] Created top folder '{TOP_FOLDER}'")

    # Upsert sub-folders + items.
    summary_added = summary_updated = 0
    for cluster, items in new_items_by_cluster.items():
        folder = upsert_folder(top["item"], cluster, DEFAULT_FOLDER_DESCRIPTIONS.get(cluster, ""))
        for item in items:
            verb = upsert_item(folder, item)
            print(f"  [{verb}] {cluster} ▸ {item['name']}")
            if verb == "added":
                summary_added += 1
            else:
                summary_updated += 1

    print()
    print(f"[INFO] Diff: +{summary_added} added, ~{summary_updated} updated.")

    if not args.apply:
        print("[DRY] not pushing back. Re-run with --apply to PUT to Postman.")
        return

    print("[INFO] PUTting modified collection back to Postman...")
    body = json.dumps({"collection": collection}).encode()
    fetch_json(
        f"https://api.getpostman.com/collections/{col_uid}",
        headers={
            "X-Api-Key": api_key,
            "Content-Type": "application/json",
        },
        method="PUT",
        body=body,
    )
    print(f"[OK] Pushed: +{summary_added} new, ~{summary_updated} updated under '{TOP_FOLDER}'.")


if __name__ == "__main__":
    main()
