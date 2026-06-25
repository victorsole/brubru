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
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of EUAA about, asylum-knowledge and operations pages.",
         "extra": "Snapshots of EUAA's about pages, its asylum-knowledge work (the asylum "
                  "report, country guidance, courts and tribunals, the Dublin procedure, "
                  "MedCOI, monitoring of the CEAS, reception, vulnerability), country of "
                  "origin information, operations (country operations, operational "
                  "assistance, resettlement) and the fundamental-rights and complaints "
                  "mechanisms."},
    ],
)
