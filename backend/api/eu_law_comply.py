"""
EU Law Comply API Endpoints

Handles compliance checking, gap analysis, and requirement extraction for EU laws.
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from typing import List, Optional
from datetime import datetime
import logging
import tempfile
import os
from pathlib import Path

from core.database import get_db
from core.config import settings
from models.user import User
from models.eu_law import LawCluster, EULaw, LawRequirement, ClusterLaw
from models.compliance import (
    ComplianceAnalysis, GapFinding, AnalysisExport, ComplianceAction
)
from models.user_document import UserDocument
from api.auth import get_current_user
from services.compliance import GapAnalyzer
from services.compliance.report_exporter import ReportExporter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/eu-law-comply", tags=["eu-law-comply"])


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
async def list_clusters(
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

        # Enrich with counts
        result = []
        for cluster in clusters:
            # Count laws in cluster
            law_count = db.query(func.count(ClusterLaw.law_id)).filter(
                ClusterLaw.cluster_id == cluster.id
            ).scalar()

            # Count requirements for this cluster
            requirement_count = db.query(func.count(LawRequirement.id)).filter(
                LawRequirement.cluster_id == cluster.id
            ).scalar()

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
            LawRequirement.criticality.desc(),
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
            LawRequirement.criticality.desc()
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
                'confidence_score': float(finding.confidence_score) if finding.confidence_score else None,
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
# Future-Comply preview (P6 — May 2026)
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
        "URL path parameter `procedure_ref` — OEIL procedure reference. "
        "Authentication via Bearer JWT.\n\n"
        "**Try it**\n\n"
        "`GET /api/eu-law-comply/future-preview/2024%2F0176%28COD%29` with "
        "the Bearer token.\n\n"
        "**You get back**\n\n"
        "`stage` (proposal | adopted | other), `headline`, `summary`, "
        "`likely_obligation_areas`, `recommended_next_steps`, plus a "
        "`deferred_to_adopted_flow` flag when the file is already adopted. "
        "Never fabricates obligations — every label is grounded in the file's "
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
# Regulatory Cascade (P3 — May 2026)
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
        "ingest. Never fabricates — empty branches stay empty."
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
# Compliance Maturity Assessment (P6 — May 2026)
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
