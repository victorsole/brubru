"""
/api/v2/ercea — European Research Council Executive Agency
(api_ec.md, executive agencies).

A Commission executive agency, its own folder. Resources under the folder prefix:
/api/v2/ercea/{news,events,publications,topics}. ERCEA's public site is the
European Research Council site (erc.europa.eu), a Drupal build (not the standard
ec.europa.eu ECL stack), reachable with plain requests, so it runs on the standard
cron path.

Reads from economy_items (body row seeded by migration 161); 5 mandatory
datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="ercea", prefix="/ercea",
    body_name="European Research Council Executive Agency",
    acronym="ERCEA", tag="v2-ercea",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the European Research Council news listing.",
         "extra": "News from the ERC on its frontier-research grant competitions, "
                  "Scientific Council decisions, results and grantee achievements."},
        {"item_type": "event", "slug": "events", "noun": "events",
         "source": "the European Research Council events listing.",
         "extra": "Conferences, info sessions and events organised by or featuring the "
                  "ERC, with their dates."},
        {"item_type": "publication", "slug": "publications", "noun": "publications",
         "source": "the ERC publications library; bodies are extracted from the source PDFs.",
         "extra": "ERC annual reports, statistics, frontier-research booklets and other "
                  "publications, by date."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of about-ERC and apply-grant pages.",
         "extra": "Snapshots of the ERC's about pages (ERC at a glance, the President "
                  "and Scientific Council, thematic working groups, standing committees, "
                  "the executive agency, the legal basis) and its grant schemes "
                  "(Starting, Consolidator, Advanced, Proof of Concept, Synergy), plus "
                  "managing your project and projects and statistics."},
    ],
)
