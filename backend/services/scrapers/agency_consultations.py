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
       "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")
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


# --------------------------------------------------------------------------- #
# BEREC — clean anchor-title listing (reuse the generic walker).
# --------------------------------------------------------------------------- #
def ingest_berec_consultations(*, fetch_bodies: bool = True, **_) -> list[Item]:
    from services.scrapers.eu_agency_listing import walk
    return walk("https://www.berec.europa.eu", "/en/public-consultations-calls-for-inputs",
                "berec", "consultation", "/en/public-consultations-calls-for-inputs/",
                "berec_consultations")


def ingest_eiopa_consultations(*, fetch_bodies: bool = True, **_) -> list[Item]:
    from services.scrapers.eu_agency_listing import walk
    return walk("https://www.eiopa.europa.eu", "/browse/consultations-and-surveys_en",
                "eiopa", "consultation", "/consultation", "eiopa_consultations")


# --------------------------------------------------------------------------- #
# AMLA — clean anchor-title listing (reuse the generic walker).
# --------------------------------------------------------------------------- #
def ingest_amla_consultations(*, fetch_bodies: bool = True, **_) -> list[Item]:
    from services.scrapers.eu_agency_listing import walk
    return walk("https://www.amla.europa.eu", "/policy/public-consultations_en",
                "amla", "consultation", "/policy/public-consultations/", "amla_consultations")


# --------------------------------------------------------------------------- #
# ECHA — the current-consultations overview groups open consultations by TYPE
# (Testing proposals, CLH proposals, Restriction, Applications for authorisation,
# Calls for comments & evidence, ...), each with a count, start + closing date and
# a link to that type's full sub-list. One row per consultation type.
# --------------------------------------------------------------------------- #
_ECHA = "https://echa.europa.eu"
_ECHA_CAT = __import__("re").compile(
    r'<dt>\s*(.*?)</dt>\s*<dd>\s*<a href="([^"]+)">([^<]*)</a>(.*?)</dd>', __import__("re").S)


def ingest_echa_consultations(*, fetch_bodies: bool = True, **_) -> list[Item]:
    import re as _re
    # ECHA sits behind a WAF that 403s raw HTTP (Aug 2026): _fetch returns a stub.
    # The dt/dd consultation list only renders in a real browser, so fetch via the
    # headless-Chromium WafBrowserFetcher (Playwright). The _ECHA_CAT structure is
    # unchanged.
    from services.scrapers.waf_browser_fetcher import WafBrowserFetcher
    with WafBrowserFetcher() as _f:
        _res = _f.fetch(_ECHA + "/consultations/current", strip_chrome=False)
    html = getattr(_res, "html", "") or ""
    now = datetime.now(timezone.utc)
    out: dict[str, Item] = {}
    for typ, href, count, rest in _ECHA_CAT.findall(html):
        title = _txt(typ)
        if not title:
            continue
        url = href if href.startswith("http") else _ECHA + href
        if url in out:
            continue
        n = _txt(count)
        dates = _re.findall(r"(\d{2}/\d{2}/\d{4})", rest)
        start = _parse_date(dates[0]) if dates else None
        deadline = _parse_date(dates[-1]) if len(dates) > 1 else None
        out[url] = _build(body_code="echa", title=f"{title} consultations", url=url,
                          status="Open", topic=n, deadline=deadline, start=start, now=now,
                          source_kind="echa_consultations")
    return list(out.values())


# --------------------------------------------------------------------------- #
# ACER — the public-consultations *calendar* lists every consultation (current +
# archive) as a document-link card: <a href="/public-consultation/...">title</a>
# followed by an "Opening/Closing: N days" relative-timing line.
# --------------------------------------------------------------------------- #
_ACER = "https://www.acer.europa.eu"
_ACER_ROW = re.compile(
    r'<div class="document-link">\s*<a[^>]*href="(/public-consultation/[^"#?]+)"[^>]*>(.*?)</a>', re.S)


def ingest_acer_consultations(*, fetch_bodies: bool = True, **_) -> list[Item]:
    html = _fetch(_ACER + "/documents/public-consultations/calendar")
    now = datetime.now(timezone.utc)
    out: dict[str, Item] = {}
    for m in _ACER_ROW.finditer(html):
        href, raw = m.group(1), m.group(2)
        title = _txt(raw)
        url = href if href.startswith("http") else _ACER + href
        if url in out or len(title) < 8:
            continue
        sm = re.search(r'(Opening|Closing|Closed)[^<]{0,30}', html[m.end():m.end() + 220])
        status = _txt(sm.group(0)) if sm else "Open"
        out[url] = _build(body_code="acer", title=title, url=url, status=status,
                          deadline=None, start=None, now=now, source_kind="acer_consultations")
    return list(out.values())


