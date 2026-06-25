"""/api/v2/esdc — European Security and Defence College (api_defence.md)."""
from __future__ import annotations
from ..economy_endpoints import make_single_body_folder
router = make_single_body_folder(
    body_code="esdc", prefix="/esdc", body_name="European Security and Defence College", acronym="ESDC", tag="v2-esdc",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items", "source": "the ESDC news RSS feed.",
         "extra": "News from the European Security and Defence College on its courses, training activities and the CSDP training network."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages", "source": "a curated set of ESDC about, network and training-configuration pages.",
         "extra": "Snapshots of the ESDC's about, mission, history, structure and network pages, its training and education and course catalogue, and its configurations (climate and security, cyber, doctoral school, missions and operations training, military Erasmus, war colleges initiative)."},
    ],
)
