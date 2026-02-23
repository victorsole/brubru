"""
Alignment Scorer Service

Scores MEP amendments against a user's policy position using AI.
Results are cached in the amendment_alignment_scores table, keyed by
(user_id, procedure_reference, policy_position_hash).

Uses the multi-provider fallback chain (Mistral -> Claude -> OpenAI -> Gemini).

Phase 4 of MEP Amendments feature.

Created: February 2026
"""

import hashlib
import json
import logging
import re
from typing import List, Dict, Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models.mep_amendment import MEPAmendment
from models.alignment_score import AlignmentScore
from services.ai.multi_provider_service import get_multi_provider_service

logger = logging.getLogger(__name__)

BATCH_SIZE = 10

SYSTEM_PROMPT = """You are an EU legislative analyst specialising in parliamentary amendments.

Your task: score each MEP amendment's alignment with the user's policy position.

Scoring scale:
  +2 = Strongly aligned (amendment directly advances the user's goals)
  +1 = Partially aligned (amendment moves in a similar direction)
   0 = Neutral or unrelated (amendment targets a different concern)
  -1 = Partially opposed (amendment moves against the user's goals)
  -2 = Strongly opposed (amendment directly contradicts the user's goals)

For each amendment, provide:
- "id": the amendment identifier (string, exactly as provided)
- "score": integer from -2 to +2
- "explanation": one sentence explaining the alignment (max 100 words)

Respond with a JSON array only. No markdown, no extra text.
Example: [{"id": "abc-123", "score": 1, "explanation": "Strengthens transparency requirements aligned with user's position."}]"""


def _hash_position(policy_position: str) -> str:
    """SHA-256 hash of the policy position text (normalised)."""
    normalised = policy_position.strip().lower()
    return hashlib.sha256(normalised.encode('utf-8')).hexdigest()


def _build_user_prompt(policy_position: str, amendments: List[Dict[str, Any]]) -> str:
    """Build the user prompt with policy position and amendment batch."""
    lines = [
        "## User's Policy Position",
        policy_position.strip(),
        "",
        "## Amendments to Score",
        "",
    ]

    for a in amendments:
        original = (a['original_text'] or '')[:300]
        proposed = (a['proposed_text'] or '')[:300]
        justification = (a.get('justification') or '')[:200]

        lines.append(f"### Amendment {a['id']}")
        lines.append(f"Element: {a['element_reference']}")
        lines.append(f"Type: {a['amendment_type']}")
        if a.get('author_names'):
            lines.append(f"Authors: {', '.join(a['author_names'])}")
        lines.append(f"Original: {original}")
        lines.append(f"Proposed: {proposed}")
        if justification:
            lines.append(f"Justification: {justification}")
        lines.append("")

    return "\n".join(lines)


def _parse_scores(response_text: str) -> List[Dict[str, Any]]:
    """Parse JSON array from AI response, handling markdown code blocks."""
    text = response_text.strip()

    # Try extracting from markdown code block first
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if json_match:
        text = json_match.group(1).strip()

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    # Try to find a JSON array in the text
    array_match = re.search(r'\[[\s\S]*\]', text)
    if array_match:
        try:
            return json.loads(array_match.group(0))
        except json.JSONDecodeError:
            pass

    logger.warning(f"Failed to parse AI response as JSON array: {text[:200]}")
    return []


