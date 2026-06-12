"""
/api/v2/fra — European Union Agency for Fundamental Rights.

EU fundamental-rights agency (api_socjust.md), its own folder. Database resources
under the folder prefix: /api/v2/fra/{case-law,...}. FRA's news/events are served
by the cross-institution feed; this folder carries FRA's distinctive databases.

Reads from economy_items (migration 132); 5 mandatory datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="fra", prefix="/fra",
    body_name="European Union Agency for Fundamental Rights",
    acronym="FRA", tag="v2-fra",
    resources=[
        {"item_type": "case_law", "slug": "case-law", "noun": "case-law entries",
         "source": "the FRA case-law database.",
         "extra": "Court decisions on EU fundamental rights from the FRA case-law database — "
                  "CJEU, ECtHR and national court rulings, each with the court, case reference and "
                  "decision type, linking to the FRA case-law page. Filter with q (e.g. a court "
                  "such as 'CJEU' or a case number)."},
    ],
)
