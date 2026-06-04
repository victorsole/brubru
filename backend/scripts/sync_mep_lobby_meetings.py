"""
Ingest MEP lobby meetings into mep_lobby_meetings, from OEIL Transparency (per
procedure) + MEP profile pages (per MEP), deduped, with Transparency Register
org enrichment.

    python3.12 -m scripts.sync_mep_lobby_meetings --procedures 40 --profiles 15
"""

import argparse
import logging
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
logging.disable(logging.INFO)

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text as sqla_text
from core.database import SessionLocal, engine
from services.scrapers.mep_lobby_meetings_scraper import (
    fetch_oeil, parse_oeil_transparency, scrape_mep_profile, norm_org,
)
from services.transparency_register_match import match_org


def _merge_key(r):
    return (r.get("mep_id") or r.get("mep_name"), norm_org(r.get("organisation") or ""), r.get("meeting_date"))


def run(n_procedures, n_profiles, dry):
    db = SessionLocal()
    # 1) Source procedures: ongoing legislative files (active rapporteurs = more
    # meetings) + adopted texts. Legislative types (COD/NLE/CNS/APP/SYN) first.
    procs = [r[0] for r in db.execute(sqla_text("""
        SELECT ref FROM (
          SELECT DISTINCT oeil_procedure_ref AS ref FROM legislative_carriages WHERE oeil_procedure_ref IS NOT NULL
          UNION
          SELECT DISTINCT procedure_ref AS ref FROM texts_adopted WHERE procedure_ref IS NOT NULL
        ) t
        ORDER BY (CASE WHEN ref ILIKE '%(COD)%' OR ref ILIKE '%(NLE)%' OR ref ILIKE '%(CNS)%'
                       OR ref ILIKE '%(APP)%' THEN 0 ELSE 1 END), ref DESC
        LIMIT :n"""), {"n": n_procedures}).fetchall()]
    print(f"[mep-meetings] {len(procs)} procedures to scan via OEIL")
    # Release the connection NOW (while alive) - the OEIL/Playwright loops below take
    # minutes, long enough for the pooler to kill an idle held connection.
    db.close()

    collected = {}   # merge_key -> row
    mep_ids = set()

    def _add(r):
        if not (r.get("organisation") and r.get("meeting_date")):
            return
        # Respect column widths (raw SQL bypasses ORM coercion).
        r["organisation"] = (r["organisation"] or "")[:500]
        r["organisation_norm"] = norm_org(r["organisation"])[:500]
        if r.get("role"):
            r["role"] = r["role"][:80]
        if r.get("mep_name"):
            r["mep_name"] = r["mep_name"][:255]
        if r.get("committee"):
            r["committee"] = r["committee"][:20]
        if r.get("procedure_ref"):
            r["procedure_ref"] = r["procedure_ref"][:50]
        k = _merge_key(r)
        if k in collected:
            ex = collected[k]
            ex["procedure_ref"] = ex.get("procedure_ref") or r.get("procedure_ref")
            ex["role"] = ex.get("role") or r.get("role")
            ex["committee"] = ex.get("committee") or r.get("committee")
            if r["source"] not in (ex["source"] or ""):
                ex["source"] = "both"
        else:
            collected[k] = r
        if r.get("mep_id"):
            mep_ids.add(r["mep_id"])

    for i, ref in enumerate(procs, 1):
        html = fetch_oeil(ref)
        if html:
            for row in parse_oeil_transparency(ref, html):
                _add(row)
        if i % 10 == 0:
            print(f"  OEIL {i}/{len(procs)} | rows so far: {len(collected)} | meps: {len(mep_ids)}")

    # 2) MEP profiles (Playwright) for the MEPs found, capped.
    profile_ids = list(mep_ids)[:n_profiles]
    print(f"[mep-meetings] scraping {len(profile_ids)} MEP profiles (Playwright)")
    for j, mid in enumerate(profile_ids, 1):
        for row in scrape_mep_profile(mid):
            _add(row)
        print(f"  profile {j}/{len(profile_ids)} ({mid}) | rows so far: {len(collected)}")

    # 3) Org enrichment (Transparency Register) + persist. The OEIL/Playwright loops
    # above run long enough for the Supabase pooler to server-side-close the pooled
    # connection mid-flight (pre_ping can't catch a drop during a query), so DISPOSE the
    # whole pool and open a genuinely fresh session for the DB-heavy phase.
    engine.dispose()
    db = SessionLocal()
    import services.transparency_register_match as trm
    trm._INDEX = trm._BY_ID = None        # force rebuild on the fresh connection
    try:
        trm._build_index(db)
    except Exception as e:
        print("[mep-meetings] WARN register index build failed:", str(e)[:120])

    added = updated = enriched = 0
    for r in collected.values():
        rec = match_org(r.get("organisation"), db, r.get("transparency_register_id"))
        if rec:
            r["transparency_register_id"] = rec["tr_id"]
            r["org_website"] = rec["website"]
            r["org_register_url"] = rec["register_url"]
            enriched += 1
    print(f"[mep-meetings] collected={len(collected)} org-enriched={enriched}")
    if dry:
        for r in list(collected.values())[:6]:
            print("  ", r["meeting_date"], r["mep_name"], "|", r["role"], "|", r["procedure_ref"], "|",
                  r["organisation"][:40], "| web:", bool(r.get("org_website")), "| src:", r["source"])
        db.close(); return

    for i_row, r in enumerate(collected.values(), 1):
        try:
            res = db.execute(sqla_text("""
                INSERT INTO mep_lobby_meetings
                  (id, procedure_ref, mep_id, mep_name, role, committee, meeting_date,
                   organisation, organisation_norm, transparency_register_id, org_website,
                   org_register_url, source, source_url, scraped_at, first_seen, last_updated)
                VALUES (:id,:proc,:mid,:name,:role,:com,:dt,:org,:orgn,:trid,:web,:reg,:src,:url,
                        now(), now(), now())
                ON CONFLICT (mep_id, organisation_norm, meeting_date) DO UPDATE SET
                  procedure_ref = COALESCE(mep_lobby_meetings.procedure_ref, EXCLUDED.procedure_ref),
                  role = COALESCE(mep_lobby_meetings.role, EXCLUDED.role),
                  source = CASE WHEN mep_lobby_meetings.source <> EXCLUDED.source THEN 'both' ELSE mep_lobby_meetings.source END,
                  org_website = COALESCE(EXCLUDED.org_website, mep_lobby_meetings.org_website),
                  org_register_url = COALESCE(EXCLUDED.org_register_url, mep_lobby_meetings.org_register_url),
                  transparency_register_id = COALESCE(EXCLUDED.transparency_register_id, mep_lobby_meetings.transparency_register_id),
                  last_updated = now()
                RETURNING (xmax = 0) AS inserted
            """), {
                "id": str(uuid.uuid4()), "proc": r.get("procedure_ref"), "mid": r.get("mep_id"),
                "name": r.get("mep_name"), "role": r.get("role"), "com": r.get("committee"),
                "dt": r.get("meeting_date"), "org": r["organisation"], "orgn": r["organisation_norm"],
                "trid": r.get("transparency_register_id"), "web": r.get("org_website"),
                "reg": r.get("org_register_url"), "src": r["source"], "url": r.get("source_url"),
            })
            ins = res.fetchone()
            if ins and ins[0]:
                added += 1
            else:
                updated += 1
            if i_row % 50 == 0:        # batch-commit so a late drop can't lose everything
                db.commit()
        except Exception as e:
            try:
                db.rollback()
            except Exception:
                db.close(); engine.dispose(); db = SessionLocal()
            print("  upsert err:", str(e)[:100])
            continue
    db.commit()
    total = db.execute(sqla_text("SELECT count(*) FROM mep_lobby_meetings")).scalar()
    print(f"[mep-meetings] DONE added={added} updated={updated} table_total={total}")
    db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--procedures", type=int, default=40)
    ap.add_argument("--profiles", type=int, default=15)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    run(a.procedures, a.profiles, a.dry_run)