# --------------------------------------------------------------------------- #
# SRB — the "consultations and requests to industry" page mixes navigation with
# real consultation entries (anchor title contains "consultation"). Keep the
# substantive ones, drop the section-nav repeats.
# --------------------------------------------------------------------------- #
_SRB = "https://www.srb.europa.eu"
_SRB_NAV = {"engagement and consultations", "public consultations",
            "upcoming consultations and requests to industry",
            "consultations and requests to industry"}


def ingest_srb_consultations(*, fetch_bodies: bool = True, **_) -> list[Item]:
    html = _fetch(_SRB + "/en/content/consultations-and-requests-industry")
    now = datetime.now(timezone.utc)
    out: dict[str, Item] = {}
    for href, raw in re.findall(r'<a[^>]*href="([^"#?]+)"[^>]*>(.*?)</a>', html, re.S):
        title = _txt(raw)
        low = title.lower()
        if "consultation" not in low or len(title) < 18 or low in _SRB_NAV:
            continue
        url = href if href.startswith("http") else _SRB + href
        if url in out:
            continue
        out[url] = _build(body_code="srb", title=title, url=url, status="",
                          deadline=None, start=None, now=now, source_kind="srb_consultations")
    return list(out.values())


# --------------------------------------------------------------------------- #
# ECB Banking Supervision — the index page shows the ongoing consultation(s),
# each a section heading followed by a "Consultation period: X to Y" info box.
# --------------------------------------------------------------------------- #
_ECB_SSM = "https://www.bankingsupervision.europa.eu"


def ingest_ecb_ssm_consultations(*, fetch_bodies: bool = True, **_) -> list[Item]:
    url_idx = _ECB_SSM + "/framework/legal-framework/public-consultations/html/index.en.html"
    html = _fetch(url_idx)
    now = datetime.now(timezone.utc)
    out: dict[str, Item] = {}
    for pm in re.finditer(r"Consultation period:\s*([^<]+)", html):
        before = html[max(0, pm.start() - 1800):pm.start()]
        heads = re.findall(r"<h[23][^>]*>(.*?)</h[23]>", before, re.S)
        heads = [_txt(h) for h in heads if len(_txt(h)) > 12]
        title = heads[-1] if heads else "ECB Banking Supervision consultation"
        period = _txt(pm.group(1))
        key = title + period
        if key in out:
            continue
        out[key] = _build(body_code="ecb_ssm", title=title, url=url_idx, status=f"Open · {period}",
                          deadline=None, start=None, now=now, source_kind="ecbssm_consult")
    return list(out.values())


# --------------------------------------------------------------------------- #
# EASA + ERA — JS-rendered document-library / listing SPAs. The consultation
# items only appear after the page hydrates, so reuse the Playwright walker
# (eu_agency_listing.ingest_browser). One thin wrapper each.
# --------------------------------------------------------------------------- #
_EASA_NAV = {"product certification consultations and publications",
             "design organisation consultations", "public consultations",
             "market consultations", "focused consultations"}


def ingest_easa_consultations(*, fetch_bodies: bool = True, **_) -> list[Item]:
    from services.scrapers.eu_agency_listing import ingest_browser
    base = "https://www.easa.europa.eu"
    items: dict[str, Item] = {}
    for path in ("/en/document-library/product-certification-consultations",
                 "/en/document-library/design-organisation-consultations"):
        for it in ingest_browser(base, path, "easa", "consultation", path + "/",
                                 "easa_consults", min_title=20, max_pages=8):
            if it.title.lower().strip() in _EASA_NAV:
                continue
            items[it.public_url] = it
    return list(items.values())


def ingest_era_consultations(*, fetch_bodies: bool = True, **_) -> list[Item]:
    from services.scrapers.eu_agency_listing import ingest_browser
    items: dict[str, Item] = {}
    for it in ingest_browser("https://www.era.europa.eu",
                             "/library/documents-regulations/consultations_en",
                             "era", "consultation", "/consultation",
                             "era_consults", min_title=20, max_pages=10):
        items[it.public_url] = it
    return list(items.values())

