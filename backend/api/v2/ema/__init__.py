"""
/api/v2/ema — European Medicines Agency.

EU health agency (api_health.md), its own folder. Resources under the folder
prefix: /api/v2/ema/{news,events}. EMA's publications list renders client-side
(EAMS) with no server-side items, so news + events only.

Reads from economy_items (migrations 119 + 121); 5 mandatory datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="ema", prefix="/ema",
    body_name="European Medicines Agency", acronym="EMA", tag="v2-ema",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the EMA news listing plus the detail pages.",
         "extra": "News from the European Medicines Agency on human and veterinary medicines, safety and public-health threats."},
        {"item_type": "event", "slug": "events", "noun": "events",
         "source": "the EMA upcoming-events listing.",
         "extra": "Committee meetings (CHMP, PRAC, CVMP and others), info days and training, with their dates."},
    ],
)
