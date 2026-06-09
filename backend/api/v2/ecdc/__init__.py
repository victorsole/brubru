"""
/api/v2/ecdc — European Centre for Disease Prevention and Control.

EU health agency (api_health.md), its own folder. Resources under the folder
prefix: /api/v2/ecdc/{news,publications}. ECDC has no separate events feed.

Reads from economy_items (migrations 119 + 121); 5 mandatory datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="ecdc", prefix="/ecdc",
    body_name="European Centre for Disease Prevention and Control",
    acronym="ECDC", tag="v2-ecdc",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the ECDC news search feed plus the detail pages.",
         "extra": "News and press releases from the European Centre for Disease Prevention and Control."},
        {"item_type": "publication", "slug": "publications", "noun": "publications",
         "source": "the ECDC publications search feed.",
         "extra": "Surveillance reports, risk assessments, threat reports and guidance from ECDC."},
        {"item_type": "surveillance_topic", "slug": "surveillance", "noun": "surveillance topics",
         "source": "the ECDC Surveillance Atlas of Infectious Diseases (REST API).",
         "extra": "Catalogue of the infectious diseases under EU surveillance — each with its Atlas "
                  "link and the REST API for the case figures by country and period. The Atlas holds "
                  "time-series surveillance data, so this is a catalogue of topics, not the numbers."},
    ],
)
