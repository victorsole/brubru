"""/api/v2/satcen — European Union Satellite Centre (api_defence.md). Angular SPA, Playwright-fed."""
from __future__ import annotations
from ..economy_endpoints import make_single_body_folder
router = make_single_body_folder(
    body_code="satcen", prefix="/satcen", body_name="European Union Satellite Centre", acronym="SatCen", tag="v2-satcen",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items", "source": "the SatCen news listing.",
         "extra": "News from the EU Satellite Centre on its geospatial-intelligence work, partnerships and visits."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages", "source": "a curated set of SatCen who-we-are, what-we-do and services pages.",
         "extra": "Snapshots of SatCen's mission and centre pages, its structure, its services (geospatial intelligence, Copernicus, humanitarian aid, contingency planning, critical infrastructure, military capabilities, weapons of mass destruction), training, capability development and key documents."},
    ],
)
