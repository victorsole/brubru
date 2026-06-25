"""
/api/v2/epso — European Personnel Selection Office (api_ec.md).

The interinstitutional EU recruitment office, its own folder. Resources under the
folder prefix: /api/v2/epso/{news,topics}. eu-careers.europa.eu is a server-rendered
Drupal site reachable with plain requests, so it runs on the standard cron path.

Reads from economy_items (body row seeded by migration 163); 5 mandatory
datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="epso", prefix="/epso",
    body_name="European Personnel Selection Office",
    acronym="EPSO", tag="v2-epso",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the EPSO / EU Careers news listing.",
         "extra": "News from EPSO on open competitions and selection procedures: "
                  "publication of results, test sessions, new competitions and candidate "
                  "information, each with its EPSO reference number where published."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of EPSO about, EU-careers, selection-process and "
                   "job-profile pages.",
         "extra": "Snapshots of EPSO's about, mission, vision and values pages, the "
                  "why-an-EU-career and salary/benefits pages, the selection process "
                  "(permanent competitions, contract-staff procedures, EPSO tests, how "
                  "to apply), equal opportunities, traineeships and the CAST permanent "
                  "job profiles (law, finance, ICT, translation, human resources and "
                  "more)."},
    ],
)
