"""
/api/v2/cepol — European Union Agency for Law Enforcement Training (api_socjust.md).

The EU agency for police training, its own folder. Resources under the folder
prefix: /api/v2/cepol/{news,topics}. cepol.europa.eu is a JS-rendered site that
blocks the default crawler UA, so it is fed through Playwright on the local
refresh (not the Railway cron).

Reads from economy_items (body row seeded by migration 154); 5 mandatory
datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="cepol", prefix="/cepol",
    body_name="European Union Agency for Law Enforcement Training",
    acronym="CEPOL", tag="v2-cepol",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the CEPOL newsroom listing.",
         "extra": "News from CEPOL on law-enforcement training courses, the exchange "
                  "programme, joint operations support, research conferences and "
                  "cooperation with EU agencies and partner countries."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of CEPOL thematic-area, training and "
                   "international-cooperation pages.",
         "extra": "Snapshots of CEPOL's thematic areas (counter-terrorism, cybercrime, "
                  "serious and organised crime, fundamental rights and data protection, "
                  "public order, leadership), its training and education portfolio "
                  "(learning portfolio, LEEd, knowledge centres, EMPACT, quality "
                  "standards) and its international-cooperation programmes (CT INFLOW, "
                  "EuroMed, TOPCOP, WB PaCT, EU4SEC Moldova)."},
    ],
)
