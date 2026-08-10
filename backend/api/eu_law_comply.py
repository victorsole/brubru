"""
EU Law Comply API Endpoints

Handles compliance checking, gap analysis, and requirement extraction for EU laws.
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, case, text
from typing import Any, Dict, List, Optional
from datetime import datetime
import hashlib
import logging
import tempfile
import os
from pathlib import Path

from core.database import get_db
from core.config import settings
from models.user import User
from models.eu_law import LawCluster, EULaw, LawRequirement, ClusterLaw
from services.tracking.tracked_files_seeder import _interest_list
from services.tracking.tracked_lens import tracked_anchors
from models.compliance import (
    ComplianceAnalysis, GapFinding, AnalysisExport, ComplianceAction,
    ComplianceWorkspace,
)
from models.user_document import UserDocument
from api.auth import get_current_user
from services.compliance import GapAnalyzer
from services.compliance.report_exporter import ReportExporter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/eu-law-comply", tags=["eu-law-comply"])


# Severity ordering. `criticality` is a free-text column, so ORDER BY criticality DESC
# sorts ALPHABETICALLY -- which put 'recommended' first and buried 'critical' last, the
# exact inverse of what a compliance user needs. Always order by this expression, never
# by the raw column. The vocabulary is normalised to these three values by
# scripts/normalise_requirement_criticality.py; anything unrecognised sorts last.
CRITICALITY_ORDER = case(
    (LawRequirement.criticality == 'critical', 0),
    (LawRequirement.criticality == 'important', 1),
    (LawRequirement.criticality == 'recommended', 2),
    else_=3,
)


def _confidence_pct(value) -> Optional[float]:
    """Return a gap finding's confidence as a 0-100 percentage.

    gap_findings.confidence_score is documented as 0-100 but the LLM prompt in
    gap_analyzer.py asks for 0.0-1.0, so every row written before 8 Aug 2026 holds a
    fraction. The frontend rendered `Math.round(score)%`, which turned 0.9 into "1%"
    and 0.2 into "0%" -- every confidence in the product was displayed as 0 or 1 per
    cent. Normalise on the way out so both the legacy fractions and any future 0-100
    values render correctly.
    """
    if value is None:
        return None
    v = float(value)
    return round(v * 100, 1) if v <= 1.0 else round(v, 1)


# ============================================================================
# BACKGROUND TASKS
# ============================================================================

async def run_compliance_analysis_task(
    analysis_id: int,
    cluster_id: int,
    document_paths: List[str]
):
    """
    Background task to run compliance analysis.

    This runs asynchronously after the API returns to the user.
    """
    from core.database import SessionLocal

    db = SessionLocal()

    try:
        logger.info(f"Starting background analysis for analysis_id={analysis_id}")

        # Get the BINDING requirements for this cluster.
        #
        # extra_metadata.interpretive marks rows that explain the law rather
        # than impose a duty: recitals, penalty ceilings, application dates,
        # classification thresholds a company is nowhere near, and support
        # measures such as regulatory sandboxes. 306 rows carry the flag and
        # until now nothing read it, so a penalties article was put to the
        # model as an obligation and came back a "gap" -- telling a company it
        # had failed to comply with the size of its own potential fine.
        #
        # They stay in the corpus and in the cluster preview, where the context
        # is worth reading. They are simply not scored.
        # COALESCE rather than a bare `!=`: the column is declared JSON, so a
        # missing key yields SQL NULL, and `NULL != 'true'` is NULL, not true.
        # Without the coalesce this filter would drop every requirement that
        # has no extra_metadata at all, which is most of the corpus.
        requirements = db.query(LawRequirement).filter(
            LawRequirement.cluster_id == cluster_id,
            func.coalesce(
                LawRequirement.extra_metadata['interpretive'].as_string(), ''
            ) != 'true',
        ).all()

        if not requirements:
            logger.warning(f"No requirements found for cluster {cluster_id}")
            analysis = db.query(ComplianceAnalysis).filter(
                ComplianceAnalysis.id == analysis_id
            ).first()
            if analysis:
                analysis.status = 'failed'
                analysis.completed_at = datetime.utcnow()
                db.commit()
            return

        logger.info(f"Found {len(requirements)} requirements to check")

        # Run gap analysis
        analyzer = GapAnalyzer(db)
        await analyzer.analyze_compliance(analysis_id, requirements, document_paths)

        logger.info(f"Compliance analysis {analysis_id} completed successfully")

    except Exception as e:
        logger.error(f"Background analysis failed for {analysis_id}: {str(e)}")

        # Mark the run failed, and be stubborn about it. The previous version
        # reused `db` and swallowed any secondary error with a bare except, so
        # when the original failure was a dropped database connection the status
        # write failed too and the run sat in 'processing' forever -- a poll loop
        # with no terminal state, indistinguishable from a slow analysis.
        #
        # Two attempts: roll back the poisoned session and retry on it, then fall
        # back to a completely fresh session. A run whose status cannot be
        # written is logged at error level, never passed over in silence.
        marked = False
        for attempt, session in enumerate(('rolled-back', 'fresh')):
            fresh = None
            try:
                if session == 'rolled-back':
                    db.rollback()
                    target = db
                else:
                    fresh = SessionLocal()
                    target = fresh
                analysis = target.query(ComplianceAnalysis).filter(
                    ComplianceAnalysis.id == analysis_id
                ).first()
                if analysis:
                    analysis.status = 'failed'
                    analysis.completed_at = datetime.utcnow()
                    analysis.analysis_params = {
                        **(analysis.analysis_params or {}),
                        'failure': str(e)[:500],
                    }
                    target.commit()
                marked = True
                break
            except Exception as inner:
                logger.warning(
                    f"Could not mark analysis {analysis_id} failed via the "
                    f"{session} session: {type(inner).__name__}: {inner}"
                )
            finally:
                if fresh is not None:
                    fresh.close()
        if not marked:
            logger.error(
                f"Analysis {analysis_id} is stuck in 'processing': the run failed "
                f"and neither session could record it. A client polling this id "
                f"will never see a terminal state."
            )

    finally:
        db.close()
        # The uploads were written with NamedTemporaryFile(delete=False) so they
        # would survive until the background task read them. Nothing deleted
        # them afterwards, so every analysis left its documents behind in the
        # system temp directory -- user-uploaded compliance material, kept
        # indefinitely on the container. Clean up here: this is the last point
        # that holds the paths, and it runs on the success and failure paths
        # alike.
        for path in document_paths or []:
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
            except OSError as exc:
                logger.warning(f"Could not remove temp upload {path}: {exc}")


# ============================================================================
# CLUSTER ENDPOINTS
# ============================================================================

@router.get("/clusters")
def list_clusters(
    startup_focused: Optional[bool] = None,
    policy_area: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all law clusters.

    Query Parameters:
    - startup_focused: Filter on the startup-oriented compliance packages
    - policy_area: Filter by policy area

    Returns list of clusters with law count and requirement count.
    """
    try:
        # Check user tier (EU Law Comply is Yellow/Blue only)
        if current_user.subscription_tier not in ['yellow', 'blue']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="EU Law Comply is available for Yellow and Blue tier users only"
            )

        # Unpublished packages never appear in the catalogue. They still resolve
        # by id, so an analysis someone already ran keeps working (migration 210).
        query = db.query(LawCluster).filter(LawCluster.is_published.is_(True))

        # Filter on the explicit flag (migration 205), never on the id. This was
        # `LawCluster.id > 11`, hardcoded when clusters 12-21 happened to be the
        # ten startup packages; every cluster seeded afterwards (ids 22-62) fell
        # on the wrong side of it, so this returned 51 "startup packages".
        if startup_focused is not None:
            query = query.filter(LawCluster.is_startup_focused.is_(bool(startup_focused)))

        # Filter by policy area
        if policy_area:
            query = query.filter(LawCluster.policy_area == policy_area)

        clusters = query.order_by(LawCluster.id).all()

        # Counts come from two grouped queries, not two per cluster. The previous
        # implementation issued 2*N COUNT round-trips (122 for 61 clusters), which cost
        # ~3.4s in production and ~24s against a remote DB from a dev machine, on the
        # endpoint that renders the EU Law Comply landing page. Keep this aggregated.
        law_counts = dict(
            db.query(ClusterLaw.cluster_id, func.count(ClusterLaw.law_id))
            .group_by(ClusterLaw.cluster_id)
            .all()
        )
        requirement_counts = dict(
            db.query(LawRequirement.cluster_id, func.count(LawRequirement.id))
            .filter(LawRequirement.cluster_id.isnot(None))
            .group_by(LawRequirement.cluster_id)
            .all()
        )

        result = []
        for cluster in clusters:
            law_count = law_counts.get(cluster.id, 0)
            requirement_count = requirement_counts.get(cluster.id, 0)

            result.append({
                'id': cluster.id,
                'name': cluster.name,
                'description': cluster.description,
                'applicability': cluster.applicability,
                'policy_area': cluster.policy_area,
                'priority_level': cluster.priority_level,
                'law_count': law_count or 0,
                'requirement_count': requirement_count or 0
            })

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing clusters: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve clusters"
        )


