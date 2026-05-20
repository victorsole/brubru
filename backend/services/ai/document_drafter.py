"""
Document Drafter

Agentic glue between the chat orchestrator and the document-generation service.
When the user asks the chat to *produce* a document, the drafter:
  1) Decides which of the 12 canonical document types best fits the query.
  2) Builds a minimum-viable payload from the query, the conversation context,
     and the user profile (full_name, organization, email).
  3) Calls the corresponding DocumentGenerator method in-process.
  4) Persists the result as a user_documents row (note, tagged by subtype)
     so it shows up in My EU Bubble → Documents with all the standard
     edit / version / DOCX-PDF / AI-context-toggle verbs.
  5) Returns a DraftedDocument the chat can embed inline (preview + edit URL).

Doc types that genuinely need user input we don't have (MEP briefing without a
named MEP, EU email without a recipient, event poster without a date and
venue) are not auto-drafted -- the drafter returns None and the chat falls
back to the existing wizard-open action.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, asdict
from typing import Optional, Any

from sqlalchemy.orm import Session

from models.user import User
from models.user_document import UserDocument
from schemas.document_generation import (
    BrandingBlock,
    GenerateOnePagerRequest,
    GenerateStakeholderMapRequest,
    GenerateResolutionRequest,
    GenerateEPQuestionRequest,
    GenerateTalkingPointsRequest,
)
from services.ai.document_generator import get_document_generator

logger = logging.getLogger(__name__)


@dataclass
class DraftedDocument:
    """Result the chat can embed inline."""
    document_id: str
    document_subtype: str         # 'one_pager' / 'stakeholder_map' / 'resolution' / ...
    title: str
    content: str
    preview: str                  # First ~500 chars, plain text
    edit_url: str                 # /my-eu-bubble?tab=documents&docId=<uuid>
    word_count: int

    def to_dict(self) -> dict:
        return asdict(self)


def _build_branding(user: User) -> BrandingBlock:
    return BrandingBlock(
        organisation_name=getattr(user, "organization", None) or None,
        contact_email=getattr(user, "email", None) or None,
        organisation_url=None,
        contact_phone=None,
        transparency_register_id=None,
        logo_storage_id=None,
    )


def _preview(text: str, length: int = 480) -> str:
    """Plain-text preview: strip markdown, collapse whitespace, truncate."""
    if not text:
        return ""
    t = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    t = re.sub(r"^#+\s*", "", t, flags=re.MULTILINE)
    t = re.sub(r"\*\*|__|`", "", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"\n+", " ", t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    if len(t) <= length:
        return t
    return t[: length - 1].rsplit(" ", 1)[0] + "…"


def _topic_from(query: str, intent_topic: str) -> str:
    """Prefer the intent-extracted topic; fall back to a cleaned-up query."""
    if intent_topic and intent_topic.strip():
        return intent_topic.strip()
    # Strip common drafting verbs to leave a topic-like remainder.
    cleaned = re.sub(
        r"^(please\s+)?(can\s+you\s+)?(draft|write|prepare|redact|create|make|generate)\s+(me\s+)?(a|an|the)?\s*",
        "",
        query.strip(),
        flags=re.IGNORECASE,
    )
    return cleaned.strip(" .?!")[:250] or "EU policy file"


# Doc-type mapping from drafting_intent.document_type to the canonical type we
# actually invoke. Entries set to None are NOT auto-drafted; the chat will
# emit the existing wizard-open action instead.
INTENT_TO_AUTODRAFT = {
    "position_paper": "one_pager",
    "justification":  "one_pager",
    "proposal":       "one_pager",
    "draft":          "one_pager",
    "talking_points": "talking_points",
    "resolution":     "resolution",
    "ep_question":    "ep_question",
    "report":         "stakeholder_map",
    # Not auto-drafted (need a specific named subject):
    "briefing":       None,   # MEP briefing requires an MEP name
    "letter":         None,   # EU email requires a named recipient
    "amendment":      None,   # Handled by the Amendator
    "summary":        None,
    "template":       None,
}


def pick_autodraft_subtype(drafting_intent) -> Optional[str]:
    if not drafting_intent or not getattr(drafting_intent, "is_drafting_query", False):
        return None
    dt = (getattr(drafting_intent, "document_type", "") or "").strip().lower()
    return INTENT_TO_AUTODRAFT.get(dt)


async def draft_from_chat_query(
    query: str,
    drafting_intent,
    user: Optional[User],
    db: Session,
) -> Optional[DraftedDocument]:
    """
    Entry point used by ai_service.chat().

    Returns a DraftedDocument when the drafter picked a type and the
    generator ran successfully. Returns None otherwise (chat should
    keep its existing wizard-open behaviour).
    """
    if user is None:
        logger.debug("[Drafter] No user, skipping auto-draft")
        return None

    subtype = pick_autodraft_subtype(drafting_intent)
    if not subtype:
        return None

    topic = _topic_from(query, getattr(drafting_intent, "topic", ""))
    branding = _build_branding(user)
    org_name = branding.organisation_name or "Your organisation"
    user_full_name = getattr(user, "full_name", None) or "You"

    generator = get_document_generator()
    document = None
    extra_tags: list = []
    extra_metadata: dict[str, Any] = {"chat_autodrafted": True, "from_query": query[:1000]}

    try:
        if subtype == "one_pager":
            request = GenerateOnePagerRequest(
                topic=topic,
                organisation_name=org_name,
                organisation_pitch=None,
                position="support_with_amendments",
                headline_ask=f"Action on {topic}",
                key_asks=[],
                supporting_evidence=None,
                tone="constructive",
                language="en",
                branding=branding,
            )
            document = await generator.generate_one_pager(request)
            extra_tags = ["one_pager"]
            extra_metadata.update({"topic": topic, "organisation_name": org_name})

        elif subtype == "stakeholder_map":
            request = GenerateStakeholderMapRequest(
                policy_topic=topic,
                scope="eu",
                objectives=f"Map the EU stakeholders most relevant to {topic} and recommend an engagement plan for {org_name}.",
                target_count=12,
                language="en",
                branding=branding,
            )
            document = await generator.generate_stakeholder_map(request)
            extra_tags = ["stakeholder_map"]
            extra_metadata.update({"policy_topic": topic})

        elif subtype == "resolution":
            request = GenerateResolutionRequest(
                topic=topic,
                context_description=(
                    f"User requested a draft EP resolution on: {query[:500]}"
                ),
                key_demands=None,
                procedure_reference=None,
                additional_references=None,
                language="en",
            )
            document = await generator.generate_resolution(request=request)
            extra_tags = ["resolution"]
            extra_metadata.update({"topic": topic})

        elif subtype == "ep_question":
            request = GenerateEPQuestionRequest(
                topic=topic,
                addressee="commission",
                question_type="standard",
                context_description=query[:1500],
                legislation_references=None,
                sources=None,
                num_sub_questions=3,
                tone="assertive",
                policy_area=None,
                procedure_reference=None,
                celex_number=None,
                language="en",
            )
            document = await generator.generate_ep_question(request=request)
            extra_tags = ["ep_question", "standard"]
            extra_metadata.update({"topic": topic, "addressee": "commission"})

        elif subtype == "talking_points":
            request = GenerateTalkingPointsRequest(
                meeting_with="EU policy stakeholders",
                meeting_institution=None,
                meeting_purpose=f"Discuss {topic}",
                topic=topic,
                procedure_reference=None,
                key_messages=[],
                key_asks=[],
                organisation_name=org_name,
                language="en",
            )
            document = await generator.generate_talking_points(request=request)
            extra_tags = ["talking_points"]
            extra_metadata.update({"topic": topic})

        else:
            return None

    except Exception as exc:
        logger.warning(f"[Drafter] Generator failed for subtype={subtype}: {exc}")
        return None

    if document is None or not document.content:
        return None

    # Persist as a user_documents row, mirroring the /api/generate/* persistence.
    try:
        user_doc = UserDocument(
            user_id=user.id,
            document_type="note",
            title=document.title,
            content=document.content,
            policy_areas=[],
            tags=[subtype, "generated", "chat_autodrafted", *extra_tags],
            doc_metadata={
                "generated": True,
                "generator_version": "1.0",
                "document_subtype": subtype,
                "language": getattr(document, "language", "en"),
                **extra_metadata,
            },
        )
        db.add(user_doc)
        db.commit()
        db.refresh(user_doc)
    except Exception as exc:
        logger.exception(f"[Drafter] Failed to persist drafted doc: {exc}")
        db.rollback()
        return None

    edit_url = f"/my-eu-bubble?tab=documents&docId={user_doc.id}"
    drafted = DraftedDocument(
        document_id=str(user_doc.id),
        document_subtype=subtype,
        title=document.title,
        content=document.content,
        preview=_preview(document.content),
        edit_url=edit_url,
        word_count=document.word_count or len((document.content or "").split()),
    )
    logger.info(
        f"[Drafter] Auto-drafted {subtype} ({drafted.word_count} words) "
        f"for user {user.id}, persisted as {user_doc.id}"
    )
    return drafted
