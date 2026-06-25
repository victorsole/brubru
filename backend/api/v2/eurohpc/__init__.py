"""/api/v2/eurohpc — European High Performance Computing Joint Undertaking (api_euratom_ju.md)."""
from __future__ import annotations
from ..economy_endpoints import make_single_body_folder
router = make_single_body_folder(
    body_code="eurohpc", prefix="/eurohpc", body_name="European High Performance Computing Joint Undertaking", acronym="EuroHPC", tag="v2-eurohpc",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the EuroHPC JU press releases.",
         "extra": "News and press releases from the EuroHPC JU on its supercomputers, AI factories, quantum computers and calls."},
        {"item_type": "event", "slug": "events", "noun": "events",
         "source": "the EuroHPC JU events listing.",
         "extra": "Events organised by the EuroHPC JU."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of EuroHPC about, AI-factories, supercomputers and quantum pages.",
         "extra": "Snapshots of the JU's about and governance pages, its AI factories and AI gigafactories, its supercomputers (access calls, awarded projects), quantum technologies and research-innovation calls."},
    ],
)
