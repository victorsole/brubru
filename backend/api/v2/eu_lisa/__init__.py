"""
/api/v2/eu-lisa — EU Agency for the Operational Management of Large-Scale IT Systems.

Single-market / large-scale-IT EU agency (api_market.md), its own folder.
Resources under the folder prefix: /api/v2/eu-lisa/{news,publications,events}.
Body code is 'eu_lisa' (the URL path uses the hyphenated 'eu-lisa').

Reads from economy_items (migrations 119 + 120); 5 mandatory datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="eu_lisa", prefix="/eu-lisa",
    body_name="European Union Agency for the Operational Management of Large-Scale IT Systems",
    acronym="eu-LISA", tag="v2-eu-lisa",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the eu-LISA news listing plus the detail pages.",
         "extra": "News from the EU Agency for the Operational Management of Large-Scale IT Systems (EES, ETIAS, SIS, VIS, Eurodac)."},
        {"item_type": "publication", "slug": "publications", "noun": "publications",
         "source": "the eu-LISA publications listing.",
         "extra": "Annual reports, statistics, research and corporate documents from eu-LISA."},
        {"item_type": "event", "slug": "events", "noun": "events",
         "source": "the eu-LISA events listing.",
         "extra": "Conferences, industry roundtables and Management Board meetings, with their dates."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of eu-LISA about and activities pages.",
         "extra": "Snapshots of eu-LISA's about pages and its activities: the large-scale "
                  "IT systems (SIS, VIS, Eurodac, EES, ETIAS), interoperability, data "
                  "protection, security, research and innovation, training, carriers, "
                  "EMPACT and pilot projects."},
    ],
)
