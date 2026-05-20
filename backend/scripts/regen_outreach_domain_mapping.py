"""Regenerate backend/services/outreach/domain_to_slug.json from active campaigns.

The runtime matcher reads ONLY the committed JSON file. This script is the
bridge between the owner's gitignored CSV workspace (data/outreach/) and the
deployable runtime mapping.

Run this after:
  - adding a new active campaign to data/outreach/active_campaigns.json
  - updating any campaign CSV (e.g. when a new startup row is added)
  - removing a campaign or deactivating it

Then commit backend/services/outreach/domain_to_slug.json so Railway picks it up.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN_REGISTRY = _ROOT / "data" / "outreach" / "active_campaigns.json"
OUTPUT_JSON = _ROOT / "backend" / "services" / "outreach" / "domain_to_slug.json"

PUBLIC_DOMAINS = {
    "gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com",
    "yahoo.com", "yahoo.co.uk", "yahoo.es", "yahoo.fr", "icloud.com",
    "me.com", "mac.com", "protonmail.com", "proton.me", "pm.me",
    "fastmail.com", "tutanota.com", "tuta.io", "gmx.com", "gmx.net",
    "aol.com", "msn.com", "mail.com", "zoho.com",
}


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower().strip())
    return re.sub(r"-+", "-", s).strip("-")


def domain_of(s: str) -> str:
    s = (s or "").strip().lower()
    if not s:
        return ""
    if "@" in s:
        s = s.split("@", 1)[1]
    s = re.sub(r"^https?://", "", s)
    s = s.split("/", 1)[0].split(":", 1)[0]
    if s.startswith("www."):
        s = s[4:]
    return s.strip()


def main() -> int:
    if not CAMPAIGN_REGISTRY.exists():
        print(f"[ERROR] no campaign registry at {CAMPAIGN_REGISTRY}")
        return 1
    registry = json.loads(CAMPAIGN_REGISTRY.read_text())

    domain_to_slug: dict[str, str] = {}
    campaigns_used: list[dict] = []

    for camp in registry.get("campaigns", []):
        if not camp.get("active"):
            print(f"[skip] {camp.get('id')}: inactive")
            continue
        csv_path = _ROOT / camp["csv_path"]
        if not csv_path.exists():
            print(f"[WARN] {camp.get('id')}: csv not found at {csv_path}")
            continue

        name_col = camp.get("name_column", "name")
        website_col = camp.get("website_column", "website")
        email_col = camp.get("email_column", "email")

        added = 0
        with csv_path.open() as f:
            for row in csv.DictReader(f):
                name = (row.get(name_col) or "").strip()
                if not name:
                    continue
                slug = slugify(name)
                for src in (row.get(website_col, ""), row.get(email_col, "")):
                    d = domain_of(src)
                    if d and d not in PUBLIC_DOMAINS:
                        if d not in domain_to_slug:
                            domain_to_slug[d] = slug
                            added += 1
        print(f"[ok] {camp.get('id')}: +{added} domain mappings")
        campaigns_used.append({"id": camp.get("id"), "csv": camp["csv_path"], "added": added})

    output = {
        "_doc": "Runtime domain -> private-guide slug mapping. Regenerated from data/outreach/active_campaigns.json + each campaign CSV by backend/scripts/regen_outreach_domain_mapping.py. Commit this file so Railway has it; the source CSVs stay gitignored.",
        "_generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "_campaigns": campaigns_used,
        "domain_to_slug": dict(sorted(domain_to_slug.items())),
    }
    OUTPUT_JSON.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    print(f"\n[OK] wrote {OUTPUT_JSON}")
    print(f"     {len(domain_to_slug)} total domains across {len(campaigns_used)} active campaigns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
