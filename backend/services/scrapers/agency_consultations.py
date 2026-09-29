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


# The three lines below are the ONE format in which a consultation's status and its
# two dates travel from here to public_consultations (scripts/sync_agency_consultations
# reads them back with `parse_body_facts`). economy_items has no column for a status or
# an opening date, so they ride in body_txt; keep writer and reader on these constants.
_L_STATUS, _L_START, _L_CLOSE = "Status: ", "Start date: ", "Closing date: "


def parse_body_facts(body_txt: str) -> dict:
    """The status / start / closing date that `_build` wrote, read back.

    Anything absent comes back None: a consultation whose deadline we could not read
    stores no deadline rather than borrowing another field's date.
    """
    out = {"status": None, "start": None, "end": None}
    for line in (body_txt or "").splitlines():
        line = line.strip()
        for label, key in ((_L_STATUS, "status"), (_L_START, "start"), (_L_CLOSE, "end")):
            if line.startswith(label):
                out[key] = line[len(label):].strip() or None
    return out


def _build(*, body_code: str, title: str, url: str, status: str = "", topic: str = "",
           deadline: datetime | None, start: datetime | None, now: datetime,
           source_kind: str, strict_deadline: bool = False) -> Item:
    bits = [b for b in [status, deadline.date().isoformat() if deadline else "", topic] if b]
    lines = [title,
             f"{_L_STATUS}{status}" if status else "",
             f"{_L_START}{start.date()}" if start else "",
             f"{_L_CLOSE}{deadline.date()}" if deadline else "",
             f"Topic: {topic}" if topic else ""]
    lines = [l for l in lines if l]
    return Item(
        body_code=body_code, item_type="consultation", title=clean(title)[:120], public_url=url,
        summary=clean(" · ".join(bits)) or clean(title)[:120],
        body_txt=clean("\n".join(lines)),
        body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
        # document_date is contracted as the CLOSING date. Falling back to the start
        # date puts an opening date in a deadline field, so a caller filtering by
        # deadline reads a date that is not one. strict_deadline keeps it NULL instead.
        document_date=deadline if strict_deadline else (deadline or start),
        creation_date=now, source_kind=source_kind, guid=url)


def _fetch(url: str) -> str:
    return requests.get(url, headers=_HEADERS, timeout=40).text



# --------------------------------------------------------------------------- #
# ECL consultation listings (AMLA, EIOPA, BEREC).
#
# These three used the generic listing walker (services/scrapers/eu_agency_listing),
# which takes the FIRST date in a 600-character window ENDING at the link. On an ECL
# consultation listing every card prints its own "Opening date" and "Deadline", so
# that look-back window reaches into the PRECEDING card and reads ITS deadline.
# AMLA's "draft RTS on the inherent and residual risk profile" was stored closing
# 6 October 2026, the deadline of the card above it; its own deadline was
# 27 September 2026 and its own status Closed. The mirror derives status from that
# date, so the consultation was served as open more than a week after it shut.
#
# The markup is regular, so parse the CARD, never a character window: one
# <article class="ecl-content-item"> per consultation, carrying its own status label,
# its title link, and a definition list of Opening date / Deadline.
# --------------------------------------------------------------------------- #
_ECL_ARTICLE = re.compile(r'<article\b[^>]*\bclass="[^"]*ecl-content-item\b[^"]*"[^>]*>.*?</article>', re.S)
_ECL_STATUS = re.compile(r'ecl-label[^>]*>\s*Status:\s*([A-Za-z][A-Za-z ]*?)\s*<', re.S)
_ECL_TITLE = re.compile(r'ecl-content-block__title.*?<a\s[^>]*href="([^"#?]+)"[^>]*>(.*?)</a>', re.S)


def _ecl_term_date(card: str, term: str) -> datetime | None:
    """The <time> under this card's own <dt>, or None. Never a date from elsewhere."""
    m = re.search(r'<dt[^>]*>\s*' + re.escape(term) + r'\s*</dt>\s*<dd[^>]*>.*?<time[^>]*datetime="'
                  r'(\d{4}-\d{2}-\d{2})', card, re.S)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _ecl_consultations(base: str, path: str, body_code: str, source_kind: str,
                       link_substr: str, max_pages: int = 40) -> list[Item]:
    now = datetime.now(timezone.utc)
    out: dict[str, Item] = {}
    for page in range(max_pages):
        url = f"{base}{path}" + (f"?page={page}" if page else "")
        try:
            html = _fetch(url)
        except Exception:
            break
        new = 0
        for card in _ECL_ARTICLE.findall(html):
            t = _ECL_TITLE.search(card)
            if not t:
                continue
            href, title = t.group(1), _txt(t.group(2))
            if len(title) < 12 or link_substr not in href:
                continue
            full = href if href.startswith("http") else base + href
            if full in out:
                continue
            st = _ECL_STATUS.search(card)
            out[full] = _build(
                body_code=body_code, title=title, url=full,
                status=_txt(st.group(1)) if st else "",
                start=_ecl_term_date(card, "Opening date"),
                deadline=_ecl_term_date(card, "Deadline"),
                now=now, source_kind=source_kind, strict_deadline=True)
            new += 1
        if not new:
            break
    return list(out.values())

