"""
/api/v2/eu-osha — European Agency for Safety and Health at Work.

EU health agency (api_health.md), its own folder. Resources under the folder
prefix: /api/v2/eu-osha/{news,publications,events}. Body code is 'eu_osha'.

Reads from economy_items (migrations 119 + 121); 5 mandatory datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="eu_osha", prefix="/eu-osha",
    body_name="European Agency for Safety and Health at Work",
    acronym="EU-OSHA", tag="v2-eu-osha",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the EU-OSHA highlights listing plus the detail pages.",
         "extra": "News highlights from the European Agency for Safety and Health at Work."},
        {"item_type": "publication", "slug": "publications", "noun": "publications",
         "source": "the EU-OSHA publications listing.",
         "extra": "Reports, reviews and guidance on occupational safety and health."},
        {"item_type": "event", "slug": "events", "noun": "events",
         "source": "the EU-OSHA events listing.",
         "extra": "Seminars, campaign events and exchange meetings, with their dates."},
    ],
)
