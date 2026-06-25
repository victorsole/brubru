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
        {"item_type": "charter_article", "slug": "charterpedia", "noun": "Charter articles",
         "source": "FRA Charterpedia.",
         "extra": "The EU Charter of Fundamental Rights article by article (Charterpedia): each "
                  "article with its FRA page collecting the explanations, related EU and national "
                  "case-law and constitutional provisions. Filter with q (e.g. 'data protection' "
                  "or 'asylum')."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of FRA about and fundamental-rights theme pages.",
         "extra": "Snapshots of FRA's about pages and its fundamental-rights themes: access "
                  "to asylum, AI and big data, borders and information systems, business and "
                  "human rights, child protection, data protection, hate crime, the rule of "
                  "law, Roma, racial and ethnic origin, people with disabilities, victims' "
                  "rights, trafficking and labour exploitation, and more."},
    ],
)
