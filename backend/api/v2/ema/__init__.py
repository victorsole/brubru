"""
/api/v2/ema — European Medicines Agency.

EU health agency (api_health.md), its own folder. Resources under the folder
prefix: /api/v2/ema/{news,events,medicines}. EMA's publications page is a nav
landing (no server-side list), so its published outputs are surfaced via the
medicines/EPAR dataset instead.

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
        {"item_type": "medicine", "slug": "medicines", "noun": "medicines",
         "source": "the EMA medicines dataset (the full register of EU-evaluated medicines / EPARs).",
         "extra": "Every medicine evaluated by EMA — name, EMA product number, status, INN, active substance, therapeutic area, marketing-authorisation holder, key dates and the EPAR URL. Filter with q (e.g. an active substance or therapeutic area)."},
    ],
)
