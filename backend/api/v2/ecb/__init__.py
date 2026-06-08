"""
/api/v2/ecb — European Central Bank folder.

Two bodies under one folder:
  - ECB proper                  /api/v2/ecb/{news,publications,events,legal-acts}
  - ECB Banking Supervision (SSM) /api/v2/ecb/banking-supervision/{news,publications,events}

All resources read from economy_items (migration 119) and expose the 5 mandatory
datapoints. Scope: read:economy.
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

from . import ecb as _ecb
from . import banking_supervision as _ssm

router = APIRouter(prefix="/ecb", tags=["v2-ecb"])


class EcbBody(BaseModel):
    code: str = Field(..., description="Body code: 'ecb' or 'ecb_ssm'.")
    acronym: str
    name: str
    mandate: Optional[str] = None
    website: Optional[str] = None
    item_counts: dict = Field(default_factory=dict, description="Stored item count per resource type.")


@router.get(
    "",
    response_model=List[EcbBody],
    summary="ECB folder directory — the two bodies and what each one carries",
    description="""**What it does**
Lists the two bodies in the ECB folder (the European Central Bank and ECB Banking Supervision / SSM) with a count of stored items per resource type.

**When to use it**
A one-call overview to discover which resources (news, publications, events, legal acts) are populated before drilling into a specific feed.

**Input**
No parameters.

**Try it**
```
GET /api/v2/ecb
```

**You get back**
Two body records, each with acronym, name, mandate, website and an `item_counts` map (e.g. `{"news": 30, "publication": 12, ...}`).

**Data freshness**
Counts are live from the database.""",
)
async def ecb_directory(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(api_user_with_rate_limit),
):
    bodies = db.execute(text(
        "SELECT code, acronym, name, mandate, website FROM economy_bodies "
        "WHERE folder = 'ecb' ORDER BY code = 'ecb' DESC, code"
    )).fetchall()
    counts = db.execute(text(
        "SELECT body_code, item_type, count(*) AS n FROM economy_items "
        "WHERE body_code IN ('ecb','ecb_ssm') GROUP BY body_code, item_type"
    )).fetchall()
    by_body: dict[str, dict] = {}
    for c in counts:
        by_body.setdefault(c.body_code, {})[c.item_type] = c.n
    return [
        EcbBody(code=b.code, acronym=b.acronym, name=b.name, mandate=b.mandate,
                website=b.website, item_counts=by_body.get(b.code, {}))
        for b in bodies
    ]


router.include_router(_ecb.router)
router.include_router(_ssm.router)
