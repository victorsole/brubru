"""
/api/v2/edpb — European Data Protection Board (api_market.md).

The EU's GDPR-consistency body, its own folder. Resources under the folder prefix:
/api/v2/edpb/{news,documents,public-consultations,topics}. edpb.europa.eu is a
server-rendered Drupal site (plain requests).

Reads from economy_items (body row seeded by migration 173); 5 mandatory datapoints.
Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="edpb", prefix="/edpb",
    body_name="European Data Protection Board",
    acronym="EDPB", tag="v2-edpb",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the EDPB news listing.",
         "extra": "News from the European Data Protection Board on GDPR guidance, "
                  "decisions and coordination of the national data-protection authorities."},
        {"item_type": "document", "slug": "documents", "noun": "documents",
         "source": "the EDPB documents listing.",
         "extra": "The EDPB's adopted opinions, guidelines, recommendations and binding "
                  "decisions on the GDPR. Filter with q (e.g. a topic or a document number)."},
        {"item_type": "public_consultation", "slug": "public-consultations",
         "noun": "public consultations",
         "source": "the EDPB public-consultations listing.",
         "extra": "Open EDPB public consultations on draft guidelines and recommendations, "
                  "with their deadlines where published."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of EDPB about, GDPR-topic and register pages.",
         "extra": "Snapshots of the EDPB's about page, its GDPR topics (key concepts, "
                  "accountability tools, cooperation and enforcement, AI and technology, "
                  "international transfers, security and data breaches, police and justice, "
                  "specific domains) and its registers."},
    ],
)
