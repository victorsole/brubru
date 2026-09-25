"""EEA news: 534 rows for 35 articles, all pointing at an unreachable address.

Found 25 September 2026 while auditing body coverage for GovClipping.

Two faults, one cause. The EEA's RSS feed was emitting its internal load-balancer address
in <link> (`http://10.140.139.135:3000/en/newsroom/news/...`), and a different IP on each
run. So:

  * every `public_url` we served for EEA news pointed at a private address that resolves
    for nobody, and
  * the ingest deduplicates on the URL, so the same article arrived as a new row on every
    run: 19 copies of each, between 8 June and 8 September.

The feed is fixed at source (checked today: 26 items, every link on www.eea.europa.eu),
but our stored rows still carry the old addresses, and nothing would have merged them.

This normalises the host, keeps one row per article, and leaves the survivors ready for
the body fetch. Every deleted row is backed up first.

Usage (from backend/):
    python3.12 scripts/repair_eea_news.py            # dry run
    python3.12 scripts/repair_eea_news.py --apply
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402

BACKUP_DIR = BACKEND.parent / "docs" / "backups"
PUBLIC_HOST = "https://www.eea.europa.eu"
PRIVATE = re.compile(r"^https?://(?:10\.|192\.168\.|127\.|172\.(?:1[6-9]|2\d|3[01])\.)[^/]*")


def canonical(url: str) -> str:
    """A private address is not a public URL. Keep the path, restore the real host."""
    return PRIVATE.sub(PUBLIC_HOST, url or "", count=1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        rows = db.execute(text(
            "SELECT id, source_url, title, coalesce(length(body_txt),0) AS blen, "
            "       scraped_at, news_date "
            "FROM eu_news_items WHERE institution = 'EEA' ORDER BY scraped_at")).fetchall()
        print(f"[INFO] {len(rows):,} EEA rows")

        groups: dict[str, list] = {}
        rewrites = 0
        for r in rows:
            fixed = canonical(r.source_url)
            if fixed != r.source_url:
                rewrites += 1
            groups.setdefault(fixed, []).append(r)

        dupes = {u: rs for u, rs in groups.items() if len(rs) > 1}
        doomed = []
        for url, members in dupes.items():
            # Keep the richest row, then the earliest: the first sighting is the real one.
            members = sorted(members, key=lambda r: (-r.blen, r.scraped_at or datetime.max))
            doomed.extend(m.id for m in members[1:])

        print(f"[INFO] {rewrites:,} URL(s) point at a private address and would be rewritten")
        print(f"[INFO] {len(groups):,} distinct article(s); {len(doomed):,} duplicate row(s) "
              f"would be removed")
        for url, members in list(dupes.items())[:4]:
            print(f"   {len(members):3} copies  {url[:86]}")

        if not args.apply:
            print("[DRY-RUN] re-run with --apply")
            return 0

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        backup = BACKUP_DIR / f"eea_news_duplicates_{stamp}.json"
        payload = db.execute(text(
            "SELECT row_to_json(n) FROM eu_news_items n WHERE id = ANY(:ids)"),
            {"ids": doomed}).scalars().all()
        backup.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
        print(f"[BACKUP] {len(payload):,} row(s) -> {backup}")
        if len(payload) != len(doomed):
            print(f"[ERROR] backed up {len(payload)} of {len(doomed)}: refusing to delete")
            return 1

        if doomed:
            db.execute(text("DELETE FROM eu_news_items WHERE id = ANY(:ids)"), {"ids": doomed})
        # Survivors get the public host.
        db.execute(text(
            "UPDATE eu_news_items SET source_url = regexp_replace("
            "  source_url, '^https?://(10\\.|192\\.168\\.|127\\.)[^/]*', :host), "
            "  scraped_at = scraped_at "
            "WHERE institution = 'EEA' AND source_url ~ '^https?://(10\\.|192\\.168\\.|127\\.)'"),
            {"host": PUBLIC_HOST})
        db.commit()

        left, private, distinct = db.execute(text(
            "SELECT count(*), count(*) FILTER (WHERE source_url ~ "
            "  '^https?://(10\\.|192\\.168\\.|127\\.)'), "
            "  count(DISTINCT source_url) FROM eu_news_items WHERE institution = 'EEA'")).fetchone()
        print(f"[VERIFY] {left} EEA row(s), {distinct} distinct URL(s), "
              f"{private} still on a private address")
        return 0 if private == 0 and left == distinct else 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
