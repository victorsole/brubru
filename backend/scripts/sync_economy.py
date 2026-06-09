#!/usr/bin/env python3.12
"""
Backfill / refresh the economy_items table for the /api/v2/ecb folder
(ECB + ECB Banking Supervision) and, later, the other economy bodies.

Sources (verified — see services/scrapers/economy_ecb.py):
  ECB     news=RSS+HTML  publication=RSS+PDF/HTML  event=Playwright  legal=Cellar
  ECB SSM news=RSS+HTML  publication=Playwright    event=Playwright

Usage:
  python3.12 scripts/sync_economy.py --body ecb --type all
  python3.12 scripts/sync_economy.py --body ecb_ssm --type news
  python3.12 scripts/sync_economy.py --all-ecb            # ECB + SSM, every type
  python3.12 scripts/sync_economy.py --all-ecb --no-bodies   # skip detail-page fetch
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.scrapers import economy_ecb as e          # noqa: E402
from services.scrapers import economy_eba as eba        # noqa: E402
from services.scrapers import economy_esma as esma      # noqa: E402
from services.scrapers import economy_eiopa as eiopa     # noqa: E402
from services.scrapers import economy_esrb as esrb       # noqa: E402
from services.scrapers import economy_srb as srb         # noqa: E402
from services.scrapers import economy_eib as eib         # noqa: E402
from services.scrapers import economy_amla as amla       # noqa: E402
from services.scrapers import economy_eppo as eppo       # noqa: E402
from services.scrapers import economy_esm as esm         # noqa: E402
from scripts._specialised_helpers import ChunkedDb       # noqa: E402

# (body_code, item_type) -> callable returning list[Item]
INGESTORS = {
    ("ecb", "news"):            e.ingest_ecb_news,
    ("ecb", "publication"):     e.ingest_ecb_publications,
    ("ecb", "event"):           e.ingest_ecb_events,
    ("ecb", "legal"):           e.fetch_ecb_legal_acts,
    ("ecb_ssm", "news"):        e.ingest_ssm_news,
    ("ecb_ssm", "publication"): e.ingest_ssm_publications,
    ("ecb_ssm", "event"):       e.ingest_ssm_events,
    ("eba", "news"):            eba.ingest_eba_news,
    ("eba", "publication"):     eba.ingest_eba_publications,
    ("eba", "event"):           eba.ingest_eba_events,
    ("esma", "news"):           esma.ingest_esma_news,
    ("esma", "publication"):    esma.ingest_esma_publications,
    ("eiopa", "news"):          eiopa.ingest_eiopa_news,
    ("eiopa", "publication"):   eiopa.ingest_eiopa_publications,
    ("eiopa", "event"):         eiopa.ingest_eiopa_events,
    ("esrb", "news"):           esrb.ingest_esrb_news,
    ("esrb", "publication"):    esrb.ingest_esrb_publications,
    ("esrb", "event"):          esrb.ingest_esrb_events,
    ("srb", "news"):            srb.ingest_srb_news,
    ("srb", "publication"):     srb.ingest_srb_publications,
    ("srb", "event"):           srb.ingest_srb_events,
    ("eib", "news"):            eib.ingest_eib_news,
    ("eib", "publication"):     eib.ingest_eib_publications,
    ("eib", "event"):           eib.ingest_eib_events,
    ("amla", "news"):           amla.ingest_amla_news,
    ("amla", "publication"):    amla.ingest_amla_publications,
    ("amla", "event"):          amla.ingest_amla_events,
    ("eppo", "news"):           eppo.ingest_eppo_news,
    ("eppo", "publication"):    eppo.ingest_eppo_publications,
    ("esm", "news"):            esm.ingest_esm_news,
    ("esm", "publication"):     esm.ingest_esm_publications,
    ("esm", "event"):           esm.ingest_esm_events,
}

_UPSERT = """
INSERT INTO economy_items
  (body_code, item_type, title, summary, public_url, body_txt, body_html,
   document_date, creation_date, source_kind, guid)
VALUES
  (%(body_code)s, %(item_type)s, %(title)s, %(summary)s, %(public_url)s, %(body_txt)s,
   %(body_html)s, %(document_date)s, %(creation_date)s, %(source_kind)s, %(guid)s)
ON CONFLICT (body_code, item_type, public_url) DO UPDATE SET
  title         = EXCLUDED.title,
  summary       = EXCLUDED.summary,
  body_txt      = EXCLUDED.body_txt,
  body_html     = EXCLUDED.body_html,
  document_date = EXCLUDED.document_date,
  source_kind   = EXCLUDED.source_kind,
  guid          = EXCLUDED.guid,
  creation_date = COALESCE(economy_items.creation_date, EXCLUDED.creation_date),
  fetched_at    = now();
"""


def _run_one(db: ChunkedDb, body: str, itype: str, *, fetch_bodies: bool, legal_limit: int) -> int:
    fn = INGESTORS[(body, itype)]
    if itype == "legal":
        items = fn(limit=legal_limit)
    else:
        items = fn(fetch_bodies=fetch_bodies)
    n = 0
    for it in items:
        db.execute(_UPSERT, {
            "body_code": it.body_code, "item_type": it.item_type, "title": it.title,
            "summary": it.summary, "public_url": it.public_url, "body_txt": it.body_txt,
            "body_html": it.body_html, "document_date": it.document_date,
            "creation_date": it.creation_date, "source_kind": it.source_kind, "guid": it.guid,
        })
        n += 1
        if n % 25 == 0:
            db.commit()
    db.commit()
    print(f"[OK] {body}/{itype}: upserted {n} items", flush=True)
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description="Backfill economy_items (ECB folder).")
    ap.add_argument("--body", choices=["ecb", "ecb_ssm", "eba", "esma", "eiopa", "esrb", "srb", "eib", "amla", "eppo", "esm"])
    ap.add_argument("--type", default="all",
                    choices=["all", "news", "publication", "event", "legal"])
    ap.add_argument("--all-ecb", action="store_true", help="ECB + SSM, every available type")
    ap.add_argument("--no-bodies", action="store_true", help="skip detail-page body fetch (faster)")
    ap.add_argument("--legal-limit", type=int, default=200)
    args = ap.parse_args()

    if args.all_ecb:
        targets = [k for k in INGESTORS]
    elif args.body:
        wanted = [args.type] if args.type != "all" else ["news", "publication", "event", "legal"]
        targets = [(args.body, t) for t in wanted if (args.body, t) in INGESTORS]
    else:
        ap.error("pass --body or --all-ecb")

    db = ChunkedDb(autocommit=False)
    total = 0
    try:
        for body, itype in targets:
            try:
                total += _run_one(db, body, itype, fetch_bodies=not args.no_bodies,
                                  legal_limit=args.legal_limit)
            except Exception as exc:  # one resource failing must not abort the rest
                db.rollback()
                print(f"[ERROR] {body}/{itype}: {exc}", flush=True)
        print(f"[DONE] total upserted: {total}", flush=True)
    finally:
        db.close()


if __name__ == "__main__":
    main()
