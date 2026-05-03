"""
Backfill rapporteur_name on committee_work_items rows whose procedure type
typically has a rapporteur (COD / INI / NLE / APP / CNS) by scraping the
OEIL procedure page.

Source: https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=…

OEIL is the canonical EP legislative observatory; rapporteur appointments
on a procedure are recorded there as soon as the lead committee names one.
DEA / RSP / RPS / DEC procedures do not have rapporteurs in the legislative
sense (delegated acts, resolutions on topical subjects, regulatory
procedure with scrutiny — all rapporteur-less or named ad-hoc) and are
skipped to avoid wasted scrapes.

Run:
    python3.12 backend/scripts/backfill_committee_rapporteurs.py            # dry-run, 5 refs
    python3.12 backend/scripts/backfill_committee_rapporteurs.py --apply
    python3.12 backend/scripts/backfill_committee_rapporteurs.py --apply --limit 200
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
sys.path.insert(0, str(ROOT / "backend"))


def get_env(k: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=5)
    args = ap.parse_args()

    db_url = get_env("DATABASE_URL")
    if not db_url:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)

    from services.api_clients.oeil_client import OEILClient

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute(
        r"""
        SELECT DISTINCT procedure_ref
          FROM committee_work_items
         WHERE rapporteur_name IS NULL
           AND procedure_ref ~ '\((COD|INI|NLE|APP|CNS)\)$'
         ORDER BY procedure_ref DESC
         LIMIT %s
        """,
        (args.limit,),
    )
    refs = [r[0] for r in cur.fetchall()]
    cur.close()
    print(f"[INFO] {len(refs)} distinct procedure refs queued (apply={args.apply})")

    client = OEILClient()
    updated = unchanged = failed = 0
    for ref in refs:
        try:
            item = await client.lookup_procedure(ref)
            if not item or not item.rapporteurs:
                print(f"  [.] {ref}: no rapporteur on OEIL page")
                unchanged += 1
                continue

            # OEIL parser gives "Shadow rapporteurNAME (Group)" when the lead
            # row is empty — that means no lead is named yet; skip.
            lead = item.rapporteurs[0]
            if lead.lower().startswith("shadow rapporteur"):
                print(f"  [.] {ref}: only shadows named, no lead yet")
                unchanged += 1
                continue
            shadows = item.shadow_rapporteurs or []
            print(f"  [OK] {ref}: lead={lead}  +{len(shadows)} shadows")
            updated += 1

            if args.apply:
                cur2 = conn.cursor()
                cur2.execute(
                    """
                    UPDATE committee_work_items
                       SET rapporteur_name = %s,
                           shadow_rapporteurs = %s::jsonb,
                           last_updated = NOW()
                     WHERE procedure_ref = %s AND rapporteur_name IS NULL
                    """,
                    (
                        lead,
                        psycopg2.extras.Json([{"name": s} for s in shadows]),
                        ref,
                    ),
                )
                conn.commit()
                cur2.close()
        except Exception as exc:
            print(f"  [ERR] {ref}: {exc}")
            failed += 1

    await client.close()
    conn.close()
    print(f"[DONE] updated={updated} unchanged={unchanged} failed={failed}{' (applied)' if args.apply else ' (dry-run)'}")


if __name__ == "__main__":
    import psycopg2.extras  # noqa: F401
    asyncio.run(main())
