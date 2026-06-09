"""
/api/v2/eit — European Institute of Innovation and Technology.

Single-market / innovation EU agency (api_market.md), its own folder. Resources
under the folder prefix: /api/v2/eit/{news,events}. EIT publishes no standalone
documents listing, so news + events only.

Reads from economy_items (migrations 119 + 120); 5 mandatory datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="eit", prefix="/eit",
    body_name="European Institute of Innovation and Technology",
    acronym="EIT", tag="v2-eit",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the EIT news listing plus the detail pages.",
         "extra": "News from the European Institute of Innovation and Technology and its Knowledge and Innovation Communities."},
        {"item_type": "event", "slug": "events", "noun": "events",
         "source": "the EIT events listing.",
         "extra": "Conferences, summits and community events, with their dates."},
    ],
)
