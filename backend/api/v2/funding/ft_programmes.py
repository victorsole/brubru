"""Per-programme F&T grant-call endpoints — /api/v2/funding/<slug>.

Some EU funding programmes on the Funding & Tenders Portal warrant their own
dedicated endpoint (rather than only being reachable through the generic
/ft-calls-for-proposals feed, which cannot distinguish them — see
scripts/ingest_ft_programme_calls.py). Their calls are ingested into
economy_items (body_code per programme, item_type='grant') so they inherit the
full 5-datapoint contract and appear automatically in /api/v2/funding/all.

Each programme is one register_resource() call → a list endpoint (bodies nulled)
and a detail endpoint /{item_id} (full body). Built one programme at a time:
    justice          — Justice Programme (JUST-* calls)
    innovation-fund  — Innovation Fund (INNOVFUND-* calls)
"""
from __future__ import annotations

from fastapi import APIRouter

from ..economy_endpoints import register_resource

router = APIRouter()

_SOURCE = ("the EU Funding & Tenders Portal (SEDIA search API), filtered to this "
           "programme's calls by topic-id prefix; refreshed daily (04:00 UTC).")

# slug, body_code, programme name, acronym, the "what it funds" sentence.
_PROGRAMMES = [
    ("justice", "just", "Justice Programme", "JUST",
     "It funds judicial cooperation in civil and criminal matters, judicial "
     "training (e-Justice) and access to justice."),
    ("innovation-fund", "innovfund", "Innovation Fund", "INNOVFUND",
     "It funds innovative low-carbon and net-zero technologies from EU Emissions "
     "Trading System auction revenues."),
]

for slug, body_code, body_name, acronym, extra in _PROGRAMMES:
    register_resource(
        router,
        body_code=body_code,
        item_type="grant",
        slug=slug,
        noun="funding calls",
        body_name=body_name,
        acronym=acronym,
        source=_SOURCE,
        tag="v2-funding",
        extra=extra,
    )
