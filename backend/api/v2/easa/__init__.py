"""
/api/v2/easa — European Union Aviation Safety Agency (api_socjust.md).

The EU's aviation safety regulator, its own folder. Resources under the folder
prefix: /api/v2/easa/{news,publications,events}. Server-rendered Drupal site
(easa.europa.eu), scraped with plain requests (no WAF).

Reads from economy_items (body row seeded); 5 mandatory datapoints.
Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="easa", prefix="/easa",
    body_name="European Union Aviation Safety Agency",
    acronym="EASA", tag="v2-easa",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the EASA newsroom (news and press releases).",
         "extra": "News and press releases from the EU Aviation Safety Agency, "
                  "covering airworthiness, drones, air operations, certification and "
                  "international cooperation."},
        {"item_type": "publication", "slug": "publications", "noun": "research reports",
         "source": "the EASA document library (research reports).",
         "extra": "Research reports and studies published by EASA on aviation safety, "
                  "sustainability and emerging technologies."},
        {"item_type": "event", "slug": "events", "noun": "events",
         "source": "the EASA events listing.",
         "extra": "Committee and expert-group meetings, stakeholder advisory bodies, "
                  "workshops and conferences hosted by EASA."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of EASA regulatory-domain and topic-hub pages.",
         "extra": "Snapshots of the EASA reference pages: the regulatory domains "
                  "(aerodromes, air operations, air traffic management, aircraft "
                  "products, aircrew, civil drones, cybersecurity, environment, "
                  "safety management and more) and the EASA Light topic hub."},
    ],
)
