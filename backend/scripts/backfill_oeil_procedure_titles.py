"""
Backfill the oeil_procedure_titles cache for procedures that have MEP amendments
but no title in the carriages corpus.

The MEP Amendments picker annotates each procedure with a title; in-progress
proposals are absent from legislative_carriages, so they showed the bare OEIL
reference. This fetches the real title from the OEIL search listing (the title
sits in `div.es_document-body > p`) via the Playwright WAF browser and caches it.

Dedupes by procedure_ref; skips refs already cached or already titled in
legislative_carriages.

Usage:
    python3.12 -m backend.scripts.backfill_oeil_procedure_titles --limit 3   # dry-run sample
    python3.12 -m backend.scripts.backfill_oeil_procedure_titles --apply      # full run
"""

import argparse
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on path

from sqlalchemy import text as sqla_text
from core.database import SessionLocal
from services.scrapers.waf_browser_fetcher import WafBrowserFetcher

BODY_P_RE = re.compile(r'class="es_document-body"[^>]*>\s*<p[^>]*>(.*?)</p>', re.S)


def _search_url(ref: str) -> str:
    return f"https://oeil.europarl.europa.eu/oeil/en/search?fullText.term={quote(ref, safe='')}&fullText.mode=EXACT_WORD"


def parse_title_for_ref(html: str, ref: str) -> str | None:
    for fragment in html.split('<div class="es_document">')[1:]:
        if ref not in fragment:
            continue
        m = BODY_P_RE.search(fragment)
        if not m:
            continue
        title = re.sub(r"<[^>]+>", "", m.group(1))
        title = re.sub(r"\s+", " ", title).strip()
        if title and len(title) >= 8:
            return title
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill OEIL procedure titles for MEP-amendment procedures.")
    parser.add_argument("--apply", action="store_true", help="Persist (default dry-run).")
    parser.add_argument("--limit", type=int, default=0, help="Only process N refs (0 = all).")
    parser.add_argument("--delay", type=float, default=0.6, help="Seconds between fetches.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        rows = db.execute(sqla_text(
            """
            SELECT DISTINCT a.procedure_reference AS ref
            FROM mep_amendments a
            WHERE a.procedure_reference <> ''
              AND NOT EXISTS (
                  SELECT 1 FROM legislative_carriages lc
                  WHERE lc.oeil_procedure_ref = a.procedure_reference AND lc.title IS NOT NULL
              )
              AND NOT EXISTS (
                  SELECT 1 FROM oeil_procedure_titles t WHERE t.procedure_ref = a.procedure_reference
              )
            ORDER BY a.procedure_reference DESC
            """
        )).fetchall()
        refs = [r[0] for r in rows]
        if args.limit:
            refs = refs[: args.limit]
        print(f"[INFO] {len(refs)} untitled procedure refs to resolve.")

        recovered = 0
        failed: list[str] = []
        with WafBrowserFetcher() as f:
            for i, ref in enumerate(refs, 1):
                try:
                    html = f.fetch(_search_url(ref), expand_accordions=False).html or ""
                    title = parse_title_for_ref(html, ref)
                except Exception as exc:
                    title = None
                    print(f"  [{i}/{len(refs)}] {ref}: fetch error {type(exc).__name__}")
                if title:
                    print(f"  [{i}/{len(refs)}] {ref} -> {title[:80]}")
                    if args.apply:
                        db.execute(sqla_text(
                            """
                            INSERT INTO oeil_procedure_titles (procedure_ref, title)
                            VALUES (:ref, :title)
                            ON CONFLICT (procedure_ref) DO UPDATE SET title = EXCLUDED.title, fetched_at = now()
                            """
                        ), {"ref": ref, "title": title})
                        if recovered and recovered % 20 == 0:
                            db.commit()
                    recovered += 1
                else:
                    failed.append(ref)
                    print(f"  [{i}/{len(refs)}] {ref}: no title found")
                time.sleep(args.delay)

        if args.apply:
            db.commit()
            print(f"[OK] Cached {recovered} titles. {len(failed)} unresolved.")
        else:
            print(f"[DRY-RUN] Would cache {recovered}. {len(failed)} unresolved. Re-run with --apply.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
