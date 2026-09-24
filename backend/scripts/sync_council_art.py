"""Council ART research papers, from the Council's own listing.

ART is the Council's Analysis and Research Team, and Brubru's /news rule names it on
every run. Until 24 September 2026 the corpus held FOUR ART rows, all of them written by
hand in `ingest_research_publications.py`, and they were not real: the first URL checked
answered "Page not found" and none of the titles appear on the Council's listing. Checked
the same way, a seeded ECA row pointed at a real report (SR-2026-09) under an invented
title: the report is about the European innovation partnership in the CAP, not the
Recovery and Resilience Facility.

So this reads the listing instead. It is not behind Cloudflare for a rendering browser
(the queue said 403 to the headless fetcher; measured today it answers 200 with the papers
in the DOM), so it costs no Scrape.do credits.

The page gives, per paper: a heading, a summary, and a PDF. It gives NO publication date,
and the PDF filename carries only a year, so `publication_date` is left NULL rather than
invented: a year read as the 1st of January is how 57 FRA rows landed on 1 January.

Usage (from backend/):
    python3.12 scripts/sync_council_art.py            # dry run
    python3.12 scripts/sync_council_art.py --apply
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402

LISTING = "https://www.consilium.europa.eu/en/documents-publications/council-research-papers/"
BASE = "https://www.consilium.europa.eu"
SOURCE = "art"
# "2026_2006_art_conspiracy_web_260325.pdf" -> the leading group is the year.
_PDF_YEAR = re.compile(r"/(\d{4})_(\d{3,4})_")
_SKIP_HEADINGS = ("ART publications", "About the Analysis", "Contact", "Previous ART")


def scrape() -> list[dict]:
    from bs4 import BeautifulSoup

    from services.scrapers.waf_browser_fetcher import WafBrowserFetcher

    with WafBrowserFetcher(settle_ms=10000, networkidle_ms=22000) as fetcher:
        res = fetcher.fetch(LISTING, expand_accordions=True, strip_chrome=False)
        html = res.html or ""
    low = html[:4000].lower()
    if any(m in low for m in ("just a moment", "checking your browser", "enable javascript and cookies")):
        raise RuntimeError("consilium served a browser challenge for the ART listing: a FETCH BLOCK, "
                           "never 'no papers'")
    soup = BeautifulSoup(html, "lxml")
    papers: list[dict] = []
    seen: set[str] = set()
    for heading in soup.find_all(["h2", "h3"]):
        title = heading.get_text(" ", strip=True)
        if not title or any(s in title for s in _SKIP_HEADINGS):
            continue
        card = heading.find_parent(["article", "li", "div"])
        if card is None:
            continue
        pdfs = [a["href"] for a in card.find_all("a", href=True) if ".pdf" in a["href"].lower()]
        if not pdfs:
            continue
        pdf = pdfs[0] if pdfs[0].startswith("http") else BASE + pdfs[0]
        if pdf in seen:
            continue
        seen.add(pdf)
        # The card's text after the title is the paper's own summary.
        body = card.get_text(" ", strip=True)
        summary = body[len(title):].strip(" |") if body.startswith(title) else body
        m = _PDF_YEAR.search(pdf)
        papers.append({
            "publication_id": f"ART-{m.group(1)}-{m.group(2)}" if m else f"ART-{pdf.rsplit('/', 1)[-1][:40]}",
            "title": title[:480],
            "summary": (summary or None) and summary[:2000],
            "pdf_url": pdf,
            "html_url": LISTING,
            "year": int(m.group(1)) if m else None,
        })
    return papers


_UPSERT = """
INSERT INTO eprs_publications
    (id, publication_id, title, publication_type, html_url, pdf_url, summary,
     publication_date, source, scraped_at, first_seen, last_updated)
VALUES
    (gen_random_uuid(), :pid, :title, 'other', :html_url, :pdf_url, :summary,
     NULL, :source, now(), now(), now())
ON CONFLICT (publication_id) DO UPDATE SET
    title        = EXCLUDED.title,
    summary      = COALESCE(EXCLUDED.summary, eprs_publications.summary),
    pdf_url      = EXCLUDED.pdf_url,
    html_url     = EXCLUDED.html_url,
    last_updated = now()
RETURNING (xmax = 0) AS inserted
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    started = datetime.now(timezone.utc)
    error, inserted, updated = None, 0, 0
    try:
        papers = scrape()
        if not papers:
            raise RuntimeError("the ART listing parsed to 0 papers: a parse failure, not an empty Council")
        print(f"[INFO] {len(papers)} ART paper(s) on the listing")
        for p in papers:
            print(f"   {p['year'] or '????'}  {p['title'][:66]}")
        if args.apply:
            db = SessionLocal()
            try:
                for p in papers:
                    row = db.execute(text(_UPSERT), {
                        "pid": p["publication_id"], "title": p["title"], "summary": p["summary"],
                        "pdf_url": p["pdf_url"], "html_url": p["html_url"], "source": SOURCE,
                    }).scalar()
                    inserted += 1 if row else 0
                    updated += 0 if row else 1
                db.commit()
            finally:
                db.close()
            print(f"[APPLIED] inserted={inserted} updated={updated}")
        else:
            print("[DRY-RUN] re-run with --apply")
    except Exception as exc:  # recorded, then a failing exit
        error = f"{type(exc).__name__}: {exc}"
        print(f"[ERROR] {error}")
    finally:
        if args.apply:
            try:
                from services.sync.freshness import record_run
                db = SessionLocal()
                record_run(db, source_key="council_art", tier="weekly",
                           status="failed" if error else "success",
                           items_added=inserted, error=error, started_at=started,
                           finished_at=datetime.now(timezone.utc))
                db.close()
            except Exception as exc:  # noqa: BLE001
                print(f"[WARN] could not record the run: {type(exc).__name__}: {exc}")
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())