# --------------------------------------------------------------------------- #
# EBA (28 Sep 2026) -- the consultations listing is plain server-rendered HTML
# (HTTP 200, no wall), one <article class="teaser-event-calendar--consultation">
# per consultation: start and end day/month, a year line ("2026" or
# "2026 - 2027"), the title and the EBA/CP reference. Before this, EBA
# consultations reached economy_items only as a press release and a PDF, so the
# consultations hub never listed a single EBA consultation (found when
# EBA/CP/2026/19 on joint decisions, opened 25 Sep 2026, was missing).
_EBA = "https://www.eba.europa.eu"
_EBA_ROW = re.compile(r'<article class="teaser-event-calendar teaser-event-calendar--consultation".*?</article>', re.S)
_EBA_DM = re.compile(r'calendar-day">\s*(\d{1,2})\s*<.*?calendar-month">\s*([A-Z][a-z]{2})\s*<', re.S)
_EBA_YEAR = re.compile(r'calendar-year"[^>]*>\s*(\d{4})(?:\s*-\s*(\d{4}))?', re.S)
_EBA_TITLE = re.compile(r'<h3[^>]*>\s*<a href="([^"]+)"[^>]*>(.*?)</a>\s*(?:<small>(.*?)</small>)?', re.S)


def _eba_row(block: str, now: datetime) -> Item | None:
    t = _EBA_TITLE.search(block)
    if not t:
        return None
    href, title, ref = t.group(1), _txt(t.group(2)), _txt(t.group(3) or "").strip("()")
    dm = _EBA_DM.findall(block)
    y = _EBA_YEAR.search(block)
    start = deadline = None
    if y and dm:
        y1 = int(y.group(1)); y2 = int(y.group(2) or y1)
        start = _parse_date(f"{dm[0][0]} {dm[0][1]} {y1}")
        if len(dm) > 1:
            deadline = _parse_date(f"{dm[1][0]} {dm[1][1]} {y2}")
    status = ("Open" if deadline and deadline.date() >= now.date() else "Closed") if deadline else ""
    url = href if href.startswith("http") else _EBA + href
    return _build(body_code="eba", title=title, url=url, status=status, topic=ref,
                  deadline=deadline, start=start, now=now, source_kind="eba_consultations")


def ingest_eba_consultations(*, fetch_bodies: bool = True, pages: int = 3, **_) -> list[Item]:
    now = datetime.now(timezone.utc)
    out: dict[str, Item] = {}
    for page in range(pages):
        html = _fetch(f"{_EBA}/publications-and-media/consultations" + (f"?page={page}" if page else ""))
        blocks = _EBA_ROW.findall(html)
        if not blocks:
            break
        for b in blocks:
            it = _eba_row(b, now)
            if it and it.public_url not in out:
                out[it.public_url] = it
    if not out:
        # A listing that parses to nothing is a changed page or a wall, never
        # "EBA has no consultations": fail loudly so the run is not recorded green.
        raise RuntimeError("EBA consultations listing parsed to 0 rows")
    return list(out.values())


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
# BEREC does NOT use the ECL card markup: each consultation is a plain <article>
# whose CLASS carries the state ("closed-consultation-content" / "open-...") and whose
# body prints "Deadline to submit contributions: <date>". There is no labelled opening
# date, so none is stored -- an unlabelled date on the card is not evidence of one.
_BEREC_ART = re.compile(r'<article\b[^>]*>.*?</article>', re.S)
_BEREC_CLASS = re.compile(r'<article\b[^>]*\bclass="([^"]*)"')
_BEREC_HREF = re.compile(r'href="(/en/public-consultations-calls-for-inputs/[^"#?]+)"')
_BEREC_DEADLINE = re.compile(r"Deadline to submit contributions:\s*(\d{1,2}\s+[A-Z][a-z]+\s+\d{4})")


def ingest_berec_consultations(*, fetch_bodies: bool = True, **_) -> list[Item]:
    base = "https://www.berec.europa.eu"
    now = datetime.now(timezone.utc)
    out: dict[str, Item] = {}
    try:
        html = _fetch(base + "/en/public-consultations-calls-for-inputs")
    except Exception:
        return []
    for card in _BEREC_ART.findall(html):
        h = _BEREC_HREF.search(card)
        if not h:
            continue
        url = base + h.group(1)
        if url in out:
            continue
        text = _txt(card)
        title = text.split(" 0")[0].strip() if text else ""
        heading = re.search(r'<h[1-4][^>]*>(.*?)</h[1-4]>', card, re.S)
        if heading:
            title = _txt(heading.group(1)) or title
        if len(title) < 12:
            continue
        cls = (_BEREC_CLASS.search(card).group(1) if _BEREC_CLASS.search(card) else "").lower()
        status = "Closed" if "closed-consultation" in cls else ("Open" if "open-consultation" in cls else "")
        d = _BEREC_DEADLINE.search(text)
        out[url] = _build(body_code="berec", title=title, url=url, status=status,
                          start=None, deadline=_parse_date(d.group(1)) if d else None,
                          now=now, source_kind="berec_consultations", strict_deadline=True)
    return list(out.values())


def ingest_eiopa_consultations(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _ecl_consultations("https://www.eiopa.europa.eu", "/browse/consultations-and-surveys_en",
                              "eiopa", "eiopa_consultations", "/consultation")


# --------------------------------------------------------------------------- #
# AMLA — clean anchor-title listing (reuse the generic walker).
# --------------------------------------------------------------------------- #
def ingest_amla_consultations(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _ecl_consultations("https://www.amla.europa.eu", "/policy/public-consultations_en",
                              "amla", "amla_consultations", "/policy/public-consultations/")


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

