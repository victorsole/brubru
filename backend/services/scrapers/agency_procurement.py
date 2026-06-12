"""Decentralised EU agency procurement / grants / calls.

Each EU body publishes its own tenders, grants and calls for expression of
interest on its own site, in its own markup, so this module collects per-agency
parsers feeding a shared schema (economy_items, item_type tender|grant|eoi_call).
Common helpers live here; agency-specific extraction lives in small functions.

Schema packed into the 5 datapoints:
  title           = tender/call title
  summary         = "reference · status · deadline"
  body_txt        = title + reference + status + deadline (+ procedure type)
  document_date   = deadline (closing date) where present, else publication
  public_url      = the tender/call page;  guid = reference (fallback URL)
  body_code       = the agency;  item_type = tender | grant | eoi_call
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
    s = (s or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%d %B %Y", "%d %b %Y",
                "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _build(*, body_code: str, item_type: str, title: str, url: str, reference: str = "",
           status: str = "", deadline: datetime | None, now: datetime,
           source_kind: str) -> Item:
    bits = [b for b in [reference, status, deadline.date().isoformat() if deadline else ""] if b]
    lines = [title,
             f"Reference: {reference}" if reference else "",
             f"Status: {status}" if status else "",
             f"Deadline: {deadline.date()}" if deadline else ""]
    lines = [l for l in lines if l]
    return Item(
        body_code=body_code, item_type=item_type, title=clean(title)[:120], public_url=url,
        summary=clean(" · ".join(bits)) or clean(title)[:120],
        body_txt=clean("\n".join(lines)),
        body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
        document_date=deadline, creation_date=now, source_kind=source_kind,
        guid=reference or url)


# --------------------------------------------------------------------------- #
# Drupal "Views table" agencies (one <tr> per item, cells tagged
# views-field-<field>). Confirmed for EFCA; reusable for any EU-theme Views
# table by passing the field-class names.
# --------------------------------------------------------------------------- #
def parse_views_table(html: str, base: str, *, body_code: str, item_type: str,
                      source_kind: str, ref_field: str, title_field: str = "title",
                      deadline_field: str | None = None, status: str = "") -> list[Item]:
    now = datetime.now(timezone.utc)
    out: list[Item] = []
    body = re.search(r"<tbody>(.*?)</tbody>", html, re.S)
    if not body:
        return out
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", body.group(1), re.S):
        def cell(field: str) -> str:
            m = re.search(rf'views-field-{re.escape(field)}[^>]*>(.*?)</td>', row, re.S)
            return m.group(1) if m else ""
        title_cell = cell(title_field)
        am = re.search(r'href="([^"]+)"', title_cell)
        title = _txt(title_cell)
        if not title:
            continue
        href = am.group(1) if am else ""
        url = href if href.startswith("http") else (base + href if href else base)
        reference = _txt(cell(ref_field))
        dl = _parse_date(_DATE.search(_txt(cell(deadline_field))).group(1)) if (
            deadline_field and _DATE.search(_txt(cell(deadline_field)))) else None
        st = status or _txt(cell("field-opencall-status"))
        out.append(_build(body_code=body_code, item_type=item_type, title=title, url=url,
                          reference=reference, status=st, deadline=dl, now=now,
                          source_kind=source_kind))
    return out


def _fetch(url: str) -> str:
    return requests.get(url, headers=_HEADERS, timeout=40).text


# --------------------------------------------------------------------------- #
# EFCA — European Fisheries Control Agency (Drupal Views tables).
# --------------------------------------------------------------------------- #
_EFCA = "https://www.efca.europa.eu"


def ingest_efca_tenders(*, fetch_bodies: bool = True, **_) -> list[Item]:
    items: list[Item] = []
    for path, status in [("/en/content/open-calls-tender", "Open"),
                         ("/en/content/negotiated-procedures", "Negotiated")]:
        items += parse_views_table(_fetch(_EFCA + path), _EFCA, body_code="efca",
                                   item_type="tender", source_kind="efca_procurement",
                                   ref_field="field-number", deadline_field="field-deadline",
                                   status=status)
    # de-dup by guid
    seen, uniq = set(), []
    for it in items:
        if it.guid not in seen:
            seen.add(it.guid); uniq.append(it)
    return uniq


def ingest_efca_calls(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return parse_views_table(_fetch(_EFCA + "/en/content/calls-expression-interest"), _EFCA,
                             body_code="efca", item_type="eoi_call",
                             source_kind="efca_procurement", ref_field="field-number",
                             deadline_field="field-deadline", status="Expression of interest")
