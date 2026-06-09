"""
/api/v2/efsa — European Food Safety Authority.

EU health agency (api_health.md), its own folder. Resources under the folder
prefix: /api/v2/efsa/{news,publications}. EFSA has no separate events feed.

Reads from economy_items (migrations 119 + 121); 5 mandatory datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="efsa", prefix="/efsa",
    body_name="European Food Safety Authority", acronym="EFSA", tag="v2-efsa",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the EFSA press RSS feed plus the detail pages.",
         "extra": "News and press releases from the European Food Safety Authority."},
        {"item_type": "publication", "slug": "publications", "noun": "publications",
         "source": "the EFSA publications listing (EFSA Journal scientific outputs and reports).",
         "extra": "Scientific opinions, statements, guidance and data reports from EFSA."},
    ],
)
