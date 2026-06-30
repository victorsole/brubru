"""
/api/v2/eugovtech — EC GovTech (the EU GovTech collection on the Interoperable
Europe Portal, DG DIGIT).

A dedicated folder for the EU GovTech sub-portal: its own listings carry the full
history that the cross-collection /api/v2/interoperable feeds only sample.
Resources under the folder prefix: /api/v2/eugovtech/{news,events,solutions,
publications,topics}.

The interoperable-europe.ec.europa.eu pages are JS-rendered, so the feeds are
scraped with Playwright (services/scrapers/economy_eugovtech.py) and refreshed
locally, not on the Railway cron (same constraint as EEAS / EU Interoperable).

Reads from economy_items (body row in migration 197); 5 mandatory datapoints.
Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="eugovtech", prefix="/eugovtech",
    body_name="EU GovTech", acronym="EU GovTech", tag="v2-eugovtech",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news",
         "source": "the EU GovTech news listing on the Interoperable Europe Portal.",
         "extra": "News from the EU GovTech community, including the Startups' Corner "
                  "digests and the GovTech4All public-sector-challenge updates. Filter "
                  "with q (e.g. a country or theme)."},
        {"item_type": "event", "slug": "events", "noun": "events",
         "source": "the EU GovTech events listing.",
         "extra": "Conferences, webinars, hackathons and matchmaking events for the "
                  "govtech ecosystem (VivaTech, Techsylvania and the community's own "
                  "sessions)."},
        {"item_type": "solution", "slug": "solutions", "noun": "reusable solutions",
         "source": "the EU GovTech solutions listing.",
         "extra": "Reusable govtech solutions and toolkits shared by the community "
                  "(e.g. civic-intelligence platforms and assessment toolkits)."},
        {"item_type": "publication", "slug": "publications", "noun": "publications",
         "source": "the EU GovTech Knowledge Centre.",
         "extra": "GovTech reports, policy briefs and foresight studies from the "
                  "Knowledge Centre: evidence on how govtech can modernise public "
                  "administrations across the EU."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "the EU GovTech hub pages (snapshots).",
         "extra": "Standing snapshots of the EU GovTech hubs: the Welcome page, the "
                  "GovTech Atlas (initiatives and startups), GovTech4All (public-sector "
                  "challenges) and the Knowledge Centre landing."},
    ],
)
