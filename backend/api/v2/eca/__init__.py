"""
/api/v2/eca — European Court of Auditors (api_eca.md).

The EU's external auditor, its own folder. Resources under the folder prefix:
/api/v2/eca/{news,publications,events,topics}. eca.europa.eu is a SharePoint SPA,
so it is read through Playwright on the cron path.

Reads from economy_items (body row seeded by migration 168); 5 mandatory
datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="eca", prefix="/eca",
    body_name="European Court of Auditors",
    acronym="ECA", tag="v2-eca",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the ECA all-news listing.",
         "extra": "News from the European Court of Auditors on its audits, reports and "
                  "institutional activity."},
        {"item_type": "publication", "slug": "publications", "noun": "publications",
         "source": "the ECA publications search.",
         "extra": "The ECA's audit output: special reports, reviews, opinions and the "
                  "annual reports on the EU budget, each with its number, title and "
                  "publication date. Filter with q (e.g. a policy area or a report "
                  "number)."},
        {"item_type": "event", "slug": "events", "noun": "events",
         "source": "the ECA events listing.",
         "extra": "Conferences, panel discussions and other events hosted by the ECA."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of ECA about and documents-and-research pages.",
         "extra": "Snapshots of the ECA's about pages (mission, governance, organisation, "
                  "legal framework, history, what we do, the EU finances, international "
                  "and institutional relations) and its documents-and-research pages "
                  "(topics, multiple reports, annual activity reports, the journal)."},
    ],
)
