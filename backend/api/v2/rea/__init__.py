"""
/api/v2/rea — European Research Executive Agency (api_ec.md, executive agencies).

A Commission executive agency, its own folder. Resources under the folder prefix:
/api/v2/rea/{news,events,publications,topics}. rea.ec.europa.eu runs on the EU ECL
stack and is reachable with plain requests, so it runs on the standard cron path.

Reads from economy_items (body row seeded by migration 162); 5 mandatory
datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="rea", prefix="/rea",
    body_name="European Research Executive Agency",
    acronym="REA", tag="v2-rea",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the REA news listing.",
         "extra": "News from REA on the Horizon Europe grants it manages: cluster 2 "
                  "(culture, creativity and inclusive society), cluster 3 (civil "
                  "security for society), the EU Soil Mission and the agricultural "
                  "products promotion programme."},
        {"item_type": "event", "slug": "events", "noun": "events",
         "source": "the REA events listing.",
         "extra": "Info days, forums and events organised by REA, with their dates."},
        {"item_type": "publication", "slug": "publications", "noun": "publications",
         "source": "the REA publications listing.",
         "extra": "REA reports, handbooks, CORDIS results packs and other publications "
                  "from the research programmes it manages."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of REA about, funding-and-grants and guidance pages.",
         "extra": "Snapshots of REA's about page, its funding-and-grants tree (the EU "
                  "Soil Mission, Horizon Europe cluster 2 with democracy and governance, "
                  "cultural heritage and social transformations, cluster 3 with disaster "
                  "resilience, crime and terrorism, external borders and resilient "
                  "infrastructures, plus agricultural products promotion) and its "
                  "applicant guidance pages."},
    ],
)
