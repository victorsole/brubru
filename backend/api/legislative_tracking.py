"""
Legislative Tracking API Endpoints

Provides REST API for tracking EU legislation and procedures.
Part of My EU Bubble - Phase 5: Advanced Features
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from core.database import get_db
from models.user import User
from .auth_optional import get_current_user_dev as get_current_user
from services.legislative_tracker import LegislativeTracker

router = APIRouter(prefix="/api/legislation", tags=["Legislative Tracking"])


# Pydantic Schemas
class TrackLegislationRequest(BaseModel):
    """Request to track legislation by CELEX."""
    celex_number: str


class TrackProcedureRequest(BaseModel):
    """Request to track OEIL procedure."""
    procedure_reference: str


class LegislationTrackingResponse(BaseModel):
    """Response with tracking information."""
    celex_number: str
    status: str
    related_amendments: List[dict]
    related_rss_entries: List[dict]
    procedure_reference: Optional[str]
    last_update: Optional[str]


class ProcedureTrackingResponse(BaseModel):
    """Response with procedure tracking information."""
    procedure_reference: str
    status: str
    current_stage: Optional[str]
    timeline: List[dict]
    related_documents: List[dict]
    next_milestone: Optional[dict]
    last_update: Optional[str]


class TrackedItemsResponse(BaseModel):
    """Response with all tracked items."""
    legislation: List[dict]
    procedures: List[dict]
    amendments: List[dict]


class StatusChangeResponse(BaseModel):
    """Response with detected status changes."""
    changes: List[dict]


class ProgressSummaryResponse(BaseModel):
    """Response with progress summary."""
    total_tracked: int
    active_procedures: int
    pending_amendments: int
    recent_updates: List[dict]
    upcoming_milestones: List[dict]
    generated_at: str


# Endpoints

@router.post("/track/celex", response_model=LegislationTrackingResponse)
async def track_legislation(
    request: TrackLegislationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Track EU legislation by CELEX number.

    Returns tracking information including related amendments and RSS entries.
    """
    tracker = LegislativeTracker(db)

    try:
        tracking_info = await tracker.track_legislation_by_celex(
            request.celex_number,
            str(current_user.id)
        )

        if "error" in tracking_info:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=tracking_info["error"]
            )

        return tracking_info

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to track legislation: {str(e)}"
        )


@router.post("/track/procedure", response_model=ProcedureTrackingResponse)
async def track_procedure(
    request: TrackProcedureRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Track OEIL procedure progress.

    Returns detailed procedure information including timeline and milestones.
    """
    tracker = LegislativeTracker(db)

    try:
        tracking_info = await tracker.track_procedure(
            request.procedure_reference,
            str(current_user.id)
        )

        if "error" in tracking_info:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=tracking_info["error"]
            )

        return tracking_info

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to track procedure: {str(e)}"
        )


@router.get("/tracked", response_model=TrackedItemsResponse)
async def get_tracked_items(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all tracked legislation and procedures for the current user.

    Returns lists of tracked items organized by type.
    """
    tracker = LegislativeTracker(db)

    try:
        tracked_items = await tracker.get_user_tracked_items(str(current_user.id))
        return tracked_items

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tracked items: {str(e)}"
        )


@router.get("/changes", response_model=StatusChangeResponse)
async def get_status_changes(
    since_hours: int = Query(24, ge=1, le=168, description="Check changes in last N hours"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Detect status changes in tracked legislation/procedures.

    Returns list of recent changes in the specified time window.
    """
    tracker = LegislativeTracker(db)

    try:
        changes = await tracker.detect_status_changes(
            str(current_user.id),
            since_hours=since_hours
        )

        return {"changes": changes}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to detect status changes: {str(e)}"
        )


@router.get("/summary", response_model=ProgressSummaryResponse)
async def get_progress_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get progress summary for all tracked items.

    Returns statistics and highlights of legislative tracking activity.
    """
    tracker = LegislativeTracker(db)

    try:
        summary = await tracker.generate_progress_summary(str(current_user.id))

        if "error" in summary:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=summary["error"]
            )

        return summary

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate progress summary: {str(e)}"
        )


