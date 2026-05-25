"""
LEGISSUM scraper — harvests the "Summaries of EU legislation" catalogue.

LEGISSUM is not exposed in the Cellar SPARQL graph, so we crawl the WAF-walled
EUR-Lex summaries tree with the Playwright fetcher:

    browse/summaries.html            -> ~32 subject chapters
    summary/chapter/{NN}.html        -> N summary slugs per chapter
    EN/legal-content/summary/{slug}.html -> one summary (title, CELEX, text)

The catalogue crawl (chapters -> slugs) is cheap (~32 page renders). Full text
+ precise titles + CELEX are fetched per summary (slow; opt-in via fetch_text).
Titles default to a slug-derived form until the detail page is fetched.

Public surface:
    get_chapters() -> [(code, title, url)]
    get_chapter_slugs(chapter_url) -> [slug, ...]
    summary_url(slug) -> str
    fetch_summary_detail(slug) -> {title, celex, text, html}
    sync_legissum(db, *, chapters_limit=None, fetch_text=False, sleep_s=0.5) -> dict
"""

from __future__ import annotations

import logging
import re
import time
from typing import List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.scrapers.waf_browser_fetcher import fetch_one

logger = logging.getLogger(__name__)

BASE = "https://eur-lex.europa.eu"
BROWSE_URL = f"{BASE}/browse/summaries.html"


def _slug_to_title(slug: str) -> str:
    t = slug.replace("-", " ").strip()
    return (t[:1].upper() + t[1:]) if t else slug


def summary_url(slug: str) -> str:
    return f"{BASE}/EN/legal-content/summary/{slug}.html"


def get_chapters() -> List[Tuple[str, str, str]]:
    """Return [(chapter_code, chapter_title, chapter_url)] from the browse page."""
    r = fetch_one(BROWSE_URL)
    if not r.ok:
        logger.warning("[legissum] browse fetch failed: %s", r.error)
        return []
    html = r.html or ""
    out: dict[str, Tuple[str, str]] = {}
    for href, txt in re.findall(
        r'<a[^>]*href="([^"]*summary/chapter/\d+\.html)"[^>]*>(.*?)</a>', html, re.DOTALL | re.IGNORECASE
    ):
        m = re.search(r"chapter/(\d+)\.html", href)
        if not m:
            continue
        code = m.group(1)
        title = re.sub(r"<[^>]+>", "", txt).strip()
        if code not in out and title:
            out[code] = (title, f"{BASE}/summary/chapter/{code}.html")
    return [(code, t, u) for code, (t, u) in sorted(out.items())]


def get_chapter_slugs(chapter_url: str) -> List[str]:
    """Distinct summary slugs linked from one chapter page."""
    r = fetch_one(chapter_url)
    if not r.ok:
        logger.warning("[legissum] chapter fetch failed (%s): %s", chapter_url, r.error)
        return []
    return sorted(set(re.findall(r"/legal-content/summary/([a-z0-9-]+)\.html", r.html or "", re.IGNORECASE)))


def fetch_summary_detail(slug: str) -> dict:
    """Fetch one summary page: precise title, summarised CELEX, body text + html."""
    r = fetch_one(summary_url(slug))
    # EUR-Lex page titles end with " | EUR-Lex" (or " - EUR-Lex").
    title = re.sub(r"\s*[|–-]\s*EUR-Lex\s*$", "", (r.title or "")).strip() or _slug_to_title(slug)
    celex = None
    m = re.search(r"uri=CELEX:([0-9][A-Z0-9()]+)", r.html or "")
    if m:
        celex = m.group(1)
    return {"title": title, "celex": celex, "text": (r.text or None), "html": (r.html or None)}


