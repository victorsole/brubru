"""
/api/v2/euda — European Union Drugs Agency (formerly EMCDDA).

EU drugs agency (api_health.md), its own folder. Resources under the folder
prefix: /api/v2/euda/{publications}.

Reads from economy_items (migration 128); 5 mandatory datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="euda", prefix="/euda",
    body_name="European Union Drugs Agency",
    acronym="EUDA", tag="v2-euda",
    resources=[
        {"item_type": "publication", "slug": "publications",
         "noun": "publications",
         "source": "the EUDA publications library.",
         "extra": "The EUDA's reference publications on the drugs phenomenon — the European Drug "
                  "Report, EU Drug Markets analyses, drug-profile and health-response guides, "
                  "country and technical reports. Each entry carries the title, publication type "
                  "and the publication page. Filter with q (e.g. a topic such as 'cocaine' or a "
                  "report series such as 'European Drug Report')."},
    ],
)
