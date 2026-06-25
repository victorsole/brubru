"""/api/v2/chips — Chips Joint Undertaking (api_euratom_ju.md)."""
from __future__ import annotations
from ..economy_endpoints import make_single_body_folder
router = make_single_body_folder(
    body_code="chips", prefix="/chips", body_name="Chips Joint Undertaking", acronym="Chips", tag="v2-chips",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items", "source": "the Chips JU news listing.",
         "extra": "News from the Chips JU on its calls, pilot lines and Europes semiconductor ecosystem under the Chips Act."},
        {"item_type": "event", "slug": "events", "noun": "events", "source": "the Chips JU events listing.",
         "extra": "Info days, workshops and symposia organised by the Chips JU."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages", "source": "a curated set of Chips JU about, governance and documents pages.",
         "extra": "Snapshots of the JU's about, governance and members, multiannual work programme (MAWP), Chips for Europe initiative, the ECS programme, general documents and publications."},
    ],
)
