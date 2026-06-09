"""
/api/v2/eu-financial-institutions — "Economic & Financial Institutions of the EU".

The institution-family folder for the EU financial-supervision and financing
bodies (one body sub-router each):
  EBA, ESMA, EIOPA, ESRB, SRB, EIB (EIF embedded), AMLA, EPPO.

All resources read from economy_items (migration 119) and expose the 5 mandatory
datapoints. Scope: read:economy. Bodies are added here as each is built.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from api.v1._deps import api_user_with_rate_limit

from . import eba as _eba
from . import esma as _esma
from . import eiopa as _eiopa
from . import esrb as _esrb
from . import srb as _srb
from . import eib as _eib
from . import amla as _amla

router = APIRouter(prefix="/eu-financial-institutions", tags=["v2-eu-financial-institutions"])


class FinBody(BaseModel):
    code: str = Field(..., description="Body code (e.g. 'eba').")
    acronym: str
    name: str
    family: Optional[str] = None
    mandate: Optional[str] = None
    website: Optional[str] = None
    item_counts: dict = Field(default_factory=dict, description="Stored item count per resource type.")


@router.get(
    "",
    response_model=List[FinBody],
    summary="Economic & Financial Institutions of the EU — directory",
    description="""**What it does**
Lists the EU financial-supervision and financing bodies in this folder (EBA, ESMA, EIOPA, ESRB, SRB, EIB, AMLA, EPPO) with a count of stored items per resource type. Bodies appear here as each is built out.

**When to use it**
A one-call overview of which bodies and resources (news, publications, events) are populated before drilling into a specific feed.

**Input**
No parameters.

**Try it**
```
GET /api/v2/eu-financial-institutions
```

**You get back**
One record per available body, with acronym, name, family, mandate, website and an `item_counts` map.

**Data freshness**
Counts are live from the database.""",
)
async def fin_directory(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(api_user_with_rate_limit),
):
    bodies = db.execute(text(
        "SELECT code, acronym, name, family, mandate, website FROM economy_bodies "
        "WHERE folder = 'eu_financial_institutions' ORDER BY acronym"
    )).fetchall()
    counts = db.execute(text(
        "SELECT body_code, item_type, count(*) AS n FROM economy_items "
        "WHERE body_code IN (SELECT code FROM economy_bodies WHERE folder = 'eu_financial_institutions') "
        "GROUP BY body_code, item_type"
    )).fetchall()
    by_body: dict[str, dict] = {}
    for c in counts:
        by_body.setdefault(c.body_code, {})[c.item_type] = c.n
    # Only surface bodies that have at least one stored item (built-out bodies).
    return [
        FinBody(code=b.code, acronym=b.acronym, name=b.name, family=b.family,
                mandate=b.mandate, website=b.website, item_counts=by_body.get(b.code, {}))
        for b in bodies if b.code in by_body
    ]


router.include_router(_eba.router)
router.include_router(_esma.router)
router.include_router(_eiopa.router)
router.include_router(_esrb.router)
router.include_router(_srb.router)
router.include_router(_eib.router)
router.include_router(_amla.router)
