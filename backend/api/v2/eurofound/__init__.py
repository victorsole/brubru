"""
/api/v2/eurofound — European Foundation for the Improvement of Living and
Working Conditions (api_socjust.md).

Eurofound's own folder. Resources under the folder prefix:
/api/v2/eurofound/{publications,topics}. The site is JS-rendered with a dead RSS
feed and an aggressive rate limit on plain requests, so its topic and
surveys-and-data reference pages are rendered through Playwright. Local refresh.

Reads from economy_items (body row in migration 153); 5 mandatory datapoints.
Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="eurofound", prefix="/eurofound",
    body_name="European Foundation for the Improvement of Living and Working Conditions",
    acronym="Eurofound", tag="v2-eurofound",
    resources=[
        {"item_type": "publication", "slug": "publications", "noun": "surveys and data tools",
         "source": "the Eurofound surveys-and-data pages.",
         "extra": "Eurofound's flagship surveys and data products: the European "
                  "Company Survey, European Quality of Life Survey, European Working "
                  "Conditions Survey, the European Restructuring Monitor, EU "
                  "PolicyWatch, the minimum-wage database and the data catalogue."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of Eurofound policy-topic pages.",
         "extra": "Snapshots of Eurofound's policy-topic pages: digitalisation, "
                  "minimum wages, gender equality, housing, restructuring, job "
                  "quality, working conditions, quality of life and industrial "
                  "relations."},
    ],
)
