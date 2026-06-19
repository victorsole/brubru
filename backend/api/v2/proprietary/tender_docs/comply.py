"""
Tender Docs <-> Comply cross-fetch: /api/v2/proprietary/tender-docs/comply-clusters.

Backend: Live cross-fetch from a funding template id (+ optional funding_mode +
ethics flags) into Brubru's EU Law Comply 53-cluster catalogue. The mapping
logic lives in `api.eu_law_comply.resolve_clusters_by_topic` so v1
(`/api/eu-law-comply/by-topic-clusters`, Bearer JWT + tier gate) and this v2
endpoint (API-key auth) stay aligned: there is exactly one comply_target ->
policy_area dictionary in the codebase.

Scope: read:knowledge (Brubru knowledge layer).
"""

from __future__ import annotations

import html as _html
import logging
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse, build_envelope
from api.eu_law_comply import resolve_clusters_by_topic

logger = logging.getLogger(__name__)

router = APIRouter(tags=["v2-proprietary-tender-docs"])

_BRUBRU_CLUSTER_URL = "https://brubru.beresol.eu/eu-law-comply/clusters/{cid}"


class _DataPoints(BaseModel):
    """The 5 mandatory Brubru v1 datapoints: present even when null."""
    public_url: Optional[str] = Field(None, description="Citizen-facing canonical URL: the Brubru EU Law Comply cluster page.")
    body_txt: Optional[str] = Field(None, description="Plain-text cluster summary composed from name + description + applicability.")
    body_html: Optional[str] = Field(None, description="HTML cluster summary.")
    document_date: Optional[date] = Field(None, description="Always null: clusters are evergreen, not document-dated.")
    creation_date: Optional[datetime] = Field(None, description="When this API response was generated.")


class TenderComplyClusterItem(_DataPoints):
    """One EU Law Comply cluster surfaced as relevant to the given tender template."""
    id: int = Field(..., description="Brubru cluster id.")
    name: str = Field(..., description="Cluster name (e.g. 'GDPR & ePrivacy compliance').")
    description: Optional[str] = Field(None, description="Cluster description.")
    applicability: Optional[str] = Field(None, description="When this cluster applies.")
    policy_area: Optional[str] = Field(None, description="EU policy-area taxonomy value the cluster sits under.")
    priority_level: Optional[str] = Field(None, description="High / Medium / Low priority for typical applicants.")
    law_count: int = Field(0, description="Number of laws in this cluster.")
    requirement_count: int = Field(0, description="Number of requirements rolled up across all laws in this cluster.")
    matched_targets: List[str] = Field(default_factory=list, description="Which template comply_target labels mapped to this cluster's policy_area.")
    match_reason: List[str] = Field(default_factory=list, description="Why the cluster surfaced: 'template' (declared on the template), 'ethics' (ethics flag), 'funding-mode' (equity/blended funding mode).")


def _compose_cluster_body(row: dict) -> tuple[str, str]:
    lines: List[str] = [row.get("name") or "Cluster"]
    if row.get("policy_area"):
        lines.append(f"Policy area: {row['policy_area']}")
    if row.get("priority_level"):
        lines.append(f"Priority: {row['priority_level']}")
    if row.get("law_count") is not None:
        lines.append(f"Laws: {row['law_count']}")
    if row.get("requirement_count") is not None:
        lines.append(f"Requirements: {row['requirement_count']}")
    if row.get("matched_targets"):
        lines.append(f"Matched targets: {', '.join(row['matched_targets'])}")
    if row.get("match_reason"):
        lines.append(f"Match reason: {', '.join(row['match_reason'])}")
    if row.get("description"):
        lines.append("")
        lines.append(str(row["description"]))
    if row.get("applicability"):
        lines.append("")
        lines.append(f"Applicability: {row['applicability']}")
    body_txt = "\n".join(str(x) for x in lines)
    body_html = "<ul>" + "".join(
        f"<li>{_html.escape(str(x))}</li>" for x in lines if x
    ) + "</ul>"
    return body_txt, body_html


