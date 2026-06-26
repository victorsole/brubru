"""/api/v2/sns — Smart Networks and Services Joint Undertaking (api_euratom_ju.md)."""
from __future__ import annotations
from ..economy_endpoints import make_single_body_folder
router = make_single_body_folder(
    body_code="sns", prefix="/sns", body_name="Smart Networks and Services Joint Undertaking", acronym="SNS", tag="v2-sns",
    resources=[
        {"item_type": "publication", "slug": "publications", "noun": "publications", "source": "the SNS JU publications and journals (PDF list).",
         "extra": "SNS JU white papers, brochures, the SNS journals and other publications on 5G/6G smart networks and services (the PDF is linked). Filter with q (e.g. 6G)."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages", "source": "a curated set of SNS JU about, governance and funding pages.",
         "extra": "Snapshots of the SNS JU's missions and objectives, governance, team, procurement, integrity, current and open calls for proposals, proposing a project, the interactive project map, key achievements and reference documents."},
    ],
)
