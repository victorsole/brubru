"""
/api/v1/discover/ecli — ECLI lookup + e-Justice search-engine deep-link.

Phase 13 of docs/applications/euvoc.md. Single entry point that turns
any ECLI into:
  - parsed components (country / court / year / ordinal)
  - a deep-link to the e-Justice ECLI search engine
  - a CJEU/InforCuria URL when the ECLI is for an EU court

When the e-Justice SPA backend exposes a JSON search API, this endpoint
will gain a `search` mode that returns parsed results instead of just a
deep-link.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from pydantic import BaseModel

from models.user import User
from services.api_clients.ecli_client import (
    deep_link,
    eur_lex_url,
    is_cjeu,
    parse,
)

from ._deps import api_user_with_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/discover/ecli", tags=["v1-discover-ecli"])


class ECLIResolution(BaseModel):
    ecli: str
    parts: dict
    is_cjeu: bool
    e_justice_url: str
    inforcuria_url: Optional[str] = None
    note: Optional[str] = None


@router.get(
    "/{ecli:path}",
    response_model=ECLIResolution,
    summary="Resolve an ECLI to its e-Justice and InforCuria deep-links",
    description=(
        "Hand it any European Case Law Identifier (e.g. "
        "ECLI:EU:C:2014:317 — the Google Spain ruling) and get back the "
        "parsed components plus deep-links to the e-Justice search "
        "engine and (for CJEU rulings) InforCuria."
    ),
)
async def resolve_ecli(
    request: Request,
    ecli: str = Path(..., description="ECLI string"),
    user: User = Depends(api_user_with_rate_limit),
) -> ECLIResolution:
    parts = parse(ecli)
    if not parts:
        raise HTTPException(
            status_code=422,
            detail={
                "error": f"Invalid ECLI shape: {ecli!r}",
                "reason_code": "invalid_ecli",
            },
        )
    return ECLIResolution(
        ecli=ecli,
        parts=parts,
        is_cjeu=is_cjeu(ecli),
        e_justice_url=deep_link(ecli),
        inforcuria_url=eur_lex_url(ecli),
        note=(
            None if is_cjeu(ecli) else
            "Non-CJEU ECLI — use the e-Justice search-engine deep-link "
            "to find the corresponding national case in your member state's portal."
        ),
    )
