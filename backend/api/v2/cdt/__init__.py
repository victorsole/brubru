"""
/api/v2/cdt — Translation Centre for the Bodies of the European Union (CdT).

The EU's interinstitutional translation agency, its own folder. Resources under the
folder prefix: /api/v2/cdt/{news,topics}. cdt.europa.eu is a server-rendered Drupal
site reachable with plain requests, so it runs on the standard cron path.

Reads from economy_items (body row seeded by migration 165); 5 mandatory
datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="cdt", prefix="/cdt",
    body_name="Translation Centre for the Bodies of the European Union",
    acronym="CdT", tag="v2-cdt",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the CdT news listing.",
         "extra": "News from the Translation Centre on its services, client network, "
                  "IATE terminology releases, management board meetings and "
                  "multilingualism initiatives."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of CdT services, about and cooperation pages.",
         "extra": "Snapshots of CdT's services (translation, terminology, audiovisual "
                  "and other language services), IATE, its story and client "
                  "cooperation, interinstitutional cooperation, the EU Agencies "
                  "Network, external language service providers, documentation and "
                  "procurement."},
    ],
)
