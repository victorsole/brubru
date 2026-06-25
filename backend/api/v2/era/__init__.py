"""
/api/v2/era — European Union Agency for Railways (api_socjust.md).

The EU's railway authority, its own folder. Resources under the folder prefix:
/api/v2/era/{news,publications,events}. Drupal site (era.europa.eu) on the EU
Bootstrap Component Library, scraped with plain requests (no WAF).

Reads from economy_items (body row seeded); 5 mandatory datapoints.
Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="era", prefix="/era",
    body_name="European Union Agency for Railways",
    acronym="ERA", tag="v2-era",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the ERA news listing.",
         "extra": "News from the EU Agency for Railways on interoperability, safety "
                  "certification, ERTMS, the single European railway area and "
                  "vehicle authorisation."},
        {"item_type": "publication", "slug": "publications", "noun": "documents",
         "source": "the ERA library (recommendations, opinions and technical advice, "
                   "work programmes and activity reports).",
         "extra": "ERA recommendations, opinions and technical advices, work "
                  "programmes and activity reports."},
        {"item_type": "event", "slug": "events", "noun": "events",
         "source": "the ERA events and training listing.",
         "extra": "Training courses, workshops and events organised by the EU Agency "
                  "for Railways."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of ERA regulatory-domain pages.",
         "extra": "Snapshots of ERA's reference pages: the regulatory domains "
                  "(technical specifications for interoperability, ERTMS, safety "
                  "management, accidents and incidents, dangerous goods, rail "
                  "environment, railway cybersecurity, train drivers, conformity "
                  "assessment and national rules)."},
    ],
)
