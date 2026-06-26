"""/api/v2/europes-rail — Europe's Rail Joint Undertaking (api_euratom_ju.md)."""
from __future__ import annotations
from ..economy_endpoints import make_single_body_folder
router = make_single_body_folder(
    body_code="rail", prefix="/europes-rail", body_name="Europe's Rail Joint Undertaking", acronym="Europe's Rail", tag="v2-europes-rail",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items", "source": "the Europe's Rail JU news listing.",
         "extra": "News from the Europe's Rail JU on railway research and innovation, its flagship projects, deliverables and calls."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages", "source": "a curated set of Europe's Rail about, projects and reference-document pages.",
         "extra": "Snapshots of the JU's about, members and governance pages, its rail projects and solutions catalogue, the Shift2Rail projects, the innovation and system pillars, the deployment group, calls for proposals and reference documents (key documents, annual activity report, annual work plan and budget)."},
    ],
)
