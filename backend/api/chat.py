"""
Chat API Endpoints

REST API endpoints for AI-powered chat with EU context injection.
Part of Phase 13: AI Context Injection - Task 13.10

Endpoints:
- POST /api/chat/message - Send message and get AI response
- POST /api/chat/stream - Stream AI response
- GET /api/chat/history/{chat_id} - Get conversation history
- DELETE /api/chat/{chat_id} - Delete conversation
- GET /api/chat/citations/{chat_id} - Get citations for conversation
"""

import functools
import json
import logging
import os
import uuid as uuid_mod
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from jose import JWTError, jwt
import asyncio

from services.ai_service import AIService, ChatMessage, get_ai_service
from services.ai.context_builder import get_context_builder
from services.ai.citation_tracker import CitationTracker
from services.ai.hybrid_legal_assistant import HybridLegalAssistant, get_hybrid_assistant
from core.database import SessionLocal
from core.config import settings as _app_settings
from models.chat import Chat, Message


def _extract_user_id_from_jwt(authorization: Optional[str]) -> Optional[str]:
    """JWT decode for the chat path. Returns the verified `sub` claim or None.

    Used to derive the AUTHORITATIVE user_id for chat operations. The request
    body's `user_id` field is NEVER trusted on its own — that was a tenant
    isolation flaw (any party who learned a UUID could read/write that user's
    chats and trigger their private-guide injection).
    """
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    if not token:
        return None
    try:
        payload = jwt.decode(token, _app_settings.SECRET_KEY, algorithms=["HS256"])
        sub = payload.get("sub")
        return str(sub) if sub else None
    except JWTError:
        return None
    except Exception:
        return None


def _chat_owned_by(chat: "Chat", jwt_user_id: Optional[str], pre_user_id: Optional[str]) -> bool:
    """Authorisation check for accessing a single Chat row.

    Rules (in order):
    - Anonymous chat (chat.pre_user_id is set): only the same pre_user_id can access.
    - Authenticated chat (chat.user_id is set, no pre_user_id): only the matching
      JWT-derived user_id can access. The body cannot stand in for the JWT.
    - Synthetic anon path (legacy: chat.user_id is the uuid5(pre_user_id) but
      pre_user_id is null on the row): treated as opaque — deny unless JWT matches.

    Callers should 404 on failure (don't leak chat existence to attackers).
    """
    if chat is None:
        return False
    # Anonymous chat path — pre_user_id is the only legitimate key.
    if chat.pre_user_id:
        return bool(pre_user_id) and pre_user_id == chat.pre_user_id
    # Authenticated chat path — JWT user_id is the only legitimate key.
    if chat.user_id is None:
        return False
    return bool(jwt_user_id) and jwt_user_id == str(chat.user_id)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Use hybrid assistant (Saul-7B + Claude) for enhanced legal analysis
# TEMPORARILY DISABLED: Saul-7B API causing request hangs
USE_HYBRID_ASSISTANT = False


# Request/Response Models

class ChatMessageRequest(BaseModel):
    """Request to send chat message"""
    message: str = Field(..., description="User message", min_length=1, max_length=5000)
    chat_id: Optional[str] = Field(None, description="Conversation ID (optional, for continuing conversation)")
    user_id: Optional[str] = Field(None, description="User ID (optional)")
    pre_user_id: Optional[str] = Field(None, description="Pre-user ID for anonymous session tracking (optional)")
    document_ids: Optional[List[str]] = Field(None, description="Document IDs to include in context (optional)")
    use_context: bool = Field(True, description="Whether to inject EU context")
    stream: bool = Field(False, description="Whether to stream response")
    nav_context: Optional[str] = Field(
        None,
        description=(
            "Navigation context hint. 'policy_interests' routes the message to "
            "the lightweight policy-taxonomy mapping flow (Mistral-first) instead "
            "of the full knowledge-bearing answer."
        ),
    )


