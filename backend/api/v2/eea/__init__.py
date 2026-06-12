"""
/api/v2/eea — European Environment Agency.

EU environment agency (api_health.md), its own folder. Resources under the folder
prefix: /api/v2/eea/{indicators}.

Reads from economy_items (migration 126); 5 mandatory datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="eea", prefix="/eea",
    body_name="European Environment Agency",
    acronym="EEA", tag="v2-eea",
    resources=[
        {"item_type": "environmental_indicator", "slug": "indicators",
         "noun": "environmental indicators",
         "source": "the EEA environmental indicators (Plone REST API).",
         "extra": "The EEA's curated environmental indicators — air, climate, biodiversity, "
                  "waste, water, energy and more. Each entry is the standing assessment of the "
                  "state of and trends in one environmental issue, with its topic and indicator-code "
                  "tags, last-update date and the indicator page. Filter with q (e.g. a topic such "
                  "as 'air pollution' or an indicator code such as AIR009)."},
    ],
)
