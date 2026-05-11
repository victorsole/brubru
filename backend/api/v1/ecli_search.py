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
import re
from datetime import date as _date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from pydantic import BaseModel, Field

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
    # The 5 mandatory Brubru v1 datapoints
    public_url: Optional[str] = Field(
        None,
        description="Canonical citizen URL — InforCuria for CJEU rulings, else e-Justice deep-link.",
    )
    body_txt: Optional[str] = Field(
        None,
        description="Null for this endpoint — ECLI lookup is metadata-only; the ruling body is not fetched. Follow public_url to read the ruling.",
    )
    body_html: Optional[str] = Field(
        None,
        description="Null for this endpoint — see body_text note.",
    )
    document_date: Optional[_date] = Field(
        None,
        description="Year of the ECLI (the 'year' part of the identifier; full date isn't encoded).",
    )
    creation_date: Optional[datetime] = Field(
        None,
        description="Time of this ECLI resolution call (stateless endpoint).",
    )


@router.get(
    "/{ecli:path}",
    response_model=ECLIResolution,
    summary="Look up an EU court ruling by case-law identifier",
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
    cjeu = is_cjeu(ecli)
    e_justice = deep_link(ecli)
    inforcuria = eur_lex_url(ecli)
    # Derive document_date as 1st January of the ECLI year (year is the only
    # date component encoded). Better than NULL for sorting / filtering.
    doc_date: Optional[_date] = None
    try:
        year = int(parts.get("year") or 0)
        if 1900 < year <= 2099:
            doc_date = _date(year, 1, 1)
    except (TypeError, ValueError):
        pass
    return ECLIResolution(
        ecli=ecli,
        parts=parts,
        is_cjeu=cjeu,
        e_justice_url=e_justice,
        inforcuria_url=inforcuria,
        note=(
            None if cjeu else
            "Non-CJEU ECLI — use the e-Justice search-engine deep-link "
            "to find the corresponding national case in your member state's portal."
        ),
        # 5 mandatory datapoints
        public_url=inforcuria or e_justice,
        document_date=doc_date,
        creation_date=datetime.utcnow(),
    )
