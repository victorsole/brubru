"""
Amendator Featured Examples API

Public read endpoint surfacing the daily-rotated list of "Example URLs" shown on
the Amendator page (eurlex_url_input.tsx). Items are stored in
public.amendator_featured_examples, ordered by position, with is_active=TRUE
shown to users. Newer items displace older ones via the rotation script
(scripts/rotate_amendator_examples.py).
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text

from core.database import SessionLocal, get_db
from sqlalchemy.orm import Session
from models.user import User
from .auth import get_current_user


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


class MyAmendableFile(BaseModel):
    carriage_id: str
    title: str
    celex: Optional[str] = None
    procedure_ref: Optional[str] = None
    eurlex_url: Optional[str] = None
    text_type: Optional[str] = None


@router.get("/my-amendable-files", response_model=List[MyAmendableFile],
            summary="Files you track that you can amend",
            description=(
                "**What it does**\nLists the legislative files you track that can be "
                "opened in Amendator (legislative acts / proposals with a EUR-Lex "
                "document), so you can amend a dossier you already follow.\n\n"
                "**When to use it**\nThe 'Amend a file you track' row in the Amendator "
                "input panel.\n\n"
                "**You get back**\nEach file's title, CELEX/procedure ref and a EUR-Lex URL."))
def my_amendable_files(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(15, ge=1, le=50),
):
    rows = db.execute(text(
        """
        SELECT lc.id::text, lc.title, lc.celex_numbers, lc.oeil_procedure_ref, lc.text_type
          FROM user_carriage_tracks uct
          JOIN legislative_carriages lc ON lc.id = uct.carriage_id
         WHERE uct.user_id = :uid AND uct.archived_at IS NULL
           AND (lc.text_type = 'LEGISLATIVE' OR array_length(lc.celex_numbers, 1) > 0)
         ORDER BY uct.tracked_since DESC
         LIMIT :lim
        """
    ), {"uid": str(current_user.id), "lim": limit}).fetchall()
    out = []
    for r in rows:
        celex = (r[2] or [None])[0]
        url = (f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"
               if celex else None)
        out.append(MyAmendableFile(
            carriage_id=r[0], title=r[1], celex=celex,
            procedure_ref=r[3], eurlex_url=url,
            text_type=(r[4].value if hasattr(r[4], "value") else r[4]),
        ))
    return out


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