@router.get("/{celex}/recital-article-map")
def get_recital_article_map(
    celex: str,
    force_recompute: bool = Query(False, description="Recompute instead of reading cached map"),
    db: Session = Depends(get_db),
):
    """
    Return the recital-to-article map for a given CELEX.

    Response shape:
        {
          "celex": "32016R0679",
          "map": {
            "Article 3": [
              {"recital_number": "27", "score": 0.41, "snippet": "..."},
              ...
            ],
            ...
          }
        }

    The map is computed on first access (from the local Formex archive) and
    cached in `eu_laws.extra_metadata.recital_article_map`. Pass
    `force_recompute=true` to rebuild.

    Uses TF-IDF cosine similarity between article text and recital text.
    See `services/parsers/recital_article_linker.py`.
    """
    from services.parsers.recital_article_store import get_or_compute_map

    mapping = get_or_compute_map(db, celex, force_recompute=force_recompute)
    if mapping is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CELEX {celex} not in eu_laws or Formex XML unavailable",
        )
    return {"celex": celex, "map": mapping}


@router.get("/{celex}/defined-terms")
def get_defined_terms(
    celex: str,
    force_recompute: bool = Query(False),
    db: Session = Depends(get_db),
):
    """
    Return the Article 3/4-style definitions dict for a CELEX.

    Response shape:
        {
          "celex": "32022R2065",
          "terms": {
            "information society service": {
              "term": "information society service",
              "definition": "...",
              "article": "Article 3",
              "point": "a"
            },
            ...
          }
        }

    Supports hover-definition UI in Amendator, Catalan pages, EUR-Lex viewer.
    """
    from services.parsers.definition_store import get_or_compute_map as _get_defs

    mapping = _get_defs(db, celex, force_recompute=force_recompute)
    if mapping is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CELEX {celex} not in eu_laws or Formex XML unavailable",
        )
    return {"celex": celex, "terms": mapping}


class AnnotateTextRequest(BaseModel):
    """
    Annotate a paragraph (or list of paragraphs) with cross-references, law
    aliases and defined-term spans.

    - If `celex` is provided, defined terms from that law are wrapped in
      <span class="defined-term" title="...">.
    - Cross-references ("Article 7 of Regulation (EU) 2024/1234") and aliases
      (GDPR, DSA, AI Act) are always wrapped unless `include_aliases=false`.
    """
    text: Optional[str] = None
    texts: Optional[List[str]] = None
    celex: Optional[str] = None
    include_aliases: bool = True


@router.post("/annotate-text")
def annotate_legal_text_api(
    payload: AnnotateTextRequest,
    db: Session = Depends(get_db),
):
    """
    One-shot annotation endpoint used by the Amendator document viewer and any
    other frontend that renders EU legal text.

    Request body shape (either form is accepted):
        {"text": "...", "celex": "32022R2065"}
        {"texts": ["paragraph 1", "paragraph 2"], "celex": "32022R2065"}

    Returns:
        {"html": "..."} or {"html": ["...", "..."]}

    If the `celex` is known and its defined_terms map is cached, every
    statutory term in the text is wrapped in a <span class="defined-term">.
    Otherwise only cross-refs and aliases are wrapped.
    """
    from services.parsers.legal_text_annotator import (
        annotate_legal_text,
        annotate_many,
    )

    if payload.text is None and not payload.texts:
        raise HTTPException(status_code=400, detail="Provide `text` or `texts`.")

    defined_terms = None
    if payload.celex:
        from services.parsers.definition_store import get_or_compute_map as _get_defs

        try:
            defined_terms = _get_defs(db, payload.celex) or None
        except Exception:
            defined_terms = None

    if payload.texts is not None:
        annotated = annotate_many(
            payload.texts,
            defined_terms,
            include_aliases=payload.include_aliases,
        )
        return {"html": annotated}

    annotated = annotate_legal_text(
        payload.text or "",
        defined_terms,
        include_aliases=payload.include_aliases,
    )
    return {"html": annotated}


