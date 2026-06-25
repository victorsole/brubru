"""/api/v2/cbe — Circular Bio-based Europe Joint Undertaking (api_euratom_ju.md)."""
from __future__ import annotations
from ..economy_endpoints import make_single_body_folder
router = make_single_body_folder(
    body_code="cbe", prefix="/cbe", body_name="Circular Bio-based Europe Joint Undertaking", acronym="CBE", tag="v2-cbe",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items", "source": "the CBE JU news listing.",
         "extra": "News from the Circular Bio-based Europe JU on its calls, bio-based projects and the circular bioeconomy."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages", "source": "a curated set of CBE about, governance, bioeconomy and funding pages.",
         "extra": "Snapshots of the JU's organisation, mission and objectives, governance, team and values, about-bioeconomy, why-a-joint-undertaking, projects, achievements, open calls, how to apply for funding and reference documents."},
    ],
)
