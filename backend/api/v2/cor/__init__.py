"""
/api/v2/cor — European Committee of the Regions (api_eesc_cor_ombud.md).

The EU's assembly of regional and local representatives, its own folder. Resources
under the folder prefix: /api/v2/cor/{news,opinions,topics}. cor.europa.eu is a
server-rendered site (plain requests).

Reads from economy_items (body row seeded by migration 170); 5 mandatory
datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="cor", prefix="/cor",
    body_name="European Committee of the Regions",
    acronym="CoR", tag="v2-cor",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the CoR all-news-and-press-releases listing.",
         "extra": "News and press releases from the European Committee of the Regions on "
                  "its opinions, plenary sessions and regional and local initiatives."},
        {"item_type": "opinion", "slug": "opinions", "noun": "opinions",
         "source": "the CoR opinions listing.",
         "extra": "The CoR's adopted opinions on EU legislation with a territorial impact. "
                  "Filter with q (e.g. a policy area or a file name)."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of CoR about, members, commission and priority pages.",
         "extra": "Snapshots of the CoR's about and members pages, its six commissions "
                  "(CIVEX, COTER, ECON, ENVE, NAT, SEDEC), its 2025-2030 priorities "
                  "(cohesion, resilience, proximity) and its studies, networks and "
                  "working groups."},
    ],
)
