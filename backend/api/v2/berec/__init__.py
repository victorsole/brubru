"""
/api/v2/berec — Body of European Regulators for Electronic Communications.

One of the single-market / digital EU agencies (api_market.md), each in its own
folder. Resources sit directly under the folder prefix:
  /api/v2/berec/{news,publications,events}

Reads from economy_items (migrations 119 + 120); 5 mandatory datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="berec", prefix="/berec",
    body_name="Body of European Regulators for Electronic Communications",
    acronym="BEREC", tag="v2-berec",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the BEREC latest-news and press-releases listings plus the detail pages.",
         "extra": "News and press releases from the Body of European Regulators for Electronic Communications."},
        {"item_type": "publication", "slug": "publications", "noun": "publications",
         "source": "the BEREC publications listing.",
         "extra": "Reports, work programmes, opinions and guidelines from BEREC."},
        {"item_type": "event", "slug": "events", "noun": "events",
         "source": "the BEREC events listing.",
         "extra": "Plenary meetings, workshops, public debriefings and stakeholder events, with their dates."},
    ],
)
