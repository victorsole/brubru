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
from urllib.parse import quote

import requests

from services.scrapers.economy_common import Item, clean

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
_HEADERS = {"User-Agent": _UA}
_DATE = re.compile(r'(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Z][a-z]{2,8}\s+\d{4})')


def _txt(x: str) -> str:
    return _html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x or ""))).strip()


def _row_url(base: str, href: str, reference: str, title: str) -> str:
    """A per-row URL. Use the row's own link if present; otherwise make the listing
    URL unique with a #fragment so rows don't collide on the UNIQUE(public_url)."""
    if href:
        return href if href.startswith("http") else base + href
    frag = reference or title[:60]
    return f"{base}#{quote(frag, safe='')}"


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
        reference = _txt(cell(ref_field))
        url = _row_url(base, href, reference, title)
        dl = _parse_date(_DATE.search(_txt(cell(deadline_field))).group(1)) if (
            deadline_field and _DATE.search(_txt(cell(deadline_field)))) else None
        st = status or _txt(cell("field-opencall-status"))
        out.append(_build(body_code=body_code, item_type=item_type, title=title, url=url,
                          reference=reference, status=st, deadline=dl, now=now,
                          source_kind=source_kind))
    return out


def parse_positional_table(html: str, base: str, *, body_code: str, item_type: str,
                           source_kind: str, title_col: int, deadline_col: int,
                           ref_col: int | None = None, status: str = "") -> list[Item]:
    """For Views tables with un-named columns (e.g. EMA value-1..value-4):
    parse <td> cells by position (0-indexed)."""
    now = datetime.now(timezone.utc)
    out: list[Item] = []
    body = re.search(r"<tbody>(.*?)</tbody>", html, re.S)
    if not body:
        return out
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", body.group(1), re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) <= max(title_col, ref_col or 0, deadline_col):
            continue
        title = _txt(cells[title_col])
        if not title:
            continue
        am = re.search(r'href="([^"]+)"', cells[title_col])
        href = am.group(1) if am else ""
        reference = _txt(cells[ref_col]) if ref_col is not None else ""
        url = _row_url(base, href, reference, title)
        dm = _DATE.search(_txt(cells[deadline_col]))
        dl = _parse_date(dm.group(1)) if dm else None
        out.append(_build(body_code=body_code, item_type=item_type, title=title, url=url,
                          reference=reference, status=status, deadline=dl, now=now,
                          source_kind=source_kind))
    return out


def _fetch(url: str) -> str:
    return requests.get(url, headers=_HEADERS, timeout=40).text


def _split_calls(items: list[Item]) -> tuple[list[Item], list[Item]]:
    """Split a procurement listing into (tenders, eoi_calls) by reference / title."""
    tenders, calls = [], []
    for it in items:
        ref = (it.guid or "").upper()
        is_eoi = "/CEI" in ref or "EOI" in ref or "expression of interest" in it.title.lower()
        (calls if is_eoi else tenders).append(it)
    return tenders, calls


# --------------------------------------------------------------------------- #
# Cedefop — named Views table (field-ced-*). One page mixes tenders + EOI calls.
# --------------------------------------------------------------------------- #
_CEDEFOP = "https://www.cedefop.europa.eu"


def _cedefop_all() -> list[Item]:
    return parse_views_table(
        _fetch(_CEDEFOP + "/en/about-cedefop/public-procurement"), _CEDEFOP,
        body_code="cedefop", item_type="tender", source_kind="cedefop_procurement",
        ref_field="field-ced-procurement-reference",
        deadline_field="field-ced-closing-date-time", status="")


def ingest_cedefop_tenders(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _split_calls(_cedefop_all())[0]


def ingest_cedefop_calls(*, fetch_bodies: bool = True, **_) -> list[Item]:
    calls = _split_calls(_cedefop_all())[1]
    for it in calls:
        it.item_type = "eoi_call"
    return calls


# --------------------------------------------------------------------------- #
# EMA — positional Views table (value-1=published, value-2=title, value-3=ref,
# value-4=deadline).
# --------------------------------------------------------------------------- #
_EMA = "https://www.ema.europa.eu"


def ingest_ema_tenders(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return parse_positional_table(
        _fetch(_EMA + "/en/about-us/procurement-grants"), _EMA, body_code="ema",
        item_type="tender", source_kind="ema_procurement",
        title_col=1, ref_col=2, deadline_col=3, status="Open")


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


# --- EFSA — positional table (col0=title+link, col1=published, col2=deadline). - #
_EFSA = "https://www.efsa.europa.eu"


def ingest_efsa_tenders(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return parse_positional_table(
        _fetch(_EFSA + "/en/calls/procurement"), _EFSA, body_code="efsa",
        item_type="tender", source_kind="efsa_procurement",
        title_col=0, deadline_col=2, status="Open")