@router.get(
    "/comply-clusters",
    response_model=PaginatedResponse[TenderComplyClusterItem],
    summary="EU Law Comply clusters relevant to a funding template: Tender Docs cross-fetch",
    description="""**What it does**
Given a funding template id (+ optional `funding_mode` + ethics flags), returns the EU Law Comply clusters whose `policy_area` matches the template's declared `comply_targets`, plus any extras driven by ethics flags or by an equity/blended funding mode. Each cluster carries the law count, requirement count, and a `match_reason` array explaining why it surfaced (`template`, `ethics`, or `funding-mode`).

Same resolution path as the v1 endpoint at `/api/eu-law-comply/by-topic-clusters`: one shared helper backs both. The v2 surface uses API-key auth (no tier gate).

**When to use it**
After picking a funding template (`/templates/{id}`), to populate a "Compliance checklist" panel that lists the EU laws the applicant will need to demonstrate compliance with. Pre-flight tool for grant applicants and for advisors building Tenderator-like products.

**Input**
- `template_id` (required): the template slug, e.g. `eic-accelerator-stage-2`, `esf-plus-agency-procurement`.
- `funding_mode`: `equity-only` / `blended` triggers Sustainable Finance + AIFMD + AML cluster additions.
- `ethics_personal_data`, `ethics_special_categories`, `ethics_clinical_studies`, `ethics_dual_use`, `ethics_animals`: booleans; each adds a curated set of clusters.
- `limit` (1-100, default 50), `page` (1-indexed).

**Try it**
```
GET /api/v2/proprietary/tender-docs/comply-clusters?template_id=eic-accelerator-stage-2
GET /api/v2/proprietary/tender-docs/comply-clusters?template_id=esf-plus-agency-procurement&ethics_personal_data=true
```

**You get back**
A `PaginatedResponse[TenderComplyClusterItem]`. Per item: `id`, `name`, `description`, `applicability`, `policy_area`, `priority_level`, `law_count`, `requirement_count`, `matched_targets`, `match_reason`, plus the 5 datapoints (`public_url` = Brubru Comply cluster page, `body_txt`/`body_html` composed). HTTP 404 if the `template_id` is unknown.

**Data freshness**
Clusters are Brubru-curated (53 today). Refreshed when laws move between clusters or when new comply_target labels enter the template catalogue.""",
)
async def list_comply_clusters(
    request: Request,
    template_id: str = Query(..., description="Funding template slug (see /templates for the catalogue)."),
    funding_mode: Optional[str] = Query(None, description="'grant' (default), 'equity-only', or 'blended': equity/blended add finance clusters."),
    ethics_personal_data: bool = Query(False),
    ethics_special_categories: bool = Query(False),
    ethics_clinical_studies: bool = Query(False),
    ethics_dual_use: bool = Query(False),
    ethics_animals: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[TenderComplyClusterItem]:
    resolved = resolve_clusters_by_topic(
        template_id=template_id,
        funding_mode=funding_mode,
        ethics_personal_data=ethics_personal_data,
        ethics_special_categories=ethics_special_categories,
        ethics_clinical_studies=ethics_clinical_studies,
        ethics_dual_use=ethics_dual_use,
        ethics_animals=ethics_animals,
        db=db,
    )

    all_rows = resolved.get("clusters") or []
    total = len(all_rows)
    start = (page - 1) * limit
    page_rows = all_rows[start : start + limit]

    items: List[TenderComplyClusterItem] = []
    for row in page_rows:
        body_txt, body_html = _compose_cluster_body(row)
        items.append(TenderComplyClusterItem(
            id=int(row["id"]),
            name=row.get("name") or "Cluster",
            description=row.get("description"),
            applicability=row.get("applicability"),
            policy_area=row.get("policy_area"),
            priority_level=row.get("priority_level"),
            law_count=int(row.get("law_count") or 0),
            requirement_count=int(row.get("requirement_count") or 0),
            matched_targets=list(row.get("matched_targets") or []),
            match_reason=list(row.get("match_reason") or []),
            public_url=_BRUBRU_CLUSTER_URL.format(cid=row["id"]),
            body_txt=body_txt,
            body_html=body_html,
            document_date=None,
            creation_date=datetime.utcnow(),
        ))

    return build_envelope(
        items, total, page, limit,
        op_core_title=f"Comply clusters for tender template {template_id}",
        op_core_type="EU Law Comply cluster",
        op_core_identifier=str(request.url),
        creation_date=datetime.utcnow(),
    )