@router.get("/clusters/for-me",
            summary="Compliance clusters for your interests and tracked files",
            description=(
                "**What it does**\nReturns the EU-law compliance clusters that match "
                "your Policy Interests (soft) or contain a law from the files you track "
                "(hard), each flagged with why it surfaced.\n\n"
                "**When to use it**\nThe 'For you' section at the top of EU Law Comply.\n\n"
                "**You get back**\nClusters with law/requirement counts + `matches_interests` "
                "and `matches_tracked` registers."))
def clusters_for_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.subscription_tier not in ['yellow', 'blue']:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="EU Law Comply is available for Yellow and Blue tier users only")
    try:
        interests = set(_interest_list(current_user))
        tracked = tracked_anchors(db, str(current_user.id))
        tracked_celex = tracked.get("celex", set())

        # Hard register: clusters containing a law whose CELEX the user tracks.
        hard_cluster_ids: set = set()
        if tracked_celex:
            law_ids = [r[0] for r in db.query(EULaw.id).filter(EULaw.celex.in_(list(tracked_celex))).all()]
            if law_ids:
                hard_cluster_ids = {r[0] for r in db.query(ClusterLaw.cluster_id)
                                    .filter(ClusterLaw.law_id.in_(law_ids)).distinct().all()}

        # Soft register: clusters whose policy_area is one of the user's interests.
        soft_ids = set()
        if interests:
            soft_ids = {c.id for c in db.query(LawCluster.id)
                        .filter(LawCluster.policy_area.in_(list(interests))).all()}

        ids = soft_ids | hard_cluster_ids
        if not ids:
            return {"clusters": []}
        clusters = (db.query(LawCluster)
                    .filter(LawCluster.id.in_(ids),
                            LawCluster.is_published.is_(True))
                    .order_by(LawCluster.id).all())

        out = []
        for c in clusters:
            law_count = db.query(func.count(ClusterLaw.law_id)).filter(ClusterLaw.cluster_id == c.id).scalar()
            req_count = db.query(func.count(LawRequirement.id)).filter(LawRequirement.cluster_id == c.id).scalar()
            out.append({
                'id': c.id, 'name': c.name, 'description': c.description,
                'applicability': c.applicability, 'policy_area': c.policy_area,
                'priority_level': c.priority_level,
                'law_count': law_count or 0, 'requirement_count': req_count or 0,
                'matches_interests': c.policy_area in interests,
                'matches_tracked': c.id in hard_cluster_ids,
            })
        # Hard matches first, then by id.
        out.sort(key=lambda x: (not x['matches_tracked'], x['id']))
        return {"clusters": out}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"clusters_for_me failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve your clusters")


@router.get("/clusters/{cluster_id}")
async def get_cluster_details(
    cluster_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed information about a specific cluster.

    Includes:
    - Cluster metadata
    - List of laws in the cluster with relationship types
    - Count of requirements by criticality
    """
    try:
        # Check user tier
        if current_user.subscription_tier not in ['yellow', 'blue']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="EU Law Comply is available for Yellow and Blue tier users only"
            )

        # Get cluster
        cluster = db.query(LawCluster).filter(LawCluster.id == cluster_id).first()
        if not cluster:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cluster {cluster_id} not found"
            )

        # Get laws in cluster with relationship types
        cluster_laws = db.query(ClusterLaw, EULaw).join(
            EULaw, ClusterLaw.law_id == EULaw.id
        ).filter(
            ClusterLaw.cluster_id == cluster_id
        ).all()

        laws = []
        for cl, law in cluster_laws:
            laws.append({
                'id': law.id,
                'celex': law.celex,
                'title': law.title,
                'date': law.date.isoformat() if law.date else None,
                'relationship_type': cl.relationship_type,
                'doc_type': law.doc_type
            })

        # Count requirements by criticality
        requirements_by_criticality = db.query(
            LawRequirement.criticality,
            func.count(LawRequirement.id)
        ).filter(
            LawRequirement.cluster_id == cluster_id
        ).group_by(
            LawRequirement.criticality
        ).all()

        criticality_counts = {
            crit: count for crit, count in requirements_by_criticality
        }

        total_requirements = sum(criticality_counts.values())

        return {
            'id': cluster.id,
            'name': cluster.name,
            'description': cluster.description,
            'applicability': cluster.applicability,
            'policy_area': cluster.policy_area,
            'priority_level': cluster.priority_level,
            'law_count': len(laws),
            'laws': laws,
            'requirement_count': total_requirements,
            'requirements_by_criticality': criticality_counts
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting cluster details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve cluster details"
        )


@router.get("/clusters/{cluster_id}/requirements")
async def get_cluster_requirements(
    cluster_id: int,
    criticality: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all requirements for a cluster.

    Query Parameters:
    - criticality: Filter by criticality ('critical', 'important', 'recommended')

    Returns list of requirements with full details.
    """
    try:
        # Check user tier
        if current_user.subscription_tier not in ['yellow', 'blue']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="EU Law Comply is available for Yellow and Blue tier users only"
            )

        # Verify cluster exists
        cluster = db.query(LawCluster).filter(LawCluster.id == cluster_id).first()
        if not cluster:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cluster {cluster_id} not found"
            )

        # Build query
        query = db.query(LawRequirement, EULaw).join(
            EULaw, LawRequirement.law_id == EULaw.id
        ).filter(
            LawRequirement.cluster_id == cluster_id
        )

        # Filter by criticality if specified
        if criticality:
            query = query.filter(LawRequirement.criticality == criticality)

        requirements_with_laws = query.order_by(
            CRITICALITY_ORDER,
            LawRequirement.deadline.asc().nullslast(),
            LawRequirement.article
        ).all()

        result = []
        for req, law in requirements_with_laws:
            result.append({
                'id': req.id,
                'law_id': req.law_id,
                'law_title': law.title,
                'law_celex': law.celex,
                'article_number': req.article,
                'requirement_text': req.requirement_text,
                'applicable_entity': req.applicable_entity,
                'deadline': req.deadline.isoformat() if req.deadline else None,
                'criticality': req.criticality,
                'extra_metadata': req.extra_metadata
            })

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting cluster requirements: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve requirements"
        )



