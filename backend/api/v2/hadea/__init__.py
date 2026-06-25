"""
/api/v2/hadea — European Health and Digital Executive Agency
(api_ec.md, executive agencies).

A Commission executive agency, its own folder. Resources under the folder prefix:
/api/v2/hadea/{news,events,calls,tenders,topics}. hadea.ec.europa.eu runs on the
EU ECL stack and is reachable with plain requests, so it runs on the standard cron
path.

Reads from economy_items (body row seeded by migration 159); 5 mandatory
datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="hadea", prefix="/hadea",
    body_name="European Health and Digital Executive Agency",
    acronym="HaDEA", tag="v2-hadea",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the HaDEA news listing.",
         "extra": "News from HaDEA on the programmes it manages: EU4Health, the Single "
                  "Market Programme (food), Horizon Europe health and digital, the "
                  "Connecting Europe Facility (digital) and the Digital Europe Programme."},
        {"item_type": "event", "slug": "events", "noun": "events",
         "source": "the HaDEA events listing.",
         "extra": "Info days, webinars and events organised by HaDEA, with their dates."},
        {"item_type": "call", "slug": "calls", "noun": "calls for proposals",
         "source": "the HaDEA calls-for-proposals listing.",
         "extra": "Open EU funding calls for proposals managed by HaDEA across its "
                  "programmes, with their deadlines where published."},
        {"item_type": "tender", "slug": "tenders", "noun": "calls for tenders",
         "source": "the HaDEA calls-for-tenders listing.",
         "extra": "HaDEA procurement calls for tenders and prior information notices, "
                  "with their deadlines where published."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of HaDEA about and programme pages.",
         "extra": "Snapshots of HaDEA's about, legal-base, programmes-and-funding and "
                  "staff pages, and its programme pages (EU4Health, Single Market "
                  "Programme food, Horizon Europe, the Connecting Europe Facility and "
                  "the Digital Europe Programme)."},
    ],
)
