"""
EU Joint Undertakings + Euratom bodies (api_euratom_ju.md). Config-driven scrapers
for the bodies that run on the EU ECL stack (ec.europa.eu subdomains, _en paths):
news / events / publications via scrape_ecl_listing, topics via snapshot_topics.

One folder per body (/api/v2/<body>); registration uses functools.partial over
these generic ingesters. Reads from economy_items (body rows seeded by migrations
179+). 5 mandatory datapoints. Scope: read:economy. No LLM is used.
"""
from __future__ import annotations

from services.scrapers.economy_common import Item, scrape_ecl_listing, snapshot_topics

# body_code -> {base, news/event/publication/topic path lists}
JU_ECL: dict[str, dict] = {
    "hydrogen": {
        "base": "https://www.clean-hydrogen.europa.eu",
        "news": ["/media/news_en", "/projects-dashboard/project-updates_en"],
        "event": ["/media/events_en"],
        "publication": ["/media/publications_en"],
        "topic": [
            "/about-us_en", "/about-us/who-we-are_en", "/about-us/our-story_en",
            "/about-us/mission-objectives_en", "/about-us/organisation_en",
            "/get-involved_en", "/get-involved/hydrogen-valleys_en",
            "/get-involved/international-collaboration_en", "/apply-funding_en",
            "/apply-funding/call-proposals-0_en", "/knowledge-management_en",
            "/knowledge-management/european-hydrogen-observatory_en",
            "/knowledge-management/annual-programme-review_en", "/projects-dashboard_en",
        ],
    },
    "edctp3": {
        "base": "https://www.global-health-edctp3.europa.eu",
        "news": ["/news-and-events/news_en"],
        "event": ["/news-and-events/events_en"],
        "publication": ["/news-and-events/publications-0_en"],
        "topic": [
            "/about-us/who-we-are_en", "/about-us/what-we-do_en",
            "/about-us/what-we-fund_en", "/about-us/our-story_en",
            "/about-us/our-governance_en", "/about-us/our-path-impact_en",
            "/about-us/lasting-benefits-europe-and-africa_en", "/partner-us_en",
            "/funding_en", "/funding/calls-proposals_en",
            "/funding/research-priorities-disease-area_en", "/funding/edctp-prizes_en",
            "/our-projects_en", "/results-and-insights_en",
            "/results-and-insights/global-health-leaders_en",
        ],
    },
    "eurohpc": {
        "base": "https://www.eurohpc-ju.europa.eu",
        "news": ["/media-events/press-releases_en"],
        "event": ["/media-events/events_en"],
        "publication": ["/media-events/publications_en"],
        "topic": [
            "/about_en", "/about/discover-eurohpc-ju_en", "/about/governance_en",
            "/ai-factories_en", "/ai-factories/ai-factories-access-modes_en",
            "/ai-gigafactories_en", "/ai-gigafactories/supporting-ai-gigafactories_en",
            "/supercomputers_en", "/supercomputers/our-supercomputers_en",
            "/supercomputers/supercomputers-access-calls_en",
            "/supercomputers/awarded-projects_en", "/quantum-technologies_en",
            "/quantum-technologies/quantum-communication_en",
            "/research-innovation/research-innovation-calls_en",
            "/research-innovation/our-projects_en",
        ],
    },
    "euratom": {
        "base": "https://euratom-supply.ec.europa.eu",
        "publication": ["/publications_en", "/publications/esa-annual-reports_en",
                        "/publications/esa-quarterly-reports_en",
                        "/publications/other-esa-publications_en"],
        "topic": [
            "/activities_en", "/activities/contract-management_en",
            "/activities/market-observatory_en",
            "/activities/supply-medical-radioisotopes_en", "/about-esa/legal-basis_en",
            "/about-esa/governance_en", "/about-esa/staff-and-organisation-chart_en",
            "/about-esa/planning-and-reporting_en", "/about-esa/other-euratom-services_en",
        ],
    },
}


def ingest_ecl(body: str, item_type: str, *, fetch_bodies: bool = True, **_) -> list[Item]:
    cfg = JU_ECL[body]
    pages = [cfg["base"] + p for p in cfg.get(item_type, [])]
    if not pages:
        return []
    return scrape_ecl_listing(body, item_type, pages, cfg["base"], fetch_bodies=fetch_bodies)


def ingest_topics(body: str, *, fetch_bodies: bool = True, **_) -> list[Item]:
    cfg = JU_ECL[body]
    return snapshot_topics(body, cfg["base"], cfg.get("topic", []), fetch_bodies=fetch_bodies)
