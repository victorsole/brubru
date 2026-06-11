"""
/api/v2/euipo — European Union Intellectual Property Office.

Single-market / intellectual-property EU agency (api_market.md), its own folder.
Resources under the folder prefix: /api/v2/euipo/{news,events}. EUIPO Observatory
publications are served from a separate CMS with no public search index, so news
+ events only.

Reads from economy_items (migrations 119 + 120); 5 mandatory datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="euipo", prefix="/euipo",
    body_name="European Union Intellectual Property Office",
    acronym="EUIPO", tag="v2-euipo",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the EUIPO news index (full text included in the source).",
         "extra": "News and announcements from the European Union Intellectual Property Office on trade marks, designs and IP enforcement."},
        {"item_type": "event", "slug": "events", "noun": "events",
         "source": "the EUIPO events index.",
         "extra": "Conferences, webinars, IPforYOU sessions and DesignEuropa events, with their dates."},
        {"item_type": "trademark", "slug": "trademarks", "noun": "trade marks",
         "source": "the TMview database (EUIPO/EM office), most recent first.",
         "extra": "A bounded slice of the most recent EU trade marks from TMview — name, application "
                  "number, applicant, status, Nice classes and filing date (TMview holds millions of "
                  "EUTMs; this surfaces the latest filings). Filter with q (e.g. an applicant or mark name)."},
        # NOTE: GIView (geographical_indication) was moved to the "Geographical Indications"
        # domain (/api/v2/geographical-indications/giview), alongside the eAmbrosia registers.
    ],
)