@router.get(
    "/clusters/{cluster_id}/cascade",
    summary="Delegated acts, implementing acts and Commission guidance for a package",
    description=(
        "**What it does**\n\n"
        "Returns everything that hangs off the laws in a compliance package: the "
        "delegated and implementing acts that carry the operative detail, and the "
        "Commission notices and guidelines that explain how to comply. Grouped by "
        "kind, because the first two create obligations and the third does not.\n\n"
        "**When to use it**\n\n"
        "Alongside GET /clusters/{id}/requirements when showing a user what a "
        "package actually covers before they upload anything.\n\n"
        "**Input**\n\n"
        "Path: `cluster_id`. Bearer JWT.\n\n"
        "**Try it**\n\n"
        "`GET /api/eu-law-comply/clusters/58/cascade`.\n\n"
        "**You get back**\n\n"
        "`binding` (delegated + implementing) and `guidance` lists, each with "
        "celex, title, parent_celex, status and a EUR-Lex link, plus counts. "
        "Empty lists where nothing has been discovered: never padded."
    ),
)
def get_cluster_cascade(
    cluster_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.subscription_tier not in ['yellow', 'blue']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="EU Law Comply is available for Yellow and Blue tier users only",
        )
    cluster = db.query(LawCluster).filter(LawCluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Cluster {cluster_id} not found")

    # secondary_acts is keyed on the PARENT's CELEX, so join through the
    # cluster's laws rather than through any procedure reference.
    rows = db.execute(text("""
        SELECT s.celex, s.title, s.parent_celex, s.act_type::text AS act_type,
               s.status::text AS status, s.source_url, s.publication_date
          FROM secondary_acts s
         WHERE s.parent_celex IN (
                 SELECT l.celex FROM cluster_laws cl
                   JOIN eu_laws l ON l.id = cl.law_id
                  WHERE cl.cluster_id = :cid AND l.celex IS NOT NULL)
           AND s.celex IS NOT NULL
         ORDER BY s.act_type, s.publication_date DESC NULLS LAST, s.celex
    """), {"cid": cluster_id}).mappings().all()

    binding, guidance = [], []
    for r in rows:
        item = {
            "celex": r["celex"],
            "title": r["title"],
            "parent_celex": r["parent_celex"],
            "act_type": r["act_type"],
            "status": r["status"],
            "url": r["source_url"] or
                  f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{r['celex']}",
            "publication_date": r["publication_date"].isoformat() if r["publication_date"] else None,
        }
        (guidance if r["act_type"] == "guidance" else binding).append(item)

    return {
        "cluster_id": cluster_id,
        "cluster_name": cluster.name,
        "binding": binding,
        "guidance": guidance,
        "counts": {
            "delegated": sum(1 for i in binding if i["act_type"] == "delegated"),
            "implementing": sum(1 for i in binding if i["act_type"] == "implementing"),
            "guidance": len(guidance),
        },
    }


# ============================================================================
# CLUSTER SUGGESTION ENDPOINT
# ============================================================================

@router.get("/suggest-clusters")
async def suggest_clusters(
    description: str,
    limit: int = 5,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Suggest relevant compliance clusters based on a business description.

    Uses TSVECTOR full-text search to find laws matching the description,
    then returns clusters those laws belong to.
    """
    from services.eu_law_search import EULawSearchService

    try:
        if current_user.subscription_tier not in ['yellow', 'blue']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="EU Law Comply is available for Yellow and Blue tier users only"
            )

        search_service = EULawSearchService(db)

        # Find relevant laws via TSVECTOR search
        matching_laws = search_service.search_tsvector(
            query=description,
            primary_only=True,
            doc_types=["Regulation", "Directive"],
            limit=20,
        )

        if not matching_laws:
            return {"clusters": [], "message": "No matching laws found for this description"}

        # Find which clusters these laws belong to
        matching_celex = [law['celex'] for law in matching_laws if law.get('celex')]

        if not matching_celex:
            return {"clusters": [], "message": "No CELEX-identified laws matched"}

        # Get law IDs for matched CELEX numbers
        matched_law_ids = db.query(EULaw.id).filter(
            EULaw.celex.in_(matching_celex)
        ).all()
        law_ids = [row[0] for row in matched_law_ids]

        if not law_ids:
            return {"clusters": [], "message": "No clustered laws matched"}

        # Find clusters containing these laws
        cluster_hits = db.query(
            LawCluster.id,
            LawCluster.name,
            LawCluster.description,
            LawCluster.policy_area,
            func.count(ClusterLaw.law_id).label('match_count')
        ).join(
            ClusterLaw, ClusterLaw.cluster_id == LawCluster.id
        ).filter(
            ClusterLaw.law_id.in_(law_ids)
        ).group_by(
            LawCluster.id, LawCluster.name, LawCluster.description, LawCluster.policy_area
        ).order_by(
            func.count(ClusterLaw.law_id).desc()
        ).limit(limit).all()

        clusters = [
            {
                "id": hit.id,
                "name": hit.name,
                "description": hit.description,
                "policy_area": hit.policy_area,
                "relevance_score": hit.match_count,
            }
            for hit in cluster_hits
        ]

        return {
            "clusters": clusters,
            "laws_searched": len(matching_laws),
            "laws_with_clusters": len(law_ids),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error suggesting clusters: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to suggest clusters"
        )


# ============================================================================
# LAW DATABASE ENDPOINTS
# ============================================================================

@router.get("/laws/search")
async def search_laws(
    query: str = "",
    policy_area: Optional[str] = None,
    doc_type: Optional[str] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Search the EU law database (28K+ laws).

    Query Parameters:
    - query: Text search in title
    - policy_area: Filter by policy area
    - doc_type: Filter by document type (Regulation, Directive, Decision)
    - year_from: Filter by year (from)
    - year_to: Filter by year (to)
    - limit: Max results (default 20)
    - offset: Pagination offset

    Returns list of laws matching criteria.
    """
    from services.eu_law_search import EULawSearchService

    try:
        # Check user tier
        if current_user.subscription_tier not in ['yellow', 'blue']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="EU Law Comply is available for Yellow and Blue tier users only"
            )

        search_service = EULawSearchService(db)
        response = search_service.search(
            query=query,
            policy_area=policy_area,
            doc_type=doc_type,
            year_from=year_from,
            year_to=year_to,
            limit=min(limit, 100),  # Cap at 100
            offset=offset
        )

        return response.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching laws: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search laws"
        )


# NOTE ON ORDER: /laws/stats MUST stay above /laws/{celex}. FastAPI matches routes in
# registration order, so with {celex} first, GET /laws/stats bound to that route with
# celex="stats" and returned 404 -- the stats endpoint was unreachable in production.
# Any new literal /laws/<word> route goes above the {celex} one too.
@router.get("/laws/stats")
async def get_law_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get statistics about the EU law database.

    Returns counts by policy area, document type, and year.
    """
    from services.eu_law_search import EULawSearchService

    try:
        if current_user.subscription_tier not in ['yellow', 'blue']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="EU Law Comply is available for Yellow and Blue tier users only"
            )

        search_service = EULawSearchService(db)

        return {
            'total_laws': db.query(EULaw).count(),
            'by_policy_area': search_service.get_policy_area_stats(),
            'by_doc_type': search_service.get_doc_type_stats(),
            'by_year': search_service.get_year_stats(year_from=2015),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting law stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics"
        )


@router.get("/laws/{celex}")
async def get_law_by_celex(
    celex: str,
    include_full_text: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific law by CELEX number.

    Path Parameters:
    - celex: CELEX number (e.g., "32016R0679" for GDPR)

    Query Parameters:
    - include_full_text: If True, include full parsed text (slower)

    Returns detailed law information with parsed content.
    """
    from services.parsers import EurlexFetcher

    try:
        # Check user tier
        if current_user.subscription_tier not in ['yellow', 'blue']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="EU Law Comply is available for Yellow and Blue tier users only"
            )

        fetcher = EurlexFetcher(db=db)
        result = fetcher.get_law_sync(celex)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Law {celex} not found"
            )

        response = {
            'celex': result.celex,
            'title': result.title,
            'short_title': result.short_title,
            'doc_type': result.doc_type,
            'date': result.date.isoformat() if result.date else None,
            'oj_reference': result.oj_reference,
            'policy_area': result.policy_area,
            'legal_basis': result.legal_basis,
            'source': result.source,
            'article_count': len(result.articles),
            'recital_count': len(result.recitals),
            'annex_count': len(result.annexes),
        }

        if include_full_text:
            response['articles'] = result.articles
            response['recitals'] = result.recitals
            response['annexes'] = result.annexes

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting law {celex}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve law"
        )


# ============================================================================
# ANALYSIS ENDPOINTS
# ============================================================================

