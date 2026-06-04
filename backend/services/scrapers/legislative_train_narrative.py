"""
Legislative Train narrative enrichment.

The EP Legislative Train file pages carry an editorial "state of play" narrative
(purpose, political background, funding mechanics, EP/Council process, latest
developments) that OEIL does not. This module fetches that narrative, extracts
the procedure reference printed on the page, and stores the narrative on the
matching `legislative_carriages` row (joined by OEIL procedure ref, falling back
to CELEX / COM where present).

Pipeline:
    discover_file_urls()  -> every /file- URL across the theme + spotlight pages
    extract_narrative()   -> {summary, oeil_ref, com_ref, source_url} from one page
    enrich_carriage()     -> UPDATE the carriage that matches the page's procedure
"""

from __future__ import annotations

import html as _html
import re
from typing import Any, Dict, List, Optional

from sqlalchemy import text as sqla_text
from sqlalchemy.orm import Session

from services.scrapers.legislative_train_scraper import LegislativeTrainScraper

# Chrome / boilerplate paragraphs to drop from the narrative (incl. the status
# glossary that the EP appends to every file page).
_CHROME_RE = re.compile(
    r"legislative train schedule|get in touch|glossary|cookie|subscribe|"
    r"discover more|sharing|follow us|©|european parliament$|"
    r"indicates the level of advancement|there are seven statuses|"
    r"^status type:|^style:|^description:",
    re.I,
)
_OEIL_REF_RE = re.compile(r"\b(\d{4}/\d{4}\([A-Z]{3,4}\))")
_COM_REF_RE = re.compile(r"COM\((\d{4})\)\s?(\d+)")
_P_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.S)
_TAG_RE = re.compile(r"<[^>]+>")
# "As of 11/2025" / "last updated on 12 November 2025" style markers.
_ASOF_RE = re.compile(r"as of\s+(\d{1,2}[/.]\d{4}|\w+\s+\d{4})", re.I)

MAX_SUMMARY_CHARS = 6000


def _clean(p: str) -> str:
    text = _html.unescape(_TAG_RE.sub("", p))
    return re.sub(r"\s+", " ", text).replace("\xa0", " ").strip()


def extract_narrative(html: str) -> Optional[Dict[str, Any]]:
    """Pull the substantive narrative + procedure refs from a Train file page."""
    if not html:
        return None
    paras = [_clean(p) for p in _P_RE.findall(html)]
    body = [
        p for p in paras
        if len(p) > 80 and not _CHROME_RE.search(p)
    ]
    if not body:
        return None
    summary = "\n\n".join(body)
    if len(summary) > MAX_SUMMARY_CHARS:
        summary = summary[:MAX_SUMMARY_CHARS].rsplit(" ", 1)[0] + "…"

    oeil_m = _OEIL_REF_RE.search(html)
    com_m = _COM_REF_RE.search(html)
    asof_m = _ASOF_RE.search(html)
    return {
        "summary": summary,
        "oeil_ref": oeil_m.group(1) if oeil_m else None,
        "com_ref": f"COM({com_m.group(1)}) {com_m.group(2)}" if com_m else None,
        "as_of": asof_m.group(1) if asof_m else None,
    }


async def discover_file_urls(scraper: Optional[LegislativeTrainScraper] = None) -> List[str]:
    """Every Legislative Train file URL across the 7 themes + the spotlight pages."""
    s = scraper or LegislativeTrainScraper()
    section_slugs = list(s.theme_slugs.values()) + [
        "spotlight-MFF", "spotlight-JD25",  # known spotlight collections
    ]
    urls: set[str] = set()
    for slug in section_slugs:
        try:
            html = await s._fetch(f"{s.base_url}{slug}")
        except Exception:
            continue
        for href in re.findall(r'href="(/legislative-train/[^"]*/file-[a-z0-9-]+)"', html or ""):
            urls.add(f"https://www.europarl.europa.eu{href}")
    return sorted(urls)


def _priority_train_id(db: Session, url: str, scraper: LegislativeTrainScraper) -> Optional[str]:
    """If the URL is under a priority theme page, return that priority train's id.

    Spotlight collections (/spotlight-MFF/...) are cross-cutting and carry no
    priority, so they don't drive train membership. The rich OEIL carriage is the
    one that should sit on the train (it has OEIL ref, committees, narrative) —
    this links the Legislative Train tab to the same carriage MTF/cards use.
    """
    slug_to_priority = {v: int(k.split("-")[1]) for k, v in scraper.theme_slugs.items()}
    m = re.search(r"/legislative-train/([^/]+)/file-", url)
    if not m:
        return None
    priority = slug_to_priority.get(m.group(1))
    if not priority:
        return None
    row = db.execute(
        sqla_text("SELECT id FROM legislative_trains WHERE priority_number = :p LIMIT 1"),
        {"p": priority},
    ).first()
    return str(row[0]) if row else None


async def enrich_carriage_from_url(
    db: Session, url: str, scraper: Optional[LegislativeTrainScraper] = None,
    apply: bool = True,
) -> Dict[str, Any]:
    """Fetch one Train file page; store its narrative AND place the rich OEIL
    carriage on its priority train (joined by the OEIL ref the page prints).

    This unifies the two carriage populations: the Legislative Train tab now
    points at the same rich carriage MTF/cards use, so its modal is full (not the
    thin theme-slug stub) and carries the narrative.
    """
    s = scraper or LegislativeTrainScraper()
    html = await s._fetch(url)
    data = extract_narrative(html or "")
    if not data or not data.get("summary"):
        return {"url": url, "status": "no_narrative"}
    oeil_ref = data.get("oeil_ref")
    if not oeil_ref:
        return {"url": url, "status": "no_oeil_ref"}

    row = db.execute(
        sqla_text("SELECT id FROM legislative_carriages WHERE oeil_procedure_ref = :r LIMIT 1"),
        {"r": oeil_ref},
    ).first()
    if not row:
        return {"url": url, "oeil_ref": oeil_ref, "status": "no_carriage"}

    train_id = _priority_train_id(db, url, s)
    if apply:
        # Narrative on every matched file; train membership only for priority-theme
        # files (COALESCE keeps any existing train_id when this URL is a spotlight).
        db.execute(
            sqla_text(
                """
                UPDATE legislative_carriages
                   SET legislative_train_summary = :sm,
                       legislative_train_url = :u,
                       legislative_train_updated_at = NOW(),
                       train_id = COALESCE(:tid, train_id)
                 WHERE oeil_procedure_ref = :r
                """
            ),
            {"sm": data["summary"], "u": url, "r": oeil_ref, "tid": train_id},
        )
        db.commit()
    return {
        "url": url, "oeil_ref": oeil_ref, "status": "enriched",
        "chars": len(data["summary"]), "train_id": train_id,
    }
