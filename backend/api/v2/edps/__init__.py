"""
/api/v2/edps — European Data Protection Supervisor (api_market.md).

The EU's data-protection authority, its own folder. Resources under the folder
prefix: /api/v2/edps/{news,press-releases,publications,topics}. edps.europa.eu is a
server-rendered Drupal site (plain requests).

Reads from economy_items (body row seeded by migration 172); 5 mandatory
datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="edps", prefix="/edps",
    body_name="European Data Protection Supervisor",
    acronym="EDPS", tag="v2-edps",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the EDPS news listing.",
         "extra": "News from the European Data Protection Supervisor on supervision, "
                  "opinions, technology monitoring and data-protection events."},
        {"item_type": "press_release", "slug": "press-releases", "noun": "press releases",
         "source": "the EDPS press-releases listing; bodies are extracted from the source PDFs.",
         "extra": "Press releases from the EDPS on its opinions, decisions and positions."},
        {"item_type": "publication", "slug": "publications", "noun": "publications",
         "source": "the EDPS publications (annual activity reports and factsheets); "
                   "bodies are extracted from the source PDFs.",
         "extra": "EDPS annual activity reports, factsheets and other publications."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of EDPS about, supervisory-role, work and technology pages.",
         "extra": "Snapshots of the EDPS's about pages, its supervisor and advisor roles, "
                  "its work (audits, complaints, guidelines), technology monitoring "
                  "(TechDispatch, TechSonar), the EU-institutions DPO network and its AI "
                  "work (the AI Act and artificial intelligence)."},
    ],
)
