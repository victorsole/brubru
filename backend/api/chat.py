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
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import asyncio

from ..services.ai_service import AIService, ChatMessage, get_ai_service
from ..services.ai.context_builder import get_context_builder
from ..services.ai.citation_tracker import CitationTracker
from ..services.ai.hybrid_legal_assistant import HybridLegalAssistant, get_hybrid_assistant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Use hybrid assistant (Saul-7B + Claude) for enhanced legal analysis
# ⚠️  TEMPORARILY DISABLED: Saul-7B API causing request hangs
USE_HYBRID_ASSISTANT = False


# Request/Response Models

class ChatMessageRequest(BaseModel):
    """Request to send chat message"""
    message: str = Field(..., description="User message", min_length=1, max_length=5000)
    chat_id: Optional[str] = Field(None, description="Conversation ID (optional, for continuing conversation)")
    user_id: Optional[str] = Field(None, description="User ID (optional)")
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


# In-memory storage (in production, use database)
# Format: {chat_id: {'messages': [...], 'citations': [...]}}
chat_storage: Dict[str, Dict[str, Any]] = {}


# Endpoints

@router.post("/message", response_model=ChatMessageResponse)
async def send_message(
    request: ChatMessageRequest,
    background_tasks: BackgroundTasks
):
    """
    Send message and get AI response with EU context.

    Args:
        request: Chat message request

    Returns:
        AI response with citations

    Example:
        POST /api/chat/message
        {
            "message": "What's the status of the AI Act?",
            "use_context": true
        }

        Response:
        {
            "chat_id": "chat_123",
            "message": "The AI Act (Regulation 2024/1689) [1] was adopted...",
            "citations": [{"id": 1, "title": "...", "url": "..."}],
            "tokens_used": 1500,
            "...": "..."
        }
    """
    start_time = datetime.now()

    try:
        # Generate chat ID if not provided
        chat_id = request.chat_id or f"chat_{int(datetime.now().timestamp() * 1000)}"

        # Get or create conversation history
        if chat_id not in chat_storage:
            chat_storage[chat_id] = {
                'messages': [],
                'citations': [],
                'created_at': datetime.now().isoformat()
            }

        conversation = chat_storage[chat_id]

        # Build conversation history
        history = [
            ChatMessage(
                role=msg['role'],
                content=msg['content'],
                timestamp=datetime.fromisoformat(msg['timestamp'])
            )
            for msg in conversation['messages']
        ]

        # Get AI service (hybrid or standard)
        if USE_HYBRID_ASSISTANT:
            # Use hybrid assistant (Saul-7B + Claude) for enhanced legal analysis
            ai_service = get_hybrid_assistant()
            logger.info("Using Hybrid Legal Assistant (Saul-7B + Claude)")
        else:
            # Use standard Claude-only service
            ai_service = get_ai_service()
            logger.info("Using standard AI service (Claude only)")

        # Generate response with timeout (180 seconds = 3 minutes for all requests)
        # Extended timeout to handle complex queries with tender context, web search, etc.
        timeout = 180.0

        try:
            response = await asyncio.wait_for(
                ai_service.chat(
                    user_message=request.message,
                    conversation_history=history,
                    user_id=request.user_id,
                    document_ids=request.document_ids,
                    use_context=request.use_context,
                    stream=False
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
            # Handle specific Claude API errors
            error_msg = str(ai_error)

            # Check for PDF page limit error
            if "100 PDF pages" in error_msg or "maximum of 100 PDF pages" in error_msg:
                logger.warning(f"PDF page limit exceeded: {error_msg}")
                raise HTTPException(
                    status_code=400,
                    detail="The uploaded PDF exceeds Claude's 100-page limit. The system will extract text from large PDFs automatically. Please try uploading again."
                )

            # Check for other document-related errors
            if "invalid_request_error" in error_msg and "pdf" in error_msg.lower():
                logger.warning(f"PDF processing error: {error_msg}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Error processing PDF document: {error_msg}"
                )

            # Re-raise other errors
            raise

        # Store messages
        conversation['messages'].append({
            'role': 'user',
            'content': request.message,
            'timestamp': datetime.now().isoformat()
        })

        conversation['messages'].append({
            'role': 'assistant',
            'content': response.message,
            'timestamp': datetime.now().isoformat()
        })

        # Store citations
        conversation['citations'].extend(response.citations)

        # Background: Index conversation for future search
        # background_tasks.add_task(index_conversation, chat_id, request.message, response.message)

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

    Args:
        request: Chat message request

    Returns:
        Streaming response

    Example:
        POST /api/chat/stream
        {
            "message": "What's the AI Act?",
            "chat_id": "chat_123"
        }

        Response: Server-Sent Events stream
        data: The AI Act
        data:  (Regulation
        data:  2024/1689)
        ...
    """
    try:
        chat_id = request.chat_id or f"chat_{int(datetime.now().timestamp() * 1000)}"

        # Get conversation history
        conversation = chat_storage.get(chat_id, {'messages': [], 'citations': []})

        history = [
            ChatMessage(
                role=msg['role'],
                content=msg['content'],
                timestamp=datetime.fromisoformat(msg['timestamp'])
            )
            for msg in conversation['messages']
        ]

        # Get AI service (streaming not yet implemented for hybrid assistant)
        # TODO: Implement streaming support in HybridLegalAssistant
        ai_service = get_ai_service()
        logger.info("Using standard AI service for streaming (hybrid streaming not yet implemented)")

        # Create streaming response
        async def generate():
            full_response = ""

            async for chunk in ai_service.chat_stream(
                user_message=request.message,
                conversation_history=history,
                use_context=request.use_context
            ):
                full_response += chunk
                yield f"data: {chunk}\n\n"

            # Store messages after streaming complete
            if chat_id not in chat_storage:
                chat_storage[chat_id] = {
                    'messages': [],
                    'citations': [],
                    'created_at': datetime.now().isoformat()
                }

            chat_storage[chat_id]['messages'].append({
                'role': 'user',
                'content': request.message,
                'timestamp': datetime.now().isoformat()
            })

            chat_storage[chat_id]['messages'].append({
                'role': 'assistant',
                'content': full_response,
                'timestamp': datetime.now().isoformat()
            })

            # Send completion event
            yield f"data: [DONE]\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    except Exception as e:
        logger.error(f"Failed to stream chat: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{chat_id}", response_model=ConversationHistoryResponse)
async def get_history(chat_id: str):
    """
    Get conversation history.

    Args:
        chat_id: Conversation ID

    Returns:
        Conversation history

    Example:
        GET /api/chat/history/chat_123

        Response:
        {
            "chat_id": "chat_123",
            "messages": [
                {"role": "user", "content": "...", "timestamp": "..."},
                {"role": "assistant", "content": "...", "timestamp": "..."}
            ],
            "total_messages": 10
        }
    """
    try:
        if chat_id not in chat_storage:
            raise HTTPException(status_code=404, detail="Conversation not found")

        conversation = chat_storage[chat_id]

        return ConversationHistoryResponse(
            chat_id=chat_id,
            messages=conversation['messages'],
            total_messages=len(conversation['messages'])
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

    Args:
        chat_id: Conversation ID

    Returns:
        All citations used in conversation

    Example:
        GET /api/chat/citations/chat_123

        Response:
        {
            "chat_id": "chat_123",
            "citations": [
                {
                    "id": 1,
                    "type": "legislation",
                    "title": "AI Act",
                    "url": "..."
                }
            ],
            "total_citations": 5
        }
    """
    try:
        if chat_id not in chat_storage:
            raise HTTPException(status_code=404, detail="Conversation not found")

        conversation = chat_storage[chat_id]
        citations = conversation.get('citations', [])

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

    Args:
        chat_id: Conversation ID

    Returns:
        Success message

    Example:
        DELETE /api/chat/chat_123

        Response:
        {"status": "deleted", "chat_id": "chat_123"}
    """
    try:
        if chat_id not in chat_storage:
            raise HTTPException(status_code=404, detail="Conversation not found")

        del chat_storage[chat_id]

        logger.info(f"Deleted conversation {chat_id}")

        return {"status": "deleted", "chat_id": chat_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_conversations(limit: int = 10):
    """
    List recent conversations.

    Args:
        limit: Maximum conversations to return

    Returns:
        List of conversation summaries

    Example:
        GET /api/chat/list?limit=10

        Response:
        {
            "conversations": [
                {
                    "chat_id": "chat_123",
                    "created_at": "...",
                    "message_count": 10,
                    "last_message": "..."
                }
            ],
            "total": 5
        }
    """
    try:
        conversations = []

        for chat_id, data in list(chat_storage.items())[:limit]:
            messages = data.get('messages', [])
            last_message = messages[-1]['content'][:100] if messages else ""

            conversations.append({
                'chat_id': chat_id,
                'created_at': data.get('created_at', ''),
                'message_count': len(messages),
                'last_message': last_message
            })

        return {
            'conversations': conversations,
            'total': len(chat_storage)
        }

    except Exception as e:
        logger.error(f"Failed to list conversations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Health check endpoint
@router.get("/health")
async def health_check():
    """
    Health check for chat service.

    Returns:
        Service status
    """
    try:
        # Check if AI service is available
        ai_service = get_ai_service()
        model_info = await ai_service.get_model_info()

        return {
            'status': 'healthy',
            'service': 'chat',
            'model': model_info['model'],
            'conversations': len(chat_storage),
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

    This endpoint:
    1. Scrapes ENVI committee data
    2. Extracts MEP profiles
    3. Tests linking with sample text
    4. Returns all internal state for inspection
    """
    try:
        from ..services.scrapers.european_parliament_scraper import EuropeanParliamentScraper
        from ..services.ai_service import get_ai_service

        result = {
            'timestamp': datetime.now().isoformat(),
            'steps': []
        }

        # Step 1: Scrape committee data
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

        # Step 2: Extract MEP data (as ai_service does from committee_info)
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

        # Step 3: Test linking
        result['steps'].append({'step': 3, 'action': 'Testing MEP name linking'})

        if mep_data:
            # Get first MEP name for testing
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
