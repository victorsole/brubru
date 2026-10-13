"""Repair the SRB rows of the consultation layer found on 13 Oct 2026.

Of the 11 rows the SRB consultation ingest had stored, 9 are not consultations (lists of
consultation requests, a press release/page/PDF per year, an overview of 2024, and the SRB's
response to a Commission consultation) and the 2 real ones carried no dates.

  1. every non-consultation row moves out of the consultation layer:
       - when the same URL already exists under the target type (3 press releases already
         sit in the news layer) the consultation-layer duplicate is deleted;
       - otherwise it is retyped (PDF -> publication/pdf, any other page -> news/html);
     its public_consultations mirror row (initiative_id = '99' || economy_items.id) is
     deleted; the script refuses if anyone tracks, answered or documented it.
  2. the two real consultations get their dates read from their own pages
     (services.scrapers.agency_consultations.srb_page_dates), never typed here.

Everything it touches is first written to backend/data/backups/. Dry-run by default;
--apply writes. Idempotent: a second run finds nothing to do. Afterwards run
`python3.12 -m scripts.sync_agency_consultations` to refresh the mirror of the two real rows.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import text  # noqa: E402
from core.database import SessionLocal  # noqa: E402
from services.scrapers.agency_consultations import (  # noqa: E402
    _build, srb_is_consultation, srb_page_dates,
)

_BACKUP = Path(__file__).resolve().parents[1] / "data" / "backups" / "srb_consultation_rows_20261013.json"


def _target(url: str) -> tuple[str, str]:
    return ("publication", "pdf") if url.lower().split("?")[0].endswith(".pdf") else ("news", "html")


def main(apply: bool) -> int:
    db = SessionLocal()
    try:
        rows = db.execute(text(
            "SELECT * FROM economy_items WHERE body_code='srb' AND item_type='consultation' ORDER BY id"
        )).mappings().all()
        print(f"[srb] {len(rows)} rows in the consultation layer")
        keep = [r for r in rows if srb_is_consultation(r["title"], r["public_url"])]
        move = [r for r in rows if not srb_is_consultation(r["title"], r["public_url"])]
        ids = [r["id"] for r in rows]
        mirror = db.execute(text(
            "SELECT * FROM public_consultations WHERE source='agency' AND source_body='SRB' "
            "AND initiative_id = ANY(:i)"), {"i": [f"99{i}" for i in ids]}).mappings().all()

        for tbl in ("user_consultation_tracks", "user_consultation_inputs",
                    "consultation_documents", "consultation_status_history"):
            n = db.execute(text(f"SELECT count(*) FROM {tbl} WHERE consultation_id = ANY(:m)"),
                           {"m": [m["id"] for m in mirror]}).scalar()
            if n:
                print(f"[ABORT] {n} rows in {tbl} depend on an SRB mirror row; decide by hand")
                return 1

        if apply and (move or keep):
            _BACKUP.parent.mkdir(parents=True, exist_ok=True)
            _BACKUP.write_text(json.dumps(
                {"economy_items": [dict(r) for r in rows], "public_consultations": [dict(m) for m in mirror]},
                default=str, ensure_ascii=False, indent=1))
            print(f"[srb] backup written: {_BACKUP}")

        for r in move:
            typ, kind = _target(r["public_url"])
            dup = db.execute(text(
                "SELECT id FROM economy_items WHERE body_code='srb' AND item_type=:t AND public_url=:u"),
                {"t": typ, "u": r["public_url"]}).first()
            what = f"DELETE duplicate of {typ} {dup[0]}" if dup else f"RETYPE -> {typ}/{kind}"
            print(f"  [{what}] {r['id']} {r['title'][:70]}")
            if apply:
                if dup:
                    db.execute(text("DELETE FROM economy_items WHERE id=:i"), {"i": r["id"]})
                else:
                    db.execute(text("UPDATE economy_items SET item_type=:t, source_kind=:k WHERE id=:i"),
                               {"t": typ, "k": kind, "i": r["id"]})
        moved_initiatives = {f"99{r['id']}" for r in move}
        doomed = [m["id"] for m in mirror if m["initiative_id"] in moved_initiatives]
        print(f"[srb] {len(doomed)} mirror rows leave public_consultations")
        if apply and doomed:
            db.execute(text("DELETE FROM public_consultations WHERE id = ANY(:m)"), {"m": doomed})

        now = datetime.now(timezone.utc)
        for r in keep:
            start, end = srb_page_dates(r["public_url"])
            it = _build(body_code="srb", title=r["title"], url=r["public_url"], status="",
                        deadline=end, start=start, now=now, source_kind="srb_consultations",
                        strict_deadline=True)
            print(f"  [DATES] {r['id']} start={start.date() if start else None} end={end.date() if end else None} "
                  f"{r['title'][:60]}")
            if apply:
                db.execute(text("UPDATE economy_items SET body_txt=:t, body_html=:h, document_date=:d WHERE id=:i"),
                           {"t": it.body_txt, "h": it.body_html, "d": it.document_date, "i": r["id"]})
        if apply:
            db.commit()
            print("[srb] APPLIED")
        else:
            db.rollback()
            print("[srb] dry run, nothing written (--apply to write)")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    sys.exit(main(ap.parse_args().apply))