async def score_amendments(
    db: Session,
    user_id: UUID,
    procedure_ref: str,
    policy_position: str,
) -> Dict[str, Any]:
    """
    Score all MEP amendments for a procedure against the user's policy position.

    Returns dict with: procedure_reference, policy_position_hash, total_scored,
    score_distribution, scores (list of score items with amendment metadata).
    """
    position_hash = _hash_position(policy_position)

    # Fetch all MEP amendments for this procedure
    mep_amendments = db.query(MEPAmendment).filter(
        MEPAmendment.procedure_reference == procedure_ref
    ).all()

    if not mep_amendments:
        return {
            'procedure_reference': procedure_ref,
            'policy_position_hash': position_hash,
            'total_scored': 0,
            'score_distribution': {},
            'scores': [],
        }

    # Check for cached scores
    cached = db.query(AlignmentScore).filter(
        AlignmentScore.user_id == user_id,
        AlignmentScore.procedure_reference == procedure_ref,
        AlignmentScore.policy_position_hash == position_hash,
    ).all()

    cached_ids = {s.mep_amendment_id for s in cached}
    uncached = [a for a in mep_amendments if a.id not in cached_ids]

    logger.info(
        f"[INFO] Alignment scoring for {procedure_ref}: "
        f"{len(mep_amendments)} total, {len(cached)} cached, {len(uncached)} to score"
    )

    # Score uncached amendments in batches
    if uncached:
        ai_service = get_multi_provider_service()
        new_scores = []

        for i in range(0, len(uncached), BATCH_SIZE):
            batch = uncached[i:i + BATCH_SIZE]
            batch_data = [
                {
                    'id': str(a.id),
                    'element_reference': a.element_reference,
                    'amendment_type': a.amendment_type,
                    'original_text': a.original_text,
                    'proposed_text': a.proposed_text,
                    'justification': a.justification,
                    'author_names': a.author_names or [],
                }
                for a in batch
            ]

            user_prompt = _build_user_prompt(policy_position, batch_data)

            try:
                response = await ai_service.generate(
                    system_prompt=SYSTEM_PROMPT,
                    messages=[{'role': 'user', 'content': user_prompt}],
                    max_tokens=2000,
                    temperature=0.3,
                )

                parsed = _parse_scores(response.message)

                # Map parsed scores back to amendments
                batch_id_map = {str(a.id): a for a in batch}
                for item in parsed:
                    aid = item.get('id', '')
                    score_val = item.get('score')
                    explanation = item.get('explanation', '')

                    if aid not in batch_id_map:
                        continue
                    if not isinstance(score_val, int) or score_val < -2 or score_val > 2:
                        continue

                    new_scores.append(AlignmentScore(
                        user_id=user_id,
                        procedure_reference=procedure_ref,
                        policy_position_hash=position_hash,
                        mep_amendment_id=batch_id_map[aid].id,
                        score=score_val,
                        explanation=explanation[:500] if explanation else None,
                    ))

            except Exception as e:
                logger.error(f"[ERROR] AI scoring failed for batch {i//BATCH_SIZE + 1}: {e}")

            batch_num = i // BATCH_SIZE + 1
            total_batches = (len(uncached) + BATCH_SIZE - 1) // BATCH_SIZE
            logger.info(f"  Batch {batch_num}/{total_batches}: scored {len(new_scores)} so far")

        # Bulk insert new scores
        if new_scores:
            db.bulk_save_objects(new_scores)
            db.commit()
            logger.info(f"[OK] Stored {len(new_scores)} new alignment scores")

    # Reload all scores (cached + new)
    all_scores = db.query(AlignmentScore).filter(
        AlignmentScore.user_id == user_id,
        AlignmentScore.procedure_reference == procedure_ref,
        AlignmentScore.policy_position_hash == position_hash,
    ).all()

    # Build amendment lookup for metadata
    amendment_map = {a.id: a for a in mep_amendments}

    # Build response
    score_distribution = {}
    score_items = []

    for s in all_scores:
        key = str(s.score)
        score_distribution[key] = score_distribution.get(key, 0) + 1

        amendment = amendment_map.get(s.mep_amendment_id)
        if amendment:
            score_items.append({
                'mep_amendment_id': str(s.mep_amendment_id),
                'score': s.score,
                'explanation': s.explanation,
                'author_names': amendment.author_names or [],
                'political_group': amendment.political_group,
                'element_reference': amendment.element_reference,
                'amendment_type': amendment.amendment_type,
            })

    return {
        'procedure_reference': procedure_ref,
        'policy_position_hash': position_hash,
        'total_scored': len(all_scores),
        'score_distribution': score_distribution,
        'scores': score_items,
    }
