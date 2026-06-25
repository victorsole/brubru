"""
/api/v2/efca — European Fisheries Control Agency (api_socjust.md).

The EU's fisheries-control agency, its own folder. Resources under the folder
prefix: /api/v2/efca/{news}. Drupal site (efca.europa.eu), scraped with plain
requests (no WAF). Only the news listing is cleanly dated, so news only.

Reads from economy_items (body row seeded); 5 mandatory datapoints.
Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="efca", prefix="/efca",
    body_name="European Fisheries Control Agency",
    acronym="EFCA", tag="v2-efca",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the EFCA latest-news listing.",
         "extra": "News from the European Fisheries Control Agency on joint "
                  "deployment plans, real-time closures, inspections, coast-guard "
                  "cooperation and fisheries-control operations."},
    ],
)
