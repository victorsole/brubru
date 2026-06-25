"""
/api/v2/cinea — European Climate, Infrastructure and Environment Executive Agency
(api_ec.md, executive agencies).

A Commission executive agency, its own folder. Resources under the folder prefix:
/api/v2/cinea/{news,events,topics}. cinea.ec.europa.eu runs on the EU ECL stack
and is reachable with plain requests, so it runs on the standard cron path.

Reads from economy_items (body row seeded by migration 157); 5 mandatory
datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="cinea", prefix="/cinea",
    body_name="European Climate, Infrastructure and Environment Executive Agency",
    acronym="CINEA", tag="v2-cinea",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the CINEA news listing.",
         "extra": "News from CINEA on the funding programmes it manages: the Connecting "
                  "Europe Facility (energy and transport), Horizon Europe energy, the "
                  "LIFE programme, the Innovation and Modernisation Funds and Green Assist."},
        {"item_type": "event", "slug": "events", "noun": "events",
         "source": "the CINEA events listing.",
         "extra": "Info days, webinars, calls briefings and conferences organised by "
                  "CINEA, with their dates."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of CINEA about, programme and funding pages.",
         "extra": "Snapshots of CINEA's about, mission and key-documents pages, its "
                  "programmes (CEF Energy, Horizon Europe energy supply, the Renewable "
                  "Energy Financing Mechanism, LIFE clean-energy transition), its "
                  "funding opportunities (calls for proposals and tenders, find your "
                  "funding programme) and the Green Assist advisory service."},
    ],
)