@router.post("/analyze")
async def create_compliance_analysis(
    cluster_id: int = Form(...),
    documents: Optional[List[UploadFile]] = File(None),
    # UUIDs of user_documents from an earlier run of this package, comma
    # separated. Migration 209 started storing the extracted text of every
    # upload, but nothing could read it back, so each run began at an empty
    # dropzone even though last month's policy was sitting in the database.
    # Either source is enough on its own, and they can be combined: re-use the
    # policy, add the new annex.
    reuse_document_ids: Optional[str] = Form(None),
    analysis_name: Optional[str] = Form(None),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new compliance analysis.

    Uploads documents and initiates gap analysis against the selected cluster.
    The analysis runs asynchronously and status can be checked via GET /analysis/{id}.

    Parameters:
    - cluster_id: ID of the law cluster to check compliance against
    - documents: List of PDF/DOCX/TXT files containing company policies
    - analysis_name: Optional name for this analysis (e.g., "Q4 2025 DSA Check")

    Returns the created analysis object with ID.
    """
    try:
        # Check user tier
        if current_user.subscription_tier not in ['yellow', 'blue']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="EU Law Comply is available for Yellow and Blue tier users only"
            )

        # Verify cluster exists
        cluster = db.query(LawCluster).filter(LawCluster.id == cluster_id).first()
        if not cluster:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cluster {cluster_id} not found"
            )

        # FastAPI hands back a single empty UploadFile when a multipart field is
        # declared but sent blank, so filter those out before counting.
        documents = [d for d in (documents or []) if d and d.filename]

        reuse_ids: List[str] = [
            s.strip() for s in (reuse_document_ids or '').split(',') if s.strip()
        ]

        if not documents and not reuse_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Upload at least one document, or re-use one from an earlier run"
            )

        # Check file types
        allowed_extensions = {'.pdf', '.docx', '.doc', '.txt'}
        for doc in documents:
            filename = doc.filename.lower()
            if not any(filename.endswith(ext) for ext in allowed_extensions):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported file type: {doc.filename}. Allowed: PDF, DOCX, TXT"
                )

        # Save uploaded documents to temporary files
        document_paths = []
        document_ids = []

        for uploaded_file in documents:
            try:
                # Create temporary file
                suffix = Path(uploaded_file.filename).suffix
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                    content = await uploaded_file.read()
                    tmp_file.write(content)
                    tmp_path = tmp_file.name

                document_paths.append(tmp_path)

                # TODO: Optionally save to user_documents table for persistence
                # For now, using temp files which will be cleaned up after analysis

                logger.info(f"Saved uploaded file {uploaded_file.filename} to {tmp_path}")

            except Exception as e:
                logger.error(f"Error saving file {uploaded_file.filename}: {str(e)}")
                # Clean up any already saved files
                for path in document_paths:
                    try:
                        os.unlink(path)
                    except:
                        pass
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to save document: {uploaded_file.filename}"
                )

        # Re-used documents: write the stored extracted text back out as .txt so
        # the analyser reads them by exactly the same path as a fresh upload.
        # Ownership is enforced in the query, so a guessed UUID belonging to
        # another user simply does not resolve.
        reused_uuids = []
        if reuse_ids:
            stored = (
                db.query(UserDocument)
                .filter(UserDocument.id.in_(reuse_ids),
                        UserDocument.user_id == current_user.id)
                .all()
            )
            found = {str(d.id) for d in stored}
            missing = [i for i in reuse_ids if i not in found]
            if missing:
                logger.warning(
                    f"Re-use requested for {len(missing)} document(s) that do not "
                    f"belong to user {current_user.id} or no longer exist: {missing}"
                )
            for d in stored:
                if not (d.content or '').strip():
                    # An empty stored document would silently weaken the run:
                    # every requirement would come back a gap for lack of
                    # evidence. Skip it and say so rather than analyse nothing.
                    logger.warning(f"Re-used document {d.id} has no extracted text; skipping")
                    continue
                with tempfile.NamedTemporaryFile(
                        delete=False, suffix='.txt', mode='w', encoding='utf-8') as tmp:
                    tmp.write(d.content)
                    document_paths.append(tmp.name)
                reused_uuids.append(d.id)

            if not document_paths:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="None of the selected documents could be re-used. "
                           "Upload the document again.",
                )

        # One durable workspace per (user, cluster). Runs, uploads and
        # remediation state all hang off it, so a second analysis of the same
        # package continues the first rather than starting from nothing.
        workspace = (
            db.query(ComplianceWorkspace)
            .filter(ComplianceWorkspace.user_id == current_user.id,
                    ComplianceWorkspace.cluster_id == cluster_id)
            .first()
        )
        if not workspace:
            workspace = ComplianceWorkspace(
                user_id=current_user.id, cluster_id=cluster_id, name=cluster.name)
            db.add(workspace)
            db.flush()

        # Persist the uploads. They used to live only in /tmp: read once,
        # deleted, and `document_ids` was ARRAY(Integer) against a UUID primary
        # key so nothing was ever recorded. A run was therefore unreproducible
        # and unauditable -- you could not answer "what did we actually check?"
        # a week later. Store the EXTRACTED TEXT, which is what the analyser
        # reads, rather than the original blob.
        from services.compliance.document_processor import DocumentProcessor
        processor = DocumentProcessor()
        # Re-used documents are already stored, so they are recorded on this run
        # without being written again. Fresh uploads occupy the FIRST len(documents)
        # entries of document_paths (the save loop runs before the re-use block),
        # so zip pairs them correctly and stops before the re-used tail.
        document_uuids = list(reused_uuids)
        for path, uploaded in zip(document_paths, documents):
            # SAVEPOINT per document. A plain try/except is not enough: a failed
            # flush poisons the whole Session, so the analysis INSERT that
            # follows fails too and the entire run dies over a provenance
            # record. Found exactly that way -- document_type 'compliance_upload'
            # violated the user_documents CHECK constraint, which permits only
            # amendment / analysis / strategy / note / uploaded, and took the
            # run with it.
            try:
                with db.begin_nested():
                    extracted = processor.process_document(path)
                    doc = UserDocument(
                        user_id=current_user.id,
                        document_type='uploaded',
                        title=(uploaded.filename or 'Uploaded document')[:500],
                        content=extracted.get('text') or '',
                        original_filename=(uploaded.filename or None),
                        include_in_ai_context=False,
                    )
                    db.add(doc)
                    db.flush()
                document_uuids.append(doc.id)
            except Exception as exc:  # noqa: BLE001
                # The document is still analysed from /tmp; we simply cannot
                # store it. Never fail the run over provenance.
                logger.warning(f"Could not persist upload {uploaded.filename}: {exc}")

        # Create analysis in processing state
        analysis = ComplianceAnalysis(
            user_id=current_user.id,
            cluster_id=cluster_id,
            workspace_id=workspace.id,
            analysis_name=analysis_name or f"{cluster.name} Analysis",
            status='processing',
            document_uuids=document_uuids or None,
            started_at=datetime.utcnow()
        )

        db.add(analysis)
        db.commit()
        db.refresh(analysis)

        # Trigger background analysis task
        if background_tasks:
            background_tasks.add_task(
                run_compliance_analysis_task,
                analysis.id,
                cluster_id,
                document_paths
            )
            logger.info(f"Scheduled background analysis task for analysis_id={analysis.id}")
        else:
            logger.warning("BackgroundTasks not available, analysis will not run")

        logger.info(f"Created compliance analysis {analysis.id} for user {current_user.id}")

        return {
            'id': analysis.id,
            'cluster_id': cluster_id,
            'cluster_name': cluster.name,
            'analysis_name': analysis.analysis_name,
            'status': analysis.status,
            'started_at': analysis.started_at.isoformat(),
            'message': 'Analysis started. Check status via GET /analysis/{id}'
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating compliance analysis: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create compliance analysis"
        )


@router.get("/analysis/{analysis_id}")
async def get_analysis_results(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get results of a compliance analysis.

    Returns:
    - Analysis summary (compliance score, status)
    - All gap findings with detailed information
    - Action plan items sorted by priority
    """
    try:
        # Get analysis
        analysis = db.query(ComplianceAnalysis).filter(
            and_(
                ComplianceAnalysis.id == analysis_id,
                ComplianceAnalysis.user_id == current_user.id
            )
        ).first()

        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis {analysis_id} not found"
            )

        # Get cluster info
        cluster = db.query(LawCluster).filter(
            LawCluster.id == analysis.cluster_id
        ).first()

        # Get gap findings with requirement details
        gap_findings = db.query(GapFinding, LawRequirement, EULaw).join(
            LawRequirement, GapFinding.requirement_id == LawRequirement.id
        ).join(
            EULaw, LawRequirement.law_id == EULaw.id
        ).filter(
            GapFinding.analysis_id == analysis_id
        ).order_by(
            GapFinding.priority,
            CRITICALITY_ORDER
        ).all()

        findings = []
        for finding, requirement, law in gap_findings:
            findings.append({
                'id': finding.id,
                'requirement_id': requirement.id,
                'article_number': requirement.article,
                'requirement_text': requirement.requirement_text,
                'law_title': law.title,
                'law_celex': law.celex,
                'status': finding.status,
                'confidence_score': _confidence_pct(finding.confidence_score),
                'evidence_text': finding.evidence_text,
                'evidence_source': finding.evidence_source,
                'gap_description': finding.gap_description,
                'recommendation': finding.recommendation,
                'priority': finding.priority,
                'estimated_effort': finding.estimated_effort,
                'criticality': requirement.criticality,
                # Who the obligation binds. A finding on "Member States shall
                # bring into force the laws necessary..." is not_applicable to a
                # company, and without this the reader sees an unexplained N/A.
                # The cluster preview already showed it; the results did not.
                'addressee': (requirement.extra_metadata or {}).get('addressee') or 'economic_operator',
                'deadline_date': requirement.deadline.isoformat() if requirement.deadline else None,
                'deadline_text': None  # TODO: Add deadline_text to LawRequirement model
            })

        return {
            'id': analysis.id,
            'cluster': {
                'id': cluster.id,
                'name': cluster.name,
                'policy_area': cluster.policy_area
            },
            'status': analysis.status,
            'total_requirements': analysis.total_requirements,
            'requirements_met': analysis.requirements_met,
            'requirements_partial': analysis.requirements_partial,
            'requirements_gap': analysis.requirements_gap,
            'compliance_score': float(analysis.compliance_score) if analysis.compliance_score is not None else None,
            # Migration 209 gave a run a durable home and a record of the
            # documents it was actually performed against. Both were persisted
            # but neither was serialised, so no client could reach them.
            'workspace_id': analysis.workspace_id,
            'document_uuids': [str(u) for u in (analysis.document_uuids or [])],
            'gap_findings': findings,
            'created_at': analysis.started_at.isoformat() if analysis.started_at else None,
            'completed_at': analysis.completed_at.isoformat() if analysis.completed_at else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting analysis results: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analysis results"
        )


