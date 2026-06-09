"""
/api/v2/enisa — European Union Agency for Cybersecurity.

Single-market / cybersecurity EU agency (api_market.md), its own folder.
Resources under the folder prefix: /api/v2/enisa/{news,publications}. ENISA's
events listing is JS-rendered with no server-side dates, so news + publications only.

Reads from economy_items (migrations 119 + 120); 5 mandatory datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="enisa", prefix="/enisa",
    body_name="European Union Agency for Cybersecurity",
    acronym="ENISA", tag="v2-enisa",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the ENISA news listing plus the detail pages.",
         "extra": "News and press releases from the European Union Agency for Cybersecurity."},
        {"item_type": "publication", "slug": "publications", "noun": "publications",
         "source": "the ENISA publications listing.",
         "extra": "Reports, threat landscapes, guidelines and studies from ENISA."},
    ],
)
