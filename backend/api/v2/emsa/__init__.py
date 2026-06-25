"""
/api/v2/emsa — European Maritime Safety Agency (api_socjust.md).

The EU's maritime safety agency, its own folder. Resources under the folder
prefix: /api/v2/emsa/{news,publications}. FlexiContent/Joomla site
(emsa.europa.eu), scraped with plain requests (no WAF). Events are only landing
pages with no dated listing, so news + publications only.

Reads from economy_items (body row in migration 150); 5 mandatory datapoints.
Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="emsa", prefix="/emsa",
    body_name="European Maritime Safety Agency",
    acronym="EMSA", tag="v2-emsa",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the EMSA newsroom (latest news).",
         "extra": "News from the European Maritime Safety Agency on ship safety, "
                  "pollution response, maritime surveillance and the digitalisation "
                  "of shipping."},
        {"item_type": "publication", "slug": "publications", "noun": "reports",
         "source": "the EMSA publications listing (reports).",
         "extra": "Reports and studies published by EMSA, including seafarer "
                  "statistics, pollution-response activity reports and technical "
                  "studies on maritime safety and sustainability."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of EMSA thematic and operational-system pages.",
         "extra": "Snapshots of EMSA's reference pages: its work areas (ship safety, "
                  "accident investigation, pollution response, maritime surveillance, "
                  "earth observation and RPAS) and its operational systems "
                  "(SafeSeaNet, LRIT, the European Maritime Single Window, Copernicus, "
                  "CISE)."},
    ],
)