class ChatMessageResponse(BaseModel):
    """Response with AI message"""
    chat_id: str
    message: str
    citations: List[Dict[str, Any]]
    tokens_used: int
    model: str
    search_time_ms: float
    total_time_ms: float
    timestamp: str
    actions: List[Dict[str, Any]] = []
    # When the user asked for a draft that we auto-produced and persisted to
    # My EU Bubble → Documents, this carries the just-saved row.
    drafted_document: Optional[Dict[str, Any]] = None


class ConversationHistoryResponse(BaseModel):
    """Conversation history"""
    chat_id: str
    messages: List[Dict[str, Any]]
    total_messages: int


class CitationsResponse(BaseModel):
    """Citations for conversation"""
    chat_id: str
    citations: List[Dict[str, Any]]
    total_citations: int


# Database helper functions (sync, run via executor)

def _get_or_create_chat(
    chat_id_str: str,
    user_id: Optional[str] = None,
    pre_user_id: Optional[str] = None,
    is_probe: bool = False,
) -> tuple:
    """Get existing chat or create new one. Returns (chat_id_str, messages_list).

    `is_probe` marks a chat as our own synthetic traffic (deploy verification,
    query audits, link checks) so usage analysis can exclude it structurally.
    Until 9 Aug 2026 probes were identified by pattern-matching `pre_user_id`
    for non-UUID slugs, which missed any probe run that sent no identifier at
    all -- a burst of 20 audit queries in 9 minutes on 7 Aug was counted as 20
    genuine anonymous users. Set it with the `X-Brubru-Probe: 1` request header.
    """
    db = SessionLocal()
    try:
        # Try to find existing chat by ID
        try:
            chat_uuid = uuid_mod.UUID(chat_id_str)
            chat = db.query(Chat).filter(Chat.id == chat_uuid).first()
        except (ValueError, AttributeError):
            chat = None

        if chat:
            # Load existing messages
            messages = db.query(Message).filter(
                Message.chat_id == chat.id
            ).order_by(Message.created_at).all()

            msg_list = [
                {'role': m.role, 'content': m.content, 'timestamp': m.created_at.isoformat()}
                for m in messages
            ]
            return str(chat.id), msg_list

        # Create new chat
        # For pre-users without a user_id, generate a deterministic UUID from pre_user_id
        # so the NOT NULL constraint on user_id is satisfied even before migration 020
        if user_id:
            chat_user_id = uuid_mod.UUID(user_id)
        elif pre_user_id:
            chat_user_id = uuid_mod.uuid5(uuid_mod.NAMESPACE_URL, f"preuser:{pre_user_id}")
        else:
            # Neither identifier supplied. This used to mint a throwaway uuid4()
            # into user_id and leave pre_user_id NULL, producing a chat that
            # belongs to nobody: it cannot join `users` (so it reads as
            # anonymous) and it cannot join `pre_user_events` (so the funnel
            # never sees the question). 51 of 60 anonymous chats in the 30 days
            # to 9 Aug 2026 were orphaned this way -- 49 anonymous messages
            # surfaced as 4 recorded `query_1` events, making activation look
            # roughly 12x worse than it was.
            #
            # Mint a real pre_user_id instead and persist it, so the row is
            # self-consistent and joinable.
            pre_user_id = str(uuid_mod.uuid4())
            chat_user_id = uuid_mod.uuid5(uuid_mod.NAMESPACE_URL, f"preuser:{pre_user_id}")
            logger.info(
                "chat created with no user_id and no pre_user_id; minted "
                "pre_user_id=%s so the session stays attributable", pre_user_id
            )

        new_chat = Chat(
            user_id=chat_user_id,
            pre_user_id=pre_user_id,
            title=None,
            message_count=0,
            chat_metadata={"is_probe": True} if is_probe else None,
        )
        db.add(new_chat)
        db.commit()
        db.refresh(new_chat)
        return str(new_chat.id), []

    finally:
        db.close()


