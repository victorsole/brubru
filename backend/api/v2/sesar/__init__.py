"""/api/v2/sesar — SESAR 3 Joint Undertaking (api_euratom_ju.md)."""
from __future__ import annotations
from ..economy_endpoints import make_single_body_folder
router = make_single_body_folder(
    body_code="sesar", prefix="/sesar", body_name="SESAR 3 Joint Undertaking", acronym="SESAR 3", tag="v2-sesar",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items", "source": "the SESAR 3 JU news listing.",
         "extra": "News from the SESAR 3 JU on air-traffic-management research, the digital European sky, U-space and its calls."},
        {"item_type": "publication", "slug": "publications", "noun": "publications", "source": "the SESAR 3 JU documents listing.",
         "extra": "SESAR 3 JU policy briefs, brochures, reports and other documents. Filter with q (e.g. a topic)."},
        {"item_type": "event", "slug": "events", "noun": "events", "source": "the SESAR 3 JU events listing.",
         "extra": "Conferences, dissemination events and the SESAR Innovation Days."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages", "source": "a curated set of SESAR 3 about and thematic pages.",
         "extra": "Snapshots of the JU's discover-SESAR and approach pages, the ATM Master Plan, smart ATM, sustainability, the innovation pipeline, digitalisation, U-space, AI, virtual centres, RTS, CNS and smart airports."},
    ],
)
