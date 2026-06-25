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
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the EEA newsroom (Plone REST API).",
         "extra": "News and announcements from the European Environment Agency."},
        {"item_type": "event", "slug": "events", "noun": "events",
         "source": "the EEA newsroom events (Plone REST API).",
         "extra": "Conferences, webinars and meetings hosted or co-hosted by the European "
                  "Environment Agency."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of EEA about and in-depth thematic pages.",
         "extra": "Snapshots of the EEA's about pages and its in-depth thematic pages "
                  "across air pollution, biodiversity, climate change mitigation and "
                  "adaptation, the circular economy, energy, water, soil, land use, "
                  "transport, nature protection, sustainable finance and more."},
    ],
)
