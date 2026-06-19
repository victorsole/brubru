"""
Tender Docs source: /api/v2/proprietary/tender-docs/*.

Backend: Brubru's funding-application template library (the section
structure + AI co-writer prompt seeds + comply targets + reference-doc
bundles shipped with the Tenderator product) plus the live cross-fetch
from a template into the EU Law Comply 53-cluster catalogue.

NATIVE: templates live in `backend/knowledge_base/funding_templates/*.json`
(committed, version-controlled). The comply cross-fetch delegates the
mapping logic to the shared helper `api.eu_law_comply.resolve_clusters_by_topic`
so v1 (Bearer JWT + tier gate) and this v2 endpoint (API-key) stay aligned.

Scope: read-only. The 6 user-scoped write endpoints on `/api/tender-files/`
(create/update/delete a personal tender_file) and the AI generator at
`/api/generate/tender-section` are NOT exposed in v2: they require a logged-in
Brubru user, not an API key, and have no third-party data-consumer use case.
"""

from fastapi import APIRouter

from . import templates as _templates
from . import comply as _comply

router = APIRouter(prefix="/tender-docs")
router.include_router(_templates.router)
router.include_router(_comply.router)
