"""
Sync Council of the EU legislative voting results into ep_roll_call_votes
(level='council') for the MEUB Votes "Council results" tab.

Pipeline: WAF-fetch the public-register list -> per entry, httpx the clean PDF ->
page-1 text (procedure ref / act / config) + page-2 vote image -> vision-parse the
arrows into per-country votes (with self-consistency confidence) -> store. The
per-country breakdown is auto-read from the Council's image-only result sheet; the
source PDF URL is kept so the UI can link/verify. NO Anthropic.

Usage:
    python3.12 -m scripts.sync_council_votes --max 20
"""

import argparse
import os
import sys
import uuid
from datetime import datetime, date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv()

import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from core.config import settings
from core.database import SessionLocal
from models.ep_vote import EpVote, EpVoteRecord
from services.scrapers.council_votes_client import (
    LIST_URL, parse_list, fetch_pdf, parse_pdf, vision_extract, EU27,
)

# Council configuration -> short code (best-effort, for display/filter)
_CONFIG_CODE = {
    "general affairs": "GAC", "foreign affairs": "FAC", "economic and financial": "ECOFIN",
    "justice and home": "JHA", "agriculture and fisheries": "AGRIFISH", "environment": "ENVI",
    "competitiveness": "COMPET", "transport": "TTE", "employment": "EPSCO", "education": "EDUC",
}


def _config_code(raw):
    if not raw:
        return None
    low = raw.lower()
    for k, v in _CONFIG_CODE.items():
        if k in low:
            return v
    return raw[:20]


def _to_date(s):
    try:
        d, m, y = s.split("/")
        return date(int(y), int(m), int(d))
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=20)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    mistral = os.getenv("MISTRAL_API_KEY") or getattr(settings, "MISTRAL_API_KEY", None)
    openai = os.getenv("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", None)

    from services.scrapers.waf_browser_fetcher import WafBrowserFetcher
    with WafBrowserFetcher(settle_ms=10000, networkidle_ms=22000) as f:
        html = (f.fetch(LIST_URL, expand_accordions=False, strip_chrome=False).html) or ""
    entries = parse_list(html)
    print(f"[council-votes] {len(entries)} entries parsed; processing up to {args.max}")

    db = SessionLocal()
    added = skipped = no_image = 0
    try:
        for e in entries[:args.max]:
            vote_key = f"council-{e['st_id']}"
            if db.query(EpVote.id).filter(EpVote.vote_key == vote_key).first():
                skipped += 1
                continue
            pdf = fetch_pdf(e["pdf_url"])
            if not pdf:
                continue
            meta = parse_pdf(pdf)
            breakdown, vf, va, vab, conf, model = {}, None, None, None, None, None
            qmv = {}
            if meta["has_vote_image"]:
                vis = vision_extract(meta["vote_image"], mistral, openai)
                if vis:
                    breakdown = vis["country_breakdown"]; vf = vis["votes_for"]
                    va = vis["votes_against"]; vab = vis["votes_abstention"]
                    conf = vis["confidence"]; model = vis["model"]; qmv = vis["qmv"]
            else:
                no_image += 1
            # PDF page-1 fields are authoritative; fall back to the list-page parse.
            act_title = meta.get("act_title") or e["act_title"]
            config_raw = meta.get("config_raw") or e.get("config_raw")
            meeting_no = meta.get("meeting_no") or e.get("meeting_no")
            config = _config_code(config_raw)
            tag = f"[{conf}]" if conf else "(no vote image / decision)"
            print(f"  {e['st_id']:22s} {config or '-':8s} "
                  f"for={vf} against={va} abs={vab} {tag} :: {(act_title or '')[:46]}")
            if args.dry_run:
                continue
            vote = EpVote(
                id=uuid.uuid4(), vote_key=vote_key, level="council",
                procedure_ref=meta.get("procedure_ref"),
                title=act_title, subject=config_raw,
                committee_code=config, vote_date=_to_date(e.get("pub_date")),
                result="adopted", votes_for=vf, votes_against=va, votes_abstention=vab,
                vote_type="qmv", country_breakdown={
                    "votes": breakdown, "qmv": qmv, "confidence": conf, "vision_model": model,
                    "meeting_no": meeting_no, "config": config_raw,
                },
                total_records=len(breakdown), source_url=e["pdf_url"],
            )
            db.add(vote)
            db.flush()
            for code, choice in breakdown.items():
                db.add(EpVoteRecord(
                    id=uuid.uuid4(), vote_id=vote.id, mep_name=EU27.get(code, code),
                    country=code, political_group=None,
                    vote_choice={"for": "+", "against": "-", "abstain": "0"}[choice],
                    is_intention=False,
                ))
            db.commit()
            added += 1
    finally:
        db.close()
    print(f"[council-votes] added={added} skipped={skipped} no_image={no_image}")


if __name__ == "__main__":
    main()
