"""/api/v2/ihi — Innovative Health Initiative Joint Undertaking (api_euratom_ju.md). Playwright-fed (TLS chain)."""
from __future__ import annotations
from ..economy_endpoints import make_single_body_folder
router = make_single_body_folder(
    body_code="ihi", prefix="/ihi", body_name="Innovative Health Initiative Joint Undertaking", acronym="IHI", tag="v2-ihi",
    resources=[
        {"item_type": "topic", "slug": "topics", "noun": "topic pages", "source": "a curated set of IHI about, funding and projects pages.",
         "extra": "Snapshots of the JU's about pages (mission and objectives, research and innovation agenda, funding model, who we are, history, IMI-IHI, plans and finances), apply-for-funding (open calls, future opportunities) and projects and results pages."},
    ],
)
