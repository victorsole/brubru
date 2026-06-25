"""/api/v2/hydrogen — Clean Hydrogen Joint Undertaking (api_euratom_ju.md)."""
from __future__ import annotations
from ..economy_endpoints import make_single_body_folder
router = make_single_body_folder(
    body_code="hydrogen", prefix="/clean-hydrogen", body_name="Clean Hydrogen Joint Undertaking", acronym="Clean Hydrogen", tag="v2-hydrogen",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the Clean Hydrogen JU news and project updates.",
         "extra": "News from the Clean Hydrogen JU on its calls, projects, hydrogen valleys and the European Hydrogen Observatory."},
        {"item_type": "event", "slug": "events", "noun": "events",
         "source": "the Clean Hydrogen JU events listing.",
         "extra": "Info days, the European Hydrogen Week and other events."},
        {"item_type": "publication", "slug": "publications", "noun": "publications",
         "source": "the Clean Hydrogen JU publications.",
         "extra": "Reports, programme reviews and key documents from the Clean Hydrogen JU."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of Clean Hydrogen JU about, get-involved and knowledge pages.",
         "extra": "Snapshots of the JU's about, mission, organisation, get-involved (hydrogen valleys, international collaboration), funding and knowledge-management pages."},
    ],
)
