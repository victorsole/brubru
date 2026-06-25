"""/api/v2/clean-aviation — Clean Aviation Joint Undertaking (api_euratom_ju.md)."""
from __future__ import annotations
from ..economy_endpoints import make_single_body_folder
router = make_single_body_folder(
    body_code="aviation", prefix="/clean-aviation", body_name="Clean Aviation Joint Undertaking", acronym="Clean Aviation", tag="v2-clean-aviation",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items", "source": "the Clean Aviation JU news-and-events listing.",
         "extra": "News, articles and podcasts from the Clean Aviation JU on low-emission aircraft research, calls, members and projects."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages", "source": "a curated set of Clean Aviation about, members, calls and research pages.",
         "extra": "Snapshots of the JU's about and who-we-are pages, governance, members, calls (for proposals), research and innovation, projects, energy-efficiency and emission-reduction work, reference documents and success stories."},
    ],
)
