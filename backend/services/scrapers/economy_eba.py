"""
EBA — European Banking Authority ingestion (/api/v2/eu-financial-institutions/eba).

Verified source map (URL-verification pass, api_econ.md L282-367):
  EBA's /rss.xml is only a 10-item e-mail-alert digest (not per-content), but the
  listing pages are SERVER-RENDERED Drupal "teaser-columns" views (paginated,
  ?page=N). So we scrape the listing pages directly — no Playwright needed.

  - news         : press-releases + speeches + interviews
  - publications : the publications listing
  - events       : the events listing
  (The doc gives EBA no dedicated legal-acts section; its rulebook content lives
   under publications, so EBA exposes news/publications/events only.)

Row shape: <article class="teaser-columns"> with the date in .link-icon--calendar,
the title+link in h3.teaser-columns__title a, and a teaser in .teaser-columns__text.
Detail pages are server-rendered. No LLM is used.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, parse_listing_date, _iso_dt,
)

_BASE = "https://www.eba.europa.eu"

EBA_LISTINGS = {
    "news": [
        f"{_BASE}/publications-and-media/press-releases",
        f"{_BASE}/publications-and-media/speeches",
        f"{_BASE}/publications-and-media/interviews",
    ],
    "publication": [
        f"{_BASE}/publications-and-media/publications",
    ],
    "event": [
        f"{_BASE}/publications-and-media/events",
    ],
}


def _parse_teaser_page(html: str) -> list[tuple[str, str, datetime | None, str | None]]:
    """Handle EBA's three Drupal teaser variants: teaser-columns (news),
    teaser (publications, links to a file), teaser-event-calendar (events)."""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[tuple[str, str, datetime | None, str | None]] = []
    for art in soup.select("article.teaser-columns, article.teaser, article.teaser-event-calendar"):
        a = art.select_one('[class*="__title"] a[href]') or art.find("a", href=True)
        if not a or not a.get("href"):
            continue
        href = a["href"]
        url = norm_url(href if href.startswith("http") else _BASE + href)
        title = clean(a.get_text(" ", strip=True).replace("​", "").strip())
        if not title:
            continue
        # Date: news/publications carry .link-icon--calendar ("8 June 2026");
        # events split day/month/year across spans.
        doc_dt = None
        cal = art.select_one(".link-icon--calendar")
        if cal:
            doc_dt = parse_listing_date(cal.get_text(" ", strip=True))
        else:
            day = art.select_one(".teaser-event-calendar__calendar-day")
            mon = art.select_one(".teaser-event-calendar__calendar-month")
            yr = art.select_one(".teaser-event-calendar__calendar-year")
            if day and mon and yr:
                doc_dt = parse_listing_date(
                    f"{day.get_text(strip=True)} {mon.get_text(strip=True)} {yr.get_text(strip=True)}")
        summ_el = art.select_one(".teaser-columns__text, .teaser__text")
        summary = clean(summ_el.get_text(" ", strip=True)[:1000]) if summ_el else None
        rows.append((url, title, doc_dt, summary))
    return rows


def scrape_listings(body_code: str, item_type: str, listing_urls, *,
                    fetch_bodies: bool = True, max_pages: int = 6) -> list[Item]:
    """Page through server-rendered teaser-columns listings and build Items."""
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for base_url in listing_urls:
        for page in range(max_pages):
            sep = "&" if "?" in base_url else "?"
            url = base_url if page == 0 else f"{base_url}{sep}page={page}"
            r = http_get(url)
            if r is None:
                break
            rows = _parse_teaser_page(r.text)
            if not rows:
                break  # past the last page
            new = 0
            for item_url, title, doc_dt, summary in rows:
                if item_url in seen:
                    continue
                seen.add(item_url)
                new += 1
                items.append(Item(body_code=body_code, item_type=item_type, title=title,
                                  public_url=item_url, summary=summary, document_date=doc_dt,
                                  creation_date=now, source_kind="html", guid=item_url))
            if new == 0:
                break  # all-duplicate page -> stop
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_eba_news(**kw) -> list[Item]:
    return scrape_listings("eba", "news", EBA_LISTINGS["news"], **kw)


def ingest_eba_publications(**kw) -> list[Item]:
    return scrape_listings("eba", "publication", EBA_LISTINGS["publication"], **kw)


def ingest_eba_events(**kw) -> list[Item]:
    return scrape_listings("eba", "event", EBA_LISTINGS["event"], **kw)


# --- EBA EUCLID: credit institutions register (CIR) -------------------------
# Reverse-engineering note (how this was found):
#   euclid.eba.europa.eu/register/cir is a SPA behind a "Continue" disclaimer
#   gate. After clicking through, the search form submits
#     POST /register/api/search/entities
#   with a Mongo-style query DSL. The DEFAULT (empty-form) query
#     {"$and": [{"_messagetype": "EUCLIDMD"}]}
#   returns the ENTIRE register in one response (~4,500 entities, no pagination).
#   Each record is wrapped in "_payload" with EntityType + EntityCode + a
#   Properties list of single-key dicts. The schema is at GET /register/cir-api/metadata.
#   Key lesson: the query payload only appears on a real form submit behind the
#   disclaimer — capture it with Playwright form interaction, do NOT guess it.
import json as _json

_EUCLID_API = "https://euclid.eba.europa.eu/register/api/search/entities"
_EUCLID_QUERY = {"$and": [{"_messagetype": "EUCLIDMD"}]}
_EUCLID_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
    "Content-Type": "application/json", "Accept": "application/json",
    "Origin": "https://euclid.eba.europa.eu",
    "Referer": "https://euclid.eba.europa.eu/register/cir/search",
}
_ENTITY_TYPE = {
    "CRD_CRE_INS": "Credit institution",
    "CRD_EEA_BRA": "Branch of an EEA credit institution",
    "CRD_NON_EEA_BRA": "Branch of a non-EEA credit institution",
}
_PROP_LABELS = {
    "ENT_NAM": "Name", "ENT_NAM_NON_LAT": "Name (non-Latin)",
    "ENT_COD": "Entity code", "ENT_COD_TYP": "Code type",
    "ENT_NAT_REF_COD": "National reference code",
    "ENT_COU_RES": "Country of residence", "ENT_TOW_CIT_RES": "Town/city",
    "ENT_AUT": "Authorisation date", "EEA_DEP_GUA_SCH": "Deposit guarantee scheme",
    "NON_EEA_DEP_GUA_SCH": "Non-EEA deposit guarantee scheme", "COM_AUT": "Competent authority",
    "ENT_COD_CRE_INS_EST_BRA": "Establishing credit institution (code)",
    "NAM_CRE_INS_EST_BRA": "Establishing credit institution (name)",
    "COU_CRE_INS_EST_BRA": "Establishing credit institution (country)",
}


def ingest_eba_credit_institutions(*, fetch_bodies: bool = True, **_) -> list[Item]:
    import requests
    try:
        r = requests.post(_EUCLID_API, headers=_EUCLID_HEADERS,
                          data=_json.dumps(_EUCLID_QUERY), timeout=120)
        if r.status_code != 200:
            return []
        rows = r.json()
    except (requests.RequestException, ValueError):
        return []
    now = datetime.now(timezone.utc)
    items: list[Item] = []
    seen: set[str] = set()
    for raw in rows:
        rec = raw.get("_payload", raw)
        props: dict = {}
        for p in rec.get("Properties", []):
            for k, v in p.items():
                props[k] = v
        code = rec.get("EntityCode") or props.get("ENT_COD")
        if not code:
            continue
        url = f"https://euclid.eba.europa.eu/register/cir/{code}"
        if url in seen:
            continue
        seen.add(url)
        name = clean(props.get("ENT_NAM") or props.get("ENT_NAM_NON_LAT") or code)
        et = rec.get("EntityType")
        # authorisation date (a list like ["2026-06-08"])
        aut = props.get("ENT_AUT")
        if isinstance(aut, list):
            aut = aut[0] if aut else None
        doc_dt = _iso_dt(str(aut)) if aut else None
        if doc_dt is None and aut:
            doc_dt = parse_listing_date(str(aut))
        # body: entity type + every labelled property
        lines = [f"Entity type: {_ENTITY_TYPE.get(et, et)}"] if et else []
        for k, v in props.items():
            if v in (None, "", []):
                continue
            val = ", ".join(str(x) for x in v) if isinstance(v, list) else str(v)
            lines.append(f"{_PROP_LABELS.get(k, k)}: {val}")
        body_txt = clean("\n".join(lines)) or None
        body_html = clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>") if lines else None
        def _s(v):
            return ", ".join(str(x) for x in v) if isinstance(v, list) else (str(v) if v else "")
        summary = clean(" | ".join(x for x in [
            _ENTITY_TYPE.get(et, et) or "",
            _s(props.get("ENT_COU_RES")), _s(props.get("ENT_TOW_CIT_RES")),
            f"code {code}",
        ] if x).strip(" |"))
        items.append(Item(body_code="eba", item_type="credit_institution", title=name,
                          public_url=url, summary=summary, body_txt=body_txt, body_html=body_html,
                          document_date=doc_dt, creation_date=now, source_kind="euclid", guid=code))
    return items
