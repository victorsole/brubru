"""
Admin API endpoints for EU Law Comply management.
Allows admins to trigger requirement extraction and monitor progress.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, List, Optional
from datetime import datetime
import asyncio

from core.database import get_db
from models.user import User
from models.eu_law import LawCluster, ClusterLaw, LawRequirement, EULaw
from .admin_auth import get_current_admin_user
from services.compliance.requirement_extractor import RequirementExtractor
from services.embeddings import VectorSearchService
from services.ai import create_chatbot

router = APIRouter()

# In-memory storage for extraction jobs
# In production, this should be moved to Redis or database
extraction_jobs: Dict[int, dict] = {}


@router.get("/clusters/stats")
def get_clusters_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get statistics for all law clusters.
    Returns cluster info with law counts and requirement counts.
    """
    clusters = db.query(LawCluster).all()
    result = []

    for cluster in clusters:
        # Count laws in cluster
        law_count = db.query(func.count(ClusterLaw.law_id)).filter(
            ClusterLaw.cluster_id == cluster.id
        ).scalar() or 0

        # Count requirements for cluster
        requirement_count = db.query(func.count(LawRequirement.id)).filter(
            LawRequirement.cluster_id == cluster.id
        ).scalar() or 0

        # Check if extraction job is running
        job_status = extraction_jobs.get(cluster.id, {}).get('status', 'idle')
        job_progress = extraction_jobs.get(cluster.id, {}).get('progress', 0)

        result.append({
            'id': cluster.id,
            'name': cluster.name,
            'policy_area': cluster.policy_area,
            'description': cluster.description,
            'law_count': law_count,
            'requirement_count': requirement_count,
            # Admin deliberately lists unpublished packages too: this endpoint
            # is the curation queue, so hiding them here would hide the work.
            'is_published': cluster.is_published,
            'binding_requirement_count': db.query(func.count(LawRequirement.id)).filter(
                LawRequirement.cluster_id == cluster.id,
                func.coalesce(
                    LawRequirement.extra_metadata['interpretive'].as_string(), ''
                ) != 'true',
            ).scalar() or 0,
            'extraction_status': job_status,
            'extraction_progress': job_progress
        })

    return result


