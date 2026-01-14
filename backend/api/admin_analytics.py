"""
Admin Analytics API

Endpoints for the monitoring dashboard (Phase E1).
Provides aggregated metrics for chat performance and quality.
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, case, and_
from sqlalchemy.orm import Session

from core.database import get_db
from api.admin_auth import get_current_admin_user
from models.chat_analytics import ChatAnalytics
from models.knowledge_gap import KnowledgeGap
from models.feedback import FeedbackSubmission
from services.ai.conversation_quality import get_conversation_quality_service

router = APIRouter(prefix="/api/admin/analytics", tags=["admin-analytics"])


@router.get("/dashboard")
async def get_dashboard_metrics(
    days: int = Query(default=7, ge=1, le=90, description="Number of days to include"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    """
    Get aggregated metrics for the admin dashboard.

    Returns:
        - Total conversations and messages
        - Provider distribution (Anthropic/OpenAI/Gemini)
        - Average response time and token usage
        - Knowledge gap rate (fallback rate)
        - Feedback summary (positive/negative/hallucination)
    """
    start_date = datetime.now() - timedelta(days=days)

    # Chat analytics metrics
    analytics_query = db.query(
        func.count(ChatAnalytics.id).label('total_messages'),
        func.avg(ChatAnalytics.response_time_ms).label('avg_response_time'),
        func.avg(ChatAnalytics.tokens_used).label('avg_tokens'),
        func.sum(ChatAnalytics.tokens_used).label('total_tokens'),
        func.sum(case((ChatAnalytics.had_knowledge_gap == True, 1), else_=0)).label('knowledge_gaps'),
    ).filter(ChatAnalytics.created_at >= start_date).first()

    # Provider distribution
    provider_dist = db.query(
        ChatAnalytics.provider,
        func.count(ChatAnalytics.id).label('count')
    ).filter(
        ChatAnalytics.created_at >= start_date
    ).group_by(ChatAnalytics.provider).all()

    provider_distribution = {p.provider: p.count for p in provider_dist}

    # Knowledge gaps by type
    gap_types = db.query(
        KnowledgeGap.missing_data_type,
        func.count(KnowledgeGap.id).label('count')
    ).filter(
        KnowledgeGap.created_at >= start_date
    ).group_by(KnowledgeGap.missing_data_type).all()

    gap_type_distribution = {g.missing_data_type or 'unknown': g.count for g in gap_types}

    # Feedback metrics
    feedback_query = db.query(
        func.count(FeedbackSubmission.id).label('total'),
        func.sum(case((FeedbackSubmission.title.like('%Positive%'), 1), else_=0)).label('positive'),
        func.sum(case((FeedbackSubmission.title.like('%Negative%'), 1), else_=0)).label('negative'),
        func.sum(case((FeedbackSubmission.feedback_type == 'hallucination', 1), else_=0)).label('hallucinations'),
    ).filter(
        FeedbackSubmission.created_at >= start_date,
        FeedbackSubmission.feedback_type.in_(['chat_rating', 'hallucination'])
    ).first()

    # Daily breakdown for charts
    daily_stats = db.query(
        func.date(ChatAnalytics.created_at).label('date'),
        func.count(ChatAnalytics.id).label('messages'),
        func.avg(ChatAnalytics.response_time_ms).label('avg_response_time'),
        func.sum(case((ChatAnalytics.had_knowledge_gap == True, 1), else_=0)).label('gaps')
    ).filter(
        ChatAnalytics.created_at >= start_date
    ).group_by(func.date(ChatAnalytics.created_at)).order_by('date').all()

    daily_breakdown = [
        {
            'date': str(d.date),
            'messages': d.messages,
            'avg_response_time': round(d.avg_response_time or 0, 2),
            'knowledge_gaps': d.gaps
        }
        for d in daily_stats
    ]

    total_messages = analytics_query.total_messages or 0
    knowledge_gaps = analytics_query.knowledge_gaps or 0

    return {
        'period': {
            'days': days,
            'start_date': start_date.isoformat(),
            'end_date': datetime.now().isoformat()
        },
        'summary': {
            'total_messages': total_messages,
            'avg_response_time_ms': round(analytics_query.avg_response_time or 0, 2),
            'avg_tokens_per_message': round(analytics_query.avg_tokens or 0, 1),
            'total_tokens_used': analytics_query.total_tokens or 0,
            'knowledge_gap_rate': round((knowledge_gaps / total_messages * 100) if total_messages > 0 else 0, 2),
        },
        'providers': provider_distribution,
        'knowledge_gaps': {
            'total': knowledge_gaps,
            'by_type': gap_type_distribution
        },
        'feedback': {
            'total': feedback_query.total or 0,
            'positive': feedback_query.positive or 0,
            'negative': feedback_query.negative or 0,
            'hallucination_reports': feedback_query.hallucinations or 0,
        },
        'daily_breakdown': daily_breakdown
    }


@router.get("/conversations")
async def get_conversation_quality_list(
    days: int = Query(default=7, ge=1, le=90),
    min_score: Optional[float] = Query(default=None, description="Minimum quality score"),
    max_score: Optional[float] = Query(default=None, description="Maximum quality score"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    """
    Get list of conversations with quality scores.

    For Phase E2 integration - once quality_score is calculated.
    """
    start_date = datetime.now() - timedelta(days=days)

    # Group analytics by conversation_id
    conversations = db.query(
        ChatAnalytics.conversation_id,
        func.count(ChatAnalytics.id).label('message_count'),
        func.sum(ChatAnalytics.tokens_used).label('total_tokens'),
        func.avg(ChatAnalytics.response_time_ms).label('avg_response_time'),
        func.sum(case((ChatAnalytics.had_knowledge_gap == True, 1), else_=0)).label('gap_count'),
        func.max(ChatAnalytics.created_at).label('last_message_at')
    ).filter(
        ChatAnalytics.created_at >= start_date,
        ChatAnalytics.conversation_id.isnot(None)
    ).group_by(
        ChatAnalytics.conversation_id
    ).order_by(
        func.max(ChatAnalytics.created_at).desc()
    ).limit(limit).offset(offset).all()

    return {
        'conversations': [
            {
                'conversation_id': str(c.conversation_id),
                'message_count': c.message_count,
                'total_tokens': c.total_tokens,
                'avg_response_time_ms': round(c.avg_response_time or 0, 2),
                'knowledge_gap_count': c.gap_count,
                'last_message_at': c.last_message_at.isoformat() if c.last_message_at else None,
                # Quality score will be added in E2
                'quality_score': None
            }
            for c in conversations
        ],
        'pagination': {
            'limit': limit,
            'offset': offset,
            'has_more': len(conversations) == limit
        }
    }


@router.get("/export")
async def export_analytics(
    days: int = Query(default=30, ge=1, le=365),
    format: str = Query(default="json", regex="^(json|csv)$"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    """
    Export raw analytics data for external analysis.
    """
    start_date = datetime.now() - timedelta(days=days)

    analytics = db.query(ChatAnalytics).filter(
        ChatAnalytics.created_at >= start_date
    ).order_by(ChatAnalytics.created_at.desc()).limit(10000).all()

    if format == "json":
        return {
            'export_date': datetime.now().isoformat(),
            'period_days': days,
            'record_count': len(analytics),
            'data': [a.to_dict() for a in analytics]
        }
    else:
        # CSV format - return as text
        import csv
        from io import StringIO
        from fastapi.responses import PlainTextResponse

        output = StringIO()
        if analytics:
            writer = csv.DictWriter(output, fieldnames=analytics[0].to_dict().keys())
            writer.writeheader()
            for a in analytics:
                writer.writerow(a.to_dict())

        return PlainTextResponse(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=chat_analytics_{days}d.csv"}
        )


# Phase E2: Quality Scoring Endpoints

@router.get("/quality/conversation/{conversation_id}")
async def get_conversation_quality(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    """
    Get quality score for a specific conversation.

    Returns:
        - Quality score (0-10)
        - Rating (excellent/good/neutral/poor/critical)
        - Score breakdown with adjustments
    """
    quality_service = get_conversation_quality_service(db)
    result = quality_service.calculate_score(conversation_id)

    if result.get('error'):
        raise HTTPException(status_code=400, detail=result['error'])

    return result


@router.get("/quality/aggregate")
async def get_quality_aggregate(
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    """
    Get aggregate quality statistics.

    Returns:
        - Average score across conversations
        - Score distribution (excellent/good/neutral/poor/critical)
        - Total conversations analysed
    """
    quality_service = get_conversation_quality_service(db)
    return quality_service.get_aggregate_stats(days)


@router.get("/quality/low-scoring")
async def get_low_scoring_conversations(
    days: int = Query(default=7, ge=1, le=90),
    threshold: float = Query(default=4.0, ge=0, le=10, description="Score threshold"),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    """
    Get conversations with quality scores below threshold.

    Useful for identifying problematic conversations that need review.
    """
    start_date = datetime.now() - timedelta(days=days)

    # Get unique conversations
    conversations = db.query(
        ChatAnalytics.conversation_id
    ).filter(
        ChatAnalytics.created_at >= start_date,
        ChatAnalytics.conversation_id.isnot(None)
    ).distinct().limit(200).all()  # Limit for performance

    quality_service = get_conversation_quality_service(db)

    low_scoring = []
    for (conv_id,) in conversations:
        result = quality_service.calculate_score(str(conv_id))
        if result.get('score') is not None and result['score'] < threshold:
            low_scoring.append(result)

    # Sort by score ascending (worst first)
    low_scoring.sort(key=lambda x: x['score'])

    return {
        'threshold': threshold,
        'period_days': days,
        'total_found': len(low_scoring),
        'conversations': low_scoring[:limit]
    }
