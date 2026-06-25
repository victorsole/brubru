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
from services.scrapers.economy_ema import EMA_DATASETS

_resources = [
    {"item_type": "news", "slug": "news", "noun": "news items",
     "source": "the EMA news listing plus the detail pages.",
     "extra": "News from the European Medicines Agency on human and veterinary medicines, safety and public-health threats."},
    {"item_type": "event", "slug": "events", "noun": "events",
     "source": "the EMA upcoming-events listing.",
     "extra": "Committee meetings (CHMP, PRAC, CVMP and others), info days and training, with their dates."},
    {"item_type": "medicine", "slug": "medicines", "noun": "medicines",
     "source": "the EMA medicines dataset (the full register of EU-evaluated medicines / EPARs).",
     "extra": "Every medicine evaluated by EMA — name, EMA product number, status, INN, active substance, therapeutic area, marketing-authorisation holder, key dates and the EPAR URL. Filter with q (e.g. an active substance or therapeutic area)."},
    {"item_type": "topic", "slug": "topics", "noun": "topic pages",
     "source": "a curated set of EMA about-us, scientific-committee and human-regulatory pages.",
     "extra": "Snapshots of EMA's about-us pages (who we are, what we do, how we work, the "
              "European medicines regulatory network, crisis preparedness, history, SME "
              "support, annual reports), its scientific committees (CHMP, PRAC, CAT, COMP, "
              "HMPC, CVMP, PDCO) and the human-regulatory overview."},
]
# One resource per EMA register dataset (shortages, referrals, orphan designations, ...).
_resources += [
    {"item_type": c["item_type"], "slug": c["slug"], "noun": c["noun"],
     "source": f"the EMA {c['noun']} dataset.", "extra": c["extra"]}
    for c in EMA_DATASETS
]

router = make_single_body_folder(
    body_code="ema", prefix="/ema",
    body_name="European Medicines Agency", acronym="EMA", tag="v2-ema",
    resources=_resources,
)
