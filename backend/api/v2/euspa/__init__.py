"""
/api/v2/euspa — European Union Agency for the Space Programme (api_socjust.md).

The EU's space-programme agency (Galileo, EGNOS, Copernicus support), its own
folder. Resources under the folder prefix: /api/v2/euspa/{news,publications,events}.
Drupal site (euspa.europa.eu), scraped with plain requests (no WAF).

Reads from economy_items (body row in migration 151); 5 mandatory datapoints.
Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="euspa", prefix="/euspa",
    body_name="European Union Agency for the Space Programme",
    acronym="EUSPA", tag="v2-euspa",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the EUSPA newsroom (news and press releases).",
         "extra": "News and press releases from the EU Agency for the Space "
                  "Programme, covering Galileo, EGNOS, Copernicus, secure connectivity "
                  "and the EU space market."},
        {"item_type": "publication", "slug": "publications", "noun": "resources",
         "source": "the EUSPA publications and multimedia resources.",
         "extra": "Reports, brochures, market reports and other resources published "
                  "by EUSPA."},
        {"item_type": "event", "slug": "events", "noun": "events",
         "source": "the EUSPA events listing.",
         "extra": "Conferences, forums, webinars and user-consultation events "
                  "organised or attended by EUSPA."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of EUSPA space-programme and industry-sector pages.",
         "extra": "Snapshots of EUSPA's reference pages: the EU space-programme "
                  "components (Galileo, EGNOS, Copernicus, secure SatCom, space "
                  "situational awareness) and the industry sectors it serves "
                  "(agriculture, aviation and drones, maritime, rail, energy, "
                  "emergency management, insurance and finance and more)."},
    ],
)
