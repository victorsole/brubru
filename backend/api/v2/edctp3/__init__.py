"""/api/v2/edctp3 — Global Health EDCTP3 Joint Undertaking (api_euratom_ju.md)."""
from __future__ import annotations
from ..economy_endpoints import make_single_body_folder
router = make_single_body_folder(
    body_code="edctp3", prefix="/edctp3", body_name="Global Health EDCTP3 Joint Undertaking", acronym="EDCTP3", tag="v2-edctp3",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the Global Health EDCTP3 JU news listing.",
         "extra": "News from the Global Health EDCTP3 JU on its calls, funded clinical research and EU-Africa partnership."},
        {"item_type": "event", "slug": "events", "noun": "events",
         "source": "the Global Health EDCTP3 JU events listing.",
         "extra": "Conferences, the EDCTP Forum and other events."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of EDCTP3 about, funding and results pages.",
         "extra": "Snapshots of the JU's who-we-are, what-we-do, what-we-fund, governance, funding (calls, research priorities, prizes), projects and results-and-insights pages."},
    ],
)
