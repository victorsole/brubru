"""
MEP Amendments API

FastAPI endpoints for fetching and querying EP committee amendments.

Routes:
- POST /api/mep-amendments/fetch/{procedure_ref:path} - Trigger fetch & parse
- GET /api/mep-amendments/by-author - Cross-procedure MEP amendment search
- GET /api/mep-amendments/sync-status - Bulk sync status (Admin)
- POST /api/mep-amendments/bulk-sync - Trigger bulk sync (Admin)
- GET /api/mep-amendments/{procedure_ref:path} - List amendments with filters
- GET /api/mep-amendments/{procedure_ref:path}/stats - Aggregated statistics
- GET /api/mep-amendments/{procedure_ref:path}/documents - List parsed documents

Created: February 2026
"""

from typing import Optional, List
from collections import Counter

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, String

from core.database import get_db
from models.user import User
from models.mep_amendment import MEPAmendment, AmendmentDocument
from schemas.mep_amendment_schemas import (
    MEPAmendmentResponse,
    MEPAmendmentListResponse,
    AmendmentDocumentResponse,
    AmendmentDocumentListResponse,
    AmendmentStatsResponse,
    RapporteurInfo,
    GroupAmendmentCount,
    ElementAmendmentCount,
    TypeAmendmentCount,
    AmendmentFetchRequest,
    AmendmentFetchResponse,
    BulkSyncRequest,
    BulkSyncResponse,
    SyncStatusResponse,
    MEPAmendmentCrossRefResponse,
    AlignmentScoreRequest,
    AlignmentScoreResponse,
    AlignmentScoreItem,
    ComparisonResponse,
    ComparisonAllyItem,
)
from .auth import get_current_user
from services.tracking.pi_committee_crosswalk import committees_for_interests
from services.tracking.tracked_files_seeder import _interest_list
from models.legislative_train import LegislativeCarriage

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mep-amendments", tags=["MEP Amendments"])


# ===== PI-aligned procedure picker =====
# NOTE: must be declared before the "/{procedure_ref:path}" catch-all GET below,
# otherwise FastAPI matches "procedures-by-committee" as a procedure reference.

