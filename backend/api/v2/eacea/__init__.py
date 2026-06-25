"""
/api/v2/eacea — European Education and Culture Executive Agency
(api_ec.md, executive agencies).

A Commission executive agency, its own folder. Resources under the folder prefix:
/api/v2/eacea/{news,events,publications,topics}. www.eacea.ec.europa.eu runs on
the EU ECL stack and is reachable with plain requests, so it runs on the standard
cron path.

Reads from economy_items (body row seeded by migration 158); 5 mandatory
datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="eacea", prefix="/eacea",
    body_name="European Education and Culture Executive Agency",
    acronym="EACEA", tag="v2-eacea",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the EACEA news listing.",
         "extra": "News from EACEA on the programmes it manages: Erasmus+, Creative "
                  "Europe, the European Solidarity Corps, CERV and Erasmus Mundus, plus "
                  "calls, info sessions and vacancy notices."},
        {"item_type": "event", "slug": "events", "noun": "events",
         "source": "the EACEA events listing.",
         "extra": "Info sessions, webinars and events organised by EACEA, with their "
                  "dates. EACEA is grants-led, so the events feed is sparse."},
        {"item_type": "publication", "slug": "publications", "noun": "publications",
         "source": "the EACEA document register (annual work programmes and activity "
                   "reports); bodies are extracted from the source PDFs.",
         "extra": "EACEA's annual work programmes and activity reports, by year."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of EACEA about, grants and scholarships pages.",
         "extra": "Snapshots of EACEA's about, platforms, transparency and document "
                  "register pages, its grants pages (how to get a grant, the 2021-2027 "
                  "programmes, managing your grant) and its scholarships pages (the "
                  "Erasmus Mundus catalogue, Intra-Africa scholarships)."},
    ],
)
