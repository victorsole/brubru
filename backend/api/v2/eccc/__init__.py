"""
/api/v2/eccc — European Cybersecurity Competence Centre (api_market.md).

The EU's cybersecurity funding and coordination body, its own folder. Resources
under the folder prefix: /api/v2/eccc/{news,calls,governing-board,nccs,topics}.
cybersecurity-centre.europa.eu runs on the EU ECL stack (plain requests).

Reads from economy_items (body row seeded by migration 174); 5 mandatory datapoints.
Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="eccc", prefix="/eccc",
    body_name="European Cybersecurity Competence Centre",
    acronym="ECCC", tag="v2-eccc",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the ECCC news listing.",
         "extra": "News from the European Cybersecurity Competence Centre on funding, "
                  "the National Coordination Centres and the cybersecurity community."},
        {"item_type": "call", "slug": "calls", "noun": "calls",
         "source": "the ECCC funding-opportunities listings (calls for proposals and "
                   "calls for expressions of interest).",
         "extra": "Open ECCC funding calls under Digital Europe and Horizon Europe "
                  "cybersecurity."},
        {"item_type": "governing_board", "slug": "governing-board", "noun": "Governing Board members",
         "source": "the ECCC Governing Board membership table.",
         "extra": "The members and alternates of the ECCC Governing Board, by Member "
                  "State, with their role. Filter with q (e.g. a country)."},
        {"item_type": "ncc", "slug": "nccs", "noun": "National Coordination Centres",
         "source": "the ECCC list of confirmed National Coordination Centres.",
         "extra": "The designated National Coordination Centre in each Member State (the "
                  "national body that channels ECCC funding and coordinates the community). "
                  "Filter with q (e.g. a country or an organisation name)."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of ECCC about, strategic-agenda and funding pages.",
         "extra": "Snapshots of the ECCC's about-us, strategic-agenda and "
                  "funding-opportunities pages."},
    ],
)
