"""
Amendator Featured Examples API

Public read endpoint surfacing the daily-rotated list of "Example URLs" shown on
the Amendator page (eurlex_url_input.tsx). Items are stored in
public.amendator_featured_examples, ordered by position, with is_active=TRUE
shown to users. Newer items displace older ones via the rotation script
(scripts/rotate_amendator_examples.py).
"""

from typing import List

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import text

from core.database import SessionLocal


router = APIRouter(prefix="/api/amendator", tags=["Amendator"])


class FeaturedExample(BaseModel):
    celex: str | None = None
    eurlex_url: str
    title: str
    description: str | None = None
    source: str | None = None
    position: int
    document_type: str | None = None


class FeaturedExamplesResponse(BaseModel):
    items: List[FeaturedExample]
    total: int


# Only documents with these types can be amended in Amendator. Other types
# (Communications, agreements, recommendations, etc.) are filtered out so the
# user is never offered something Amendator's parser cannot structure.
AMENDABLE_TYPES = (
    "regulation", "directive", "decision_legislative",
    "proposal_cod", "proposal_app", "proposal_cns",
)


@router.get("/featured-examples", response_model=FeaturedExamplesResponse)
def list_featured_examples(limit: int = Query(10, ge=1, le=20)):
    """Return active featured examples for the Amendator input panel.

    Filters out non-amendable document types (Communications, agreements,
    recommendations, etc.) at query time. Count is flexible — fewer items is
    fine; the rotation script keeps the list fresh, the cap is just a ceiling.
    """
    db = SessionLocal()
    try:
        rows = db.execute(text(
            """
            SELECT celex, eurlex_url, title, description, source, position, document_type
              FROM amendator_featured_examples
             WHERE is_active = TRUE
               AND (document_type IS NULL OR document_type = ANY(:amendable))
             ORDER BY position ASC, added_at DESC
             LIMIT :lim
            """
        ), {"lim": limit, "amendable": list(AMENDABLE_TYPES)}).fetchall()
        items = [
            FeaturedExample(
                celex=r[0], eurlex_url=r[1], title=r[2],
                description=r[3], source=r[4], position=r[5],
                document_type=r[6],
            ) for r in rows
        ]
        return FeaturedExamplesResponse(items=items, total=len(items))
    finally:
        db.close()
