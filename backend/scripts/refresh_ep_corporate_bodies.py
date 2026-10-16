"""EP Open Data's corporate bodies (committees, groups, delegations, national parties) as a
lookup file, so an MEP's memberships read "LIBE" or "PfE" rather than "org/6586" (16 Oct 2026).

Source: https://data.europarl.europa.eu/api/v2/corporate-bodies (no WAF, one call).
Writes knowledge_base/ep_corporate_bodies.json: {"org/6586": ["LIBE", "COMMITTEE_PARLIAMENTARY_STANDING"]}.

    python3.12 scripts/refresh_ep_corporate_bodies.py            # dry run: counts only
    python3.12 scripts/refresh_ep_corporate_bodies.py --apply
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "knowledge_base" / "ep_corporate_bodies.json"
URL = ("https://data.europarl.europa.eu/api/v2/corporate-bodies"
       "?format=application%2Fld%2Bjson&language=en&offset=0&limit=50000")


def fetch() -> dict[str, list[str]]:
    req = urllib.request.Request(URL, headers={"Accept": "application/ld+json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        rows = json.load(r).get("data") or []
    return {x["id"]: [x.get("label") or "", str(x.get("classification") or "").rsplit("/", 1)[-1]]
            for x in rows if x.get("id")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    bodies = fetch()
    if len(bodies) < 1000:
        print(f"[ERROR] only {len(bodies)} bodies returned: not overwriting {OUT.name}")
        return 1
    print(f"[INFO] {len(bodies)} corporate bodies")
    if args.apply:
        lines = [f"{json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}" for k, v in sorted(bodies.items())]
        OUT.write_text("{\n" + ",\n".join(lines) + "\n}\n")
        print(f"[DONE] wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
