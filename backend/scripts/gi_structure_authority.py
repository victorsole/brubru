"""
Restructure gi_details.competent_authority into a structured jsonb value:

    {"authority": "<national competent authority>", "control_body": "<regional control
     body / producer group, or null>"}

- authority     = the member state's NATIONAL competent authority (from the GIView
                  Country-authorities card; these are the high-frequency values shared
                  across a country, e.g. INAO for FR, the Ministerio for ES).
- control_body  = the regional control body / recognised producer group (from the
                  eAmbrosia roster producerGroupName / recognisedProducersGroup, e.g.
                  "Consorzio Tutela Vini d'Abruzzo", "Consejo Regulador ..."), where one
                  exists — else null.

Idempotent: rows already structured (dict) are re-derived from their current parts.

  python3.12 scripts/gi_structure_authority.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2
import requests
from core.config import settings

ROSTER = "https://webgate.ec.europa.eu/eambrosia-api/api/v1/geographical-indications"


def control_of(x):
    rpg = x.get("recognisedProducersGroup") or []
    if rpg and isinstance(rpg, list) and rpg[0].get("name"):
        return rpg[0]["name"]
    return x.get("producerGroupName") or None


def main():
    roster = requests.get(ROSTER, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}, timeout=120).json()
    cbmap = {x["fileNumber"]: control_of(x) for x in roster if x.get("fileNumber")}

    c = psycopg2.connect(settings.DATABASE_URL, connect_timeout=20); c.autocommit = True
    cur = c.cursor()
    cur.execute("SELECT file_number, countries, competent_authority FROM gi_details")
    rows = cur.fetchall()

    # flatten current value to a plain string (handles both string and already-structured)
    def cur_auth(ca):
        if isinstance(ca, dict):
            return ca.get("authority") or ca.get("control_body")
        return ca

    strings = [(fn, cts, cur_auth(ca)) for fn, cts, ca in rows]
    vc = Counter(s for _, _, s in strings if s)
    NATIONAL = {v for v, n in vc.items() if n > 3}       # national bodies are shared widely

    # country -> national authority (mode among national-valued rows)
    cm = defaultdict(Counter)
    for fn, cts, s in strings:
        if s in NATIONAL and cts:
            cm[cts[0]][s] += 1
    cmap = {ct: cnt.most_common(1)[0][0] for ct, cnt in cm.items()}

    filled = with_control = 0
    for fn, cts, s in strings:
        country = (cts or [None])[0]
        is_nat = s in NATIONAL
        authority = cmap.get(country) or (s if is_nat else None)
        control = cbmap.get(fn) or (None if is_nat else s)
        if control:
            with_control += 1
        val = {"authority": authority, "control_body": control}
        cur.execute("UPDATE gi_details SET competent_authority=%s::jsonb WHERE file_number=%s",
                    (json.dumps(val, ensure_ascii=False), fn))
        filled += 1
    print(f"[structure] rewrote {filled} rows | with a control_body: {with_control} | "
          f"countries mapped: {len(cmap)}")
    c.close()


if __name__ == "__main__":
    main()
