"""/api/v2/euratom — Euratom Supply Agency (api_euratom_ju.md)."""
from __future__ import annotations
from ..economy_endpoints import make_single_body_folder
router = make_single_body_folder(
    body_code="euratom", prefix="/euratom", body_name="Euratom Supply Agency", acronym="Euratom-SA", tag="v2-euratom",
    resources=[
        {"item_type": "publication", "slug": "publications", "noun": "publications",
         "source": "the Euratom Supply Agency publications (annual and quarterly reports).",
         "extra": "ESA annual reports, quarterly reports and other publications on the nuclear-materials market."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of Euratom Supply Agency activities and about pages.",
         "extra": "Snapshots of the ESA's activities (contract management, the market observatory, supply of medical radioisotopes) and its about pages (legal basis, governance, organisation, planning and reporting)."},
    ],
)
