"""
/api/v2/eas — European School of Administration (EAS / EUSA) (api_ec.md).

The interinstitutional EU training school, its own folder. Resources under the
folder prefix: /api/v2/eas/{publications,topics}. EUSA has no standalone website,
so its corporate documents come from the Commission strategy-documents pages
(rendered through Playwright) and its about/leadership pages from the Commission
department page; this runs on the local refresh path.

Reads from economy_items (body row seeded by migration 164); 5 mandatory
datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="eas", prefix="/eas",
    body_name="European School of Administration",
    acronym="EUSA", tag="v2-eas",
    resources=[
        {"item_type": "publication", "slug": "publications", "noun": "publications",
         "source": "the Commission strategy-documents pages filtered by the EAS "
                   "corporate body (annual activity reports and management plans).",
         "extra": "The European School of Administration's annual activity reports and "
                  "management plans, by year."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "the Commission department page and the EUSA leadership pages.",
         "extra": "Snapshots of the European School of Administration's Commission "
                  "department page (mission, role and contact) and its leadership "
                  "pages."},
    ],
)
