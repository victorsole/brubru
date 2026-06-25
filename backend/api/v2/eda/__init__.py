"""/api/v2/eda — European Defence Agency (api_defence.md)."""
from __future__ import annotations
from ..economy_endpoints import make_single_body_folder
router = make_single_body_folder(
    body_code="eda", prefix="/eda", body_name="European Defence Agency", acronym="EDA", tag="v2-eda",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items", "source": "the EDA news listing.",
         "extra": "News from the European Defence Agency on capability development, defence research, industry engagement and the EU defence initiatives."},
        {"item_type": "publication", "slug": "publications", "noun": "publications", "source": "the EDA publications listing.",
         "extra": "EDA factsheets, reports and the defence-data publications. Filter with q (e.g. a capability area)."},
        {"item_type": "event", "slug": "events", "noun": "events", "source": "the EDA events listing.",
         "extra": "Workshops, conferences and community events organised by the EDA, with their dates."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages", "source": "a curated set of EDA what-we-do and who-we-are pages.",
         "extra": "Snapshots of the EDA's what-we-do pages (EU defence initiatives, capability development, research and technology, industry engagement, EU policies, training and exercises, enablers, support to operations) and its who-we-are pages."},
    ],
)
