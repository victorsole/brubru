"""
/api/v2/ecdc — European Centre for Disease Prevention and Control.

EU health agency (api_health.md), its own folder. Resources under the folder
prefix: /api/v2/ecdc/{news,publications}. ECDC has no separate events feed.

Reads from economy_items (migrations 119 + 121); 5 mandatory datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="ecdc", prefix="/ecdc",
    body_name="European Centre for Disease Prevention and Control",
    acronym="ECDC", tag="v2-ecdc",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the ECDC news search feed plus the detail pages.",
         "extra": "News and press releases from the European Centre for Disease Prevention and Control."},
        {"item_type": "publication", "slug": "publications", "noun": "publications",
         "source": "the ECDC publications search feed.",
         "extra": "Surveillance reports, risk assessments, threat reports and guidance from ECDC."},
    ],
)
