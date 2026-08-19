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

def parse_field_cards(html: str, base: str, *, body_code: str, item_type: str, source_kind: str,
                      title_substr: str, ref_field: str, deadline_field: str,
                      status: str = "") -> list[Item]:
    """Drupal field-card listings (e.g. Eurojust): one card per item, each with a
    title link plus field--name-field-<X> divs for reference and closing date."""
    now = datetime.now(timezone.utc)
    out: list[Item] = []
    title_re = re.compile(r'<a href="([^"]*' + re.escape(title_substr) + r'[^"#?]*)"[^>]*>(.*?)</a>', re.S)
    matches = list(title_re.finditer(html))
    seen = set()
    for i, m in enumerate(matches):
        href, raw = m.group(1), m.group(2)
        title = _txt(raw)
        if not title or len(title) < 8:
            continue
        url = href if href.startswith("http") else base + href
        if url in seen:
            continue
        seen.add(url)
        win = html[m.end(): matches[i + 1].start() if i + 1 < len(matches) else m.end() + 1800]
        rm = re.search(rf'field--name-field-{re.escape(ref_field)}.*?field__item"[^>]*>([^<]+)', win, re.S)
        reference = _txt(rm.group(1)) if rm else ""
        dm = re.search(
            rf'field--name-field-{re.escape(deadline_field)}.*?(\d{{4}}-\d{{2}}-\d{{2}}|\d{{1,2}}[/.]\d{{1,2}}[/.]\d{{4}}|\d{{1,2}}\s+[A-Z][a-z]+\s+\d{{4}})',
            win, re.S)
        dl = _parse_date(dm.group(1)) if dm else None
        out.append(_build(body_code=body_code, item_type=item_type, title=title, url=url,
                          reference=reference, status=status, deadline=dl, now=now,
                          source_kind=source_kind))
    return out


# --- Eurojust — Drupal field-cards --------------------------------------- #
_EUROJUST = "https://www.eurojust.europa.eu"


def ingest_eurojust_tenders(*, fetch_bodies: bool = True, **_) -> list[Item]:
    items = parse_field_cards(_fetch(_EUROJUST + "/about-us/procurement/ongoing-calls-for-tender"),
                              _EUROJUST, body_code="eurojust", item_type="tender",
                              source_kind="eurojust_procurement", title_substr="/procurement/",
                              ref_field="tender-reference", deadline_field="end-date", status="Open")
    low = parse_field_cards(_fetch(_EUROJUST + "/about-us/procurement/low-value-contracts"),
                            _EUROJUST, body_code="eurojust", item_type="tender",
                            source_kind="eurojust_procurement", title_substr="/procurement/",
                            ref_field="tender-reference", deadline_field="end-date",
                            status="Low-value contract")
    seen = {i.public_url for i in items}
    merged = items + [i for i in low if i.public_url not in seen]
    # keep only real tenders (those carrying a tender reference, not nav links)
    return [i for i in merged if i.guid and not i.guid.startswith("http")]

# --- ETF — field-cards with linked short-title + deadline in body --------- #
_ETF = "https://www.etf.europa.eu"


def ingest_etf_tenders(*, fetch_bodies: bool = True, **_) -> list[Item]:
    # deadline_field="deadline" finds the field; the closing date also appears in
    # the card body ("Deadline ... DD/MM/YYYY"), which the window date-search picks up.
    return parse_field_cards(
        _fetch(_ETF + "/en/about/procurement"), _ETF, body_code="etf", item_type="tender",
        source_kind="etf_procurement", title_substr="/en/about/procurement/",
        ref_field="deadline", deadline_field="deadline", status="Open")


# --- EUAA — Drupal Views positional table -------------------------------- #
_EUAA = "https://euaa.europa.eu"


