"""
/api/v1/discover/eurio — EURIO research-information discovery endpoints.

Phase 7 of docs/applications/euvoc.md. Tenderator companion: when a TED
tender lives under a Horizon Europe call, partners can pivot to the
related research projects + consortium + deliverables here.

Honesty disclaimer: the EURIO live endpoint is not yet configured (see
services/api_clients/eurio_sparql_client.py). Until it is, every
endpoint returns an empty result set with a `note` field flagging the
gap. The wiring is otherwise complete — flipping `EURIO_ENDPOINT_URL`
on activates live data with no API change.

Endpoints:
    GET /api/v1/discover/eurio/projects?topic=...&framework=...
    GET /api/v1/discover/eurio/projects/{uri}/consortium
    GET /api/v1/discover/eurio/projects/{uri}/deliverables
    GET /api/v1/discover/eurio/projects/{uri}/funding
    GET /api/v1/discover/eurio/organisations/{name}/projects
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from models.user import User
from services.api_clients.eurio_sparql_client import (
    DEFAULT_EURIO_ENDPOINT,
    EURIOClient,
)

from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/discover/eurio", tags=["v1-discover-eurio"])

# Endpoint URL is read from env at request time so an ops change doesn't
# require a code deploy.
_ENV_KEY = "EURIO_SPARQL_ENDPOINT"


def _client() -> EURIOClient:
    return EURIOClient(endpoint_url=os.environ.get(_ENV_KEY, DEFAULT_EURIO_ENDPOINT))


# ----------------------------- response shapes -----------------------------


class EURIOPayload(BaseModel):
    note: Optional[str] = None
    label: str
    fetched_at: str
    results: list[dict] = Field(default_factory=list)
    count: int = 0


# ----------------------------- endpoints -----------------------------


@router.get(
    "/projects",
    response_model=PaginatedResponse[dict],
    summary="Find Horizon Europe / FP7 / H2020 projects by topic",
    description=(
        "EURIO project lookup by free-text topic + optional framework "
        "programme. Returns empty + a `note` field while the EURIO live "
        "endpoint is being identified (see service docstring)."
    ),
)
async def find_projects(
    request: Request,
    topic: str = Query(..., min_length=2),
    framework: Optional[str] = Query(None, description="Horizon Europe / H2020 / FP7 / Erasmus+"),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[dict]:
    async with _client() as c:
        payload = await c.find_projects_by_topic(topic, framework=framework, limit=limit)
    return build_envelope(
        items=payload.get("results", []),
        total=len(payload.get("results", [])),
        page=1,
        limit=limit,
        coverage_complete=False,
        op_core_title="EURIO research-projects listing",
        op_core_type="EU research projects",
        op_core_identifier=str(request.url),
        op_core_referenced_by=[
            "https://brubru.beresol.eu/api/v1/discover/cellar/eurovoc",
        ],
    )


@router.get(
    "/projects/{project_uri:path}/consortium",
    response_model=EURIOPayload,
    summary="Project consortium (organisations + roles)",
)
async def project_consortium(
    request: Request,
    project_uri: str,
    user: User = Depends(api_user_with_rate_limit),
) -> EURIOPayload:
    async with _client() as c:
        return EURIOPayload(**await c.get_project_consortium(project_uri))


@router.get(
    "/projects/{project_uri:path}/deliverables",
    response_model=EURIOPayload,
    summary="Project deliverables",
)
async def project_deliverables(
    request: Request,
    project_uri: str,
    user: User = Depends(api_user_with_rate_limit),
) -> EURIOPayload:
    async with _client() as c:
        return EURIOPayload(**await c.get_project_deliverables(project_uri))


@router.get(
    "/projects/{project_uri:path}/funding",
    response_model=EURIOPayload,
    summary="Project funding breakdown",
)
async def project_funding(
    request: Request,
    project_uri: str,
    user: User = Depends(api_user_with_rate_limit),
) -> EURIOPayload:
    async with _client() as c:
        return EURIOPayload(**await c.get_project_funding_breakdown(project_uri))


@router.get(
    "/organisations/{org_name}/projects",
    response_model=EURIOPayload,
    summary="Projects an organisation has participated in",
)
async def org_projects(
    request: Request,
    org_name: str,
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(api_user_with_rate_limit),
) -> EURIOPayload:
    async with _client() as c:
        return EURIOPayload(**await c.find_projects_by_organisation(org_name, limit=limit))
