"""
/api/v2/ombudsman — European Ombudsman (api_eesc_cor_ombud.md).

The EU's maladministration watchdog, its own folder. Resources under the folder
prefix: /api/v2/ombudsman/{news,topics}. ombudsman.europa.eu is a single-page app,
so it is read through Playwright on the cron path.

Reads from economy_items (body row seeded by migration 171); 5 mandatory
datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="ombudsman", prefix="/ombudsman",
    body_name="European Ombudsman",
    acronym="Ombudsman", tag="v2-ombudsman",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the European Ombudsman news-and-documents listing.",
         "extra": "News, press releases and decisions from the European Ombudsman on "
                  "inquiries into maladministration, transparency, access to documents "
                  "and ethics in the EU institutions."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of European Ombudsman about and work pages.",
         "extra": "Snapshots of the Ombudsman's pages on the office holder, strategy, "
                  "history, how it works, its areas of work and impact, the legal basis, "
                  "the European Network of Ombudsmen, how to make a complaint, the "
                  "strategic inquiries and top inquiries, and publications."},
    ],
)