def _save_messages(
    chat_id_str: str,
    user_content: str,
    assistant_content: str,
    citations: Optional[List[Dict]] = None,
    tokens_used: int = 0,
    model: str = "",
    provider: str = "",
    user_id: Optional[str] = None,
):
    """Save user + assistant messages to database and update chat stats."""
    db = SessionLocal()
    try:
        try:
            chat_uuid = uuid_mod.UUID(chat_id_str)
        except (ValueError, AttributeError):
            logger.error(f"[ERROR] Invalid chat_id for save: {chat_id_str}")
            return

        chat = db.query(Chat).filter(Chat.id == chat_uuid).first()

        if not chat:
            # Create chat on the fly if it doesn't exist
            chat = Chat(
                id=chat_uuid,
                user_id=uuid_mod.UUID(user_id) if user_id else uuid_mod.uuid4(),
                title=None,
                message_count=0,
            )
            db.add(chat)
            db.flush()

        # Save user message
        user_msg = Message(
            chat_id=chat.id,
            role="user",
            content=user_content,
        )
        db.add(user_msg)

        # Save assistant message
        assistant_msg = Message(
            chat_id=chat.id,
            role="assistant",
            content=assistant_content,
            tokens_used=tokens_used if tokens_used else None,
            model=model if model else None,
            provider=provider if provider else None,
            citations=citations if citations else None,
        )
        db.add(assistant_msg)

        # Update chat stats
        chat.message_count = (chat.message_count or 0) + 2
        chat.total_tokens_used = (chat.total_tokens_used or 0) + tokens_used
        chat.last_message_at = datetime.now(timezone.utc)
        chat.last_message_preview = assistant_content[:500] if assistant_content else None

        # Auto-generate title from first user message if not set
        if not chat.title and user_content:
            chat.title = user_content[:100] + ("..." if len(user_content) > 100 else "")

        db.commit()

    except Exception as e:
        db.rollback()
        logger.error(f"[ERROR] Failed to save messages: {e}")
    finally:
        db.close()


def _get_chat_messages(chat_id_str: str) -> Optional[List[Dict]]:
    """Get all messages for a chat. Returns None if chat not found."""
    db = SessionLocal()
    try:
        try:
            chat_uuid = uuid_mod.UUID(chat_id_str)
        except (ValueError, AttributeError):
            return None

        chat = db.query(Chat).filter(Chat.id == chat_uuid).first()
        if not chat:
            return None

        messages = db.query(Message).filter(
            Message.chat_id == chat.id
        ).order_by(Message.created_at).all()

        return [m.to_dict() for m in messages]

    finally:
        db.close()


def _get_chat_citations(chat_id_str: str) -> Optional[List[Dict]]:
    """Get all citations from assistant messages in a chat."""
    db = SessionLocal()
    try:
        try:
            chat_uuid = uuid_mod.UUID(chat_id_str)
        except (ValueError, AttributeError):
            return None

        chat = db.query(Chat).filter(Chat.id == chat_uuid).first()
        if not chat:
            return None

        messages = db.query(Message).filter(
            Message.chat_id == chat.id,
            Message.role == "assistant",
            Message.citations.isnot(None),
        ).order_by(Message.created_at).all()

        all_citations = []
        for m in messages:
            if m.citations:
                all_citations.extend(m.citations)
        return all_citations

    finally:
        db.close()


def _delete_chat(chat_id_str: str) -> bool:
    """Delete a chat and its messages. Returns True if deleted."""
    db = SessionLocal()
    try:
        try:
            chat_uuid = uuid_mod.UUID(chat_id_str)
        except (ValueError, AttributeError):
            return False

        chat = db.query(Chat).filter(Chat.id == chat_uuid).first()
        if not chat:
            return False

        db.delete(chat)  # CASCADE deletes messages
        db.commit()
        return True

    except Exception as e:
        db.rollback()
        logger.error(f"[ERROR] Failed to delete chat: {e}")
        return False
    finally:
        db.close()