def _upsert(
    db: Session,
    *,
    slug: str,
    title: str,
    chapter_code: str,
    chapter_title: str,
    url: str,
    celex: Optional[str] = None,
    summary_text: Optional[str] = None,
    summary_html: Optional[str] = None,
    text_fetched: bool = False,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO public.legissum_summaries
                (slug, title, chapter_code, chapter_title, url, celex,
                 summary_text, summary_html, text_fetched_at, updated_at)
            VALUES
                (:slug, :title, :cc, :ct, :url, :celex, :stext, :shtml,
                 CASE WHEN :tf THEN NOW() ELSE NULL END, NOW())
            ON CONFLICT (slug) DO UPDATE SET
                title = EXCLUDED.title,
                chapter_code = EXCLUDED.chapter_code,
                chapter_title = EXCLUDED.chapter_title,
                url = EXCLUDED.url,
                celex = COALESCE(EXCLUDED.celex, public.legissum_summaries.celex),
                summary_text = COALESCE(EXCLUDED.summary_text, public.legissum_summaries.summary_text),
                summary_html = COALESCE(EXCLUDED.summary_html, public.legissum_summaries.summary_html),
                text_fetched_at = CASE WHEN :tf THEN NOW() ELSE public.legissum_summaries.text_fetched_at END,
                updated_at = NOW()
            """
        ),
        {
            "slug": slug, "title": title, "cc": chapter_code, "ct": chapter_title,
            "url": url, "celex": celex, "stext": summary_text, "shtml": summary_html, "tf": text_fetched,
        },
    )


def enrich_pending(db: Session, *, limit: Optional[int] = None, sleep_s: float = 0.5) -> dict:
    """Resumable enrichment: fetch each summary page for rows that have no body
    yet (text_fetched_at IS NULL) and fill the real title + CELEX + body. Re-runs
    pick up where they left off, so a long crawl can be chunked or restarted.
    Failed fetches stay unmarked and are retried on the next run."""
    q = "SELECT slug FROM public.legissum_summaries WHERE text_fetched_at IS NULL ORDER BY chapter_code, slug"
    if limit:
        q += f" LIMIT {int(limit)}"
    slugs = [r[0] for r in db.execute(text(q)).all()]
    enriched = 0
    for slug in slugs:
        try:
            detail = fetch_summary_detail(slug)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[legissum] enrich fetch failed for %s: %s", slug, exc)
            time.sleep(sleep_s)
            continue
        if detail and detail.get("text"):
            db.execute(
                text(
                    "UPDATE public.legissum_summaries SET title = :t, "
                    "celex = COALESCE(:c, celex), summary_text = :st, summary_html = :sh, "
                    "text_fetched_at = NOW(), updated_at = NOW() WHERE slug = :s"
                ),
                {"t": detail["title"], "c": detail.get("celex"),
                 "st": detail.get("text"), "sh": detail.get("html"), "s": slug},
            )
            db.commit()
            enriched += 1
            if enriched % 25 == 0:
                logger.info("[legissum] enriched %d/%d", enriched, len(slugs))
        time.sleep(sleep_s)
    return {"candidates": len(slugs), "enriched": enriched}


def sync_legissum(
    db: Session,
    *,
    chapters_limit: Optional[int] = None,
    fetch_text: bool = False,
    sleep_s: float = 0.5,
) -> dict:
    """Crawl chapters -> slugs and upsert the catalogue. With fetch_text=True
    also fetch each summary's title/CELEX/body (slow). Returns counts."""
    chapters = get_chapters()
    if chapters_limit:
        chapters = chapters[:chapters_limit]
    n_chapters = 0
    n_summaries = 0
    n_text = 0
    for code, ctitle, curl in chapters:
        slugs = get_chapter_slugs(curl)
        n_chapters += 1
        for slug in slugs:
            detail = None
            if fetch_text:
                try:
                    detail = fetch_summary_detail(slug)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("[legissum] detail fetch failed for %s: %s", slug, exc)
                    detail = None
                time.sleep(sleep_s)
            _upsert(
                db,
                slug=slug,
                title=(detail["title"] if detail else _slug_to_title(slug)),
                chapter_code=code,
                chapter_title=ctitle,
                url=summary_url(slug),
                celex=(detail.get("celex") if detail else None),
                summary_text=(detail.get("text") if detail else None),
                summary_html=(detail.get("html") if detail else None),
                text_fetched=bool(detail),
            )
            n_summaries += 1
            if detail:
                n_text += 1
        db.commit()
        logger.info("[legissum] chapter %s (%s): %d summaries", code, ctitle, len(slugs))
    return {"chapters": n_chapters, "summaries": n_summaries, "with_text": n_text}