@router.post("/analysis/{analysis_id}/export")
async def export_analysis_report(
    analysis_id: int,
    export_format: str = 'docx',
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export compliance report to DOCX/PDF format.

    Parameters:
    - export_format: 'docx' or 'pdf' (default: 'docx')

    Returns URL to download the generated report.
    Yellow tier users get watermarked reports.
    Blue tier users get reports without watermark.
    Both 'docx' and 'pdf' are supported.
    """
    try:
        # Get analysis
        analysis = db.query(ComplianceAnalysis).filter(
            and_(
                ComplianceAnalysis.id == analysis_id,
                ComplianceAnalysis.user_id == current_user.id
            )
        ).first()

        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis {analysis_id} not found"
            )

        if analysis.status != 'completed':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Analysis must be completed before export"
            )

        # Validate format
        if export_format not in ['docx', 'pdf']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Export format must be 'docx' or 'pdf'"
            )

        # Both formats share one path. PDF returned 501 until 8 Aug 2026; it is
        # now produced by ReportExporter.export_analysis_pdf from the same data
        # as the DOCX, so the two cannot disagree.
        include_watermark = current_user.subscription_tier == 'yellow'

        cluster = db.query(LawCluster).filter(LawCluster.id == analysis.cluster_id).first()
        safe_cluster = (cluster.name if cluster else f"cluster_{analysis.cluster_id}")
        safe_cluster = "".join(c if c.isalnum() or c in "-_" else "_" for c in safe_cluster)[:60]
        filename = f"Brubru_EU_Compliance_Report_{safe_cluster}_{analysis_id}.{export_format}"
        output_path = os.path.join(tempfile.gettempdir(), filename)

        exporter = ReportExporter(db)
        if export_format == 'pdf':
            exporter.export_analysis_pdf(analysis_id, output_path, include_watermark)
            media_type = 'application/pdf'
        else:
            exporter.export_analysis(analysis_id, output_path, include_watermark)
            media_type = ('application/vnd.openxmlformats-officedocument'
                          '.wordprocessingml.document')

        file_size = os.path.getsize(output_path)

        export = AnalysisExport(
            analysis_id=analysis_id,
            user_id=current_user.id,
            export_format=export_format,
            file_path=output_path,
            file_size_bytes=file_size,
            created_at=datetime.utcnow()
        )
        db.add(export)
        db.commit()
        db.refresh(export)

        logger.info(
            f"Generated {export_format.upper()} export {export.id} "
            f"({file_size} bytes) for analysis {analysis_id}"
        )

        from fastapi.responses import FileResponse
        return FileResponse(
            path=output_path,
            filename=filename,
            media_type=media_type,
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting analysis: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export analysis"
        )


@router.get("/history")
async def get_user_analysis_history(
    limit: int = 10,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get user's compliance analysis history.

    Used for:
    - Usage history sidebar in EU Law Comply page
    - Dashboard in My EU Bubble

    Parameters:
    - limit: Number of analyses to return (default: 10)
    - offset: Pagination offset (default: 0)

    Returns list of past analyses with summary info.
    """
    try:
        # Get user's analyses
        analyses = db.query(ComplianceAnalysis, LawCluster).join(
            LawCluster, ComplianceAnalysis.cluster_id == LawCluster.id
        ).filter(
            ComplianceAnalysis.user_id == current_user.id
        ).order_by(
            ComplianceAnalysis.created_at.desc()
        ).limit(limit).offset(offset).all()

        result = []
        for analysis, cluster in analyses:
            result.append({
                'id': analysis.id,
                'analysis_name': analysis.analysis_name,
                'cluster_name': cluster.name,
                'cluster_id': cluster.id,
                'status': analysis.status,
                'compliance_score': float(analysis.compliance_score) if analysis.compliance_score is not None else None,
                'requirements_met': analysis.requirements_met,
                'requirements_gap': analysis.requirements_gap,
                'created_at': analysis.started_at.isoformat() if analysis.started_at else None,
                'completed_at': analysis.completed_at.isoformat() if analysis.completed_at else None
            })

        # Get total count for pagination
        total_count = db.query(func.count(ComplianceAnalysis.id)).filter(
            ComplianceAnalysis.user_id == current_user.id
        ).scalar()

        return {
            'analyses': result,
            'total_count': total_count,
            'limit': limit,
            'offset': offset
        }

    except Exception as e:
        logger.error(f"Error getting analysis history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analysis history"
        )




# ============================================================================
# WORKSPACES (durable per user + cluster) AND RUN DIFFING
# ============================================================================

@router.get(
    "/workspaces",
    summary="Your compliance workspaces",
    description=(
        "**What it does**\n\n"
        "Lists the compliance packages you have worked on, with the number of "
        "runs, the latest score, when it last ran, and how many obligations you "
        "have triaged. This is the durable object: a second analysis of the same "
        "package continues the first rather than starting over.\n\n"
        "**When to use it**\n\n"
        "The landing view of EU Law Comply for a returning user.\n\n"
        "**Input**\n\nBearer JWT. No parameters.\n\n"
        "**Try it**\n\n`GET /api/eu-law-comply/workspaces`.\n\n"
        "**You get back**\n\n"
        "`workspaces` sorted by most recent activity, each with cluster_id, "
        "name, run_count, last_run_at, latest_score, open_actions. Empty list "
        "for a new user."
    ),
)
def list_workspaces(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = db.execute(text("""
        SELECT w.id, w.cluster_id, w.name, w.created_at,
               (SELECT count(*) FROM compliance_analyses a WHERE a.workspace_id = w.id) AS run_count,
               (SELECT max(a.started_at) FROM compliance_analyses a WHERE a.workspace_id = w.id) AS last_run_at,
               (SELECT a.compliance_score FROM compliance_analyses a
                 WHERE a.workspace_id = w.id AND a.status = 'completed'
                 ORDER BY a.started_at DESC LIMIT 1) AS latest_score,
               (SELECT count(*) FROM compliance_actions ca
                 WHERE ca.user_id = w.user_id AND ca.cluster_id = w.cluster_id
                   AND ca.status IN ('pending','in_progress')) AS open_actions
          FROM compliance_workspaces w
         WHERE w.user_id = :uid
         ORDER BY last_run_at DESC NULLS LAST, w.created_at DESC
    """), {"uid": str(current_user.id)}).mappings().all()

    return {"workspaces": [{
        "id": r["id"],
        "cluster_id": r["cluster_id"],
        "name": r["name"],
        "run_count": r["run_count"],
        "last_run_at": r["last_run_at"].isoformat() if r["last_run_at"] else None,
        "latest_score": float(r["latest_score"]) if r["latest_score"] is not None else None,
        "open_actions": r["open_actions"],
    } for r in rows], "count": len(rows)}


@router.get(
    "/clusters/{cluster_id}/documents",
    summary="Documents you can re-use for this package",
    description=(
        "**What it does**\n\n"
        "Lists the documents you have already analysed against this compliance "
        "package, so a repeat check can re-use them instead of asking you to "
        "find and upload the same policy again.\n\n"
        "**When to use it**\n\n"
        "When opening a package you have run before. Offer the stored documents "
        "alongside the upload control; the user can re-use, add, or do both.\n\n"
        "**Input**\n\n"
        "`cluster_id` in the path. Bearer JWT. Only your own documents are ever "
        "returned.\n\n"
        "**Try it**\n\n`GET /api/eu-law-comply/clusters/58/documents`.\n\n"
        "**You get back**\n\n"
        "`documents`: a list of `{id, title, filename, characters, last_used_at, "
        "used_in_runs}`, newest first, and `count`. Pass the ids you want to "
        "`POST /analyze` as `reuse_document_ids`, comma separated."
    ),
)
async def list_reusable_documents(
    cluster_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Documents already analysed against this package by this user.

    Sourced from compliance_analyses.document_uuids rather than from
    user_documents at large: the point is "what did I check this package
    against last time", not "everything I have ever uploaded anywhere".
    """
    runs = (
        db.query(ComplianceAnalysis)
        .filter(ComplianceAnalysis.user_id == current_user.id,
                ComplianceAnalysis.cluster_id == cluster_id,
                ComplianceAnalysis.document_uuids.isnot(None))
        .order_by(ComplianceAnalysis.started_at.desc())
        .all()
    )

    # Preserve most-recent-first order, and count how many runs used each doc.
    order: List[str] = []
    used_in: Dict[str, int] = {}
    last_used: Dict[str, Optional[datetime]] = {}
    for run in runs:
        for uid in (run.document_uuids or []):
            key = str(uid)
            if key not in used_in:
                order.append(key)
                last_used[key] = run.started_at
            used_in[key] = used_in.get(key, 0) + 1

    if not order:
        return {"documents": [], "count": 0}

    docs = {
        str(d.id): d
        for d in db.query(UserDocument)
                   .filter(UserDocument.id.in_(order),
                           UserDocument.user_id == current_user.id)
                   .all()
    }

    # Collapse byte-identical documents. Uploading the same policy on three
    # occasions writes three user_documents rows, and offering the user three
    # indistinguishable choices is worse than offering none: there is no way to
    # tell them apart and no reason to prefer one. Keyed on a hash of the
    # extracted text, so this is exact rather than a guess at the filename.
    # The most recently used row wins and carries the combined run count.
    out = []
    seen: Dict[str, int] = {}          # content hash -> index in `out`
    for key in order:
        d = docs.get(key)
        if not d:
            continue      # deleted since; simply not offered
        digest = hashlib.sha256((d.content or '').encode('utf-8')).hexdigest()
        if digest in seen:
            existing = out[seen[digest]]
            existing["used_in_runs"] += used_in[key]
            existing["duplicate_copies"] += 1
            continue
        seen[digest] = len(out)
        out.append({
            "id": str(d.id),
            "title": d.title,
            "filename": d.original_filename,
            "characters": len(d.content or ''),
            "last_used_at": last_used[key].isoformat() if last_used.get(key) else None,
            "used_in_runs": used_in[key],
            "duplicate_copies": 0,
        })
    return {"documents": out, "count": len(out)}


@router.get(
    "/analysis/{analysis_id}/diff",
    summary="What changed since the previous run of this package",
    description=(
        "**What it does**\n\n"
        "Compares a completed analysis against the previous completed run in the "
        "same workspace, obligation by obligation, and reports what improved, "
        "what regressed and what is unchanged. This is what makes re-running "
        "worth doing.\n\n"
        "**When to use it**\n\n"
        "After a re-run against an updated document set.\n\n"
        "**Input**\n\nPath: `analysis_id`. Bearer JWT.\n\n"
        "**Try it**\n\n`GET /api/eu-law-comply/analysis/8/diff`.\n\n"
        "**You get back**\n\n"
        "`improved`, `regressed`, `reclassified` and `unchanged` counts plus the "
        "per-obligation detail, and `score_delta`. Movement into or out of "
        "not_applicable is reported as reclassified, not as an improvement: "
        "nothing was remediated, the scope was reassessed. When there is no earlier "
        "run, `comparable: false` and an explanation, never a fabricated "
        "baseline."
    ),
)
def get_analysis_diff(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current = (
        db.query(ComplianceAnalysis)
        .filter(ComplianceAnalysis.id == analysis_id,
                ComplianceAnalysis.user_id == current_user.id)
        .first()
    )
    if not current:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Analysis {analysis_id} not found")

    previous = (
        db.query(ComplianceAnalysis)
        .filter(ComplianceAnalysis.user_id == current_user.id,
                ComplianceAnalysis.cluster_id == current.cluster_id,
                ComplianceAnalysis.id != current.id,
                ComplianceAnalysis.status == 'completed',
                ComplianceAnalysis.started_at < current.started_at)
        .order_by(ComplianceAnalysis.started_at.desc())
        .first()
    )
    if not previous:
        return {
            "comparable": False,
            "reason": "This is the first completed run of this package, so there is "
                      "nothing to compare it against.",
            "analysis_id": analysis_id,
        }

    def findings_by_requirement(aid):
        rows = (
            db.query(GapFinding.requirement_id, GapFinding.status,
                     LawRequirement.article, LawRequirement.requirement_text)
            .join(LawRequirement, LawRequirement.id == GapFinding.requirement_id)
            .filter(GapFinding.analysis_id == aid)
            .all()
        )
        return {r[0]: {"status": r[1], "article": r[2], "text": r[3]} for r in rows}

    now_map, then_map = findings_by_requirement(current.id), findings_by_requirement(previous.id)

    # gap < partial < met is a compliance scale. not_applicable is NOT on it:
    # it says the obligation does not bind this company at all. Ranking it
    # between partial and met made "partial -> not_applicable" read as an
    # improvement, which flatters the report -- nothing was remediated, the
    # scope was reassessed. Transitions into or out of not_applicable are
    # reported separately as reclassified.
    RANK = {"gap": 0, "partial": 1, "met": 2}
    improved, regressed, reclassified, unchanged = [], [], [], 0
    for req_id, now in now_map.items():
        then = then_map.get(req_id)
        if not then:
            continue                      # not analysed last time: not a change
        if then["status"] == now["status"]:
            unchanged += 1
            continue
        entry = {
            "requirement_id": req_id,
            "article": now["article"],
            "requirement_text": (now["text"] or "")[:300],
            "from": then["status"],
            "to": now["status"],
        }
        a, b = RANK.get(then["status"]), RANK.get(now["status"])
        if a is None or b is None:
            reclassified.append(entry)
        elif b > a:
            improved.append(entry)
        else:
            regressed.append(entry)

    delta = None
    if current.compliance_score is not None and previous.compliance_score is not None:
        delta = round(float(current.compliance_score) - float(previous.compliance_score), 2)

    return {
        "comparable": True,
        "analysis_id": current.id,
        "compared_with": {
            "analysis_id": previous.id,
            "ran_at": previous.started_at.isoformat() if previous.started_at else None,
            "score": float(previous.compliance_score) if previous.compliance_score is not None else None,
        },
        "score_delta": delta,
        "counts": {
            "improved": len(improved),
            "regressed": len(regressed),
            "reclassified": len(reclassified),
            "unchanged": unchanged,
            "not_in_previous_run": (len(now_map) - len(improved) - len(regressed)
                                    - len(reclassified) - unchanged),
        },
        "improved": improved,
        "regressed": regressed,
        "reclassified": reclassified,
    }


# ============================================================================
# FINDING STATE (compliance_actions)
# ============================================================================
#
# compliance_actions has existed since the feature was built and held zero rows:
# nothing read or wrote it, so a gap analysis was a snapshot you could not act
# on. Every re-run started from nothing and no decision a user made about a
# finding survived. These two endpoints make a finding's remediation state
# durable, which is the smallest useful piece of the persistent-workspace model.

VALID_ACTION_STATUSES = {'pending', 'in_progress', 'completed', 'cancelled'}


@router.put(
    "/findings/{finding_id}/action",
    summary="Set the remediation state of a gap finding",
    description=(
        "**What it does**\n\n"
        "Records what you have decided to do about one finding: its status, who "
        "owns it, when it is due and any resolution note. Creates the action on "
        "first call and updates it afterwards, so the caller does not need to "
        "know whether one exists.\n\n"
        "**When to use it**\n\n"
        "From the finding drawer in EU Law Comply, when a user triages a gap.\n\n"
        "**Input**\n\n"
        "Path: `finding_id`. Body: `status` (pending | in_progress | completed | "
        "cancelled), optional `assigned_to`, `due_date` (YYYY-MM-DD), "
        "`resolution_notes`. Bearer JWT.\n\n"
        "**Try it**\n\n"
        "`PUT /api/eu-law-comply/findings/42/action` with `{\"status\": \"in_progress\"}`.\n\n"
        "**You get back**\n\n"
        "The stored action: id, gap_finding_id, status, assigned_to, due_date, "
        "resolution_notes, created_at."
    ),
)
def set_finding_action(
    finding_id: int,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    new_status = str(payload.get('status', '')).strip().lower()
    if new_status not in VALID_ACTION_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"status must be one of {sorted(VALID_ACTION_STATUSES)}",
        )

    # Ownership is checked through the finding's analysis: a user may only act on
    # findings from their own analyses.
    row = (
        db.query(GapFinding, ComplianceAnalysis, LawRequirement)
        .join(ComplianceAnalysis, ComplianceAnalysis.id == GapFinding.analysis_id)
        .join(LawRequirement, LawRequirement.id == GapFinding.requirement_id)
        .filter(GapFinding.id == finding_id,
                ComplianceAnalysis.user_id == current_user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Finding {finding_id} not found")
    finding, _analysis, requirement = row

    due = payload.get('due_date')
    if due:
        try:
            due = datetime.strptime(str(due)[:10], "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="due_date must be YYYY-MM-DD")
    else:
        due = None

    # Look the action up by the OBLIGATION, not the finding. gap_findings are
    # recreated on every analysis run, so keying on finding_id meant triage
    # entered against one run was invisible to the next -- it survived a reload
    # but not a re-run, which is the case that matters. See migration 207.
    action = (
        db.query(ComplianceAction)
        .filter(ComplianceAction.user_id == current_user.id,
                ComplianceAction.cluster_id == _analysis.cluster_id,
                ComplianceAction.requirement_id == requirement.id)
        .first()
    )
    if not action:
        action = ComplianceAction(
            user_id=current_user.id,
            requirement_id=requirement.id,
            cluster_id=_analysis.cluster_id,
            gap_finding_id=finding_id,
            # action_title is NOT NULL; derive it from the obligation so the row
            # is readable on its own, e.g. in an export or an admin view.
            action_title=(requirement.article or f"Requirement {requirement.id}")[:200],
            action_description=(requirement.requirement_text or "")[:2000] or None,
        )
        db.add(action)
    else:
        # Re-point at the finding it was last touched from.
        action.gap_finding_id = finding_id

    action.status = new_status
    if 'assigned_to' in payload:
        action.assigned_to = (payload.get('assigned_to') or None)
    if 'resolution_notes' in payload:
        action.resolution_notes = (payload.get('resolution_notes') or None)
    if due is not None or 'due_date' in payload:
        action.due_date = due
    if new_status == 'in_progress' and action.started_at is None:
        action.started_at = datetime.utcnow()
    action.completed_at = datetime.utcnow() if new_status == 'completed' else None

    db.commit()
    db.refresh(action)
    return action.to_dict()


@router.get(
    "/analysis/{analysis_id}/actions",
    summary="Remediation state for every finding in an analysis",
    description=(
        "**What it does**\n\n"
        "Returns the saved remediation actions for an analysis, keyed by gap "
        "finding id, so the findings table can show what has already been "
        "triaged after a reload or a re-run.\n\n"
        "**When to use it**\n\n"
        "Alongside GET /analysis/{id} when rendering the findings table.\n\n"
        "**Input**\n\n"
        "Path: `analysis_id`. Bearer JWT.\n\n"
        "**Try it**\n\n"
        "`GET /api/eu-law-comply/analysis/6/actions`.\n\n"
        "**You get back**\n\n"
        "`{actions: {<gap_finding_id>: {...}}, count: N}`. Empty when nothing has "
        "been triaged yet."
    ),
)
def get_analysis_actions(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    owns = (
        db.query(ComplianceAnalysis.id)
        .filter(ComplianceAnalysis.id == analysis_id,
                ComplianceAnalysis.user_id == current_user.id)
        .first()
    )
    if not owns:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Analysis {analysis_id} not found")

    # Join actions to THIS run's findings through requirement_id, so state
    # entered against an earlier run of the same cluster still shows up. Keying
    # the response on gap_finding_id keeps the frontend contract unchanged.
    rows = (
        db.query(ComplianceAction, GapFinding.id)
        .join(GapFinding, GapFinding.requirement_id == ComplianceAction.requirement_id)
        .filter(GapFinding.analysis_id == analysis_id,
                ComplianceAction.user_id == current_user.id)
        .all()
    )
    actions = {}
    for action, finding_id in rows:
        actions[finding_id] = action.to_dict()
    return {"actions": actions, "count": len(actions)}


# ============================================================================
# Future-Comply preview (P6: May 2026)
# ============================================================================

from models.legislative_train import LegislativeCarriage  # noqa: E402
from services.compliance.proposal_preview import (  # noqa: E402
    compose_future_comply_preview,
)


@router.get(
    "/future-preview/{procedure_ref:path}",
    summary="Future-Comply preview for an in-flight proposal",
    description=(
        "**What it does**\n\n"
        "Returns a structured 'what to prepare for if this passes as drafted' "
        "preview for an in-flight EU legislative proposal, grounded in the "
        "carriage's real data (status, policy areas, AI summary, days in "
        "stage). When the file is already adopted, it points the user at the "
        "existing gap-analysis flow rather than fabricating obligations.\n\n"
        "**When to use it**\n\n"
        "Call from the legislative file detail modal or from the EU Law "
        "Comply page when the user enters an OEIL procedure reference for an "
        "in-flight file. Pair with the Personalised Impact endpoint for a "
        "fuller picture.\n\n"
        "**Input**\n\n"
        "URL path parameter `procedure_ref`: OEIL procedure reference. "
        "Authentication via Bearer JWT.\n\n"
        "**Try it**\n\n"
        "`GET /api/eu-law-comply/future-preview/2024%2F0176%28COD%29` with "
        "the Bearer token.\n\n"
        "**You get back**\n\n"
        "`stage` (proposal | adopted | other), `headline`, `summary`, "
        "`likely_obligation_areas`, `recommended_next_steps`, plus a "
        "`deferred_to_adopted_flow` flag when the file is already adopted. "
        "Never fabricates obligations: every label is grounded in the file's "
        "real classification."
    ),
)
async def get_future_comply_preview(
    procedure_ref: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    carriage = (
        db.query(LegislativeCarriage)
        .filter(LegislativeCarriage.oeil_procedure_ref == procedure_ref)
        .first()
    )
    if not carriage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No legislative file found with procedure_ref={procedure_ref}"
            ),
        )

    preview = compose_future_comply_preview(current_user, carriage)
    return preview.to_dict()


# ============================================================================
# Regulatory Cascade (P3: May 2026)
# ============================================================================

from services.compliance.regulatory_cascade import (  # noqa: E402
    compose_regulatory_cascade,
)


@router.get(
    "/cascade/{procedure_ref:path}",
    summary="Regulatory cascade for a legislative file",
    description=(
        "**What it does**\n\n"
        "Returns the tree of regulatory work that hangs off a primary EU "
        "act: implementing acts, delegated acts, and related in-flight "
        "files in the same policy areas. Lets users move from a one-act "
        "Comply view to a tier-2+ view of everything the file triggers.\n\n"
        "**When to use it**\n\n"
        "Call from the legislative file detail modal alongside Personalised "
        "Impact and Future-Comply. Or from the EU Law Comply page when the "
        "user wants to see the broader regulatory neighbourhood.\n\n"
        "**Input**\n\n"
        "URL path parameter `procedure_ref` (OEIL ref e.g. `2024/0176(COD)`). "
        "Authentication via Bearer JWT.\n\n"
        "**Try it**\n\n"
        "`GET /api/eu-law-comply/cascade/2024%2F0176%28COD%29`.\n\n"
        "**You get back**\n\n"
        "Per-branch counts, the implementing + delegated act lists (with "
        "status, dates, source URLs), the related in-flight files, and "
        "honest absence flags for transposition + CEN data we don't yet "
        "ingest. Never fabricates: empty branches stay empty."
    ),
)
async def get_regulatory_cascade(
    procedure_ref: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    carriage = (
        db.query(LegislativeCarriage)
        .filter(LegislativeCarriage.oeil_procedure_ref == procedure_ref)
        .first()
    )
    if not carriage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No legislative file found with procedure_ref={procedure_ref}"
            ),
        )

    cascade = compose_regulatory_cascade(db, carriage)
    return cascade.to_dict()


# ============================================================================
# Compliance Maturity Assessment (P6: May 2026)
# ============================================================================

from services.compliance.maturity_assessment import (  # noqa: E402
    compose_maturity_assessment,
)


@router.get(
    "/maturity",
    summary="Compliance maturity assessment for the authenticated user",
    description=(
        "**What it does**\n\n"
        "Scores the user 0-100 across four axes: awareness (do they track "
        "the right files?), impact analysis (do they take positions and "
        "compare files?), advocacy (do they draft amendments and "
        "documents?), and follow-through (do they close compliance loops?). "
        "Each axis tops out at 25. The result includes a tier (beginner / "
        "intermediate / advanced / expert), per-axis signal counts, and the "
        "three highest-lift recommendations for next steps.\n\n"
        "**When to use it**\n\n"
        "Call from the EU Law Comply landing page so the user lands on a "
        "personalised maturity card. Shareable: the user can screenshot it "
        "as a one-page benchmark.\n\n"
        "**Input**\n\n"
        "Authentication via Bearer JWT. No parameters.\n\n"
        "**Try it**\n\n"
        "`GET /api/eu-law-comply/maturity` with `Authorization: Bearer <token>`.\n\n"
        "**You get back**\n\n"
        "Total `score` (0-100), `tier`, `tier_label`, four `axes` "
        "(name, score, signals, rationale), top-3 `recommendations` (axis, "
        "action, rationale, expected_lift), plus `profile_complete` and "
        "`has_any_activity` flags so the frontend can render honest "
        "empty-state messaging when the user is brand new."
    ),
)
async def get_compliance_maturity(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assessment = compose_maturity_assessment(db, current_user)
    return assessment.to_dict()


# ---------------------------------------------------------------------------
# Tender Docs cross-fetch (16 Jun 2026)
# ---------------------------------------------------------------------------

@router.get(
    "/by-topic-clusters",
    summary="Compliance clusters relevant to a Tender Docs template + funding context",
    description=(
        "**What it does**\n"
        "Given a funding template id + optional funding_mode + ethics flags, "
        "returns the EU Law Comply clusters whose `policy_area` is listed in "
        "the template's `comply_targets`, plus any extras driven by the ethics "
        "table answers (e.g. ethics_personal_data=true → GDPR clusters).\n\n"
        "**When to use it**\n"
        "Populating the right-rail Comply panel in the Tender Docs editor: "
        "live cross-fetch into the EU Law Comply cluster catalogue.\n\n"
        "**Input**\n"
        "Query: `template_id` (required), `funding_mode`, `ethics_personal_data`, "
        "`ethics_clinical_studies`, `ethics_dual_use`, `ethics_animals` (booleans).\n\n"
        "**You get back**\n"
        "Clusters with `law_count` + `requirement_count` + a `match_reason` "
        "showing why each one surfaced (template / ethics_flag)."
    ),
)
async def clusters_by_topic(
    template_id: str,
    funding_mode: Optional[str] = None,
    ethics_personal_data: bool = False,
    ethics_clinical_studies: bool = False,
    ethics_dual_use: bool = False,
    ethics_animals: bool = False,
    ethics_special_categories: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.subscription_tier not in ['yellow', 'blue']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="EU Law Comply is available for Yellow and Blue tier users only",
        )

    return resolve_clusters_by_topic(
        template_id=template_id,
        funding_mode=funding_mode,
        ethics_personal_data=ethics_personal_data,
        ethics_special_categories=ethics_special_categories,
        ethics_clinical_studies=ethics_clinical_studies,
        ethics_dual_use=ethics_dual_use,
        ethics_animals=ethics_animals,
        db=db,
    )


def resolve_clusters_by_topic(
    *,
    template_id: str,
    funding_mode: Optional[str],
    ethics_personal_data: bool,
    ethics_special_categories: bool,
    ethics_clinical_studies: bool,
    ethics_dual_use: bool,
    ethics_animals: bool,
    db: Session,
) -> Dict[str, Any]:
    """Auth-agnostic helper.

    Single source of truth for the "tender template -> comply clusters" mapping.
    Used by the v1 endpoint above (Bearer JWT + tier gate) and by the v2
    proprietary endpoint at /api/v2/proprietary/tender-docs/comply-clusters
    (API-key auth). Raises HTTPException(404) if the template id is unknown.
    """
    import json as _json
    from pathlib import Path as _Path
    _tpl_dir = _Path(__file__).resolve().parent.parent / "knowledge_base" / "funding_templates"
    _tpl_path = _tpl_dir / f"{template_id}.json"
    if not _tpl_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Funding template '{template_id}' not found",
        )
    with _tpl_path.open() as fh:
        template = _json.load(fh)

    targets: List[str] = list(template.get("comply_targets") or [])
    reasons: Dict[str, List[str]] = {t: ["template"] for t in targets}

    # Ethics-flag-driven additions
    flag_extras: List[tuple] = [
        (ethics_personal_data,       ["GDPR", "Data Protection"]),
        (ethics_special_categories,  ["GDPR Special Categories", "Health Data"]),
        (ethics_clinical_studies,    ["Clinical Trials", "Medical Devices", "IVDR"]),
        (ethics_dual_use,            ["Dual-Use", "Export Controls"]),
        (ethics_animals,             ["Animal Research"]),
    ]
    for flag_on, areas in flag_extras:
        if not flag_on:
            continue
        for a in areas:
            if a not in targets:
                targets.append(a)
            reasons.setdefault(a, []).append("ethics")

    if funding_mode in ("equity-only", "blended"):
        for a in ("Sustainable Finance (SFDR)", "AIFMD", "Anti-Money Laundering"):
            if a not in targets:
                targets.append(a)
            reasons.setdefault(a, []).append("funding-mode")

    if not targets:
        return {"clusters": [], "match_reasons": {}, "template_id": template_id}

    # Curated translation: template-side comply_target labels (short, applicant-
    # friendly) → actual policy_area values present in law_clusters (full, EU-
    # taxonomy). Substring-only match produced false positives (e.g. "AI" matched
    # "AffAIrs"); this map fixes that.
    # The right-hand values MUST be values that actually occur in
    # law_clusters.policy_area, and since 8 Aug 2026 those are constrained to the 34
    # canonical areas in knowledge_base/policy_taxonomy.json (see
    # scripts/normalise_cluster_policy_areas.py). Before that normalisation this map
    # still pointed at granular values that no longer existed after canon seeding, so
    # e.g. "CSRD" -> "Financial Services and Markets" matched nothing while the CSRD
    # cluster sat under "Financial Services". If you add a target here, check the value
    # against `SELECT DISTINCT policy_area FROM law_clusters` before committing.
    target_to_policy_areas: Dict[str, List[str]] = {
        "AI": ["Digital Policy and Digital Economy"],
        "Artificial Intelligence": ["Digital Policy and Digital Economy"],
        "AI Act": ["Digital Policy and Digital Economy"],
        "GDPR": ["Justice and Fundamental Rights"],
        "Data Protection": ["Justice and Fundamental Rights"],
        "GDPR Special Categories": ["Justice and Fundamental Rights"],
        "Health Data": ["Justice and Fundamental Rights", "Health"],
        "Cybersecurity": ["Digital Policy and Digital Economy"],
        "Product Safety": ["Trade and Economic Security", "Health"],
        "Medical Devices": ["Health"],
        "IVDR": ["Health"],
        "Clinical Trials": ["Health"],
        "Bioethics": ["Health"],
        "Dual-Use": ["Trade and Economic Security"],
        "Export Controls": ["Trade and Economic Security"],
        "Foreign Subsidies": ["Competition", "Trade and Economic Security"],
        "Sustainable Finance (SFDR)": ["Economic and Financial Affairs"],
        "AIFMD": ["Economic and Financial Affairs"],
        "Anti-Money Laundering": ["Economic and Financial Affairs"],
        "Environment": ["Environment"],
        "Energy": ["Climate Action", "Environment"],
        "CSRD": ["Climate Action", "Economic and Financial Affairs"],
        "Climate": ["Climate Action"],
        "Education": [],
        "Fundamental Rights": ["Justice and Fundamental Rights"],
        "Research Integrity": [],
        "Animal Research": [],
        "Data Act": ["Digital Policy and Digital Economy"],
        "Defence": ["Trade and Economic Security"],
        # v2 templates (Move 3, Jun 2026): CEF, CREA, CERV, DIGITAL, ERASMUS+, LIFE
        "Audiovisual": ["Digital Policy and Digital Economy"],
        "Climate Action": ["Climate Action"],
        "Connectivity (5G, 6G)": [
            "Communication Networks, Content and Technology",
            "Digital Policy and Digital Economy",
        ],
        "Copyright": ["Digital Policy and Digital Economy"],
        "Digital Infrastructure": [
            "Digital Policy and Digital Economy",
            "Communication Networks, Content and Technology",
        ],
        "Trans-European Networks": ["Transport"],
        "Transport": ["Transport"],
        # Move 4 (Jun 2026): ESF+ agency procurement
        "Public Procurement": ["Trade and Economic Security", "Competition"],
        # Textiles / circular economy (Aug 2026): DPP-TEX cluster 58.
        "Textiles": ["Environment"],
        "Circular Economy": ["Environment"],
        "Ecodesign": ["Environment"],
        "Digital Product Passport": ["Environment"],
        # No current LawCluster for these: leave to the fallback (silent zero match).
        # "Gender Equality": [],
        # "Non-Discrimination": [],
    }
    resolved_policy_areas: set[str] = set()
    target_to_actual: Dict[str, List[str]] = {}
    for t in targets:
        mapped = target_to_policy_areas.get(t, [])
        # Fallback: case-insensitive equality to the DB value
        if not mapped:
            mapped = [t]
        for pa in mapped:
            resolved_policy_areas.add(pa)
        target_to_actual[t] = mapped

    if not resolved_policy_areas:
        return {"clusters": [], "match_reasons": reasons, "template_id": template_id, "targets_resolved": targets, "funding_mode": funding_mode}

    # Exact-match policy_area (case-insensitive). This avoids "AI" matching
    # "AffAIrs" and similar false positives.
    or_clauses = [func.lower(LawCluster.policy_area) == pa.lower() for pa in resolved_policy_areas]
    clusters = (
        db.query(LawCluster)
        .filter(or_(*or_clauses), LawCluster.is_published.is_(True))
        .order_by(LawCluster.id)
        .all()
    )

    out = []
    for c in clusters:
        law_count = db.query(func.count(ClusterLaw.law_id)).filter(ClusterLaw.cluster_id == c.id).scalar()
        req_count = db.query(func.count(LawRequirement.id)).filter(LawRequirement.cluster_id == c.id).scalar()
        # Which template targets resolved to this cluster's policy_area
        matched_targets = [t for t, pas in target_to_actual.items() if (c.policy_area or "") in pas]
        match_reason = sorted({r for t in matched_targets for r in reasons.get(t, [])})
        out.append({
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "applicability": c.applicability,
            "policy_area": c.policy_area,
            "priority_level": c.priority_level,
            "law_count": law_count or 0,
            "requirement_count": req_count or 0,
            "matched_targets": matched_targets,
            "match_reason": match_reason or ["template"],
        })

    return {
        "clusters": out,
        "match_reasons": reasons,
        "template_id": template_id,
        "targets_resolved": targets,
        "funding_mode": funding_mode,
    }