def ingest_euaa_calls(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return parse_positional_table(
        _fetch(_EUAA + "/about-us/procurement"), _EUAA,
        body_code="euaa", item_type="eoi_call",
        source_kind="euaa_procurement",
        title_col=1, ref_col=0, deadline_col=2, status="Open",
    )


# --- EUDA — plain HTML table (no Drupal markers) -------------------------- #
_EUDA = "https://www.euda.europa.eu"


def ingest_euda_tenders(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return parse_positional_table(
        _fetch(_EUDA + "/about/procurement_en"), _EUDA,
        body_code="euda", item_type="tender", source_kind="euda_procurement",
        title_col=1, ref_col=0, deadline_col=3, status="Open",
    )


# --- ENISA — Drupal Views with positional headers + <time datetime> ------- #
_ENISA = "https://www.enisa.europa.eu"


def _parse_enisa_table(html: str, base: str) -> list[Item]:
    """ENISA tbody rows: 5 cells per row. Title cell 0 (with anchor),
    reference cell 1, call-type cell 2, deadline cell 3 (<time datetime>),
    status cell 4."""
    now = datetime.now(timezone.utc)
    out: list[Item] = []
    body = re.search(r"<tbody.*?</tbody>", html, re.S)
    if not body:
        return out
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", body.group(0), re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) < 5:
            continue
        title_html, ref_html, type_html, deadline_html, status_html = cells[:5]
        am = re.search(r'href="([^"]+)"', title_html)
        if not am:
            continue
        title = _txt(title_html)
        if not title:
            continue
        url = am.group(1) if am.group(1).startswith("http") else base + am.group(1)
        reference = _txt(ref_html)
        call_type = _txt(type_html)
        dl = None
        dt_m = re.search(r'datetime="([^"]+)"', deadline_html)
        if dt_m:
            try:
                dl = datetime.fromisoformat(dt_m.group(1).replace("Z", "+00:00"))
            except ValueError:
                dl = None
        if dl is None:
            dm = _DATE.search(_txt(deadline_html))
            dl = _parse_date(dm.group(1)) if dm else None
        status_text = _txt(status_html).upper() or "OPEN"
        is_eoi = ("EXPRESSIONS OF INTEREST" in call_type.upper()
                  or "CEI" in (reference or "").upper())
        out.append(_build(
            body_code="enisa", item_type=("eoi_call" if is_eoi else "tender"),
            title=title, url=url, reference=reference, status=status_text,
            deadline=dl, now=now, source_kind="enisa_procurement",
        ))
    return out


def ingest_enisa_tenders(*, fetch_bodies: bool = True, **_) -> list[Item]:
    items = _parse_enisa_table(_fetch(_ENISA + "/working-with-us/procurement"), _ENISA)
    return [i for i in items if i.item_type == "tender"]


def ingest_enisa_calls(*, fetch_bodies: bool = True, **_) -> list[Item]:
    items = _parse_enisa_table(_fetch(_ENISA + "/working-with-us/procurement"), _ENISA)
    return [i for i in items if i.item_type == "eoi_call"]


# --- ERA — bespoke listing-item cards ------------------------------------- #
_ERA = "https://www.era.europa.eu"


def _parse_era_articles(html: str, base: str) -> list[Item]:
    """ERA <article class="listing-item ..."> cards. Title in a
    <span class="title"> inside <a class="standalone">. Opening/closing date
    is the first <time datetime>. Status badge text-bg-success ("Open").
    The card does not expose a procurement reference, so the URL slug becomes
    the guid (same pattern as the existing ETF parser for low-value cards)."""
    now = datetime.now(timezone.utc)
    out: list[Item] = []
    article_re = re.compile(
        r'<article[^>]*class="[^"]*listing-item[^"]*"[^>]*>(.*?)</article>', re.S)
    for body in article_re.findall(html):
        am = re.search(
            r'<a[^>]+href="(/procurement/[^"]+)"[^>]*>\s*<span class="title">(.*?)</span>',
            body, re.S)
        if not am:
            am = re.search(r'<a[^>]+href="(/procurement/[^"]+)"[^>]*>(.*?)</a>',
                           body, re.S)
        if not am:
            continue
        title = _txt(am.group(2))
        if not title:
            continue
        url = base + am.group(1)
        st_m = re.search(r'badge[^"]*text-bg-success[^"]*"[^>]*>\s*(\w[\w\s-]+?)\s*<',
                         body)
        status = _txt(st_m.group(1)) if st_m else "Open"
        dt_m = re.search(r'<time[^>]+datetime="([^"]+)"', body)
        dl = None
        if dt_m:
            try:
                dl = datetime.fromisoformat(dt_m.group(1).replace("Z", "+00:00"))
            except ValueError:
                dl = None
        reference = am.group(1).rsplit("/", 1)[-1]
        out.append(_build(
            body_code="era", item_type="tender", title=title, url=url,
            reference=reference, status=status, deadline=dl, now=now,
            source_kind="era_procurement",
        ))
    return out


def ingest_era_tenders(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _parse_era_articles(
        _fetch(_ERA + "/agency/procurement_en?f%5B0%5D=era_procurement_status%3Aopen"),
        _ERA,
    )


# --- ECDC — ct-procurement article cards, paginated ?page=N --------------- #
_ECDC = "https://www.ecdc.europa.eu"


def _parse_ecdc_articles(html: str, base: str) -> list[Item]:
    """ECDC <article class="ct-procurement"> cards. Reference in a
    <span class="fw-semibold">Ref.:</span> meta-item. Deadline inside a
    <time datetime="..."> inside its own meta-item div (NOT plain text)."""
    now = datetime.now(timezone.utc)
    out: list[Item] = []
    article_re = re.compile(
        r'<article[^>]*class="[^"]*ct-procurement[^"]*"[^>]*>(.*?)</article>', re.S)
    for body in article_re.findall(html):
        am = re.search(r'<a[^>]+href="([^"]+)"[^>]*hreflang="en"[^>]*>(.*?)</a>',
                       body, re.S)
        if not am:
            continue
        title = _txt(am.group(2))
        if not title:
            continue
        href = am.group(1)
        url = href if href.startswith("http") else base + href
        ref_m = re.search(r'>Ref\.\s*:?\s*</span>\s*([^<]+)', body)
        reference = _txt(ref_m.group(1)) if ref_m else ""
        deadline_block = re.search(r'>Deadline[^<]*</span>.*?</div>', body, re.S)
        dl = None
        status = ""
        if deadline_block:
            block = deadline_block.group(0)
            dt_m = re.search(r'datetime="([^"]+)"', block)
            if dt_m:
                try:
                    dl = datetime.fromisoformat(dt_m.group(1).replace("Z", "+00:00"))
                except ValueError:
                    pass
            st_m = re.search(r'\b(Open|Closed|Awarded)\b', _txt(block))
            status = st_m.group(1) if st_m else ""
        out.append(_build(
            body_code="ecdc", item_type="tender", title=title, url=url,
            reference=reference, status=status, deadline=dl, now=now,
            source_kind="ecdc_procurement",
        ))
    return out


def ingest_ecdc_tenders(*, fetch_bodies: bool = True, max_pages: int = 4, **_) -> list[Item]:
    """ECDC paginates via ?page=N (0-indexed). Crawl up to max_pages."""
    items: list[Item] = []
    seen = set()
    for page in range(max_pages):
        url = _ECDC + "/en/about-ecdc/procurement-and-grants"
        if page:
            url += f"?page={page}"
        for it in _parse_ecdc_articles(_fetch(url), _ECDC):
            if it.guid in seen:
                continue
            seen.add(it.guid)
            items.append(it)
    return items


# --- ECHA — Playwright text snapshot -------------------------------------- #
_ECHA = "https://echa.europa.eu"
_ECHA_PROCUREMENT_URL = _ECHA + "/about-us/business-opportunities"


def _parse_echa_text(text: str) -> list[Item]:
    """ECHA WAF-blocks scripted access; Playwright (text mode) flattens the
    listing table to per-row blocks: <title>\\n(<REF>)\\t<TYPE>\\t<DEADLINE>."""
    now = datetime.now(timezone.utc)
    out: list[Item] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines) - 1:
        ln = lines[i].strip()
        nxt = lines[i + 1].strip()
        if ln and nxt.startswith("(") and ")" in nxt:
            ref_end = nxt.find(")")
            reference = nxt[1:ref_end]
            rest = nxt[ref_end + 1:].lstrip("\t").strip()
            parts = [p.strip() for p in rest.split("\t") if p.strip()]
            if len(parts) >= 2:
                ttype, deadline_text = parts[0], parts[1]
                title = ln
                dm = _DATE.search(deadline_text)
                dl = _parse_date(dm.group(1)) if dm else None
                url = f"{_ECHA_PROCUREMENT_URL}#{reference}"
                is_eoi = "interest" in ttype.lower() or "CEI" in reference.upper()
                out.append(_build(
                    body_code="echa",
                    item_type=("eoi_call" if is_eoi else "tender"),
                    title=title, url=url, reference=reference, status="Open",
                    deadline=dl, now=now, source_kind="echa_procurement",
                ))
                i += 2
                continue
        i += 1
    return out


def _fetch_echa_playwright() -> str:
    from services.scrapers.waf_browser_fetcher import WafBrowserFetcher
    with WafBrowserFetcher() as f:
        return f.fetch(_ECHA_PROCUREMENT_URL, strip_chrome=True).text


def ingest_echa_tenders(*, fetch_bodies: bool = True, **_) -> list[Item]:
    items = _parse_echa_text(_fetch_echa_playwright())
    return [i for i in items if i.item_type == "tender"]


def ingest_echa_calls(*, fetch_bodies: bool = True, **_) -> list[Item]:
    items = _parse_echa_text(_fetch_echa_playwright())
    return [i for i in items if i.item_type == "eoi_call"]


# --- EIGE — defensive empty-listing handler ------------------------------- #
_EIGE = "https://eige.europa.eu"


def ingest_eige_tenders(*, fetch_bodies: bool = True, **_) -> list[Item]:
    """EIGE shows 'There are currently no ongoing procedures' when empty.
    When EIGE publishes calls they appear as a Drupal Views table on this
    page; parse_views_table returns [] cleanly when no <tbody> is present."""
    html = _fetch(_EIGE + "/about/procurement")
    return parse_views_table(
        html, _EIGE, body_code="eige", item_type="tender",
        source_kind="eige_procurement",
        ref_field="reference", deadline_field="deadline", status="Open",
    )


# --- FRA — Playwright (Anubis WAF) + defensive empty handling ------------- #
_FRA = "https://fra.europa.eu"


def _fetch_fra_playwright(path: str) -> str:
    from services.scrapers.waf_browser_fetcher import WafBrowserFetcher
    with WafBrowserFetcher() as f:
        return f.fetch(_FRA + path, strip_chrome=False).html


def ingest_fra_tenders(*, fetch_bodies: bool = True, **_) -> list[Item]:
    """FRA is behind Anubis bot-challenge; Playwright clears it. The Ongoing
    Procedures page returns 'There are no open procedures at the present
    time.' when empty; we return []. When listings are present, parse via
    parse_views_table with FRA's Drupal field names."""
    html = _fetch_fra_playwright("/en/about-fra/procurement/ongoing-procedures")
    if "no open procedures" in html.lower():
        return []
    return parse_views_table(
        html, _FRA, body_code="fra", item_type="tender",
        source_kind="fra_procurement",
        ref_field="reference", deadline_field="closing-date", status="Open",
    )


# --- EEA — F&T-only for open calls; stub returning [] --------------------- #
_EEA = "https://www.eea.europa.eu"


def ingest_eea_tenders(*, fetch_bodies: bool = True, **_) -> list[Item]:
    """EEA publishes its open calls on the EU F&T Portal, not on its own
    site. The on-agency page is informational + past-contracts PDFs only.
    Stub returns [] so cron does not error; EEA opportunities flow through
    the F&T ingest (FtCallForTenders / FtCallForProposals)."""
    return []


# --- EU-OSHA — Drupal Views views-row + per-year archive ------------------ #
_EU_OSHA = "https://osha.europa.eu"


def _parse_eu_osha_views(html: str, base: str, body_code: str, item_type: str,
                        source_kind: str) -> list[Item]:
    """EU-OSHA procurement listing (revamp-row grid, JS-rendered). Each entry has
    an optional publication-date <time datetime> then views-field-title > h2 > a
    linking to a /procurement/call-tender/<slug> (or /call-expression-.../) detail
    page. Match the detail links directly (robust to the grid wrapper) and pair
    each with the nearest preceding <time> as its document date."""
    now = datetime.now(timezone.utc)
    out: list[Item] = []
    seen: set[str] = set()
    pat = re.compile(
        r'views-field-title[^>]*>\s*<h2[^>]*>\s*<a[^>]+href="'
        r'(/en/about-eu-osha/procurement/call[^"]+)"[^>]*>(.*?)</a>', re.S)
    for m in pat.finditer(html):
        href, title = m.group(1), _txt(m.group(2))
        if not title or href in seen:
            continue
        seen.add(href)
        pre = html[max(0, m.start() - 500):m.start()]
        times = re.findall(r'<time[^>]*datetime="([^"]+)"', pre)
        doc_dt = _parse_date(times[-1][:10]) if times else None
        out.append(_build(
            body_code=body_code, item_type=item_type, title=title, url=base + href,
            reference="", status="Open", deadline=doc_dt, now=now,
            source_kind=source_kind,
        ))
    return out


def ingest_eu_osha_tenders(*, fetch_bodies: bool = True, max_pages: int = 4, **_) -> list[Item]:
    """EU-OSHA procurement. The site's WAF fingerprints TLS and drops raw HTTP
    clients (requests/urllib -> RemoteDisconnected), while a real browser and
    curl pass, so fetch via the headless-browser WafBrowserFetcher (same tool
    used for FRA). Two current listings: open calls for tender and calls for
    expression of interest. (The old /calls_archive/<year> tree is gone.)"""
    from services.scrapers.waf_browser_fetcher import WafBrowserFetcher
    items: list[Item] = []
    seen: set[str] = set()
    pages = [
        "/en/about-eu-osha/procurement/calls-tender",
        "/en/about-eu-osha/procurement/calls-expression-interest",
    ]
    with WafBrowserFetcher() as f:
        for path in pages:
            res = f.fetch(_EU_OSHA + path, strip_chrome=False)
            if getattr(res, "error", None) or not getattr(res, "html", None):
                continue
            for it in _parse_eu_osha_views(res.html, _EU_OSHA,
                                           body_code="eu_osha", item_type="tender",
                                           source_kind="eu_osha_procurement"):
                if it.guid in seen:
                    continue
                seen.add(it.guid)
                items.append(it)
    return items


def ingest_eu_osha_calls(*, fetch_bodies: bool = True, **_) -> list[Item]:
    """Calls for expression of interest at /calls-expression-interest; layout
    matches _parse_eu_osha_views. EU-OSHA's WAF drops raw HTTP (_fetch ->
    RemoteDisconnected), so render via WafBrowserFetcher like ingest_eu_osha_tenders.
    Returns [] cleanly when there are no open EOI calls."""
    from services.scrapers.waf_browser_fetcher import WafBrowserFetcher
    with WafBrowserFetcher() as f:
        res = f.fetch(_EU_OSHA + "/en/about-eu-osha/procurement/calls-expression-interest",
                      strip_chrome=False)
    return _parse_eu_osha_views(
        getattr(res, "html", "") or "", _EU_OSHA,
        body_code="eu_osha", item_type="eoi_call",
        source_kind="eu_osha_procurement",
    )


# --- Eurofound — Playwright sub-page crawl -------------------------------- #
_EUROFOUND = "https://www.eurofound.europa.eu"


def _fetch_eurofound_playwright(path: str) -> str:
    from services.scrapers.waf_browser_fetcher import WafBrowserFetcher
    with WafBrowserFetcher() as f:
        return f.fetch(_EUROFOUND + path, strip_chrome=False).html


def ingest_eurofound_tenders(*, fetch_bodies: bool = True, **_) -> list[Item]:
    """Eurofound rate-limits raw HTTP (429); Playwright gets through. The
    parser mirrors the EU-OSHA views-row pattern; if Eurofound's per-tab
    listing markup diverges, this returns [] cleanly and a follow-up pass
    can refine the regex once row examples are captured."""
    # Eurofound consolidated its procurement onto a single /en/about/procurement
    # page (Aug 2026); the old /calls-tenders-140k + /calls-tenders-below-140k
    # sub-pages 404. Returns [] cleanly when the page shows no open procedures.
    items: list[Item] = []
    try:
        html = _fetch_eurofound_playwright("/en/about/procurement")
    except Exception:
        return []
    items += _parse_eu_osha_views(
        html, _EUROFOUND, body_code="eurofound", item_type="tender",
        source_kind="eurofound_procurement",
    )
    return items


def ingest_eurofound_calls(*, fetch_bodies: bool = True, **_) -> list[Item]:
    # Same consolidated /en/about/procurement page as tenders (old
    # /calls-expression-interest sub-page 404s).
    try:
        html = _fetch_eurofound_playwright("/en/about/procurement")
    except Exception:
        return []
    return _parse_eu_osha_views(
        html, _EUROFOUND, body_code="eurofound", item_type="eoi_call",
        source_kind="eurofound_procurement",
    )


# --- EIB — procurement via TED API v3 ------------------------------------ #
# EIB does not publish its corporate procurement on its own site; everything
# goes through TED. Brubru's TED scraper currently ingests only member-state
# notices, so this scraper hits TED's public POST API directly and pulls EIB
# notices into economy_items(body_code='eib', item_type='tender').
_TED_API = "https://api.ted.europa.eu/v3/notices/search"


def _ted_text(field_value):
    """Multilingual TED field → English (or first available) string."""
    if not field_value:
        return ""
    if isinstance(field_value, str):
        return field_value
    if isinstance(field_value, dict):
        for lang in ("eng", "fre", "deu", "spa"):
            v = field_value.get(lang)
            if v:
                return v[0] if isinstance(v, list) else v
        for v in field_value.values():
            if v:
                return v[0] if isinstance(v, list) else v
    if isinstance(field_value, list) and field_value:
        return _ted_text(field_value[0])
    return ""


def _ted_search_eib(limit: int = 200, only_open: bool = True) -> list[dict]:
    """Hit the TED public API v3 for EIB-buyer notices. Open-only by default
    (deadline-receipt-request >= today). Returns the raw JSON notices list."""
    import json as _json
    import urllib.request as _urllib_request
    from urllib.error import HTTPError
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    q_parts = ['buyer-name="European Investment Bank"']
    if only_open:
        q_parts.append(f"deadline-receipt-request>={today}")
    payload = _json.dumps({
        "query": " AND ".join(q_parts),
        "fields": [
            "publication-number", "buyer-name", "notice-title",
            "publication-date", "deadline-receipt-request",
            "procedure-type", "links",
        ],
        "limit": limit,
        "page": 1,
    }).encode("utf-8")
    req = _urllib_request.Request(
        _TED_API, data=payload, method="POST",
        headers={"User-Agent": _UA, "Content-Type": "application/json",
                 "Accept": "application/json"},
    )
    try:
        body = _urllib_request.urlopen(req, timeout=30).read()
        return _json.loads(body).get("notices", [])
    except HTTPError as e:
        return []
    except Exception:
        return []


def _ted_search(query: str, limit: int = 200) -> list[dict]:
    """Generic TED API v3 search. Public POST endpoint, no auth."""
    import json as _json
    import urllib.request as _urllib_request
    from urllib.error import HTTPError
    payload = _json.dumps({
        "query": query,
        "fields": [
            "publication-number", "buyer-name", "notice-title",
            "publication-date", "deadline-receipt-request",
            "procedure-type", "links",
        ],
        "limit": limit,
        "page": 1,
    }).encode("utf-8")
    req = _urllib_request.Request(
        _TED_API, data=payload, method="POST",
        headers={"User-Agent": _UA, "Content-Type": "application/json",
                 "Accept": "application/json"},
    )
    try:
        body = _urllib_request.urlopen(req, timeout=30).read()
        return _json.loads(body).get("notices", [])
    except HTTPError:
        return []
    except Exception:
        return []


def _ted_to_item(n: dict, *, body_code: str, item_type: str, source_kind: str) -> Item | None:
    """Common TED notice → Item conversion. Returns None when essential
    fields are missing."""
    now = datetime.now(timezone.utc)
    pub_num = n.get("publication-number") or ""
    title = _ted_text(n.get("notice-title"))
    if not pub_num or not title:
        return None
    procedure = _ted_text(n.get("procedure-type"))
    dl_raw = n.get("deadline-receipt-request")
    dl_str = ""
    if isinstance(dl_raw, str):
        dl_str = dl_raw
    elif isinstance(dl_raw, dict):
        for v in dl_raw.values():
            if v:
                dl_str = v[0] if isinstance(v, list) else v
                break
    elif isinstance(dl_raw, list) and dl_raw:
        dl_str = dl_raw[0]
    deadline = None
    if dl_str:
        try:
            deadline = datetime.fromisoformat(dl_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            deadline = None
    ted_url = f"https://ted.europa.eu/en/notice/-/detail/{pub_num}"
    return _build(
        body_code=body_code, item_type=item_type, title=title, url=ted_url,
        reference=pub_num, status=procedure or "Open",
        deadline=deadline, now=now, source_kind=source_kind,
    )


def ingest_eib_procurement(*, fetch_bodies: bool = True, **_) -> list[Item]:
    """EIB procurement opportunities pulled from TED. body_code='eib',
    item_type='tender'. We try open-only first; if TED returns 0 (rare),
    fall back to a recent-publications window so the feed is not empty."""
    now = datetime.now(timezone.utc)
    out: list[Item] = []
    notices = _ted_search_eib(limit=200, only_open=True)
    if not notices:
        notices = _ted_search_eib(limit=50, only_open=False)
    for n in notices:
        pub_num = n.get("publication-number") or ""
        title = _ted_text(n.get("notice-title"))
        if not pub_num or not title:
            continue
        buyer = _ted_text(n.get("buyer-name")) or "European Investment Bank"
        procedure = _ted_text(n.get("procedure-type"))
        # Deadline can come back as ISO date or epoch-ish string; try ISO first.
        dl_raw = n.get("deadline-receipt-request")
        dl_str = ""
        if isinstance(dl_raw, str):
            dl_str = dl_raw
        elif isinstance(dl_raw, dict):
            for v in dl_raw.values():
                if v: dl_str = v[0] if isinstance(v, list) else v; break
        elif isinstance(dl_raw, list) and dl_raw:
            dl_str = dl_raw[0]
        deadline = None
        if dl_str:
            try:
                deadline = datetime.fromisoformat(dl_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                deadline = None
        pub_str = ""
        pub_raw = n.get("publication-date")
        if isinstance(pub_raw, str):
            pub_str = pub_raw
        # TED's canonical notice URL
        ted_url = f"https://ted.europa.eu/en/notice/-/detail/{pub_num}"
        reference = pub_num
        out.append(_build(
            body_code="eib", item_type="tender", title=title, url=ted_url,
            reference=reference,
            status=procedure or "Open",
            deadline=deadline, now=now, source_kind="eib_procurement",
        ))
    return out


# --- Move 5 (15 Jun 2026): EU-institution framework contracts via TED ----- #
# Pulls open Framework Contract (FWC) notices from TED API v3 for the major
# EU institutions. FWCs are the parent contracts under which specific re-
# openings are later published (TAS's Lot 1 OCA / Lot 5 / Lot 8 lives here).
# Each notice → economy_items(body_code='<inst>', item_type='framework').

_EU_INSTITUTION_BUYERS = (
    ("commission", "European Commission"),
    ("eib", "European Investment Bank"),
    ("eeas", "European External Action Service"),
    ("parliament", "European Parliament"),
    ("council", "Council of the European Union"),
    ("ecb", "European Central Bank"),
)


def ingest_eu_institution_frameworks(*, fetch_bodies: bool = True, **_) -> list[Item]:
    """One pass per institution. The TED API does not expose an
    is-framework-agreement filter we can rely on, so we use the practical
    heuristic 'notice-title contains framework' + open deadline. This
    matches the Commission's Lot N OCA / EISMEA / DG-INTPA FWCs that
    actually carry 'framework' in the published title."""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    out: list[Item] = []
    for body_code, buyer in _EU_INSTITUTION_BUYERS:
        q = (
            f'buyer-name="{buyer}" '
            f'AND notice-title="framework" '
            f'AND deadline-receipt-request>={today}'
        )
        notices = _ted_search(q, limit=200)
        for n in notices:
            item = _ted_to_item(
                n, body_code=body_code, item_type="framework",
                source_kind="eu_inst_framework",
            )
            if item:
                out.append(item)
    return out
