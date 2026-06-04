"""
Ingest EC Have-Your-Say feedback into consultation_feedback (Tier-1 positions layer).

For each consultation that has feedback, pull the org submissions, classify each one's
stated stance with Qwen (only when there is substantive inline text), match the org to
the Transparency Register, and upsert. Org-anchored: this is later surfaced on a file via
the lobbying-org register-id match. NO Anthropic.

    python3.12 -m scripts.sync_consultation_feedback --consultations 27 --max-feedback 30 --max-qwen 200
"""

import argparse
import asyncio
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
from services.scrapers.hys_feedback_scraper import (
    fetch_initiative, publications_with_feedback, fetch_feedback, parse_feedback,
)
from services.positions.stance_extractor import extract_stance
from services.transparency_register_match import match_org
from services.scrapers.mep_lobby_meetings_scraper import norm_org

MIN_TEXT = 120   # below this, treat as boilerplate/attachment-only (skip Qwen)


async def run(n_consultations, max_feedback, max_qwen, dry):
    db = SessionLocal()
    cons = db.execute(sqla_text("""
        SELECT initiative_id, short_title, title, dg_responsible, policy_areas, feedback_count
        FROM public_consultations WHERE feedback_count > 0
        ORDER BY feedback_count DESC LIMIT :n"""), {"n": n_consultations}).fetchall()
    db.close()
    print(f"[cf] {len(cons)} consultations with feedback to scan")

    rows = []
    qwen_used = 0
    for i, c in enumerate(cons, 1):
        iid = str(c.initiative_id)
        init = fetch_initiative(iid)
        if not init:
            continue
        title = c.short_title or c.title or (init.get("shortTitle") or "")
        dg = c.dg_responsible or init.get("unit")
        pareas = list(c.policy_areas or [])
        for pub in publications_with_feedback(init):
            for raw in fetch_feedback(pub["id"], max_items=max_feedback):
                p = parse_feedback(raw, iid, title, dg, pareas, pub["id"])
                if not p:
                    continue
                ftext = p.pop("feedback_text", "") or ""
                if len(ftext) >= MIN_TEXT and qwen_used < max_qwen:
                    s = await extract_stance(ftext, p["organisation"], title)
                    qwen_used += 1
                else:
                    s = {"stance": "attachment_only" if len(ftext) < MIN_TEXT else "unclear", "summary": None}
                p["stance"] = s["stance"]
                p["stance_summary"] = s["summary"]
                p["organisation_norm"] = norm_org(p["organisation"])
                rows.append(p)
        if i % 5 == 0:
            print(f"  {i}/{len(cons)} consultations | rows={len(rows)} | qwen={qwen_used}")

    print(f"[cf] collected={len(rows)} qwen_calls={qwen_used}")
    if dry:
        for r in rows[:8]:
            print("  ", (r["organisation"] or "")[:34], "| tr:", r["transparency_register_id"],
                  "| stance:", r["stance"], "|", (r["consultation_title"] or "")[:34])
        return

    # Persist on a fresh session (Qwen loop runs long; pooler may drop the connection).
    engine.dispose()
    db = SessionLocal()
    import services.transparency_register_match as trm
    trm._INDEX = trm._BY_ID = None
    try:
        trm._build_index(db)
    except Exception as e:
        print("[cf] WARN register index:", str(e)[:100])

    added = updated = enriched = 0
    for i_row, r in enumerate(rows, 1):
        rec = match_org(r["organisation"], db, r.get("transparency_register_id"))
        if rec:
            r["transparency_register_id"] = r.get("transparency_register_id") or rec.get("tr_id")
            enriched += 1
        try:
            res = db.execute(sqla_text("""
                INSERT INTO consultation_feedback
                  (id, initiative_id, publication_id, consultation_title, dg_responsible, policy_areas,
                   organisation, organisation_norm, transparency_register_id, user_type, country, language,
                   stance, stance_summary, feedback_excerpt, feedback_date, source_url,
                   scraped_at, first_seen, last_updated)
                VALUES (:id,:iid,:pid,:title,:dg,:pa,:org,:orgn,:tr,:ut,:co,:lang,:st,:sum,:exc,:dt,:url,
                        now(), now(), now())
                ON CONFLICT (publication_id, organisation_norm, feedback_date) DO UPDATE SET
                  stance = EXCLUDED.stance, stance_summary = EXCLUDED.stance_summary,
                  transparency_register_id = COALESCE(EXCLUDED.transparency_register_id, consultation_feedback.transparency_register_id),
                  last_updated = now()
                RETURNING (xmax = 0) AS inserted
            """), {
                "id": str(uuid.uuid4()), "iid": r["initiative_id"], "pid": r["publication_id"],
                "title": r["consultation_title"], "dg": r["dg_responsible"], "pa": r["policy_areas"],
                "org": r["organisation"], "orgn": r["organisation_norm"], "tr": r.get("transparency_register_id"),
                "ut": r.get("user_type"), "co": r.get("country"), "lang": r.get("language"),
                "st": r.get("stance"), "sum": r.get("stance_summary"), "exc": r.get("feedback_excerpt"),
                "dt": r.get("feedback_date"), "url": r.get("source_url"),
            })
            ins = res.fetchone()
            added += 1 if (ins and ins[0]) else 0
            updated += 0 if (ins and ins[0]) else 1
            if i_row % 50 == 0:
                db.commit()
        except Exception as e:
            try: db.rollback()
            except Exception: db.close(); engine.dispose(); db = SessionLocal()
            print("  upsert err:", str(e)[:90])
    db.commit()
    total = db.execute(sqla_text("SELECT count(*) FROM consultation_feedback")).scalar()
    clear = db.execute(sqla_text("SELECT count(*) FROM consultation_feedback WHERE stance IN ('support','oppose','amend','mixed')")).scalar()
    print(f"[cf] DONE added={added} updated={updated} org_matched={enriched} table_total={total} clear_stances={clear}")
    db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--consultations", type=int, default=27)
    ap.add_argument("--max-feedback", type=int, default=30)
    ap.add_argument("--max-qwen", type=int, default=200)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    asyncio.run(run(a.consultations, a.max_feedback, a.max_qwen, a.dry_run))
