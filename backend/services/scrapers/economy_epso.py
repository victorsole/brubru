"""
EPSO — European Personnel Selection Office (api_ec.md L3983-4072). /api/v2/epso.

EPSO's public site is eu-careers.europa.eu, a Drupal build (not the standard ECL
card layout), server-rendered and reachable with plain requests. Source map
(verified 25 Jun 2026):
  - news  : /en/news — Drupal Views .views-row rows: .views-field-title a (title +
            /en/news/<slug>/<id> link), an EPSO reference number and a <time
            datetime> created date. Detail = HTML.
  - topic : curated about, why-an-EU-career, selection-process, equal-opportunities
            and CAST job-profile pages.

(Live vacancies/competitions are served from a JS candidate portal with no
server-side listing, so no vacancies resource is exposed.)

EPSO organises the open competitions and selection procedures that recruit
permanent and contract staff for the EU institutions. Reads from economy_items
(body row seeded by migration 163); 5 mandatory datapoints. Scope: read:economy.
No LLM is used.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, _iso_dt, snapshot_topics,
)

_BASE = "https://eu-careers.europa.eu"
NEWS_PAGES = [f"{_BASE}/en/news"]

_CAST = [
    "administration-human-resources", "archivistics-records-management",
    "child-care-staff", "educational-psychologists", "finance",
    "information-and-communication-technology", "information-and-document-security",
    "it-security", "law", "manual-and-administrative-support-workers",
    "political-affairs-eu-policies", "project-programme-management", "proofreaders",
    "secretaries-clerks", "security-operations", "technical-security", "translators",
]
_TOPIC_PATHS = [
    "/en/about-epso/who-we-are",
    "/en/mission",
    "/en/vision",
    "/en/operating-principles",
    "/en/values",
    "/en/eu-careers/why-an-eu-career",
    "/en/international-environment",
    "/en/working-and-living-brussels-and-luxembourg",
    "/en/personal-and-professional-development",
    "/en/salary-and-benefits",
    "/en/eu-careers/staff-categories",
    "/en/eu-careers/benefits",
    "/en/selection-process",
    "/en/competitions-permanent-positions",
    "/en/selection-procedures-contract-staff-positions",
    "/en/selection-procedures-other-staff-categories",
    "/en/selection-procedure/epso-tests",
    "/en/how-apply-competition-overview",
    "/en/what-know-about-testing",
    "/en/instructions-and-policies-candidates",
    "/en/equal-opportunities/equal-opportunities",
    "/en/equal-opportunities/diversity-inclusion",
    "/en/job-opportunities/traineeships",
] + [f"/en/job-opportunities/{c}-cast-permanent" for c in _CAST]


def ingest_epso_news(*, fetch_bodies: bool = True, **_) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    r = http_get(NEWS_PAGES[0])
    if r is None:
        return items
    soup = BeautifulSoup(r.text, "html.parser")
    for row in soup.select(".views-row"):
        a = row.select_one(".views-field-title a[href], .views-field-title a")
        if not a or not a.get("href") or "/en/news/" not in a["href"]:
            continue
        url = norm_url(a["href"] if a["href"].startswith("http") else _BASE + a["href"])
        if url in seen:
            continue
        seen.add(url)
        title = clean(a.get_text(" ", strip=True))
        t = row.select_one("time[datetime]")
        doc_dt = _iso_dt(t["datetime"]) if t and t.get("datetime") else None
        ref = row.select_one(".views-field-field-epso-reference-number .field-content")
        summary = clean(ref.get_text(" ", strip=True)[:300]) if ref else None
        items.append(Item(body_code="epso", item_type="news", title=title[:300],
                          public_url=url, summary=summary, document_date=doc_dt,
                          creation_date=now, source_kind="html", guid=url))
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_epso_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("epso", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies)
