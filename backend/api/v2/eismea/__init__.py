"""
/api/v2/eismea — European Innovation Council and SMEs Executive Agency
(api_ec.md, executive agencies).

A Commission executive agency, its own folder. Resources under the folder prefix:
/api/v2/eismea/{news,events,publications,calls,topics}. eismea.ec.europa.eu runs on
the EU ECL stack and is reachable with plain requests, so it runs on the standard
cron path.

Reads from economy_items (body row seeded by migration 160); 5 mandatory
datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="eismea", prefix="/eismea",
    body_name="European Innovation Council and SMEs Executive Agency",
    acronym="EISMEA", tag="v2-eismea",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the EISMEA news listing.",
         "extra": "News from EISMEA on the European Innovation Council, the European "
                  "Innovation Ecosystems, the Single Market Programme and the I3 "
                  "instrument, plus calls and project announcements."},
        {"item_type": "event", "slug": "events", "noun": "events",
         "source": "the EISMEA events listing.",
         "extra": "Forums, info days and events organised by EISMEA, with their dates."},
        {"item_type": "publication", "slug": "publications", "noun": "publications",
         "source": "the EISMEA documents library; bodies are extracted from the source PDFs.",
         "extra": "EISMEA work programmes, annual activity reports, annual accounts and "
                  "other corporate documents, by date."},
        {"item_type": "call", "slug": "calls", "noun": "calls for proposals",
         "source": "the EISMEA calls-for-proposals listing.",
         "extra": "Open EU funding calls for proposals managed by EISMEA across the "
                  "European Innovation Council, European Innovation Ecosystems, Single "
                  "Market Programme and I3 instrument."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of EISMEA about, programme and funding pages.",
         "extra": "Snapshots of EISMEA's about page, its programmes (European Innovation "
                  "Council, European Innovation Ecosystems, Single Market Programme, the "
                  "I3 instrument), its funding-opportunities page and the legacy EASME "
                  "documents."},
    ],
)
