"""Decentralised EU agency public consultations.

EU agencies are not on the Commission's "Have Your Say" platform — they run their
own public consultations on their own sites, in their own markup. This module
collects per-agency parsers feeding a shared schema (economy_items, item_type
'consultation'). The central EC Have Your Say consultations stay at
/api/v2/commission/consultations and are UNION-ed into /consultations/all.

Schema packed into the 5 datapoints:
  title          = consultation / draft-document title
  summary        = "status · closing date · topic"
  body_txt       = title + status + start date + closing date
  document_date  = closing date (deadline) where present, else start/publication
  public_url     = the consultation page;  guid = reference / URL
  body_code      = the agency;  item_type = consultation
"""
from __future__ import annotations

import html as _html
import re
from datetime import datetime, timezone

import requests

from services.scrapers.economy_common import Item, clean

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
_HEADERS = {"User-Agent": _UA}
_DATE = re.compile(r'(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Z][a-z]{2,8}\s+\d{4})')


def _txt(x: str) -> str:
    return _html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x or ""))).strip()


def _parse_date(s: str) -> datetime | None:
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%d %B %Y", "%d %b %Y", "%d/%m/%y"):
        try:
            return datetime.strptime((s or "").strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _build(*, body_code: str, title: str, url: str, status: str = "", topic: str = "",
           deadline: datetime | None, start: datetime | None, now: datetime,
           source_kind: str) -> Item:
    bits = [b for b in [status, deadline.date().isoformat() if deadline else "", topic] if b]
    lines = [title,
             f"Status: {status}" if status else "",
             f"Start date: {start.date()}" if start else "",
             f"Closing date: {deadline.date()}" if deadline else "",
             f"Topic: {topic}" if topic else ""]
    lines = [l for l in lines if l]
    return Item(
        body_code=body_code, item_type="consultation", title=clean(title)[:120], public_url=url,
        summary=clean(" · ".join(bits)) or clean(title)[:120],
        body_txt=clean("\n".join(lines)),
        body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
        document_date=deadline or start, creation_date=now, source_kind=source_kind, guid=url)


def _fetch(url: str) -> str:
    return requests.get(url, headers=_HEADERS, timeout=40).text


# --------------------------------------------------------------------------- #
# EMA — open consultations are draft documents (herbal monographs, scientific
# guidelines, concept papers) rendered as file cards (file-title + PDF link).
# --------------------------------------------------------------------------- #
_EMA = "https://www.ema.europa.eu"


def ingest_ema_consultations(*, fetch_bodies: bool = True, **_) -> list[Item]:
    html = _fetch(_EMA + "/en/news-events/open-consultations")
    now = datetime.now(timezone.utc)
    out: dict[str, Item] = {}
    for card in re.split(r"views-field-rendered-entity", html)[1:]:
        tm = re.search(r"file-title[^>]*>(.*?)</p>", card, re.S)
        title = _txt(tm.group(1)) if tm else ""
        lm = re.search(r'href="(/[^"]+\.pdf|/en/documents/[^"]+)"', card)
        if not title or not lm:
            continue
        href = lm.group(1)
        url = href if href.startswith("http") else _EMA + href
        if url in out:
            continue
        dm = _DATE.search(_txt(card))
        out[url] = _build(body_code="ema", title=title, url=url, status="Open",
                          deadline=None, start=_parse_date(dm.group(1)) if dm else None,
                          now=now, source_kind="ema_consultations")
    return list(out.values())