@router.get(
    "/procedures-by-committee",
    summary="Procedures that have MEP amendments, annotated by committee",
    description=(
        "Lists every procedure with committee amendments, each annotated with its "
        "committee code(s), amendment count and (best-effort) title. Also returns "
        "the signed-in user's Policy-Interest committees so the picker can default "
        "to 'My interests'. Powers the PI-aligned MEP Amendments picker."
    ),
)
async def get_procedures_by_committee(
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Procedures-with-amendments grouped/annotated by committee, plus the user's PI committees."""
    rows = (
        db.query(
            MEPAmendment.procedure_reference,
            MEPAmendment.committee_code,
            func.count(MEPAmendment.id),
        )
        .group_by(MEPAmendment.procedure_reference, MEPAmendment.committee_code)
        .all()
    )

    proc_map: dict = {}
    for proc_ref, committee, count in rows:
        if not proc_ref:
            continue
        p = proc_map.setdefault(
            proc_ref, {"procedure_ref": proc_ref, "count": 0, "committees": [], "title": None}
        )
        p["count"] += count
        if committee and committee not in p["committees"]:
            p["committees"].append(committee)

    # Title enrichment. Primary: the carriages corpus (keyed on OEIL ref).
    refs = list(proc_map.keys())
    if refs:
        titles = dict(
            db.query(LegislativeCarriage.oeil_procedure_ref, LegislativeCarriage.title)
            .filter(LegislativeCarriage.oeil_procedure_ref.in_(refs))
            .all()
        )
        for ref, p in proc_map.items():
            if titles.get(ref):
                p["title"] = titles[ref]

        # Secondary: the OEIL title cache (migration 096) for in-progress
        # proposals that are not in the carriages corpus, so the picker shows a
        # real title instead of the bare reference ("2023/0477(COD)").
        missing = [ref for ref, p in proc_map.items() if not p["title"]]
        if missing:
            from sqlalchemy import text as sqla_text, bindparam
            stmt = sqla_text(
                "SELECT procedure_ref, title FROM oeil_procedure_titles WHERE procedure_ref IN :refs"
            ).bindparams(bindparam("refs", expanding=True))
            cached = dict(db.execute(stmt, {"refs": missing}).fetchall())
            for ref in missing:
                if cached.get(ref):
                    proc_map[ref]["title"] = cached[ref]

    procedures = sorted(proc_map.values(), key=lambda x: x["count"], reverse=True)

    interests = _interest_list(current_user) if current_user else []
    my_committees = sorted(committees_for_interests(interests))
    return {"procedures": procedures, "my_committees": my_committees}


# ===== Fetch & Parse =====

@router.post(
    "/fetch/{procedure_ref:path}",
    response_model=AmendmentFetchResponse,
    summary="Fetch and parse amendments for a procedure",
    description="Triggers discovery from OEIL and parsing of DOCX amendment documents"
)
async def fetch_amendments(
    procedure_ref: str,
    body: Optional[AmendmentFetchRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> AmendmentFetchResponse:
    """Trigger amendment fetching for a procedure (Yellow+ tier)."""
    try:
        if current_user.subscription_tier not in ['yellow', 'blue', 'admin']:
            raise HTTPException(
                status_code=403,
                detail="Yellow or Blue subscription required to fetch amendments"
            )

        from sqlalchemy.ext.asyncio import AsyncSession
        from services.scrapers.ep_amendment_sync_service import EPAmendmentSyncService

        force = body.force_refetch if body else False

        # The sync service expects an async session; wrap sync session if needed
        service = EPAmendmentSyncService(db=db)
        result = await service.sync_amendments_for_procedure(
            procedure_ref=procedure_ref,
            force_refetch=force
        )

        return AmendmentFetchResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to fetch amendments for {procedure_ref}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch amendments: {str(e)}"
        )


# ===== Cross-Procedure MEP Search =====

@router.get(
    "/by-author",
    response_model=MEPAmendmentCrossRefResponse,
    summary="Search amendments by MEP author across all procedures"
)
async def get_amendments_by_author(
    author: str = Query(..., min_length=2, description="MEP name to search for"),
    group: Optional[str] = Query(None, description="Filter by political group"),
    element_type: Optional[str] = Query(None, description="Filter by element type"),
    limit: int = Query(50, ge=1, le=500, description="Items per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MEPAmendmentCrossRefResponse:
    """
    Search amendments by MEP author name across ALL procedures (Yellow+ tier).

    Use case: "Show me all amendments by Axel Voss"
    """
    try:
        if current_user.subscription_tier not in ['yellow', 'blue', 'admin']:
            raise HTTPException(status_code=403, detail="Yellow or Blue subscription required")

        # Build query: search author_names array for partial match
        query = db.query(MEPAmendment).filter(
            MEPAmendment.author_names.any(author)
        )

        if group:
            query = query.filter(MEPAmendment.political_group == group)
        if element_type:
            query = query.filter(MEPAmendment.element_type == element_type)

        total = query.count()

        # Get procedure breakdown
        proc_counts = (
            db.query(
                MEPAmendment.procedure_reference,
                MEPAmendment.committee_code,
                func.count(MEPAmendment.id),
            )
            .filter(MEPAmendment.author_names.any(author))
            .group_by(MEPAmendment.procedure_reference, MEPAmendment.committee_code)
            .all()
        )

        # Aggregate procedures (a procedure may appear in multiple committees)
        proc_map: dict = {}
        for proc_ref, committee, count in proc_counts:
            if proc_ref not in proc_map:
                proc_map[proc_ref] = {"procedure_ref": proc_ref, "count": 0, "committees": []}
            proc_map[proc_ref]["count"] += count
            if committee and committee not in proc_map[proc_ref]["committees"]:
                proc_map[proc_ref]["committees"].append(committee)

        procedures = sorted(proc_map.values(), key=lambda p: p["count"], reverse=True)

        # Paginated items
        items = (
            query
            .order_by(MEPAmendment.procedure_reference, MEPAmendment.amendment_number)
            .offset(offset)
            .limit(limit)
            .all()
        )

        return MEPAmendmentCrossRefResponse(
            author_name=author,
            total_amendments=total,
            procedures=procedures,
            items=[MEPAmendmentResponse.model_validate(a) for a in items],
            limit=limit,
            offset=offset,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to search amendments by author '{author}': {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== Bulk Sync (Admin) =====

@router.get(
    "/sync-status",
    response_model=SyncStatusResponse,
    summary="Get bulk amendment sync status"
)
async def get_sync_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyncStatusResponse:
    """Get aggregate sync status for amendment documents (Admin only)."""
    try:
        if current_user.subscription_tier != 'admin':
            raise HTTPException(status_code=403, detail="Admin access required")

        from services.scrapers.bulk_amendment_sync_service import BulkAmendmentSyncService

        service = BulkAmendmentSyncService(db=db)
        status_data = service.get_sync_status()

        return SyncStatusResponse(**status_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get sync status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def _run_bulk_sync(db: Session, request: BulkSyncRequest):
    """Background task for bulk sync."""
    from services.scrapers.bulk_amendment_sync_service import BulkAmendmentSyncService

    try:
        service = BulkAmendmentSyncService(db=db)
        result = await service.sync_all(
            years=request.years,
            work_types=request.work_types,
            force_refetch=request.force_refetch,
        )
        logger.info(
            f"[OK] Bulk sync finished: {result.documents_parsed} parsed, "
            f"{result.amendments_stored} amendments"
        )
    except Exception as e:
        logger.exception(f"[ERROR] Bulk sync failed: {e}")


@router.post(
    "/bulk-sync",
    status_code=202,
    summary="Trigger bulk amendment sync from EP Open Data API"
)
async def trigger_bulk_sync(
    body: Optional[BulkSyncRequest] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Trigger async bulk sync of amendment documents (Admin only).
    Returns 202 Accepted immediately; sync runs in background.
    """
    try:
        if current_user.subscription_tier != 'admin':
            raise HTTPException(status_code=403, detail="Admin access required")

        request = body or BulkSyncRequest()

        background_tasks.add_task(_run_bulk_sync, db, request)

        return {
            "status": "accepted",
            "message": f"Bulk sync started for years={request.years}, types={request.work_types}",
            "check_status_at": "/api/mep-amendments/sync-status",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to trigger bulk sync: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== Alignment Scoring (Phase 4) =====

@router.post(
    "/{procedure_ref:path}/alignment",
    response_model=AlignmentScoreResponse,
    summary="Score MEP amendments against a policy position"
)
async def score_alignment(
    procedure_ref: str,
    body: AlignmentScoreRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AlignmentScoreResponse:
    """
    AI-powered alignment scoring (Yellow+ tier).

    Scores all MEP amendments for a procedure against the user's policy position.
    Results are cached -- re-submitting the same position returns cached scores.
    """
    try:
        if current_user.subscription_tier not in ['yellow', 'blue', 'admin']:
            raise HTTPException(status_code=403, detail="Yellow or Blue subscription required")

        from services.amendator.alignment_scorer import score_amendments

        result = await score_amendments(
            db=db,
            user_id=current_user.id,
            procedure_ref=procedure_ref,
            policy_position=body.policy_position,
        )

        return AlignmentScoreResponse(
            procedure_reference=result['procedure_reference'],
            policy_position_hash=result['policy_position_hash'],
            total_scored=result['total_scored'],
            score_distribution=result['score_distribution'],
            scores=[AlignmentScoreItem(**s) for s in result['scores']],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Alignment scoring failed for {procedure_ref}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Alignment scoring failed: {str(e)}")


@router.get(
    "/{procedure_ref:path}/comparison",
    response_model=ComparisonResponse,
    summary="Get comparative analysis from cached alignment scores"
)
async def get_comparison(
    procedure_ref: str,
    policy_position_hash: str = Query(..., description="Hash from alignment scoring response"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ComparisonResponse:
    """
    Comparative analysis (Yellow+ tier).

    Computes best allies, coverage gaps, and political landscape
    from previously cached alignment scores. Run alignment scoring first.
    """
    try:
        if current_user.subscription_tier not in ['yellow', 'blue', 'admin']:
            raise HTTPException(status_code=403, detail="Yellow or Blue subscription required")

        from services.amendator.comparison_analyzer import get_comparison as compute_comparison

        result = compute_comparison(
            db=db,
            user_id=current_user.id,
            procedure_ref=procedure_ref,
            policy_position_hash=policy_position_hash,
        )

        return ComparisonResponse(
            best_allies=[ComparisonAllyItem(**a) for a in result['best_allies']],
            coverage_gaps=result['coverage_gaps'],
            political_landscape=result['political_landscape'],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Comparison analysis failed for {procedure_ref}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")


# ===== List Amendments =====

@router.get(
    "/{procedure_ref:path}/documents",
    response_model=AmendmentDocumentListResponse,
    summary="List parsed documents for a procedure"
)
async def list_documents(
    procedure_ref: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> AmendmentDocumentListResponse:
    """Get all amendment documents discovered for a procedure."""
    try:
        if current_user.subscription_tier not in ['yellow', 'blue', 'admin']:
            raise HTTPException(status_code=403, detail="Yellow or Blue subscription required")

        query = db.query(AmendmentDocument).filter(
            AmendmentDocument.procedure_reference == procedure_ref
        ).order_by(AmendmentDocument.document_date.desc())

        items = query.all()

        return AmendmentDocumentListResponse(
            items=[AmendmentDocumentResponse.model_validate(d) for d in items],
            total=len(items)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to list documents for {procedure_ref}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def _extract_rapporteur_from_oeil(data: dict) -> Optional[RapporteurInfo]:
    """Extract rapporteur info from OEIL procedure data dict."""
    import re
    kp = data.get('key_players', {}) or {}
    committee = kp.get('committee_responsible', {}) or {}
    rap = committee.get('rapporteur')
    if not rap or not rap.get('name'):
        return None

    name = rap['name']
    group = rap.get('political_group')

    # Sometimes group is embedded in name: "SURNAME Name (GROUP)"
    if not group:
        m = re.search(r'\(([A-Z][A-Za-z&/]+(?:/[A-Z]+)?)\)\s*$', name)
        if m:
            group = m.group(1)
            name = name[:m.start()].strip()

    return RapporteurInfo(
        name=name,
        political_group=group,
        photo_url=rap.get('photo_url'),
        mep_id=rap.get('mep_id'),
    )


async def _lookup_rapporteur(procedure_ref: str, db: Session) -> Optional[RapporteurInfo]:
    """Look up rapporteur from OEIL data; fetch from OEIL on-demand if missing."""
    try:
        from models.legislative_train import LegislativeCarriage

        carriage = db.query(LegislativeCarriage).filter(
            LegislativeCarriage.oeil_procedure_ref == procedure_ref
        ).first()

        # Try cached OEIL data first
        if carriage and carriage.oeil_procedure_data:
            result = _extract_rapporteur_from_oeil(carriage.oeil_procedure_data)
            if result:
                return result

        # Fetch from OEIL on-demand
        try:
            from services.scrapers.oeil_scraper import OEILScraper
            scraper = OEILScraper()
            procedure = await scraper.get_procedure_full(procedure_ref)
            if procedure:
                oeil_data = procedure.model_dump(mode='json')

                # Cache in legislative_carriages for next time
                if carriage:
                    carriage.oeil_procedure_data = oeil_data
                    db.commit()

                result = _extract_rapporteur_from_oeil(oeil_data)
                if result:
                    return result
        except Exception as e:
            logger.debug(f"OEIL fetch for rapporteur failed: {e}")

        return None
    except Exception as e:
        logger.debug(f"Rapporteur lookup failed for {procedure_ref}: {e}")
        return None


@router.get(
    "/{procedure_ref:path}/stats",
    response_model=AmendmentStatsResponse,
    summary="Get amendment statistics for a procedure"
)
async def get_stats(
    procedure_ref: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> AmendmentStatsResponse:
    """Get aggregated amendment statistics."""
    try:
        if current_user.subscription_tier not in ['yellow', 'blue', 'admin']:
            raise HTTPException(status_code=403, detail="Yellow or Blue subscription required")

        amendments = db.query(MEPAmendment).filter(
            MEPAmendment.procedure_reference == procedure_ref
        ).all()

        if not amendments:
            return AmendmentStatsResponse(
                procedure_reference=procedure_ref,
                total_amendments=0,
                total_documents=0,
                committees=[],
                by_group=[],
                by_element=[],
                by_type=[],
                top_authors=[]
            )

        total = len(amendments)

        # Unique committees
        committees = sorted(set(a.committee_code for a in amendments if a.committee_code))

        # Count documents
        doc_count = db.query(AmendmentDocument).filter(
            AmendmentDocument.procedure_reference == procedure_ref,
            AmendmentDocument.status == 'parsed'
        ).count()

        # By political group
        # Amendments with no group AND no authors are rapporteur draft proposals
        def _effective_group(a) -> str:
            if a.political_group:
                return a.political_group
            if not a.author_names or len(a.author_names) == 0:
                return 'Rapporteur'
            return 'NI'

        group_counts = Counter(_effective_group(a) for a in amendments)
        by_group = [
            GroupAmendmentCount(
                political_group=g,
                count=c,
                percentage=round(c / total * 100, 1)
            )
            for g, c in group_counts.most_common()
        ]

        # By element (top 20 most contested)
        element_counts = Counter(
            (a.element_reference, a.element_type) for a in amendments
        )
        by_element = [
            ElementAmendmentCount(
                element_reference=ref,
                element_type=etype,
                count=c
            )
            for (ref, etype), c in element_counts.most_common(20)
        ]

        # By amendment type
        type_counts = Counter(a.amendment_type for a in amendments)
        by_type = [
            TypeAmendmentCount(
                amendment_type=t,
                count=c,
                percentage=round(c / total * 100, 1)
            )
            for t, c in type_counts.most_common()
        ]

        # Top authors (flatten author_names arrays, count per author)
        author_group = {}
        author_counts = Counter()
        for a in amendments:
            for name in (a.author_names or []):
                author_counts[name] += 1
                if name not in author_group:
                    author_group[name] = _effective_group(a)

        top_authors = [
            {'name': name, 'group': author_group.get(name, 'Unknown'), 'count': count}
            for name, count in author_counts.most_common(15)
        ]

        # Look up rapporteur from OEIL data (fetches on-demand if not cached)
        rapporteur = await _lookup_rapporteur(procedure_ref, db)

        return AmendmentStatsResponse(
            procedure_reference=procedure_ref,
            total_amendments=total,
            total_documents=doc_count,
            committees=committees,
            rapporteur=rapporteur,
            by_group=by_group,
            by_element=by_element,
            by_type=by_type,
            top_authors=top_authors
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get stats for {procedure_ref}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{procedure_ref:path}",
    response_model=MEPAmendmentListResponse,
    summary="List amendments for a procedure with filters"
)
async def list_amendments(
    procedure_ref: str,
    group: Optional[str] = Query(None, description="Filter by political group (e.g. EPP, S&D)"),
    author: Optional[str] = Query(None, description="Filter by author name (partial match)"),
    element_type: Optional[str] = Query(None, description="Filter by element type (article, recital, annex)"),
    amendment_type: Optional[str] = Query(None, description="Filter by type (modification, suppression, addition)"),
    committee: Optional[str] = Query(None, description="Filter by committee code"),
    sort_by: str = Query("amendment_number", description="Sort field"),
    sort_desc: bool = Query(False, description="Sort descending"),
    limit: int = Query(50, ge=1, le=500, description="Items per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> MEPAmendmentListResponse:
    """List amendments with optional filters."""
    try:
        if current_user.subscription_tier not in ['yellow', 'blue', 'admin']:
            raise HTTPException(status_code=403, detail="Yellow or Blue subscription required")

        query = db.query(MEPAmendment).filter(
            MEPAmendment.procedure_reference == procedure_ref
        )
        filters_applied = {}

        if group:
            # "Rapporteur" maps to amendments with no group and no authors
            if group == 'Rapporteur':
                query = query.filter(
                    (MEPAmendment.political_group.is_(None)) | (MEPAmendment.political_group == ''),
                    func.array_length(MEPAmendment.author_names, 1).is_(None),
                )
            else:
                query = query.filter(MEPAmendment.political_group == group)
            filters_applied['group'] = group

        if author:
            # Search in the author_names array (PostgreSQL ANY)
            query = query.filter(
                MEPAmendment.author_names.any(author)
            )
            filters_applied['author'] = author

        if element_type:
            query = query.filter(MEPAmendment.element_type == element_type)
            filters_applied['element_type'] = element_type

        if amendment_type:
            query = query.filter(MEPAmendment.amendment_type == amendment_type)
            filters_applied['amendment_type'] = amendment_type

        if committee:
            query = query.filter(MEPAmendment.committee_code == committee)
            filters_applied['committee'] = committee

        # Count total before pagination
        total = query.count()

        # Sort
        sort_column = getattr(MEPAmendment, sort_by, MEPAmendment.amendment_number)
        if sort_desc:
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Paginate
        items = query.offset(offset).limit(limit).all()

        # Label rapporteur amendments (no group + no authors = draft report)
        response_items = []
        for a in items:
            item = MEPAmendmentResponse.model_validate(a)
            if not item.political_group and len(item.author_names) == 0:
                item.political_group = 'Rapporteur'
            response_items.append(item)

        return MEPAmendmentListResponse(
            items=response_items,
            total=total,
            limit=limit,
            offset=offset,
            filters_applied=filters_applied if filters_applied else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to list amendments for {procedure_ref}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
