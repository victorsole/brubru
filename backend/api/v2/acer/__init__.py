"""
/api/v2/acer — Agency for the Cooperation of Energy Regulators.

Single-market / energy EU agency (api_market.md), its own folder. Resources sit
directly under the folder prefix: /api/v2/acer/{news,publications}. ACER's public
events are JS-rendered from an extranet, so only news + publications are exposed.

Reads from economy_items (migrations 119 + 120); 5 mandatory datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="acer", prefix="/acer",
    body_name="Agency for the Cooperation of Energy Regulators",
    acronym="ACER", tag="v2-acer",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the ACER news and press-releases listings plus the detail pages.",
         "extra": "News and press releases from the Agency for the Cooperation of Energy Regulators."},
        {"item_type": "publication", "slug": "publications", "noun": "publications",
         "source": "the ACER publications listing; bodies are extracted from the source PDFs.",
         "extra": "Market monitoring reports, position papers, opinions and other ACER documents."},
    ],
)
