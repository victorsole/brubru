"""
/api/v2/cpvo — Community Plant Variety Office.

Single-market / plant-variety-rights EU agency (api_market.md), its own folder.
Resources under the folder prefix: /api/v2/cpvo/{news,publications,events}.

Reads from economy_items (migrations 119 + 120); 5 mandatory datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="cpvo", prefix="/cpvo",
    body_name="Community Plant Variety Office",
    acronym="CPVO", tag="v2-cpvo",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the CPVO news listing plus the detail pages.",
         "extra": "Official announcements and news from the Community Plant Variety Office."},
        {"item_type": "publication", "slug": "publications", "noun": "publications",
         "source": "the CPVO reports listing; bodies are extracted from the source PDFs.",
         "extra": "Annual reports, statistics and corporate documents from the CPVO."},
        {"item_type": "event", "slug": "events", "noun": "events",
         "source": "the CPVO conferences and events listing.",
         "extra": "Seminars, conferences and meetings, with their dates."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of CPVO about, mission and law-and-practice pages.",
         "extra": "Snapshots of CPVO reference pages: about us, our mission, the "
                  "strategic plan, research and development, law and practice (board of "
                  "appeal, legislation in force), reports, statistics and the FAQ on "
                  "Community plant variety rights."},
    ],
)