def _load_chat_for_owner(chat_id_str: str, jwt_user_id: Optional[str], pre_user_id: Optional[str]) -> Optional["Chat"]:
    """Load a chat row and verify ownership in one step.

    Returns the Chat object if the caller owns it, None otherwise. Callers should
    treat None uniformly as 404 — do not leak whether the chat existed at all.
    """
    db = SessionLocal()
    try:
        try:
            chat_uuid = uuid_mod.UUID(chat_id_str)
        except (ValueError, AttributeError):
            return None
        chat = db.query(Chat).filter(Chat.id == chat_uuid).first()
        if not chat:
            return None
        if not _chat_owned_by(chat, jwt_user_id, pre_user_id):
            logger.warning(
                "chat ownership rejected: chat_id=%s jwt_user=%s pre_user=%s chat.user_id=%s chat.pre_user_id=%s",
                chat_id_str, jwt_user_id, pre_user_id, chat.user_id, chat.pre_user_id,
            )
            return None
        return chat
    finally:
        db.close()


def _list_chats(user_id: Optional[str] = None, limit: int = 50, pre_user_id: Optional[str] = None) -> Dict[str, Any]:
    """List recent chats, filtered by user_id OR pre_user_id.

    Callers must pass exactly one of (user_id, pre_user_id). The route enforces
    that at least one is present and that user_id is JWT-derived (never
    user-supplied) — see list_conversations().
    """
    db = SessionLocal()
    try:
        query = db.query(Chat).filter(Chat.is_active == True)

        if user_id:
            try:
                user_uuid = uuid_mod.UUID(user_id)
                query = query.filter(Chat.user_id == user_uuid)
            except (ValueError, AttributeError):
                # Bad UUID → return empty rather than the whole table.
                return {'conversations': [], 'total': 0}
        elif pre_user_id:
            query = query.filter(Chat.pre_user_id == pre_user_id)
        else:
            # Defence in depth: if both are None, return empty rather than
            # leaking the whole platform.
            return {'conversations': [], 'total': 0}

        chats = query.order_by(Chat.last_message_at.desc().nullslast()).limit(limit).all()

        conversations = []
        for chat in chats:
            conversations.append({
                'chat_id': str(chat.id),
                'id': str(chat.id),
                'user_id': str(chat.user_id),
                'title': chat.title,
                'created_at': chat.created_at.isoformat() if chat.created_at else '',
                'message_count': chat.message_count or 0,
                'last_message': chat.last_message_preview or '',
                'last_message_at': chat.last_message_at.isoformat() if chat.last_message_at else None,
            })

        total = db.query(Chat).filter(Chat.is_active == True).count()

        return {
            'conversations': conversations,
            'total': total,
        }

    finally:
        db.close()


def _count_chats() -> int:
    """Count total active chats."""
    db = SessionLocal()
    try:
        return db.query(Chat).filter(Chat.is_active == True).count()
    finally:
        db.close()


# Endpoints

