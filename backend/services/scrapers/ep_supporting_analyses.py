"""European Parliament database — committee supporting analyses (Policy Department
studies). Backs /api/v2/parliament/supporting-analyses.

The Parliament's Policy Departments produce the in-house expertise that committees
commission to support their legislative work: studies, in-depth analyses,
briefings and at-a-glance notes. They are published on the EP Think Tank under the
"Policy Departments" source (contributors=poldep). One row per document.

Source: the Think Tank advanced search renders results server-side and accepts
plain GET requests (no browser needed) with an X-Requested-With header. It caps
the DISPLAYED result set at 500 per query, so the walk is partitioned by year
(every poldep year is well under 500). Pagination is `&page=N` (0-indexed,
10 results per page). Row IS the content (title + type + date + abstract); the
canonical link is the Think Tank document page.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone

import requests

from services.scrapers.economy_common import Item, clean

_BASE = "https://www.europarl.europa.eu/thinktank/en/research/advanced-search"
_DOC = "https://www.europarl.europa.eu/thinktank/en/document/{ref}"
_CONTRIB = "poldep"  # Policy Departments (the committee supporting-analyses producers)
_FIRST_YEAR = 1992   # Think Tank poldep corpus starts 31/08/1992
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")
_HEADERS = {"User-Agent": _UA, "X-Requested-With": "XMLHttpRequest"}

_CARD = re.compile(r'<div class="es_document ', re.S)
_REF = re.compile(r'/thinktank/en/document/([^"?]+)')
_TITLE = re.compile(r'es_document-title.*?<span class="t-item">(.*?)</span>', re.S)
_TYPE = re.compile(r'documenttype[^>]*>(.*?)</span>', re.S)
_DATE = re.compile(r'subtitle-date">(.*?)</span>')
_SUMMARY = re.compile(r'es_document-body.*?<p[^>]*>(.*?)</p>', re.S)
# Committee named in the title, e.g. "Research for EMPL Committee - ..."
_CTTEE = re.compile(r'for (?:the )?([A-Z]{3,5}) Committee')


def _strip(s: str | None) -> str | None:
    return clean(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))) if s else None


def _parse_date(d: str | None) -> datetime | None:
    if not d:
        return None
    try:
        return datetime.strptime(d.strip(), "%d-%m-%Y").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_cards(html: str, now: datetime) -> list[Item]:
    items: list[Item] = []
    for seg in _CARD.split(html)[1:]:
        rm = _REF.search(seg)
        if not rm:
            continue
        ref = rm.group(1)
        title = _strip(_TITLE.search(seg).group(1)) if _TITLE.search(seg) else None
        if not title:
            continue
        dtype = _strip(_TYPE.search(seg).group(1)) if _TYPE.search(seg) else None
        date_s = _DATE.search(seg).group(1).strip() if _DATE.search(seg) else None
        summ = _strip(_SUMMARY.search(seg).group(1)) if _SUMMARY.search(seg) else None
        cm = _CTTEE.search(title)
        cttee = cm.group(1) if cm else None
        url = _DOC.format(ref=ref)
        lines = [title,
                 f"Type: {dtype}" if dtype else "",
                 f"Committee: {cttee}" if cttee else "",
                 f"Date: {date_s}" if date_s else "",
                 f"Reference: {ref}",
                 summ or ""]
        lines = [l for l in lines if l]
        items.append(Item(
            body_code="parliament", item_type="supporting_analysis",
            title=clean(title)[:120], public_url=url,
            summary=clean(" | ".join(x for x in [dtype, cttee, date_s] if x)) or clean(title)[:120],
            body_txt=clean("\n".join(lines)),
            body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
            document_date=_parse_date(date_s), creation_date=now,
            source_kind="ep_thinktank", guid=ref))
    return items


def _year_url(year: int, page: int) -> str:
    return (f"{_BASE}?contributors={_CONTRIB}"
            f"&startDate=01/01/{year}&endDate=31/12/{year}&page={page}")


def walk_year(session: requests.Session, year: int, *, max_pages: int = 60):
    """Yield Items for one year, page by page, stopping when a page has no cards."""
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for page in range(max_pages):
        for attempt in range(3):
            try:
                r = session.get(_year_url(year, page), timeout=40)
                if r.status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(1.5)
        else:
            return
        cards = _parse_cards(r.text, now)
        fresh = [c for c in cards if c.guid not in seen]
        if not fresh:
            return
        for c in fresh:
            seen.add(c.guid)
            yield c
        time.sleep(0.3)  # be gentle on the Think Tank


def ingest_supporting_analyses(*, fetch_bodies: bool = True, first_year: int = _FIRST_YEAR,
                               **_) -> list[Item]:
    s = requests.Session()
    s.headers.update(_HEADERS)
    this_year = datetime.now(timezone.utc).year
    items: list[Item] = []
    seen: set[str] = set()
    for year in range(this_year, first_year - 1, -1):
        for it in walk_year(s, year):
            if it.guid not in seen:
                seen.add(it.guid)
                items.append(it)
    return items
