"""Give delegated and implementing acts the dates of the ACT, not of our import.

GovClipping (25 September 2026): "a regulation from 2014 looks as if it were published in
2026". They were right. /legislative/delegated-acts and /legislative/implementing-acts
served only creation_date and last_updated, and both hold Brubru's import timestamps.
Measured that day, 4 of 7,521 rows had a publication_date and 6,976 carried a CELEX that
Cellar can date.

It is not only a display problem: the list endpoint sorts AND filters on publication_date,
so published_from / published_to were answered from those 4 rows.

Cellar holds both dates an act has, and this fills both:
    publication_date <- cdm:work_date_creation_legacy   the Official Journal date
    adoption_date    <- cdm:work_date_document          the date it was adopted
Checked against the Journal for three acts before trusting it: 32014R0241 -> OJ L 74 of
14.3.2014, 32016R0161 -> OJ L 32 of 9.2.2016, 32014R0342 -> OJ L 100 of 3.4.2014.

A CELEX Cellar does not know is NOT dated and NOT guessed: it is written to
docs/backups/secondary_acts_unresolvable_celex_<date>.json, which is evidence for the
separate question of whether those CELEX values are right at all.

CELEX literals in Cellar are typed xsd:string; a VALUES clause with plain literals matches
nothing and returns a confident empty result.

Usage (from backend/):
    python3.12 scripts/backfill_secondary_act_dates.py                 # dry run, 200 acts
    python3.12 scripts/backfill_secondary_act_dates.py --apply --all
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from services.api_clients.cellar_sparql_client import CellarSPARQLClient  # noqa: E402

BACKUP_DIR = BACKEND.parent / "docs" / "backups"
XSD = "^^<http://www.w3.org/2001/XMLSchema#string>"
BATCH = 80


def _query(celexes: list[str]) -> str:
    values = " ".join(f'"{c}"{XSD}' for c in celexes)
    return f"""
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
SELECT ?celex ?adopted ?published WHERE {{
  VALUES ?celex {{ {values} }}
  ?work cdm:resource_legal_id_celex ?celex .
  OPTIONAL {{ ?work cdm:work_date_document ?adopted . }}
  OPTIONAL {{ ?work cdm:work_date_creation_legacy ?published . }}
}}
"""


def _val(row: dict, key: str, *, as_date: bool = False):
    """Cellar returns {"value": ...}. Dates are cut to YYYY-MM-DD; identifiers are NOT:
    truncating a CELEX to 10 characters turns 32021R0776R(04) into 32021R0776 and files
    the corrigendum's dates under the act it corrects."""
    v = row.get(key)
    if isinstance(v, dict):
        v = v.get("value")
    if not v:
        return None
    return str(v)[:10] if as_date else str(v)