@router.post("/message", response_model=ChatMessageResponse)
async def send_message(
    request: ChatMessageRequest,
    background_tasks: BackgroundTasks,
    authorization: Optional[str] = Header(None),
    x_brubru_probe: Optional[str] = Header(None, alias="X-Brubru-Probe"),
):
    """
    Send message and get AI response with EU context.
    """
    start_time = datetime.now()
    # See stream_message: our own verification traffic self-identifies.
    is_probe = str(x_brubru_probe or "").lower() in {"1", "true", "yes"}

    # AUTHORISATION: derive user_id from the JWT only. The body's `user_id`
    # field is logged for forensics (a mismatch is an attack signal) but never
    # trusted as authority. Anonymous flow continues to work through
    # `pre_user_id` when no JWT is present.
    jwt_user_id = _extract_user_id_from_jwt(authorization)
    if request.user_id and request.user_id != jwt_user_id:
        logger.warning(
            "chat /message body user_id=%s mismatched JWT user_id=%s — body ignored",
            request.user_id, jwt_user_id,
        )
    request.user_id = jwt_user_id  # the only authoritative source

    try:
        # Get or create chat (runs in executor to not block async)
        loop = asyncio.get_event_loop()

        if request.chat_id:
            chat_id, history_dicts = await loop.run_in_executor(
                None, _get_or_create_chat, request.chat_id, request.user_id,
                request.pre_user_id, is_probe
            )
        else:
            chat_id, history_dicts = await loop.run_in_executor(
                None, _get_or_create_chat, str(uuid_mod.uuid4()), request.user_id,
                request.pre_user_id, is_probe
            )

        # Build conversation history
        history = [
            ChatMessage(
                role=msg['role'],
                content=msg['content'],
                timestamp=datetime.fromisoformat(msg['timestamp'])
            )
            for msg in history_dicts
        ]

        # Get AI service (hybrid or standard)
        if USE_HYBRID_ASSISTANT:
            ai_service = get_hybrid_assistant()
            logger.info("Using Hybrid Legal Assistant (Saul-7B + Claude)")
        else:
            ai_service = get_ai_service()
            logger.info("Using standard AI service (Claude only)")

        # Determine if this is a pre-user (anonymous, not signed up)
        is_pre_user = bool(request.pre_user_id and not request.user_id)

        # Generate response with timeout (180 seconds = 3 minutes)
        timeout = 180.0

        try:
            response = await asyncio.wait_for(
                ai_service.chat(
                    user_message=request.message,
                    conversation_history=history,
                    user_id=request.user_id,
                    document_ids=request.document_ids,
                    use_context=request.use_context,
                    stream=False,
                    is_pre_user=is_pre_user
                ),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Chat request timed out after {timeout} seconds")
            raise HTTPException(
                status_code=504,
                detail=f"Request timed out after {timeout} seconds. Please try a simpler question or try again later."
            )
        except Exception as ai_error:
            error_msg = str(ai_error)

            if "100 PDF pages" in error_msg or "maximum of 100 PDF pages" in error_msg:
                logger.warning(f"PDF page limit exceeded: {error_msg}")
                raise HTTPException(
                    status_code=400,
                    detail="The uploaded PDF exceeds Claude's 100-page limit. The system will extract text from large PDFs automatically. Please try uploading again."
                )

            if "invalid_request_error" in error_msg and "pdf" in error_msg.lower():
                logger.warning(f"PDF processing error: {error_msg}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Error processing PDF document: {error_msg}"
                )

            raise

        # Save messages to database in background (non-blocking)
        background_tasks.add_task(
            _save_messages,
            chat_id,
            request.message,
            response.message,
            response.citations,
            response.tokens_used,
            response.model,
            getattr(response, 'provider', ''),
            request.user_id,
        )

        logger.info(f"Chat response generated for {chat_id}: {len(response.message)} chars")

        return ChatMessageResponse(
            chat_id=chat_id,
            message=response.message,
            citations=response.citations,
            tokens_used=response.tokens_used,
            model=response.model,
            search_time_ms=response.search_time_ms,
            total_time_ms=response.total_time_ms,
            timestamp=datetime.now().isoformat(),
            actions=response.actions or [],
            drafted_document=getattr(response, "drafted_document", None),
        )

    except Exception as e:
        import traceback
        logger.error(f"Failed to process chat message: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def stream_message(
    request: ChatMessageRequest,
    authorization: Optional[str] = Header(None),
    x_brubru_probe: Optional[str] = Header(None, alias="X-Brubru-Probe"),
):
    """
    Stream AI response.
    """
    try:
        # Our own verification traffic self-identifies so it can be excluded
        # from user analytics structurally rather than by guessing at id shapes.
        is_probe = str(x_brubru_probe or "").lower() in {"1", "true", "yes"}
        # AUTHORISATION: see /message — JWT is the only authoritative source.
        jwt_user_id = _extract_user_id_from_jwt(authorization)
        if request.user_id and request.user_id != jwt_user_id:
            logger.warning(
                "chat /stream body user_id=%s mismatched JWT user_id=%s — body ignored",
                request.user_id, jwt_user_id,
            )
        request.user_id = jwt_user_id

        loop = asyncio.get_event_loop()

        if request.chat_id:
            chat_id, history_dicts = await loop.run_in_executor(
                None, _get_or_create_chat, request.chat_id, request.user_id,
                request.pre_user_id, is_probe
            )
        else:
            chat_id, history_dicts = await loop.run_in_executor(
                None, _get_or_create_chat, str(uuid_mod.uuid4()), request.user_id,
                request.pre_user_id, is_probe
            )

        history = [
            ChatMessage(
                role=msg['role'],
                content=msg['content'],
                timestamp=datetime.fromisoformat(msg['timestamp'])
            )
            for msg in history_dicts
        ]

        ai_service = get_ai_service()
        is_pre_user = bool(request.pre_user_id and not request.user_id)
        logger.info("Using standard AI service for streaming (hybrid streaming not yet implemented)")

        async def generate():
            full_response = ""
            stream_citations: list = []
            # Provider telemetry, consumed from the "meta" event below and
            # written onto the saved assistant row. Before 6 Aug 2026 the
            # streaming path saved model/provider/tokens as NULL, so 22% of
            # assistant messages were unattributable and the 126-second
            # latency could not be traced to a provider.
            meta: dict = {}

            # The conversation id, before any text. The non-streaming path
            # returns it in the response body, but the SSE path never sent it,
            # so the browser's chatId stayed null forever and every message
            # opened a NEW conversation with no history. Result: zero
            # multi-turn chats in 694 conversations between 1 May and 5 Aug
            # 2026 -- every user talking to an assistant with no memory of the
            # previous sentence.
            yield f"data: {json.dumps({'type': 'chat', 'chat_id': str(chat_id)})}\n\n"

            async for chunk in ai_service.chat_stream(
                user_message=request.message,
                conversation_history=history,
                use_context=request.use_context,
                is_pre_user=is_pre_user,
                document_ids=request.document_ids,
                nav_context=request.nav_context,
                # Authoritative user, from the JWT. Without it the streaming
                # path cannot load the user's private guide, cannot know which
                # procedures they already track, and cannot attribute analytics.
                user_id=request.user_id,
            ):
                # Status/entity events are JSON -- pass through as SSE but don't save to DB
                if chunk.startswith("{"):
                    try:
                        parsed = json.loads(chunk)
                        # The post-processed final text. Swap it into the copy
                        # we persist as well as forwarding it to the client:
                        # otherwise the DB keeps the RAW streamed answer, and
                        # every later read of it (query audits, conversation
                        # history, exports) sees defects that were already
                        # fixed on screen.
                        if parsed.get("type") == "replace":
                            replacement = parsed.get("content")
                            if isinstance(replacement, str) and replacement:
                                full_response = replacement
                            yield f"data: {chunk}\n\n"
                            continue
                        # The citation list backing the [N] markers. Forward it
                        # to the client AND keep it so the saved message stores
                        # its sources: otherwise conversation history renders
                        # bare markers forever (audit follow-up, 28 Jul 2026).
                        if parsed.get("type") == "citations":
                            found = parsed.get("citations")
                            if isinstance(found, list):
                                stream_citations = found
                            yield f"data: {chunk}\n\n"
                            continue
                        # Router-only event: captured for persistence and
                        # deliberately NOT forwarded, so adding it needs no
                        # frontend change and cannot surface as raw JSON in a
                        # stale bundle.
                        if parsed.get("type") == "meta":
                            meta = parsed
                            logger.info(
                                "[stream-meta] provider=%s model=%s tokens=%s "
                                "context_ms=%s llm_ms=%s attempts=%s",
                                parsed.get("provider"), parsed.get("model"),
                                parsed.get("tokens_used"), parsed.get("context_ms"),
                                parsed.get("llm_ms"), parsed.get("attempts"),
                            )
                            continue
                        if parsed.get("type") in ("status", "entities", "actions"):
                            yield f"data: {chunk}\n\n"
                            continue
                    except (json.JSONDecodeError, AttributeError):
                        pass

                full_response += chunk
                # SSE protocol: newlines in data must be sent as separate
                # data: lines, otherwise the parser drops content after \n.
                # Encode \n as \\n so the frontend receives them as literal text.
                safe_chunk = chunk.replace('\n', '\\n')
                yield f"data: {safe_chunk}\n\n"

            # Save messages to database after streaming completes.
            # Runs in a thread: production is a SINGLE uvicorn worker and a
            # sync ORM write here blocks the event loop for every other
            # in-flight stream.
            await asyncio.get_event_loop().run_in_executor(
                None,
                functools.partial(
                    _save_messages,
                    chat_id,
                    request.message,
                    full_response,
                    citations=stream_citations or None,
                    tokens_used=meta.get("tokens_used") or 0,
                    model=meta.get("model") or "",
                    provider=meta.get("provider") or "",
                    user_id=request.user_id,
                ),
            )

            yield f"data: [DONE]\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    except Exception as e:
        logger.error(f"Failed to stream chat: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{chat_id}", response_model=ConversationHistoryResponse)
async def get_history(
    chat_id: str,
    pre_user_id: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    """Get conversation history. Requires ownership (JWT or matching pre_user_id)."""
    try:
        jwt_user_id = _extract_user_id_from_jwt(authorization)
        loop = asyncio.get_event_loop()

        # Ownership check first — 404 on miss to avoid leaking existence.
        chat = await loop.run_in_executor(
            None, _load_chat_for_owner, chat_id, jwt_user_id, pre_user_id
        )
        if chat is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

        messages = await loop.run_in_executor(None, _get_chat_messages, chat_id)
        if messages is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return ConversationHistoryResponse(
            chat_id=chat_id,
            messages=messages,
            total_messages=len(messages)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/citations/{chat_id}", response_model=CitationsResponse)
async def get_citations(
    chat_id: str,
    pre_user_id: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    """Get citations for conversation. Requires ownership."""
    try:
        jwt_user_id = _extract_user_id_from_jwt(authorization)
        loop = asyncio.get_event_loop()

        chat = await loop.run_in_executor(
            None, _load_chat_for_owner, chat_id, jwt_user_id, pre_user_id
        )
        if chat is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

        citations = await loop.run_in_executor(None, _get_chat_citations, chat_id)
        if citations is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return CitationsResponse(
            chat_id=chat_id,
            citations=citations,
            total_citations=len(citations)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get citations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{chat_id}")
async def delete_conversation(
    chat_id: str,
    pre_user_id: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    """Delete conversation. Requires ownership."""
    try:
        jwt_user_id = _extract_user_id_from_jwt(authorization)
        loop = asyncio.get_event_loop()

        chat = await loop.run_in_executor(
            None, _load_chat_for_owner, chat_id, jwt_user_id, pre_user_id
        )
        if chat is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

        deleted = await loop.run_in_executor(None, _delete_chat, chat_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Conversation not found")

        logger.info(f"Deleted conversation {chat_id} (owner jwt_user_id={jwt_user_id} pre_user_id={pre_user_id})")
        return {"status": "deleted", "chat_id": chat_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_conversations(
    limit: int = 50,
    pre_user_id: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    """List recent conversations for the caller.

    Authorisation:
    - JWT bearer token → list that user's chats (the body / query `user_id`
      that older clients used to send is now ignored).
    - No JWT but `pre_user_id` query string → list that anon session's chats.
    - Neither → 401.

    Admins still call /api/chat/list with a Bearer token but use the dedicated
    admin endpoints when they need to inspect another user's history.
    """
    try:
        jwt_user_id = _extract_user_id_from_jwt(authorization)
        if not jwt_user_id and not pre_user_id:
            raise HTTPException(status_code=401, detail="Authentication required")

        # Authenticated path wins. Otherwise filter by pre_user_id (anon).
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, _list_chats, jwt_user_id, limit, None if jwt_user_id else pre_user_id
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list conversations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Health check endpoint
@router.get("/health")
async def health_check():
    """
    Health check for chat service.
    """
    try:
        ai_service = get_ai_service()
        model_info = await ai_service.get_model_info()

        loop = asyncio.get_event_loop()
        chat_count = await loop.run_in_executor(None, _count_chats)

        # The running commit, so "is my fix actually live?" is one cheap curl
        # rather than a 130-second chat probe or a reading of the deploy log.
        # A green deploy log proves nothing; this proves what is executing.
        # Railway injects RAILWAY_GIT_COMMIT_SHA on every build.
        commit = (
            os.getenv("RAILWAY_GIT_COMMIT_SHA")
            or os.getenv("GIT_COMMIT_SHA")
            or "unknown"
        )
        return {
            'status': 'healthy',
            'service': 'chat',
            # The generator model is chosen per request from the free
            # open-model chain; this field reported a hardcoded Anthropic id
            # that has not been chat's primary since June.
            'generator': 'multi-provider open-model chain',
            'chain': get_ai_service().multi_provider.available_providers
                     if getattr(get_ai_service(), 'multi_provider', None) else [],
            'model': model_info['model'],
            'commit': commit[:12],
            'conversations': chat_count,
            'timestamp': datetime.now().isoformat()
        }

    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }


# DEBUG ENDPOINT for MEP linking
@router.get("/debug/mep-linking")
async def debug_mep_linking():
    """
    Debug endpoint to test MEP name linking functionality.
    """
    try:
        from services.scrapers.european_parliament_scraper import EuropeanParliamentScraper
        from services.ai_service import get_ai_service

        result = {
            'timestamp': datetime.now().isoformat(),
            'steps': []
        }

        result['steps'].append({'step': 1, 'action': 'Scraping ENVI committee data'})
        scraper = EuropeanParliamentScraper()
        committee_members = await scraper.get_committee_members('ENVI')

        if not committee_members:
            return {
                **result,
                'error': 'Failed to scrape committee data',
                'committee_data': None
            }

        result['committee_data'] = {
            'member_count': len(committee_members),
            'sample_members': committee_members[:3] if len(committee_members) > 0 else []
        }

        result['steps'].append({'step': 2, 'action': 'Extracting MEP profiles'})
        mep_data = {}

        for member in committee_members:
            name = member.get('name', '')
            mep_id = member.get('mep_id', '')

            if name and mep_id:
                key = name.upper()
                url_name = name.replace(' ', '+')

                mep_data[key] = {
                    'mep_id': mep_id,
                    'name': name,
                    'url': f"https://www.europarl.europa.eu/meps/en/{mep_id}/{url_name}/home"
                }

        result['mep_data'] = {
            'count': len(mep_data),
            'sample_keys': list(mep_data.keys())[:5],
            'sample_names': [mep_data[k]['name'] for k in list(mep_data.keys())[:5]]
        }

        result['steps'].append({'step': 3, 'action': 'Testing MEP name linking'})

        if mep_data:
            first_mep_name = list(mep_data.values())[0]['name']

            test_cases = [
                f"**{first_mep_name}** serves as Chair.",
                f"The committee is chaired by {first_mep_name}.",
                f"{first_mep_name} is a member."
            ]

            ai_service = get_ai_service()

            test_results = []
            for test_text in test_cases:
                linked_text = ai_service._linkify_mep_names(test_text, mep_data)

                test_results.append({
                    'original': test_text,
                    'linked': linked_text,
                    'has_markdown_link': '[' in linked_text and '](' in linked_text
                })

            result['link_tests'] = test_results
            result['linking_works'] = any(t['has_markdown_link'] for t in test_results)
        else:
            result['link_tests'] = []
            result['linking_works'] = False
            result['error'] = 'No MEP data extracted'

        return result

    except Exception as e:
        logger.error(f"Debug endpoint error: {str(e)}")
        import traceback
        return {
            'error': str(e),
            'traceback': traceback.format_exc(),
            'timestamp': datetime.now().isoformat()
        }
