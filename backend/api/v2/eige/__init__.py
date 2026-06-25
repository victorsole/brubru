"""
/api/v2/eige — European Institute for Gender Equality.

EU gender-equality agency (api_socjust.md), its own folder. Resources under the
folder prefix: /api/v2/eige/{news,events,publications}.

Reads from economy_items (migration 129); 5 mandatory datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="eige", prefix="/eige",
    body_name="European Institute for Gender Equality",
    acronym="EIGE", tag="v2-eige",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the EIGE newsroom.",
         "extra": "News from the European Institute for Gender Equality on gender equality, "
                  "the Gender Equality Index, gender-based violence and gender mainstreaming."},
        {"item_type": "event", "slug": "events", "noun": "events",
         "source": "the EIGE newsroom events.",
         "extra": "Conferences, webinars and meetings hosted or co-hosted by EIGE."},
        {"item_type": "publication", "slug": "publications", "noun": "publications",
         "source": "the EIGE publications library.",
         "extra": "EIGE reports, studies, toolkits and guides on gender equality. Filter with q "
                  "(e.g. a topic such as 'gender-based violence' or 'gender mainstreaming')."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of EIGE about, gender-mainstreaming and "
                   "gender-based-violence pages.",
         "extra": "Snapshots of EIGE's about and organisation pages, its gender "
                  "mainstreaming work (what it is, policy areas, countries, good "
                  "practices, toolkits), its gender-based-violence work (focus areas, "
                  "the regulatory framework, data collection, the Istanbul Convention), "
                  "the Gender Equality Index, gender statistics and the thesaurus."},
    ],
)