@router.get("/coverage-stats")
def get_coverage_stats(db: Session = Depends(get_db)):
    """
    Aggregate coverage of the legal-text intelligence layer across the
    `eu_laws` table and the `legislative_tracking` table.

    Read-only. Used by the My EU Bubble Analytics tab.
    """
    from sqlalchemy import text as sqla_text

    # Global coverage across eu_laws.extra_metadata
    global_row = db.execute(
        sqla_text(
            """
            SELECT
              COUNT(*) FILTER (WHERE extra_metadata ? 'recital_article_map')::int AS with_recital_map,
              COUNT(*) FILTER (WHERE extra_metadata ? 'defined_terms')::int AS with_defined_terms,
              COUNT(*)::int AS total_laws
            FROM eu_laws
            """
        )
    ).first()

    # Tracked-law coverage: join legislative_tracking <-> eu_laws on celex
    tracked_row = db.execute(
        sqla_text(
            """
            SELECT
              COUNT(DISTINCT lt.celex_number)::int AS tracked_total,
              COUNT(DISTINCT CASE WHEN el.extra_metadata ? 'recital_article_map'
                                  THEN lt.celex_number END)::int AS tracked_with_recital_map,
              COUNT(DISTINCT CASE WHEN el.extra_metadata ? 'defined_terms'
                                  THEN lt.celex_number END)::int AS tracked_with_defined_terms
            FROM legislative_tracking lt
            LEFT JOIN eu_laws el ON el.celex = lt.celex_number
            WHERE lt.celex_number IS NOT NULL
            """
        )
    ).first()

    # Aggregate numbers: total recital-article links + total defined terms
    aggregate_row = db.execute(
        sqla_text(
            """
            SELECT
              COALESCE(SUM((
                SELECT COUNT(*)::int
                FROM jsonb_each(extra_metadata->'recital_article_map') je
                WHERE jsonb_typeof(je.value) = 'array'
              )), 0)::bigint AS total_article_buckets,
              COALESCE(SUM(jsonb_array_length(COALESCE(
                jsonb_path_query_array(extra_metadata, '$.recital_article_map.*[*]'),
                '[]'::jsonb
              ))), 0)::bigint AS total_recital_links,
              COALESCE(SUM((
                SELECT COUNT(*)::int
                FROM jsonb_object_keys(extra_metadata->'defined_terms')
              )), 0)::bigint AS total_defined_terms
            FROM eu_laws
            WHERE extra_metadata ? 'recital_article_map' OR extra_metadata ? 'defined_terms'
            """
        )
    ).first()

    # Top 5 laws by recital-article link count -- the headline stat
    top_laws = db.execute(
        sqla_text(
            """
            SELECT
              celex,
              title,
              jsonb_array_length(COALESCE(
                jsonb_path_query_array(extra_metadata, '$.recital_article_map.*[*]'),
                '[]'::jsonb
              ))::int AS link_count
            FROM eu_laws
            WHERE extra_metadata ? 'recital_article_map'
            ORDER BY link_count DESC
            LIMIT 5
            """
        )
    ).fetchall()

    return {
        "global": {
            "total_laws": (global_row.total_laws if global_row else 0),
            "with_recital_map": (global_row.with_recital_map if global_row else 0),
            "with_defined_terms": (global_row.with_defined_terms if global_row else 0),
        },
        "tracked": {
            "total": (tracked_row.tracked_total if tracked_row else 0),
            "with_recital_map": (tracked_row.tracked_with_recital_map if tracked_row else 0),
            "with_defined_terms": (tracked_row.tracked_with_defined_terms if tracked_row else 0),
        },
        "aggregates": {
            "total_article_buckets": int(aggregate_row.total_article_buckets) if aggregate_row else 0,
            "total_recital_links": int(aggregate_row.total_recital_links) if aggregate_row else 0,
            "total_defined_terms": int(aggregate_row.total_defined_terms) if aggregate_row else 0,
        },
        "top_laws_by_links": [
            {
                "celex": row.celex,
                "title": (row.title[:160] if row.title else row.celex),
                "link_count": int(row.link_count),
            }
            for row in top_laws
        ],
    }


class ResolveRefsRequest(BaseModel):
    text: str
    annotate_html: bool = False


@router.post("/resolve-references")
def resolve_cross_references(payload: ResolveRefsRequest):
    """
    Resolve inline EU legal citations in the submitted text.

    Body:
        {"text": "See Article 7 of Regulation (EU) 2024/1234 and Directive 2011/93/EU.",
         "annotate_html": false}

    Response (annotate_html=false):
        {"refs": [{"raw": "...", "celex": "...", "url": "...", "article": "7", ...}, ...]}

    Response (annotate_html=true):
        {"html": "<...>See <a href=... data-celex=...>Article 7 of Regulation (EU) 2024/1234</a>..."}
    """
    from services.parsers.cross_reference_resolver import (
        resolve_references_json,
        annotate_html,
    )

    if payload.annotate_html:
        return {"html": annotate_html(payload.text)}
    return {"refs": resolve_references_json(payload.text)}
