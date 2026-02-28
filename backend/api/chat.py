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

import logging
import uuid as uuid_mod
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import asyncio

from services.ai_service import AIService, ChatMessage, get_ai_service
from services.ai.context_builder import get_context_builder
from services.ai.citation_tracker import CitationTracker
from services.ai.hybrid_legal_assistant import HybridLegalAssistant, get_hybrid_assistant
from core.database import SessionLocal
from models.chat import Chat, Message

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

def _get_or_create_chat(chat_id_str: str, user_id: Optional[str] = None, pre_user_id: Optional[str] = None) -> tuple:
    """Get existing chat or create new one. Returns (chat_id_str, messages_list)."""
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
            chat_user_id = uuid_mod.uuid4()

        new_chat = Chat(
            user_id=chat_user_id,
            pre_user_id=pre_user_id,
            title=None,
            message_count=0,
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


def _list_chats(user_id: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
    """List recent chats, optionally filtered by user."""
    db = SessionLocal()
    try:
        query = db.query(Chat).filter(Chat.is_active == True)

        if user_id:
            try:
                user_uuid = uuid_mod.UUID(user_id)
                query = query.filter(Chat.user_id == user_uuid)
            except (ValueError, AttributeError):
                pass

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
    background_tasks: BackgroundTasks
):
    """
    Send message and get AI response with EU context.
    """
    start_time = datetime.now()

    try:
        # Get or create chat (runs in executor to not block async)
        loop = asyncio.get_event_loop()

        if request.chat_id:
            chat_id, history_dicts = await loop.run_in_executor(
                None, _get_or_create_chat, request.chat_id, request.user_id, request.pre_user_id
            )
        else:
            chat_id, history_dicts = await loop.run_in_executor(
                None, _get_or_create_chat, str(uuid_mod.uuid4()), request.user_id, request.pre_user_id
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
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"Failed to process chat message: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def stream_message(request: ChatMessageRequest):
    """
    Stream AI response.
    """
    try:
        loop = asyncio.get_event_loop()

        if request.chat_id:
            chat_id, history_dicts = await loop.run_in_executor(
                None, _get_or_create_chat, request.chat_id, request.user_id, request.pre_user_id
            )
        else:
            chat_id, history_dicts = await loop.run_in_executor(
                None, _get_or_create_chat, str(uuid_mod.uuid4()), request.user_id, request.pre_user_id
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

            async for chunk in ai_service.chat_stream(
                user_message=request.message,
                conversation_history=history,
                use_context=request.use_context,
                is_pre_user=is_pre_user
            ):
                full_response += chunk
                yield f"data: {chunk}\n\n"

            # Save messages to database after streaming completes
            _save_messages(
                chat_id,
                request.message,
                full_response,
                user_id=request.user_id,
            )

            yield f"data: [DONE]\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    except Exception as e:
        logger.error(f"Failed to stream chat: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{chat_id}", response_model=ConversationHistoryResponse)
async def get_history(chat_id: str):
    """
    Get conversation history.
    """
    try:
        loop = asyncio.get_event_loop()
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
async def get_citations(chat_id: str):
    """
    Get citations for conversation.
    """
    try:
        loop = asyncio.get_event_loop()
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
async def delete_conversation(chat_id: str):
    """
    Delete conversation.
    """
    try:
        loop = asyncio.get_event_loop()
        deleted = await loop.run_in_executor(None, _delete_chat, chat_id)

        if not deleted:
            raise HTTPException(status_code=404, detail="Conversation not found")

        logger.info(f"Deleted conversation {chat_id}")

        return {"status": "deleted", "chat_id": chat_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_conversations(limit: int = 50, user_id: Optional[str] = None):
    """
    List recent conversations.
    """
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _list_chats, user_id, limit)
        return result

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

        return {
            'status': 'healthy',
            'service': 'chat',
            'model': model_info['model'],
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
