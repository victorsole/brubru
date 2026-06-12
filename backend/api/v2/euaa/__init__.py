"""
/api/v2/euaa — European Union Agency for Asylum.

EU asylum agency (api_socjust.md), its own folder. Resources under the folder
prefix: /api/v2/euaa/{news,publications}.

Reads from economy_items (migration 131); 5 mandatory datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="euaa", prefix="/euaa",
    body_name="European Union Agency for Asylum",
    acronym="EUAA", tag="v2-euaa",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the EUAA press releases and news.",
         "extra": "News and press releases from the EU Agency for Asylum on the asylum situation, "
                  "country reports and operations."},
    ],
)
