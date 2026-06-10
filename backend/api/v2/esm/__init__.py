"""
/api/v2/esm — European Stability Mechanism folder.

ESM is intergovernmental (NOT an EU institution), so it sits in its own folder
rather than eu-financial-institutions. Single body; its resources sit directly
under the folder prefix:
  /api/v2/esm/{news,publications,events}

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

from ..economy_endpoints import register_resource

router = APIRouter(prefix="/esm", tags=["v2-esm"])

_BODY = "European Stability Mechanism"
_ACRO = "the ESM"
_TAG = "v2-esm"


class EsmBody(BaseModel):
    code: str = Field(..., description="Body code: 'esm'.")
    acronym: str
    name: str
    mandate: Optional[str] = None
    website: Optional[str] = None
    item_counts: dict = Field(default_factory=dict, description="Stored item count per resource type.")


@router.get(
    "",
    response_model=List[EsmBody],
    summary="ESM folder directory — what the European Stability Mechanism carries",
    description="""**What it does**
Returns the European Stability Mechanism with a count of stored items per resource type.

**When to use it**
A one-call overview to discover which resources (news, publications, events) are populated before drilling into a specific feed.

**Input**
No parameters.

**Try it**
```
GET /api/v2/esm
```

**You get back**
One body record with acronym, name, mandate, website and an `item_counts` map (e.g. `{"news": 60, "publication": 13, "event": 5}`).

**Data freshness**
Counts are live from the database.""",
)
async def esm_directory(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(api_user_with_rate_limit),
):
    bodies = db.execute(text(
        "SELECT code, acronym, name, mandate, website FROM economy_bodies WHERE folder = 'esm'"
    )).fetchall()
    counts = db.execute(text(
        "SELECT item_type, count(*) AS n FROM economy_items WHERE body_code = 'esm' GROUP BY item_type"
    )).fetchall()
    cmap = {c.item_type: c.n for c in counts}
    return [
        EsmBody(code=b.code, acronym=b.acronym, name=b.name, mandate=b.mandate,
                website=b.website, item_counts=cmap)
        for b in bodies
    ]


register_resource(
    router, body_code="esm", item_type="news", slug="news", noun="news items",
    body_name=_BODY, acronym=_ACRO, tag=_TAG,
    source="the ESM newsroom plus the detail pages.",
    extra="Press releases and news from the European Stability Mechanism and the EFSF.",
)
register_resource(
    router, body_code="esm", item_type="publication", slug="publications", noun="publications",
    body_name=_BODY, acronym=_ACRO, tag=_TAG,
    source="the ESM publications listing.",
    extra="Annual reports, ESM briefs, research and analysis from the European Stability Mechanism.",
)
register_resource(
    router, body_code="esm", item_type="event", slug="events", noun="events",
    body_name=_BODY, acronym=_ACRO, tag=_TAG,
    source="the ESM events listing.",
    extra="Eurogroup meetings, Board of Governors meetings and other ESM events, with their dates.",
)
# Database: ESM/EFSF financial-assistance programmes.
register_resource(
    router, body_code="esm", item_type="programme", slug="programmes", noun="programmes",
    body_name=_BODY, acronym=_ACRO, tag=_TAG,
    source="the ESM/EFSF country financial-assistance programme pages.",
    extra="The ESM/EFSF financial-assistance programmes (Greece, Ireland, Portugal, Spain, Cyprus), "
          "each with its programme overview. The detailed disbursement figures live in ESM's Power BI "
          "report; this catalogues the programmes and their narrative.",
)
