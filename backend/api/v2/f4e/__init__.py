"""/api/v2/f4e — Fusion for Energy (api_euratom_ju.md)."""
from __future__ import annotations
from ..economy_endpoints import make_single_body_folder
router = make_single_body_folder(
    body_code="f4e", prefix="/f4e", body_name="Fusion for Energy", acronym="F4E", tag="v2-f4e",
    resources=[
        {"item_type": "press_release", "slug": "press-releases", "noun": "press releases", "source": "the F4E press-releases archive (PDF list).",
         "extra": "Fusion for Energy press releases on ITER components, contracts, milestones and the European fusion supply chain (English copies; the PDF is linked). Filter with q (e.g. ITER or a component)."},
        {"item_type": "publication", "slug": "publications", "noun": "publications", "source": "the F4E publications archive (PDF list).",
         "extra": "F4E factsheets, posters, brochures and reports on ITER and fusion (the PDF is linked)."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages", "source": "a curated set of F4E about, fusion-explainer, ITER and governance pages.",
         "extra": "Snapshots of F4E's mission and values, what-is-fusion and merits-of-fusion explainers, developing fusion, ITER and the device, the story so far, governance and committees, and how to get involved."},
    ],
)
