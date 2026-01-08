"""
Conversation Quality Scoring Service

Phase E2: Automated scoring per conversation based on multiple signals.
Calculates quality scores without requiring a separate database table.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy import func, case
from sqlalchemy.orm import Session
from uuid import UUID

from backend.core.database import SessionLocal
from backend.models.chat_analytics import ChatAnalytics
from backend.models.knowledge_gap import KnowledgeGap
from backend.models.feedback import FeedbackSubmission

logger = logging.getLogger(__name__)


# Quality scoring weights
QUALITY_WEIGHTS = {
    'positive_feedback': 2.0,      # User gave positive feedback
    'negative_feedback': -1.0,     # User gave negative feedback
    'hallucination_report': -3.0,  # User reported hallucination
    'knowledge_gap': -1.0,         # AI admitted uncertainty
    'follow_up_question': 0.5,     # Engagement signal
    'long_response': 0.2,          # Detailed answer (per 100 chars)
    'fast_response': 0.3,          # Response < 2s
    'slow_response': -0.2,         # Response > 5s
    'high_tier_sources': 0.5,      # Used Tier 1-2 sources
}

# Base score for neutral conversation
BASE_SCORE = 5.0


class ConversationQualityService:
    """
    Service for calculating conversation quality scores.

    Scores range from 0-10:
    - 0-3: Poor quality (issues detected)
    - 4-6: Neutral (no strong signals)
    - 7-8: Good quality (positive signals)
    - 9-10: Excellent (multiple positive signals)
    """

    def __init__(self, db: Session):
        self.db = db

    def calculate_score(self, conversation_id: str) -> Dict[str, Any]:
        """
        Calculate quality score for a conversation.

        Args:
            conversation_id: The conversation UUID

        Returns:
            Dict with score and breakdown
        """
        try:
            conv_uuid = UUID(conversation_id)
        except ValueError:
            return {'error': 'Invalid conversation ID', 'score': None}

        # Get analytics for this conversation
        analytics = self.db.query(ChatAnalytics).filter(
            ChatAnalytics.conversation_id == conv_uuid
        ).all()

        if not analytics:
            return {
                'conversation_id': conversation_id,
                'score': None,
                'reason': 'No analytics data found'
            }

        # Start with base score
        score = BASE_SCORE
        breakdown = {
            'base_score': BASE_SCORE,
            'adjustments': []
        }

        # Count messages
        message_count = len(analytics)
        breakdown['message_count'] = message_count

        # Follow-up bonus (more messages = more engagement)
        if message_count > 1:
            follow_up_bonus = (message_count - 1) * QUALITY_WEIGHTS['follow_up_question']
            score += follow_up_bonus
            breakdown['adjustments'].append({
                'reason': f'Follow-up questions ({message_count - 1})',
                'delta': round(follow_up_bonus, 2)
            })

        # Check for knowledge gaps
        gap_count = sum(1 for a in analytics if a.had_knowledge_gap)
        if gap_count > 0:
            gap_penalty = gap_count * QUALITY_WEIGHTS['knowledge_gap']
            score += gap_penalty
            breakdown['adjustments'].append({
                'reason': f'Knowledge gaps ({gap_count})',
                'delta': round(gap_penalty, 2)
            })

        # Response time analysis
        avg_response_time = sum(a.response_time_ms or 0 for a in analytics) / len(analytics)
        if avg_response_time < 2000:  # < 2 seconds
            score += QUALITY_WEIGHTS['fast_response']
            breakdown['adjustments'].append({
                'reason': 'Fast response time',
                'delta': QUALITY_WEIGHTS['fast_response']
            })
        elif avg_response_time > 5000:  # > 5 seconds
            score += QUALITY_WEIGHTS['slow_response']
            breakdown['adjustments'].append({
                'reason': 'Slow response time',
                'delta': QUALITY_WEIGHTS['slow_response']
            })

        # Response length bonus (detailed answers)
        avg_response_length = sum(a.response_length or 0 for a in analytics) / len(analytics)
        if avg_response_length > 500:
            length_bonus = min((avg_response_length / 100) * QUALITY_WEIGHTS['long_response'], 1.0)
            score += length_bonus
            breakdown['adjustments'].append({
                'reason': 'Detailed responses',
                'delta': round(length_bonus, 2)
            })

        # Source tier quality
        tier_1_2_count = 0
        for a in analytics:
            if a.source_tiers_used:
                tier_1_2_count += sum(1 for t in a.source_tiers_used if t in [1, 2])
        if tier_1_2_count > 0:
            tier_bonus = min(tier_1_2_count * QUALITY_WEIGHTS['high_tier_sources'], 1.5)
            score += tier_bonus
            breakdown['adjustments'].append({
                'reason': f'High-tier sources used ({tier_1_2_count})',
                'delta': round(tier_bonus, 2)
            })

        # Get feedback for this conversation (if any)
        # Note: We'd need conversation_id in feedback to link properly
        # For now, we'll check by time window around the conversation
        first_message = min(a.created_at for a in analytics if a.created_at)
        last_message = max(a.created_at for a in analytics if a.created_at)

        feedback = self.db.query(FeedbackSubmission).filter(
            FeedbackSubmission.created_at >= first_message,
            FeedbackSubmission.created_at <= last_message + timedelta(minutes=30),
            FeedbackSubmission.feedback_type.in_(['chat_rating', 'hallucination'])
        ).all()

        for f in feedback:
            if 'Positive' in (f.title or ''):
                score += QUALITY_WEIGHTS['positive_feedback']
                breakdown['adjustments'].append({
                    'reason': 'Positive feedback',
                    'delta': QUALITY_WEIGHTS['positive_feedback']
                })
            elif 'Negative' in (f.title or ''):
                score += QUALITY_WEIGHTS['negative_feedback']
                breakdown['adjustments'].append({
                    'reason': 'Negative feedback',
                    'delta': QUALITY_WEIGHTS['negative_feedback']
                })
            elif f.feedback_type == 'hallucination':
                score += QUALITY_WEIGHTS['hallucination_report']
                breakdown['adjustments'].append({
                    'reason': 'Hallucination reported',
                    'delta': QUALITY_WEIGHTS['hallucination_report']
                })

        # Clamp score to 0-10 range
        final_score = max(0, min(10, score))

        return {
            'conversation_id': conversation_id,
            'score': round(final_score, 2),
            'rating': self._score_to_rating(final_score),
            'message_count': message_count,
            'avg_response_time_ms': round(avg_response_time, 2),
            'breakdown': breakdown,
            'calculated_at': datetime.now().isoformat()
        }

    def _score_to_rating(self, score: float) -> str:
        """Convert numeric score to rating label."""
        if score >= 9:
            return 'excellent'
        elif score >= 7:
            return 'good'
        elif score >= 4:
            return 'neutral'
        elif score >= 2:
            return 'poor'
        else:
            return 'critical'

    def get_aggregate_stats(self, days: int = 7) -> Dict[str, Any]:
        """
        Get aggregate quality statistics.

        Args:
            days: Number of days to include

        Returns:
            Aggregate statistics
        """
        start_date = datetime.now() - timedelta(days=days)

        # Get unique conversations
        conversations = self.db.query(
            ChatAnalytics.conversation_id
        ).filter(
            ChatAnalytics.created_at >= start_date,
            ChatAnalytics.conversation_id.isnot(None)
        ).distinct().all()

        if not conversations:
            return {
                'period_days': days,
                'total_conversations': 0,
                'scores': []
            }

        # Calculate scores for each
        scores = []
        ratings = {'excellent': 0, 'good': 0, 'neutral': 0, 'poor': 0, 'critical': 0}

        for (conv_id,) in conversations:
            result = self.calculate_score(str(conv_id))
            if result.get('score') is not None:
                scores.append(result['score'])
                ratings[result['rating']] += 1

        avg_score = sum(scores) / len(scores) if scores else 0

        return {
            'period_days': days,
            'total_conversations': len(conversations),
            'average_score': round(avg_score, 2),
            'score_distribution': {
                'excellent': ratings['excellent'],
                'good': ratings['good'],
                'neutral': ratings['neutral'],
                'poor': ratings['poor'],
                'critical': ratings['critical']
            },
            'calculated_at': datetime.now().isoformat()
        }


def get_conversation_quality_service(db: Session) -> ConversationQualityService:
    """Factory function for ConversationQualityService."""
    return ConversationQualityService(db)
