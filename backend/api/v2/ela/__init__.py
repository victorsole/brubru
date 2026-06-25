"""
/api/v2/ela — European Labour Authority (api_socjust.md).

The EU's labour-mobility authority, its own folder. Resources under the folder
prefix: /api/v2/ela/{news}. Drupal site (ela.europa.eu), scraped with plain
requests (no WAF). The events listing mixes in cross-language related-event
widgets with no body, so news only.

Reads from economy_items (body row in migration 152); 5 mandatory datapoints.
Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="ela", prefix="/ela",
    body_name="European Labour Authority",
    acronym="ELA", tag="v2-ela",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the ELA news listing.",
         "extra": "News from the European Labour Authority on labour mobility, "
                  "posting of workers, social-security coordination, EURES and joint "
                  "inspections."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of ELA policy-topic and activity pages.",
         "extra": "Snapshots of ELA's reference pages: its policy topics (posting of "
                  "workers, social-security coordination, international road transport, "
                  "undeclared work) and its activities (EURES, concerted and joint "
                  "inspections, cooperation between member states, mediation, analysis "
                  "and risk assessment)."},
    ],
)