@router.post("/clusters/{cluster_id}/extract")
async def trigger_requirement_extraction(
    cluster_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Trigger requirement extraction for a specific cluster.
    Runs in background and updates progress.
    """
    # Check if cluster exists
    cluster = db.query(LawCluster).filter(LawCluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail=f"Cluster {cluster_id} not found")

    # Check if extraction is already running for this cluster
    if cluster_id in extraction_jobs and extraction_jobs[cluster_id]['status'] == 'running':
        raise HTTPException(
            status_code=409,
            detail=f"Extraction already running for cluster {cluster_id}"
        )

    # Initialize job tracking
    extraction_jobs[cluster_id] = {
        'status': 'pending',
        'progress': 0,
        'current_law': 0,
        'total_laws': 0,
        'started_at': datetime.now().isoformat(),
        'completed_at': None,
        'error': None
    }

    # Start extraction in background
    background_tasks.add_task(
        run_extraction_with_tracking,
        cluster_id=cluster_id
    )

    return {
        'message': f'Extraction started for cluster: {cluster.name}',
        'cluster_id': cluster_id,
        'job_id': cluster_id
    }


@router.get("/clusters/{cluster_id}/extraction-status")
async def get_extraction_status(
    cluster_id: int,
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get the current status of requirement extraction for a cluster.
    """
    if cluster_id not in extraction_jobs:
        return {
            'cluster_id': cluster_id,
            'status': 'idle',
            'progress': 0,
            'message': 'No extraction job found'
        }

    job = extraction_jobs[cluster_id]
    return {
        'cluster_id': cluster_id,
        'status': job['status'],
        'progress': job['progress'],
        'current_law': job['current_law'],
        'total_laws': job['total_laws'],
        'started_at': job['started_at'],
        'completed_at': job['completed_at'],
        'error': job['error']
    }


async def run_extraction_with_tracking(cluster_id: int):
    """
    Run requirement extraction with progress tracking.
    Updates extraction_jobs dict with progress.
    """
    from core.database import SessionLocal

    db = SessionLocal()

    try:
        # Update status to running
        extraction_jobs[cluster_id]['status'] = 'running'

        # Get cluster
        cluster = db.query(LawCluster).filter(LawCluster.id == cluster_id).first()
        if not cluster:
            raise Exception(f"Cluster {cluster_id} not found")

        # Get laws in cluster
        cluster_laws = db.query(ClusterLaw).filter(
            ClusterLaw.cluster_id == cluster_id
        ).all()

        total_laws = len(cluster_laws)
        extraction_jobs[cluster_id]['total_laws'] = total_laws

        if total_laws == 0:
            extraction_jobs[cluster_id]['status'] = 'completed'
            extraction_jobs[cluster_id]['progress'] = 100
            extraction_jobs[cluster_id]['completed_at'] = datetime.now().isoformat()
            return

        # Initialize extractor
        extractor = RequirementExtractor(db)

        # Process each law
        total_requirements = 0
        for i, cluster_law in enumerate(cluster_laws, 1):
            # Update progress
            extraction_jobs[cluster_id]['current_law'] = i
            extraction_jobs[cluster_id]['progress'] = int((i / total_laws) * 100)

            # Get full law object
            law = db.query(EULaw).filter(EULaw.id == cluster_law.law_id).first()
            if not law:
                continue

            try:
                # Extract requirements
                requirements = extractor.extract_requirements_from_law(law, cluster_id)

                # Save to database
                for req in requirements:
                    db.add(req)

                db.commit()
                total_requirements += len(requirements)

            except Exception as e:
                print(f"Error processing law {law.celex}: {str(e)}")
                db.rollback()
                continue

        # Mark as completed
        extraction_jobs[cluster_id]['status'] = 'completed'
        extraction_jobs[cluster_id]['progress'] = 100
        extraction_jobs[cluster_id]['completed_at'] = datetime.now().isoformat()
        extraction_jobs[cluster_id]['total_requirements'] = total_requirements

    except Exception as e:
        extraction_jobs[cluster_id]['status'] = 'failed'
        extraction_jobs[cluster_id]['error'] = str(e)
        extraction_jobs[cluster_id]['completed_at'] = datetime.now().isoformat()

    finally:
        db.close()


# ============================================================================
# SEMANTIC SEARCH ENDPOINTS (Phase 2)
# ============================================================================

@router.post("/clusters/{cluster_id}/build-index")
async def build_semantic_index(
    cluster_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Build semantic search index for a cluster.
    Generates embeddings for all requirements in the cluster.
    """
    # Check if cluster exists
    cluster = db.query(LawCluster).filter(LawCluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail=f"Cluster {cluster_id} not found")

    # Build index in background
    background_tasks.add_task(
        build_index_background,
        cluster_id=cluster_id
    )

    return {
        'message': f'Building semantic index for cluster: {cluster.name}',
        'cluster_id': cluster_id
    }


async def build_index_background(cluster_id: int):
    """Build vector search index in background."""
    from core.database import SessionLocal

    db = SessionLocal()
    try:
        search_service = VectorSearchService(db)
        count = search_service.build_requirement_index(
            cluster_id=cluster_id,
            force_rebuild=True
        )
        print(f"✓ Built index for cluster {cluster_id} with {count} requirements")
    except Exception as e:
        print(f"✗ Failed to build index for cluster {cluster_id}: {str(e)}")
    finally:
        db.close()


@router.get("/search/requirements")
async def search_requirements(
    query: str = Query(..., description="Search query text"),
    cluster_id: Optional[int] = Query(None, description="Filter by cluster ID"),
    top_k: int = Query(10, description="Number of results to return"),
    min_score: float = Query(0.5, description="Minimum similarity score (0-1)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Semantic search across requirements.
    Returns requirements ranked by similarity to query.
    """
    search_service = VectorSearchService(db)

    try:
        results = search_service.search_requirements(
            query=query,
            top_k=top_k,
            cluster_id=cluster_id,
            min_score=min_score
        )

        return {
            'query': query,
            'count': len(results),
            'results': results
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


@router.get("/requirements/{requirement_id}/similar")
async def find_similar_requirements(
    requirement_id: int,
    top_k: int = Query(10, description="Number of results to return"),
    min_score: float = Query(0.6, description="Minimum similarity score"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Find requirements similar to a given requirement.
    Useful for identifying duplicates or related obligations.
    """
    search_service = VectorSearchService(db)

    try:
        results = search_service.find_similar_requirements(
            requirement_id=requirement_id,
            top_k=top_k,
            min_score=min_score
        )

        return {
            'requirement_id': requirement_id,
            'count': len(results),
            'similar_requirements': results
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Similarity search failed: {str(e)}"
        )


# ============================================================================
# MODEL SELECTION & CONFIGURATION (Phase 5)
# ============================================================================

@router.get("/models/available")
async def get_available_models(
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get list of available AI models for requirement extraction.
    """
    from services.compliance.hf_requirement_extractor import HuggingFaceRequirementExtractor

    models = HuggingFaceRequirementExtractor.MODELS

    return {
        'models': [
            {
                'id': model_id,
                'name': info['name'],
                'type': info['type'],
                'memory_gb': info['memory_gb'],
                'quality': info['quality'],
                'speed': info['speed']
            }
            for model_id, info in models.items()
        ]
    }


@router.post("/clusters/{cluster_id}/extract-with-model")
async def extract_with_model(
    cluster_id: int,
    model: str = Query("gpt-4", description="Model to use for extraction"),
    max_laws: Optional[int] = Query(None, description="Limit number of laws to process"),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Trigger requirement extraction with a specific model.
    Supports: gpt-4, saul-7b, llama-3.1-8b, mistral-7b
    """
    # Check if cluster exists
    cluster = db.query(LawCluster).filter(LawCluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail=f"Cluster {cluster_id} not found")

    # Validate model
    valid_models = ['gpt-4', 'saul-7b', 'llama-3.1-8b', 'mistral-7b']
    if model not in valid_models:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model. Must be one of: {', '.join(valid_models)}"
        )

    # Check if extraction is already running
    if cluster_id in extraction_jobs and extraction_jobs[cluster_id]['status'] == 'running':
        raise HTTPException(
            status_code=409,
            detail=f"Extraction already running for cluster {cluster_id}"
        )

    # Initialize job tracking
    extraction_jobs[cluster_id] = {
        'status': 'pending',
        'progress': 0,
        'current_law': 0,
        'total_laws': 0,
        'model': model,
        'started_at': datetime.now().isoformat(),
        'completed_at': None,
        'error': None
    }

    # Start extraction in background
    background_tasks.add_task(
        run_extraction_with_model,
        cluster_id=cluster_id,
        model=model,
        max_laws=max_laws
    )

    return {
        'message': f'Extraction started for cluster: {cluster.name}',
        'cluster_id': cluster_id,
        'model': model,
        'job_id': cluster_id
    }


async def run_extraction_with_model(
    cluster_id: int,
    model: str = 'gpt-4',
    max_laws: Optional[int] = None
):
    """
    Run requirement extraction with specified model.
    Tracks progress in extraction_jobs dict.
    """
    from core.database import SessionLocal

    db = SessionLocal()

    try:
        # Update status to running
        extraction_jobs[cluster_id]['status'] = 'running'

        # Get cluster
        cluster = db.query(LawCluster).filter(LawCluster.id == cluster_id).first()
        if not cluster:
            raise Exception(f"Cluster {cluster_id} not found")

        # Get laws in cluster
        cluster_laws = db.query(ClusterLaw).filter(
            ClusterLaw.cluster_id == cluster_id
        ).all()

        if max_laws:
            cluster_laws = cluster_laws[:max_laws]

        total_laws = len(cluster_laws)
        extraction_jobs[cluster_id]['total_laws'] = total_laws

        if total_laws == 0:
            extraction_jobs[cluster_id]['status'] = 'completed'
            extraction_jobs[cluster_id]['progress'] = 100
            extraction_jobs[cluster_id]['completed_at'] = datetime.now().isoformat()
            return

        # Initialize extractor with specified model
        extractor = RequirementExtractor(db, model=model)

        # Process each law
        total_requirements = 0
        for i, cluster_law in enumerate(cluster_laws, 1):
            # Update progress
            extraction_jobs[cluster_id]['current_law'] = i
            extraction_jobs[cluster_id]['progress'] = int((i / total_laws) * 100)

            # Get full law object
            law = db.query(EULaw).filter(EULaw.id == cluster_law.law_id).first()
            if not law:
                continue

            try:
                # Extract requirements
                requirements = extractor.extract_requirements_from_law(law, cluster_id)

                # Save to database
                for req in requirements:
                    db.add(req)

                db.commit()
                total_requirements += len(requirements)

            except Exception as e:
                print(f"Error processing law {law.celex}: {str(e)}")
                db.rollback()
                continue

        # Mark as completed
        extraction_jobs[cluster_id]['status'] = 'completed'
        extraction_jobs[cluster_id]['progress'] = 100
        extraction_jobs[cluster_id]['completed_at'] = datetime.now().isoformat()
        extraction_jobs[cluster_id]['total_requirements'] = total_requirements

    except Exception as e:
        extraction_jobs[cluster_id]['status'] = 'failed'
        extraction_jobs[cluster_id]['error'] = str(e)
        extraction_jobs[cluster_id]['completed_at'] = datetime.now().isoformat()

    finally:
        db.close()


# ============================================================================
# RAG CHATBOT ENDPOINTS (Phase 4)
# ============================================================================

@router.post("/chatbot/ask")
async def ask_chatbot(
    question: str = Query(..., description="Question to ask"),
    cluster_id: Optional[int] = Query(None, description="Focus on specific cluster"),
    top_k: int = Query(5, description="Number of requirements to retrieve"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Ask the RAG chatbot a compliance question.
    The bot will retrieve relevant requirements and generate an informed answer.
    """
    try:
        # Create chatbot instance
        chatbot = create_chatbot(db, cluster_id=cluster_id)

        # Get answer
        response = chatbot.answer_question(
            question=question,
            top_k=top_k,
            include_sources=True
        )

        return response

    except Exception as e:
        logger.error(f"Chatbot error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Chatbot error: {str(e)}"
        )
