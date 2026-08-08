"""
EU Law Comply API Endpoints

Handles compliance checking, gap analysis, and requirement extraction for EU laws.
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, case
from typing import Any, Dict, List, Optional
from datetime import datetime
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
    ComplianceAnalysis, GapFinding, AnalysisExport, ComplianceAction
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

        # Get requirements for this cluster
        requirements = db.query(LawRequirement).filter(
            LawRequirement.cluster_id == cluster_id
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

        # Mark analysis as failed
        try:
            analysis = db.query(ComplianceAnalysis).filter(
                ComplianceAnalysis.id == analysis_id
            ).first()
            if analysis:
                analysis.status = 'failed'
                analysis.completed_at = datetime.utcnow()
                db.commit()
        except:
            pass

    finally:
        db.close()


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
    - startup_focused: Filter for startup packages (IDs 12-21) if True
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

        query = db.query(LawCluster)

        # Filter by startup-focused
        if startup_focused is not None:
            if startup_focused:
                query = query.filter(LawCluster.id > 11)  # Startup packages: 12-21
            else:
                query = query.filter(LawCluster.id <= 11)  # General packages: 1-11

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
        clusters = db.query(LawCluster).filter(LawCluster.id.in_(ids)).order_by(LawCluster.id).all()

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


# ============================================================================
# ANALYSIS ENDPOINTS
# ============================================================================

@router.post("/analyze")
async def create_compliance_analysis(
    cluster_id: int = Form(...),
    documents: List[UploadFile] = File(...),
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

        # Validate documents
        if not documents or len(documents) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one document must be uploaded"
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

        # Create analysis in processing state
        analysis = ComplianceAnalysis(
            user_id=current_user.id,
            cluster_id=cluster_id,
            analysis_name=analysis_name or f"{cluster.name} Analysis",
            status='processing',
            document_ids=document_ids if document_ids else None,
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
            'compliance_score': float(analysis.compliance_score) if analysis.compliance_score else None,
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

        # Generate DOCX report
        if export_format == 'docx':
            # Determine if watermark is needed (Yellow tier only)
            include_watermark = current_user.subscription_tier == 'yellow'

            # Create temp file for export
            cluster = db.query(LawCluster).filter(LawCluster.id == analysis.cluster_id).first()
            filename = f"Brubru_EU_Compliance_Report_{cluster.name.replace(' ', '_')}_{analysis_id}.docx"
            output_path = os.path.join(tempfile.gettempdir(), filename)

            # Generate report
            exporter = ReportExporter(db)
            exporter.export_analysis(analysis_id, output_path, include_watermark)

            # Get file size
            file_size = os.path.getsize(output_path)

            # Create export record
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

            logger.info(f"Generated DOCX export {export.id} for analysis {analysis_id}")

            # Return file as download
            from fastapi.responses import FileResponse
            return FileResponse(
                path=output_path,
                filename=filename,
                media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                headers={
                    'Content-Disposition': f'attachment; filename="{filename}"'
                }
            )

        else:
            # PDF export not yet implemented
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="PDF export not yet implemented. Use 'docx' format."
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
                'compliance_score': float(analysis.compliance_score) if analysis.compliance_score else None,
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
        .filter(or_(*or_clauses))
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

