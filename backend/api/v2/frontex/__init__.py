"""
/api/v2/frontex — European Border and Coast Guard Agency (api_socjust.md).

The EU external-borders agency, its own folder. Resources under the folder prefix:
/api/v2/frontex/{news,topics}. frontex.europa.eu is server-rendered and reachable
with plain requests, so it runs on the standard cron path.

Reads from economy_items (body row seeded by migration 156); 5 mandatory
datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="frontex", prefix="/frontex",
    body_name="European Border and Coast Guard Agency",
    acronym="Frontex", tag="v2-frontex",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the Frontex news-release listing.",
         "extra": "News releases from Frontex on joint operations, border-crossing "
                  "trends, the standing corps, returns, search and rescue and "
                  "cooperation with Member States and third countries."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of Frontex about, careers and transparency pages.",
         "extra": "Snapshots of Frontex reference pages: tasks and mission, the "
                  "management board, procurement and grants, the standing corps "
                  "(about, training, profiles), accountability, data protection and "
                  "public access to documents."},
    ],
)
