"""
Backfill real titles for carriages stuck with the "Procedure File: REF" placeholder.

The OEIL *procedure-file* page exposes only the placeholder in its <title> tag, but
the OEIL *search* listing carries the real descriptive title in
`div.es_document-body > p`. This script searches OEIL by exact reference, parses
that title, and updates legislative_carriages.title.

Uses the repo's Playwright fetcher (the OEIL search is JS/WAF-walled). One browser
instance is reused across all refs; a short delay keeps it polite.

Usage:
    python3.12 -m backend.scripts.backfill_titles_from_oeil_search --limit 3        # dry-run sample
    python3.12 -m backend.scripts.backfill_titles_from_oeil_search --apply          # full run
"""

import argparse
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on path

from core.database import SessionLocal
from models.legislative_train import LegislativeCarriage
from services.scrapers.waf_browser_fetcher import WafBrowserFetcher

PLACEHOLDER_RE = re.compile(r"^\s*Procedure File:\s*\d{4}/\d+\([A-Z]+\)", re.IGNORECASE)
BODY_P_RE = re.compile(r'class="es_document-body"[^>]*>\s*<p[^>]*>(.*?)</p>', re.S)


def _search_url(ref: str) -> str:
    return f"https://oeil.europarl.europa.eu/oeil/en/search?fullText.term={quote(ref, safe='')}&fullText.mode=EXACT_WORD"


def parse_title_for_ref(html: str, ref: str) -> str | None:
    """Find the es_document card matching the ref and return its body-paragraph title."""
    for fragment in html.split('<div class="es_document">')[1:]:
        if ref not in fragment:
            continue
        m = BODY_P_RE.search(fragment)
        if not m:
            continue
        title = re.sub(r"<[^>]+>", "", m.group(1))
        title = re.sub(r"\s+", " ", title).strip()
        if title and not PLACEHOLDER_RE.match(title) and len(title) >= 8:
            return title
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill carriage titles from OEIL search.")
    parser.add_argument("--apply", action="store_true", help="Persist changes (default dry-run).")
    parser.add_argument("--limit", type=int, default=0, help="Only process N rows (0 = all).")
    parser.add_argument("--delay", type=float, default=0.6, help="Seconds between fetches.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        q = (
            db.query(LegislativeCarriage)
            .filter(
                LegislativeCarriage.oeil_procedure_ref.isnot(None),
                LegislativeCarriage.title.ilike("Procedure File:%"),
            )
            .order_by(LegislativeCarriage.last_updated.desc().nullslast())
        )
        rows = q.limit(args.limit).all() if args.limit else q.all()
        print(f"[INFO] {len(rows)} placeholder-titled carriages to resolve.")

        recovered = 0
        failed = []
        with WafBrowserFetcher() as f:
            for i, c in enumerate(rows, 1):
                ref = c.oeil_procedure_ref
                try:
                    res = f.fetch(_search_url(ref), expand_accordions=False)
                    title = parse_title_for_ref(res.html or "", ref)
                except Exception as exc:
                    title = None
                    print(f"  [{i}/{len(rows)}] {ref}: fetch error {type(exc).__name__}")
                if title:
                    print(f"  [{i}/{len(rows)}] {ref} -> {title[:80]}")
                    if args.apply:
                        c.title = title
                    recovered += 1
                else:
                    failed.append(ref)
                    print(f"  [{i}/{len(rows)}] {ref}: no title found")
                if args.apply and recovered and recovered % 20 == 0:
                    db.commit()
                time.sleep(args.delay)

        if args.apply:
            db.commit()
            print(f"[OK] Recovered + saved {recovered} titles. {len(failed)} unresolved.")
        else:
            print(f"[DRY-RUN] Would recover {recovered}. {len(failed)} unresolved. Re-run with --apply.")
        if failed:
            print("  unresolved:", ", ".join(failed[:15]), ("…" if len(failed) > 15 else ""))
    finally:
        db.close()


if __name__ == "__main__":
    main()