async def resolve(celexes: list[str]) -> dict[str, dict]:
    client = CellarSPARQLClient()
    out: dict[str, dict] = {}
    for i in range(0, len(celexes), BATCH):
        chunk = celexes[i:i + BATCH]
        try:
            rows = await client.select(_query(chunk))
        except Exception as exc:  # recorded, never silently skipped
            print(f"  [ERROR] batch {i // BATCH + 1}: {type(exc).__name__}: {exc}", flush=True)
            continue
        for r in rows:
            celex = _val(r, "celex")
            if celex:
                out[celex] = {"adopted": _val(r, "adopted", as_date=True),
                              "published": _val(r, "published", as_date=True)}
        print(f"  [{min(i + BATCH, len(celexes)):5}/{len(celexes)}] resolved {len(out)}", flush=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--all", action="store_true", help="every undated act, not the first 200")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        limit = "" if args.all else " LIMIT 200"
        celexes = [r[0] for r in db.execute(text(
            "SELECT DISTINCT celex FROM secondary_acts "
            "WHERE celex IS NOT NULL AND (publication_date IS NULL OR adoption_date IS NULL)"
            f" ORDER BY celex{limit}")).fetchall()]
        print(f"[INFO] {len(celexes):,} CELEX to date")
        if not celexes:
            print("[INFO] nothing to do")
            return 0

        cache = BACKUP_DIR / "secondary_act_dates_cache.json"
        cached = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
        todo = [c for c in celexes if c not in cached]
        if cached:
            print(f"[INFO] {len(cached):,} CELEX already resolved in {cache.name}; "
                  f"{len(todo):,} to fetch")
        found = dict(cached)
        if todo:
            found.update(asyncio.run(resolve(todo)))
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(found, indent=1), encoding="utf-8")
        missing = sorted(set(celexes) - set(found))
        # An act cannot be published before it is adopted. Cellar itself carries a few
        # inconsistent records: for 32021D1877 it gives work_date_document 2021-11-22 with
        # an entry into force of 2021-11-15, which is impossible, while the OJ date
        # (2021-10-26) is right. Where the pair contradicts itself the adoption date is
        # dropped rather than served: a date we can show is wrong is worse than no date.
        contradictory = 0
        for v in found.values():
            if v.get("adopted") and v.get("published") and v["published"] < v["adopted"]:
                v["adopted"] = None
                contradictory += 1
        if contradictory:
            print(f"[INFO] {contradictory} act(s) had an adoption date after their "
                  f"publication date; adoption date dropped for those")

        dated = {c: v for c, v in found.items() if v["published"] or v["adopted"]}
        print(f"[INFO] Cellar knew {len(found):,}; {len(dated):,} carry a date; "
              f"{len(missing):,} CELEX did not resolve at all")

        # A cross-check against the rows that already had a date, before writing anything.
        agree = db.execute(text(
            "SELECT celex, publication_date::text FROM secondary_acts "
            "WHERE publication_date IS NOT NULL AND celex = ANY(:c)"),
            {"c": list(dated)}).fetchall()
        for celex, stored in agree:
            fetched = dated[celex]["published"]
            if fetched and stored != fetched:
                print(f"  [WARN] {celex}: stored {stored}, Cellar says {fetched}")

        if not args.apply:
            for c, v in list(dated.items())[:6]:
                print(f"   {c}  adopted={v['adopted']}  published={v['published']}")
            print("[DRY-RUN] re-run with --apply")
            return 0

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        if missing:
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            path = BACKUP_DIR / f"secondary_acts_unresolvable_celex_{stamp}.json"
            path.write_text(json.dumps(missing, indent=1), encoding="utf-8")
            print(f"[INFO] {len(missing):,} unresolvable CELEX written to {path}")

        updated = 0
        for celex, v in dated.items():
            updated += db.execute(text(
                # CAST(...), not :pub::date -- SQLAlchemy's text() does not bind a
                # parameter written with the PostgreSQL :: cast glued to it, and drops it
                # from the parameter set, so the statement fails on a missing parameter.
                "UPDATE secondary_acts SET "
                "  publication_date = coalesce(publication_date, CAST(:pub AS date)), "
                "  adoption_date    = coalesce(adoption_date, CAST(:adopt AS date)), "
                "  last_updated = now() "
                "WHERE celex = :celex AND (publication_date IS NULL OR adoption_date IS NULL)"),
                {"pub": v["published"], "adopt": v["adopted"], "celex": celex}).rowcount
        db.commit()
        print(f"[APPLIED] {updated:,} row(s) dated")

        still = db.execute(text(
            "SELECT count(*) FROM secondary_acts WHERE celex IS NOT NULL "
            "AND publication_date IS NULL")).scalar()
        total = db.execute(text("SELECT count(*) FROM secondary_acts")).scalar()
        have = db.execute(text(
            "SELECT count(*) FROM secondary_acts WHERE publication_date IS NOT NULL")).scalar()
        print(f"[VERIFY] {have:,}/{total:,} rows now have a publication_date; "
              f"{still:,} with a CELEX still undated")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
