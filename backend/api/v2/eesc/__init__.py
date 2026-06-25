"""
/api/v2/eesc — European Economic and Social Committee (api_eesc_cor_ombud.md).

The EU's organised-civil-society consultative body, its own folder. Resources under
the folder prefix: /api/v2/eesc/{news,press-releases,opinions,events,topics}.
eesc.europa.eu is a server-rendered Drupal site (plain requests).

Reads from economy_items (body row seeded by migration 169); 5 mandatory
datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="eesc", prefix="/eesc",
    body_name="European Economic and Social Committee",
    acronym="EESC", tag="v2-eesc",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the EESC news listing.",
         "extra": "News from the European Economic and Social Committee on its opinions, "
                  "plenary sessions and civil-society initiatives."},
        {"item_type": "press_release", "slug": "press-releases", "noun": "press releases",
         "source": "the EESC press-releases listing.",
         "extra": "Press releases from the EESC on adopted opinions, resolutions and "
                  "positions."},
        {"item_type": "opinion", "slug": "opinions", "noun": "opinions",
         "source": "the EESC opinions listing.",
         "extra": "The EESC's adopted opinions and information reports on EU legislative "
                  "proposals and own-initiative topics. Filter with q (e.g. a policy area "
                  "or a file name)."},
        {"item_type": "event", "slug": "events", "noun": "events",
         "source": "the EESC events listing.",
         "extra": "Conferences, hearings, webinars and other events organised by the EESC."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of EESC about, members, sections and policy-area pages.",
         "extra": "Snapshots of the EESC's about and members-groups pages (employers, "
                  "workers, civil-society groups), its sections (ECO, INT, TEN, SOC, NAT, "
                  "REX, CCMI) and observatories, and its 25 policy areas."},
    ],
)
