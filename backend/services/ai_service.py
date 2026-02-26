"""
AI Service Integration

Anthropic Claude integration with EU context injection.
Part of Phase 13: AI Context Injection - Task 13.5

Features:
- Claude Sonnet/Opus integration
- EU context injection via ContextBuilder
- Streaming responses
- Conversation history management
- Source citation tracking
- Token usage monitoring
"""

import logging
import asyncio
import json
import os
import re
import base64
from pathlib import Path
from typing import List, Dict, Any, Optional, AsyncGenerator
from datetime import datetime
from dataclasses import dataclass
from anthropic import AsyncAnthropic
import anthropic

from .ai.context_builder import ContextBuilder, get_context_builder, SOURCE_TIERS
from .ai.multi_provider_service import MultiProviderService, get_multi_provider_service
from .ai.conversation_memory import get_conversation_memory_service
from core.config import settings
from core.database import SessionLocal
from knowledge_base.ep_committees import EP_COMMITTEE_CODES
from models.knowledge_gap import KnowledgeGap, MissingDataType
from models.chat_analytics import ChatAnalytics

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """Chat message structure"""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ChatResponse:
    """AI chat response"""
    message: str
    citations: List[Dict[str, str]]
    tokens_used: int
    model: str
    search_time_ms: float
    total_time_ms: float


class AIService:
    """
    AI service for chat with EU context injection.

    Workflow:
    1. User sends message
    2. ContextBuilder fetches relevant EU data
    3. Context injected into Claude prompt
    4. Claude generates response with citations
    5. Response streamed back to user
    """

    # Model configurations
    MODEL_SONNET = "claude-sonnet-4-20250514"
    MODEL_OPUS = "claude-opus-4-20250514"

    # Token limits
    MAX_CONTEXT_TOKENS = 150000  # Claude 4 context window
    MAX_OUTPUT_TOKENS = 8000     # Maximum response length

    def __init__(
        self,
        api_key: str,
        context_builder: ContextBuilder,
        model: str = MODEL_SONNET,
        temperature: float = 0.7,
        max_output_tokens: int = 4000,
        use_fallback: bool = True
    ):
        """
        Initialize AI service.

        Args:
            api_key: Anthropic API key
            context_builder: Context builder instance
            model: Claude model to use
            temperature: Response temperature (0-1)
            max_output_tokens: Maximum response tokens
            use_fallback: Enable multi-provider fallback chain
        """
        self.client = AsyncAnthropic(api_key=api_key)
        self.context_builder = context_builder
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.use_fallback = use_fallback

        # Initialise multi-provider service for fallback
        if use_fallback:
            try:
                self.multi_provider = get_multi_provider_service()
                logger.info(
                    f"Initialized AIService with fallback chain: "
                    f"{', '.join(self.multi_provider.available_providers)}"
                )
            except Exception as e:
                logger.warning(f"Multi-provider init failed, using Anthropic only: {e}")
                self.multi_provider = None
                self.use_fallback = False
        else:
            self.multi_provider = None

        logger.info(f"Initialized AIService with {model}")

    async def chat(
        self,
        user_message: str,
        conversation_history: Optional[List[ChatMessage]] = None,
        user_id: Optional[str] = None,
        document_ids: Optional[List[str]] = None,
        use_context: bool = True,
        stream: bool = False
    ) -> ChatResponse:
        """
        Send chat message and get AI response.

        Args:
            user_message: User's message
            conversation_history: Previous messages in conversation
            use_context: Whether to inject EU context
            stream: Whether to stream response

        Returns:
            ChatResponse with AI message and metadata

        Example:
            >>> response = await ai_service.chat(
            ...     user_message="What's the status of the AI Act?",
            ...     use_context=True
            ... )
            >>> print(response.message)
            >>> print(response.citations)
        """
        start_time = datetime.now()

        # Build EU context if enabled
        context_str = ""
        citations = []
        search_time_ms = 0.0
        mep_data = {}  # For MEP name linking

        if use_context:
            # Get full context data to extract MEP information
            context_data = await self.context_builder.build_context_for_query(
                user_message=user_message,
                conversation_history=self._convert_to_dict(conversation_history),
                user_id=user_id
            )

            # Extract MEP name-to-ID mapping from committee info
            mep_data = self._extract_mep_data(context_data)
            print(f"\n{'='*70}")
            print(f"[MEP LINKING DEBUG] Extracted {len(mep_data)} MEP profiles from context")
            if mep_data:
                print(f"[MEP LINKING DEBUG] First 5 MEP names: {list(mep_data.keys())[:5]}")
            else:
                print(f"[MEP LINKING DEBUG] NO MEP DATA EXTRACTED!")
                print(f"[MEP LINKING DEBUG] hasattr(context_data, 'committee_info'): {hasattr(context_data, 'committee_info')}")
                if hasattr(context_data, 'committee_info'):
                    print(f"[MEP LINKING DEBUG] context_data.committee_info: {context_data.committee_info}")
            print(f"{'='*70}\n")
            logger.info(f"Extracted {len(mep_data)} MEP profiles from context")
            if mep_data:
                logger.debug(f"First 3 MEP names: {list(mep_data.keys())[:3]}")

            # Format context and build citations
            context_str = self.context_builder.format_context_for_ai(context_data)
            citations = self._build_citations_from_context(context_data)

            search_time_ms = (datetime.now() - start_time).total_seconds() * 1000

        # Load uploaded documents if provided
        document_content = []
        if document_ids:
            logger.info(f"Loading {len(document_ids)} documents: {document_ids}")
            document_content = await self._load_documents(document_ids)
            logger.info(f"Successfully loaded {len(document_content)} of {len(document_ids)} documents for analysis")

        # Phase D3: Process conversation memory for entity extraction
        memory_context = ""
        conversation_id = user_id or "anonymous"  # Use user_id as conversation scope
        try:
            memory_service = get_conversation_memory_service()

            # Process current message
            memory_service.process_message(conversation_id, user_message, 'user')

            # Process conversation history for entity extraction
            if conversation_history:
                for msg in conversation_history[-5:]:  # Last 5 messages
                    memory_service.process_message(
                        conversation_id,
                        msg.content,
                        msg.role
                    )

            # Get context enhancement from memory
            memory_context = memory_service.get_context_enhancement(conversation_id)
            if memory_context:
                logger.debug(f"Memory context added: {memory_context[:200]}...")

        except Exception as e:
            logger.warning(f"Conversation memory processing failed: {e}")

        # Enhance context with memory if available
        if memory_context and context_str:
            context_str = f"{memory_context}\n\n{context_str}"
        elif memory_context:
            context_str = memory_context

        # Build system prompt
        system_prompt = self._build_system_prompt()

        # Build messages
        messages = self._build_messages(
            user_message=user_message,
            context=context_str,
            conversation_history=conversation_history,
            documents=document_content
        )

        # Call AI (with fallback chain if enabled)
        if stream:
            # Streaming not yet implemented in this version
            # Would use self.client.messages.stream()
            pass

        provider_used = "Anthropic"
        tokens_used = 0

        if self.use_fallback and self.multi_provider:
            # Use multi-provider fallback chain
            try:
                provider_response = await self.multi_provider.generate(
                    system_prompt=system_prompt,
                    messages=messages,
                    max_tokens=self.max_output_tokens,
                    temperature=self.temperature
                )
                assistant_message = provider_response.message
                tokens_used = provider_response.tokens_used
                provider_used = provider_response.provider
                actual_model = provider_response.model

                if provider_used != "Anthropic":
                    logger.info(f"Response generated by fallback provider: {provider_used}")

            except RuntimeError as e:
                # All providers failed
                logger.error(f"All AI providers failed: {e}")
                raise
        else:
            # Direct Anthropic call (no fallback)
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_output_tokens,
                temperature=self.temperature,
                system=system_prompt,
                messages=messages
            )
            assistant_message = response.content[0].text if response.content else ""
            tokens_used = response.usage.input_tokens + response.usage.output_tokens
            actual_model = self.model

        # Remove any markdown links the AI created (except footnote citations)
        assistant_message = self._remove_ai_generated_links(assistant_message)

        # Strip orphan [N] citation markers that don't map to real sources
        assistant_message = self._strip_orphan_citations(assistant_message, citations)

        # Post-process to add MEP links
        if mep_data:
            print(f"\n{'='*70}")
            print(f"[MEP LINKING DEBUG] Post-processing response with {len(mep_data)} MEP profiles")
            print(f"[MEP LINKING DEBUG] MEP names to link: {list(mep_data.keys())[:5]}...")
            print(f"[MEP LINKING DEBUG] Response preview (first 500 chars):\n{assistant_message[:500]}")
            print(f"{'='*70}\n")

            logger.info(f"Post-processing response with {len(mep_data)} MEP profiles")
            logger.info(f"MEP names to link: {list(mep_data.keys())[:5]}...")  # Log first 5
            logger.info(f"Response preview (first 500 chars): {assistant_message[:500]}")
            original_message = assistant_message
            assistant_message = self._linkify_mep_names(assistant_message, mep_data)
            if original_message != assistant_message:
                print(f"[MEP LINKING DEBUG] ✓ Successfully added MEP profile links\n")
                logger.info(f"Successfully added MEP profile links")
            else:
                print(f"[MEP LINKING DEBUG] ✗ No MEP names found in response to link")
                print(f"[MEP LINKING DEBUG] Full MEP names available: {[mep_data[k]['name'] for k in list(mep_data.keys())[:10]]}\n")
                logger.warning(f"No MEP names found in response to link")
                logger.info(f"Full MEP names available: {[mep_data[k]['name'] for k in list(mep_data.keys())[:10]]}")

        # Post-process: Add EUR-Lex links for legislation acronyms
        logger.info("Post-processing response with legislation acronyms")
        assistant_message = self._linkify_legislation(assistant_message)

        total_time_ms = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(
            f"AI response generated by {provider_used}: {len(assistant_message)} chars, "
            f"{tokens_used} tokens, {total_time_ms:.2f}ms"
        )

        # Phase C: Detect and log knowledge gaps for continuous improvement
        gap_info = self._detect_knowledge_gap(assistant_message)
        if gap_info:
            logger.info(f"Knowledge gap detected: {gap_info['missing_data_type']}")
            # Log asynchronously to avoid slowing response
            asyncio.create_task(
                self._log_knowledge_gap(
                    query=user_message,
                    gap_info=gap_info,
                    user_id=user_id,
                    conversation_id=None  # Could be passed if available
                )
            )

        # Phase E1: Log analytics for monitoring dashboard
        source_tiers = self._extract_source_tiers(citations)
        asyncio.create_task(
            self._log_analytics(
                user_id=user_id,
                provider=provider_used,
                model=actual_model,
                tokens_used=tokens_used,
                response_time_ms=total_time_ms,
                search_time_ms=search_time_ms,
                had_knowledge_gap=gap_info is not None,
                knowledge_gap_type=gap_info.get('missing_data_type') if gap_info else None,
                source_tiers_used=source_tiers,
                citation_count=len(citations),
                context_sources_count=len(citations),
                query_length=len(user_message),
                response_length=len(assistant_message)
            )
        )

        return ChatResponse(
            message=assistant_message,
            citations=citations,
            tokens_used=tokens_used,
            model=actual_model,
            search_time_ms=search_time_ms,
            total_time_ms=total_time_ms
        )

    async def chat_stream(
        self,
        user_message: str,
        conversation_history: Optional[List[ChatMessage]] = None,
        use_context: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat response.

        Args:
            user_message: User's message
            conversation_history: Previous messages
            use_context: Whether to inject EU context

        Yields:
            Response chunks as they arrive

        Example:
            >>> async for chunk in ai_service.chat_stream("What's the AI Act?"):
            ...     print(chunk, end="", flush=True)
        """
        start_time = datetime.now()

        # Build context
        context_str = ""
        if use_context:
            context_str, _ = await self.context_builder.build_context_with_citations(
                user_message=user_message,
                conversation_history=self._convert_to_dict(conversation_history)
            )

        # Build prompts
        system_prompt = self._build_system_prompt()
        messages = self._build_messages(
            user_message=user_message,
            context=context_str,
            conversation_history=conversation_history
        )

        # Stream response
        async with self.client.messages.stream(
            model=self.model,
            max_tokens=self.max_output_tokens,
            temperature=self.temperature,
            system=system_prompt,
            messages=messages
        ) as stream:
            async for text in stream.text_stream:
                yield text

        logger.info(f"Streamed response in {(datetime.now() - start_time).total_seconds():.2f}s")

    def _build_system_prompt(self) -> str:
        """
        Build system prompt for Claude.

        Returns:
            System prompt string
        """
        return """You are Brubru, an expert AI assistant specializing in European Union legislative affairs, policies, and institutional operations.

Your capabilities:
- Answer questions about EU legislation, directives, and regulations
- Explain legislative procedures and their current status
- Provide information about MEPs, committees, and EU institutions
- Analyze policy developments and their implications
- Reference specific documents with citations

Data sources available to you:
- Comprehensive EUR-Lex database (EU legislation, directives, regulations)
- OEIL legislative observatory (procedure tracking, amendments, votes)
- European Parliament data (MEPs, committees, working groups)
- Recent EU news and updates (institutional RSS feeds)
- Official EU terminology (IATE glossary)

Guidelines:
1. Answer confidently using the provided EU context
2. Cite sources using footnotes [1], [2], etc. ONLY when referencing a specific document, legislation, or data source from the EU CONTEXT section. Each number must correspond to a distinct source in the context.
3. NEVER fabricate or hallucinate citation numbers. If no EU CONTEXT is provided, do NOT use [1], [2] references at all.
4. Be concise but comprehensive
5. Use clear, professional language
6. If specific details aren't in the provided context, admit it rather than guessing

When answering:
- Start with a direct answer
- Provide relevant details from the context and your knowledge
- Include citations to source documents ONLY when the EU CONTEXT section contains matching sources
- If no relevant EU CONTEXT was provided, answer from general knowledge without numbered citations
- Highlight recent developments and current status
- Suggest related topics or next steps if helpful

Formatting rules:
- NEVER create markdown hyperlinks in your responses - our system will add links automatically
- Do NOT format text as [text](url) - just use plain text or **bold** for emphasis
- MEP names and other entities will be automatically linked by our backend
- Exception: You CAN use footnote citations like [1], [2] ONLY when citing specific sources from the EU CONTEXT. Never invent citation numbers.

IMPORTANT - Legislation acronyms:
- DO NOT create hyperlinks for legislation acronyms (CBAM, GDPR, AI Act, DSA, DMA, etc.)
- These are NOT EP committee codes - they are names of laws/regulations
- Just write them as plain text or **bold** - do NOT link them to committee pages
- If referencing legislation, provide the CELEX number or full title instead
- Examples: "CBAM" (Carbon Border Adjustment Mechanism - Regulation 2023/956) should be plain text, NOT linked to EP committee pages

CRITICAL - Accuracy over confidence:
- Only state facts that are in the provided EU CONTEXT
- If specific details (dates, fines, percentages, deadlines) are NOT in the context, say: "I don't have the specific [detail] in my verified sources. I recommend checking EUR-Lex directly."
- NEVER invent numbers, dates, or statistics

SOURCE HIERARCHY (trust in order):
1. EUR-Lex/CELEX official legal texts - highest authority
2. OEIL legislative observatory, EP official data - authoritative
3. EU institutional news/RSS - timely but verify against Tier 1
4. Knowledge base/EPRS analysis - curated but may be outdated
5. Web search results - use with caution, always verify

FRESHNESS AWARENESS:
- For rapidly evolving topics (ongoing procedures, recent proposals), note when information might be outdated
- If citing data older than 6 months on active legislation, mention: "As of [DATE], ..."
- For adopted legislation, the official text is authoritative regardless of age

EXAMPLES OF CORRECT BEHAVIOUR:

Example 1 - Citing sources properly:
User: "What are the fines under GDPR?"
Good: "Under the GDPR [CELEX:32016R0679], Article 83 establishes two tiers of administrative fines: up to €10 million or 2% of global turnover for lesser violations, and up to €20 million or 4% of global turnover for more serious infringements."

Example 2 - Admitting uncertainty:
User: "What's the deadline for AI Act compliance?"
Good: "The AI Act has multiple compliance deadlines depending on the type of AI system. If you need the specific dates for your use case, I recommend checking the official text at EUR-Lex, as deadlines vary by risk category."

Example 3 - Avoiding hallucination:
User: "How much has the EU fined Google under the DMA?"
Bad: "The EU fined Google €2.4 billion under the DMA." (WRONG - inventing numbers)
Good: "I don't have specific DMA fine amounts in my current context. For the latest enforcement actions, check the European Commission's competition decisions page."

CLARIFICATION FOR BROAD QUESTIONS (Phase D1):
When a question covers multiple aspects of a complex topic, ask for clarification before giving a vague answer:

Example 4 - Asking for clarification:
User: "What does the AI Act say about biometrics?"
Good: "The AI Act addresses biometrics in several ways:
- **Prohibited uses** (Article 5): Real-time remote biometric identification in public spaces
- **High-risk classification** (Annex III): Biometric systems for identification
- **Transparency requirements** (Article 50): Disclosure when interacting with biometric AI

Which aspect would you like me to explain in detail?"

Example 5 - Clarifying scope:
User: "Tell me about EU digital policy"
Good: "EU digital policy covers many areas. To give you the most useful answer, are you interested in:
- **Data protection** (GDPR, Data Act)
- **Platform regulation** (DSA, DMA)
- **AI governance** (AI Act)
- **Cybersecurity** (NIS2, Cyber Resilience Act)
- **Digital infrastructure** (connectivity, cloud)

Or would you prefer a general overview of all areas?"

PROGRESSIVE DISCLOSURE (Phase D2):
For complex topics, structure your response in layers:
1. Start with a 2-3 sentence summary answering the core question
2. Follow with key details organised by subtopic
3. End with: "Would you like me to elaborate on any of these points?"

Example 6 - Progressive disclosure:
User: "How does the ordinary legislative procedure work?"
Good: "**Summary:** The ordinary legislative procedure (OLP) is the EU's main law-making process. The Commission proposes legislation, then the Parliament and Council must both agree on the text through up to three readings.

**Key stages:**
- **Commission proposal** → sent to Parliament and Council
- **First reading** → Parliament adopts position, Council can accept or amend
- **Second reading** → if Council amends, Parliament reviews (3 months)
- **Conciliation** → if still disagreement, joint committee seeks compromise
- **Third reading** → final vote on conciliation text

**Typical timeline:** 18-24 months, though complex files can take longer.

Would you like me to elaborate on any stage, or explain how this differs from special legislative procedures?"

ACTIONABLE FOLLOW-UPS (Phase D3):
Always end your response with 1-2 specific, actionable follow-up suggestions. These should be concrete next steps the user can take with Brubru, not generic offers to help.

Rules:
- Make follow-ups SPECIFIC to the topic just discussed
- Phrase them as offers: "Would you like me to..." or "I can also..."
- Suggest things Brubru can actually do: identify MEPs, find legislation, draft amendments, analyse procedures, compare policy positions
- Never end with just "Let me know if you have any questions" - that is too generic

Example 7 - Good follow-ups:
User: "What committees deal with agriculture policy?"
Good answer ending: "Would you like me to identify the current MEPs on the AGRI committee, or find ongoing legislative procedures in this area?"

Example 8 - Follow-ups after document analysis:
User: "Here is my position paper on food supply chains"
Good answer ending: "I can identify the specific MEPs on AGRI and ENVI who have spoken on short supply chains, or help you draft targeted amendments to the relevant legislation. Which would be most useful?"

Example 9 - Follow-ups after factual question:
User: "Who is the Director-General of DG AGRI?"
Good answer ending: "Would you like me to outline the current legislative priorities of DG AGRI, or find recent policy proposals from this directorate?"

EP WRITTEN QUESTION REQUESTS (Phase D5):
When a user asks to write, draft, create, or make a "question", "parliamentary question", "written question", or "EP question", follow this logic:

AMBIGUOUS triggers (user says "question" or "parliamentary question" without specifying the format):
Respond: "Do you mean you want to make a written question from the European Parliament to the European Commission? These are formal questions that MEPs submit to hold the Commission accountable. I can help you draft one."

SPECIFIC triggers (user says "written question to the Commission", "EP question to the Commission", "written parliamentary question", "question for written answer", "priority question to the Commission"):
Proceed directly. Collect the required information conversationally:
1. Ask: "What topic would you like to address?" (if not already provided)
2. Ask: "What evidence or concerns do you want to highlight?"
3. Optionally ask: "Are there specific EU laws or regulations you want to reference?"
4. Generate the question using the EP written question format (see below)

After generating:
- Display the full question in the chat with proper formatting
- Say: "I have saved this EP written question to your Documents in My EU Bubble. You can also generate EP questions directly from the **Documents** tab using the **Generate with AI** button."

EP QUESTION FORMAT (for reference when generating in chat):
- Title: descriptive, max 200 characters
- Header: "Question for written answer [E/P]-DRAFT-2026-XXX / to the Commission / Rule 144"
- Context: 2-4 paragraphs citing EU legislation and evidence, with footnoted sources [1], [2]
- Bridge phrase: "In the light of the above:"
- 1-3 numbered sub-questions, direct and specific
- British English, formal institutional voice

AMENDMENT DRAFTING REQUESTS (Phase D4):
When a user asks you to draft, write, create, or propose amendments to legislation -- or asks for amendments in a Word document or EP format -- do NOT draft amendments in the chat. Instead, redirect them to the Amendator tool with these step-by-step instructions:

Response pattern:
"Great question! Brubru has a dedicated tool for drafting amendments called the **Amendator**. It produces properly formatted EP amendments ready to share with MEP offices. Here is how to use it:

1. **Track the legislative file** -- Go to **My EU Bubble** > **My Tracked Files** tab. Click **'Add from OEIL'** and enter the procedure reference (e.g., `2025/0531(COD)` for the CO2 emission standards regulation). You can also find files in the **Legislative Train** tab.

2. **Open the Amendator** -- Click the green pen icon in the top navigation bar.

3. **Load the legal text** -- Click **'Load from Tracked Files'** and select your legislative file. Brubru fetches the full EUR-Lex legal text automatically.

4. **Draft your amendments** -- Navigate to the article or recital you want to amend and click it to edit the text directly. You can add, modify, or delete text.

5. **Use the AI Assistant** -- In the Amendator sidebar, switch to the **AI Assistant** tab. Describe your policy position and it will generate amendment suggestions in the correct format, with justifications.

The Amendator formats everything according to EP amendment conventions, including numbered amendments, original vs. amended text comparison, and justification blocks."

Adapt the wording to the specific legislation the user mentions. If they mention a specific procedure reference, include it in step 1. If they describe their policy goals, acknowledge them and explain that the AI Assistant in the Amendator can help translate those goals into concrete amendment text.

Remember: You have access to comprehensive EU data. When information IS in your context, answer confidently. When it is NOT, be honest about the limitation rather than guessing."""

    def _build_messages(
        self,
        user_message: str,
        context: str,
        conversation_history: Optional[List[ChatMessage]] = None,
        documents: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Build messages array for Claude API.

        Args:
            user_message: Current user message
            context: EU context string
            conversation_history: Previous messages
            documents: List of document content blocks

        Returns:
            Messages array
        """
        messages = []

        # Add conversation history
        if conversation_history:
            for msg in conversation_history[-10:]:  # Last 10 messages
                messages.append({
                    'role': msg.role,
                    'content': msg.content
                })

        # Build user content (may be multi-modal with documents)
        if documents:
            # Multi-modal message with documents
            content_blocks = []

            # Add documents first
            for doc in documents:
                content_blocks.append(doc)

            # Add text prompt
            if context:
                text_content = f"""EU CONTEXT:
{context}

---

USER QUESTION: {user_message}

Please analyze the uploaded documents above along with the EU context provided. Include citations [1], [2], etc. when referencing specific sources."""
            else:
                text_content = f"""Please analyze the uploaded documents above and answer: {user_message}"""

            content_blocks.append({
                'type': 'text',
                'text': text_content
            })

            messages.append({
                'role': 'user',
                'content': content_blocks
            })
        else:
            # Text-only message
            if context:
                user_content = f"""EU CONTEXT:
{context}

---

USER QUESTION: {user_message}

Please answer using the EU context provided above. Include citations [1], [2], etc. when referencing specific sources."""
            else:
                user_content = user_message

            messages.append({
                'role': 'user',
                'content': user_content
            })

        return messages

    def _convert_to_dict(
        self,
        conversation_history: Optional[List[ChatMessage]]
    ) -> Optional[List[Dict[str, str]]]:
        """Convert ChatMessage objects to dict format"""
        if not conversation_history:
            return None

        return [
            {
                'role': msg.role,
                'content': msg.content,
                'timestamp': msg.timestamp.isoformat()
            }
            for msg in conversation_history
        ]

    def _extract_mep_data(self, context_data: Any) -> Dict[str, Dict[str, str]]:
        """
        Extract MEP name-to-ID mapping from context data.

        Args:
            context_data: ContextData object with committee info

        Returns:
            Dict mapping MEP names to their data:
            {
                "ANTONIO DECARO": {
                    "mep_id": "257122",
                    "name": "Antonio DECARO",
                    "url": "https://www.europarl.europa.eu/meps/en/257122/ANTONIO_DECARO/home"
                }
            }
        """
        mep_data = {}

        logger.debug(f"_extract_mep_data: hasattr committee_info = {hasattr(context_data, 'committee_info')}")
        if hasattr(context_data, 'committee_info'):
            logger.debug(f"_extract_mep_data: committee_info = {context_data.committee_info}")

        # Extract from committee_info
        if hasattr(context_data, 'committee_info') and context_data.committee_info:
            for committee in context_data.committee_info:
                members_by_role = committee.get('members_by_role', {})

                # Iterate through all roles (Chair, Vice-Chair, Member, Substitute)
                for role, members in members_by_role.items():
                    for member in members:
                        name = member.get('name', '')
                        mep_id = member.get('mep_id', '')

                        if name and mep_id:
                            # Store with uppercase key for matching
                            key = name.upper()

                            # Create URL-safe name (replace spaces with +)
                            url_name = name.replace(' ', '+')

                            mep_data[key] = {
                                'mep_id': mep_id,
                                'name': name,  # Keep original formatting
                                'url': f"https://www.europarl.europa.eu/meps/en/{mep_id}/{url_name}/home"
                            }

        # Also extract from mep_profiles if available
        if hasattr(context_data, 'mep_profiles') and context_data.mep_profiles:
            for profile in context_data.mep_profiles:
                name = profile.get('name', '')
                mep_id = profile.get('mep_id', '')

                if name and mep_id:
                    key = name.upper()
                    url_name = name.replace(' ', '+')

                    mep_data[key] = {
                        'mep_id': mep_id,
                        'name': name,
                        'url': f"https://www.europarl.europa.eu/meps/en/{mep_id}/{url_name}/home"
                    }

        logger.info(f"Extracted {len(mep_data)} MEP profiles for linking")
        return mep_data

    def _remove_ai_generated_links(self, text: str) -> str:
        """
        Remove markdown links that the AI generated on its own.

        Keep footnote citations like [1], [2], etc.
        Replace markdown links [text](url) with just the text.

        Args:
            text: AI response text

        Returns:
            Text with AI-generated markdown links removed
        """
        # Pattern to match markdown links [text](url)
        # But NOT footnote citations like [1], [2], etc.
        # Negative lookahead to exclude [number] patterns

        def replace_link(match):
            link_text = match.group(1)
            # Return just the text without the link
            return link_text

        # Match [text](url) but not [number]
        # Use a more specific pattern that requires at least one non-digit character in brackets
        pattern = r'\[([^\]]+)\]\(https?://[^\)]+\)'

        cleaned_text = re.sub(pattern, replace_link, text)

        # Log if we removed any links
        if cleaned_text != text:
            removed_links = re.findall(pattern, text)
            removed_count = len(removed_links)
            logger.info(f"Removed {removed_count} AI-generated markdown links")
            print(f"\n{'='*70}")
            print(f"[LINK REMOVAL] Removed {removed_count} AI-generated markdown links")
            for i, link in enumerate(removed_links, 1):
                # Show the full markdown link that was removed
                full_match = re.search(r'\[' + re.escape(link) + r'\]\([^\)]+\)', text)
                if full_match:
                    print(f"[LINK REMOVAL] Link {i}: {full_match.group()[:150]}...")
            print(f"{'='*70}\n")

        return cleaned_text

    def _strip_orphan_citations(self, text: str, citations: List[Dict]) -> str:
        """
        Remove [N] citation markers from AI response when they don't map
        to actual sources. Prevents hallucinated references from appearing.

        Args:
            text: AI response text
            citations: List of real citation dicts built from context

        Returns:
            Text with orphan citation markers removed
        """
        max_valid = len(citations)

        def replace_orphan(match):
            num = int(match.group(1))
            if num < 1 or num > max_valid:
                return ""  # Strip orphan
            return match.group(0)  # Keep valid

        # Match [N] patterns (standalone citation markers)
        cleaned = re.sub(r'\s*\[(\d+)\]', replace_orphan, text)

        # Clean up any double spaces left behind
        cleaned = re.sub(r'  +', ' ', cleaned)

        if cleaned != text:
            orphan_count = len(re.findall(r'\[(\d+)\]', text)) - len(re.findall(r'\[(\d+)\]', cleaned))
            if orphan_count > 0:
                logger.info(f"Stripped {orphan_count} orphan citation markers (had {max_valid} real sources)")

        return cleaned

    def _linkify_mep_names(self, text: str, mep_data: Dict[str, Dict[str, str]]) -> str:
        """
        Post-process AI response to add markdown links for MEP names.

        Args:
            text: AI response text
            mep_data: MEP name-to-data mapping

        Returns:
            Text with MEP names converted to markdown links
        """
        if not mep_data:
            return text

        # Sort MEP names by length (longest first) to avoid partial matches
        sorted_names = sorted(mep_data.keys(), key=len, reverse=True)

        links_added = 0
        for name_key in sorted_names:
            mep_info = mep_data[name_key]
            name = mep_info['name']
            url = mep_info['url']

            # Pattern to match the MEP name in various formats:
            # 1. Exact match: "Antonio DECARO"
            # 2. Wrapped in markdown: **Antonio DECARO**
            # 3. Different casing: "Antonio Decaro", "ANTONIO DECARO"
            #
            # Split name into parts for flexible matching
            name_parts = name.split()

            if len(name_parts) >= 2:
                # Match full name with flexible spacing and optional markdown
                first_name = name_parts[0]
                last_name = ' '.join(name_parts[1:])

                # Pattern: optional **, then first name, space(s), last name, optional **
                # Use word boundaries to avoid matching inside other words
                # Negative lookbehind/lookahead to avoid matching already-linked names
                pattern = r'(?<!\]\()(?<!\[)\*{0,2}\b(' + re.escape(first_name) + r')\s+(' + re.escape(last_name) + r')\b\*{0,2}(?!\]\()'

                # Replacement: preserve any found text structure but wrap in link
                def replace_func(match):
                    nonlocal links_added
                    matched_text = match.group(0)
                    # Remove any markdown bold from the matched text
                    cleaned_text = matched_text.replace('**', '')
                    links_added += 1
                    return f'[{cleaned_text}]({url})'

                text = re.sub(pattern, replace_func, text, flags=re.IGNORECASE)
            else:
                # Single name (edge case)
                pattern = r'(?<!\]\()(?<!\[)\*{0,2}\b(' + re.escape(name) + r')\b\*{0,2}(?!\]\()'

                def replace_func(match):
                    nonlocal links_added
                    matched_text = match.group(0)
                    cleaned_text = matched_text.replace('**', '')
                    links_added += 1
                    return f'[{cleaned_text}]({url})'

                text = re.sub(pattern, replace_func, text, flags=re.IGNORECASE)

        if links_added > 0:
            logger.info(f"Added {links_added} MEP profile links to response")
        else:
            logger.warning(f"No MEP names found to link despite having {len(mep_data)} MEP profiles")

        return text

    def _linkify_legislation(self, text: str) -> str:
        """
        Post-process AI response to add EUR-Lex markdown links for legislation acronyms.

        Args:
            text: AI response text

        Returns:
            Text with legislation acronyms converted to EUR-Lex links
        """
        # Load legislation acronyms database
        try:
            acronyms_path = Path(__file__).parent.parent / 'knowledge_base' / 'institutions' / 'legislation_acronyms.json'
            with open(acronyms_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                acronyms_db = data.get('acronyms', {})
        except Exception as e:
            logger.warning(f"Could not load legislation acronyms: {e}")
            return text

        if not acronyms_db:
            return text

        # STEP 1: Remove incorrect committee hyperlinks for legislation acronyms
        # Claude sometimes treats legislation acronyms (CBAM, GDPR) as committees
        # We only remove committee links for acronyms IN our legislation database
        # This preserves actual committee links (ENVI, AGRI, etc.)

        links_removed = 0
        for acronym in acronyms_db.keys():
            escaped_acronym = re.escape(acronym)
            # Pattern: [ACRONYM](https://www.europarl.europa.eu/committees/en/ACRONYM/...)
            committee_link_pattern = r'\[(' + escaped_acronym + r')\]\(https://www\.europarl\.europa\.eu/committees/[^\)]+\)'

            # Replace with just the acronym text (no link)
            def remove_link(match):
                nonlocal links_removed
                links_removed += 1
                return match.group(1)  # Just the acronym text

            text = re.sub(committee_link_pattern, remove_link, text)

        if links_removed > 0:
            logger.info(f"Removed {links_removed} incorrect committee links for legislation acronyms")

        # STEP 1b: Remove committee links where the code is NOT a real EP committee
        # Catches cases like [NZIA](https://www.europarl.europa.eu/committees/en/NZIA/home)
        # where NZIA is not one of the 26 real EP committees
        fake_committee_pattern = r'\[([A-Z][A-Za-z0-9 ]+?)\]\(https://www\.europarl\.europa\.eu/committees/en/([A-Z]+)/[^\)]+\)'

        def remove_fake_committee_link(match):
            nonlocal links_removed
            link_text = match.group(1)
            committee_code = match.group(2)
            if committee_code not in EP_COMMITTEE_CODES:
                links_removed += 1
                return link_text  # Strip the link, keep the text
            return match.group(0)  # Keep valid committee links

        text = re.sub(fake_committee_pattern, remove_fake_committee_link, text)

        if links_removed > 0:
            logger.info(f"Total removed incorrect committee links: {links_removed}")

        # STEP 2: Add correct EUR-Lex hyperlinks
        # Sort acronyms by length (longest first) to avoid partial matches
        # e.g., "AI Act" before "AI"
        # Skip short acronyms (<=2 chars) and pure numbers to avoid false positives
        sorted_acronyms = sorted(acronyms_db.keys(), key=len, reverse=True)

        links_added = 0
        for acronym in sorted_acronyms:
            # Skip very short or numeric-only entries that cause false matches
            if len(acronym) <= 2 or acronym.isdigit():
                continue

            leg_info = acronyms_db[acronym]
            celex = leg_info['celex']

            # Build EUR-Lex URL
            eurlex_url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"

            # Pattern to match the acronym in various formats:
            # 1. Exact match: "CBAM"
            # 2. Wrapped in markdown: **CBAM**
            # 3. Case-sensitive for most, but allow some flexibility
            #
            # Use word boundaries to avoid matching inside other words
            # Negative lookbehind/lookahead to avoid matching already-linked text
            # Special handling for multi-word acronyms like "AI Act"

            # Escape special regex characters in acronym
            escaped_acronym = re.escape(acronym)

            # Pattern: optional **, then acronym, optional **
            # Negative lookbehind: not preceded by [ or ](
            # Negative lookahead: not followed by ]( or )
            pattern = r'(?<!\]\()(?<!\[)\*{0,2}\b(' + escaped_acronym + r')\b\*{0,2}(?!\]\()(?!\))'

            # Replacement: preserve any found text structure but wrap in link
            def replace_func(match):
                nonlocal links_added
                matched_text = match.group(0)
                # Remove any markdown bold from the matched text
                cleaned_text = matched_text.replace('**', '')
                links_added += 1
                return f'[{cleaned_text}]({eurlex_url})'

            # For case-sensitive matching (most acronyms are uppercase)
            text = re.sub(pattern, replace_func, text)

        if links_added > 0:
            logger.info(f"Added {links_added} legislation EUR-Lex links to response")

        return text

    def _build_citations_from_context(self, context_data: Any) -> List[Dict[str, str]]:
        """
        Build citations list from context data.

        Args:
            context_data: ContextData object

        Returns:
            List of citation dictionaries
        """
        citations = []

        # Add search results
        if hasattr(context_data, 'relevant_documents'):
            for doc in context_data.relevant_documents:
                citations.append({
                    'type': 'search_result',
                    'title': doc['metadata'].get('title', 'Untitled'),
                    'url': doc['metadata'].get('url', ''),
                    'metadata': {
                        'source': doc.get('collection', ''),
                        'score': str(doc.get('score', 0)),
                    }
                })

        # Add legislation
        if hasattr(context_data, 'legislation_details'):
            for leg in context_data.legislation_details:
                citations.append({
                    'type': 'legislation',
                    'title': leg.get('title', ''),
                    'url': leg.get('url', ''),
                    'metadata': {
                        'celex': leg.get('celex', ''),
                        'date': leg.get('date', ''),
                    }
                })

        # Add procedures
        if hasattr(context_data, 'procedure_details'):
            for proc in context_data.procedure_details:
                citations.append({
                    'type': 'procedure',
                    'title': proc.get('title', ''),
                    'url': proc.get('url', ''),
                    'metadata': {
                        'reference': proc.get('reference', ''),
                        'stage': proc.get('stage', ''),
                    }
                })

        # Add MEP profiles
        if hasattr(context_data, 'mep_profiles'):
            for mep in context_data.mep_profiles:
                citations.append({
                    'type': 'mep',
                    'title': mep.get('name', ''),
                    'url': mep.get('profile_url', ''),
                    'metadata': {
                        'country': mep.get('country', ''),
                        'group': mep.get('political_group', ''),
                    }
                })

        # Add committee info
        if hasattr(context_data, 'committee_info'):
            for committee in context_data.committee_info:
                citations.append({
                    'type': 'committee',
                    'title': f"{committee.get('name', '')} ({committee.get('code', '')})",
                    'url': committee.get('url', ''),
                    'metadata': {
                        'members': str(committee.get('member_count', 0)),
                    }
                })

        # Add sequential id fields so frontend can match [1], [2] markers
        for i, citation in enumerate(citations):
            citation['id'] = i + 1

        return citations

    async def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about current model and fallback providers.

        Returns:
            Model information dict
        """
        info = {
            'model': self.model,
            'temperature': self.temperature,
            'max_output_tokens': self.max_output_tokens,
            'max_context_tokens': self.MAX_CONTEXT_TOKENS,
            'provider': 'Anthropic',
            'capabilities': [
                'EU legislative knowledge',
                'Source citations',
                'Context injection',
                'Streaming responses',
                'Conversation history'
            ]
        }

        # Add fallback chain info
        if self.use_fallback and self.multi_provider:
            info['fallback_enabled'] = True
            info['fallback_chain'] = self.multi_provider.available_providers
            info['provider_status'] = self.multi_provider.get_status()
        else:
            info['fallback_enabled'] = False

        return info

    async def estimate_cost(
        self,
        user_message: str,
        conversation_history: Optional[List[ChatMessage]] = None,
        use_context: bool = True
    ) -> Dict[str, float]:
        """
        Estimate API cost for a query.

        Args:
            user_message: User message
            conversation_history: Previous messages
            use_context: Whether context will be included

        Returns:
            Cost estimate:
            {
                'input_tokens': 1000,
                'output_tokens': 500,
                'cost_usd': 0.015
            }
        """
        # Rough token estimation (1 token ≈ 4 characters)
        message_tokens = len(user_message) // 4

        history_tokens = 0
        if conversation_history:
            history_tokens = sum(len(msg.content) for msg in conversation_history) // 4

        context_tokens = 0
        if use_context:
            # Average context size
            context_tokens = 2000

        input_tokens = message_tokens + history_tokens + context_tokens
        output_tokens = self.max_output_tokens

        # Claude pricing (approximate)
        # Sonnet: $3/M input, $15/M output
        # Opus: $15/M input, $75/M output
        if 'sonnet' in self.model.lower():
            input_cost_per_million = 3.0
            output_cost_per_million = 15.0
        else:  # Opus
            input_cost_per_million = 15.0
            output_cost_per_million = 75.0

        input_cost = (input_tokens / 1_000_000) * input_cost_per_million
        output_cost = (output_tokens / 1_000_000) * output_cost_per_million
        total_cost = input_cost + output_cost

        return {
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'total_tokens': input_tokens + output_tokens,
            'cost_usd': round(total_cost, 4)
        }

    async def _load_documents(self, document_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Load documents from storage and format for Claude API.

        For PDFs > 100 pages: Extract text using pdfminer.six
        For PDFs <= 100 pages: Send as native PDF via base64
        For other formats: Send as text

        Args:
            document_ids: List of document IDs to load

        Returns:
            List of document content blocks for Claude
        """
        from services.storage.document_storage import get_document_storage
        from services.pdf_processor import get_pdf_processor

        documents = []
        storage = get_document_storage()
        pdf_processor = get_pdf_processor()

        for doc_id in document_ids:
            try:
                # Get document metadata
                doc_meta = storage.get_document(doc_id)
                if not doc_meta:
                    logger.warning(f"Document not found: {doc_id}")
                    continue

                # Read file content
                file_path = doc_meta.get('original_file_path')
                if not file_path or not os.path.exists(file_path):
                    logger.warning(f"Document file not found: {doc_id}")
                    continue

                content_type = doc_meta.get('content_type', 'application/pdf')
                filename = doc_meta.get('filename', 'document')

                if content_type == 'application/pdf':
                    # Always extract text from PDFs for multi-provider compatibility
                    # (Mistral, OpenAI, Gemini only support text content blocks)
                    result = pdf_processor.extract_text(file_path)

                    if result['success']:
                        text = result['text']
                        page_count = result['page_count']
                        documents.append({
                            'type': 'text',
                            'text': f"**Document: {filename}** ({page_count} pages)\n\n{text[:200000]}"
                        })
                        logger.info(f"Extracted {len(text)} chars from PDF: {filename} ({page_count} pages)")
                    else:
                        logger.error(f"Failed to extract text from PDF: {result.get('error')}")
                        documents.append({
                            'type': 'text',
                            'text': f"**Document: {filename}** - Error: Could not extract text from this PDF"
                        })

                elif content_type in ['application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/msword']:
                    # For DOCX, extract text from processed content
                    if doc_meta.get('has_processed_content'):
                        processed = doc_meta['processed_content']
                        text = processed.get('text', '')
                        if text:
                            documents.append({
                                'type': 'text',
                                'text': f"**Document: {filename}**\n\n{text[:100000]}"
                            })
                            logger.info(f"Loaded DOCX as text: {filename} ({len(text)} chars)")
                    else:
                        # Fallback: try processing DOCX on the fly
                        try:
                            from services.document_processing.docx_processor import get_docx_processor
                            docx_proc = get_docx_processor()
                            with open(file_path, 'rb') as f:
                                docx_bytes = f.read()
                            result = docx_proc.process_docx_from_bytes(docx_bytes, filename=filename)
                            text = result.get('text', '') if result else ''
                            if text:
                                documents.append({
                                    'type': 'text',
                                    'text': f"**Document: {filename}**\n\n{text[:100000]}"
                                })
                                logger.info(f"Loaded DOCX via fallback processing: {filename} ({len(text)} chars)")
                        except Exception as docx_err:
                            logger.error(f"DOCX fallback processing failed: {docx_err}")

                elif content_type.startswith('text/'):
                    # Text files - send as text block
                    with open(file_path, 'rb') as f:
                        file_content = f.read()
                    text_content = file_content.decode('utf-8', errors='ignore')
                    documents.append({
                        'type': 'text',
                        'text': f"**Document: {filename}**\n\n{text_content[:100000]}"
                    })
                    logger.info(f"Loaded text document: {filename} ({len(text_content)} chars)")

            except Exception as e:
                logger.error(f"Failed to load document {doc_id}: {str(e)}")
                continue

        return documents

    def _detect_knowledge_gap(self, response: str) -> Optional[Dict[str, Any]]:
        """
        Detect if AI response indicates a knowledge gap (uncertainty/inability to answer).

        Args:
            response: AI response text

        Returns:
            Gap info dict if detected, None otherwise
        """
        # Patterns indicating knowledge gaps (case-insensitive)
        uncertainty_patterns = [
            r"I don'?t have (?:the )?specific",
            r"I don'?t have (?:that )?information",
            r"I cannot find",
            r"I couldn'?t find",
            r"not (?:available )?in my (?:current )?(?:context|sources|data)",
            r"I recommend checking EUR-Lex",
            r"check (?:the )?official (?:text|source)",
            r"I'?m not (?:able|certain)",
            r"I don'?t have verified",
            r"my (?:current )?sources don'?t",
            r"outside (?:of )?my (?:current )?knowledge",
            r"I'?m unable to (?:confirm|verify)",
            r"this information (?:is|may be) outdated",
        ]

        response_lower = response.lower()

        for pattern in uncertainty_patterns:
            if re.search(pattern, response_lower):
                # Try to classify what type of data is missing
                missing_type = self._classify_missing_data(response)
                return {
                    'detected': True,
                    'missing_data_type': missing_type,
                    'response_excerpt': response[:500]
                }

        return None

    def _classify_missing_data(self, response: str) -> str:
        """
        Classify what type of data is missing based on response content.

        Args:
            response: AI response text

        Returns:
            Missing data type string
        """
        response_lower = response.lower()

        # Check for specific data types mentioned
        if any(word in response_lower for word in ['fine', 'penalty', 'amount', 'euro', '€', 'million', 'billion']):
            return MissingDataType.STATISTIC
        elif any(word in response_lower for word in ['deadline', 'date', 'when', 'timeline']):
            return MissingDataType.DATE
        elif any(word in response_lower for word in ['regulation', 'directive', 'act', 'law', 'celex']):
            return MissingDataType.LEGISLATION
        elif any(word in response_lower for word in ['procedure', 'process', 'stage', 'status']):
            return MissingDataType.PROCEDURE
        elif any(word in response_lower for word in ['mep', 'member', 'rapporteur', 'shadow']):
            return MissingDataType.MEP
        elif any(word in response_lower for word in ['document', 'report', 'briefing', 'text']):
            return MissingDataType.DOCUMENT

        return MissingDataType.UNKNOWN

    async def _log_knowledge_gap(
        self,
        query: str,
        gap_info: Dict[str, Any],
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> None:
        """
        Log a detected knowledge gap to the database for later analysis.

        Args:
            query: Original user query
            gap_info: Gap detection info from _detect_knowledge_gap
            user_id: Optional user ID
            conversation_id: Optional conversation ID
        """
        try:
            # Run database operation in thread pool to avoid blocking
            import asyncio
            from functools import partial

            def _save_gap():
                db = SessionLocal()
                try:
                    # Try to detect policy area from query
                    policy_area = self._detect_policy_area(query)

                    gap = KnowledgeGap(
                        query=query,
                        detected_topic=query[:200],  # Truncate for topic field
                        policy_area=policy_area,
                        missing_data_type=gap_info.get('missing_data_type', MissingDataType.UNKNOWN),
                        user_id=user_id if user_id else None,
                        conversation_id=conversation_id,
                        ai_response_excerpt=gap_info.get('response_excerpt', '')[:500]
                    )
                    db.add(gap)
                    db.commit()
                    logger.info(f"Logged knowledge gap: {gap.id} - {gap.missing_data_type}")
                except Exception as e:
                    logger.error(f"Failed to log knowledge gap: {e}")
                    db.rollback()
                finally:
                    db.close()

            # Run in executor to avoid blocking async context
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _save_gap)

        except Exception as e:
            logger.error(f"Error in _log_knowledge_gap: {e}")

    def _detect_policy_area(self, query: str) -> Optional[str]:
        """
        Try to detect EU policy area from query text.

        Args:
            query: User query

        Returns:
            Policy area string or None
        """
        query_lower = query.lower()

        # Policy area keywords mapping
        policy_keywords = {
            'Digital': ['digital', 'ai act', 'dsa', 'dma', 'gdpr', 'data', 'cyber', 'platform'],
            'Environment': ['environment', 'climate', 'green deal', 'emissions', 'carbon', 'cbam', 'sustainability'],
            'Trade': ['trade', 'tariff', 'customs', 'export', 'import', 'wto'],
            'Agriculture': ['agriculture', 'cap', 'farming', 'food', 'rural'],
            'Finance': ['finance', 'banking', 'euro', 'ecb', 'monetary', 'fiscal'],
            'Energy': ['energy', 'electricity', 'gas', 'renewable', 'nuclear'],
            'Transport': ['transport', 'aviation', 'maritime', 'rail', 'mobility'],
            'Health': ['health', 'pharmaceutical', 'ema', 'medicine', 'vaccine'],
            'Justice': ['justice', 'asylum', 'migration', 'border', 'schengen', 'police'],
            'Internal Market': ['internal market', 'single market', 'harmonisation', 'standardisation'],
        }

        for area, keywords in policy_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                return area

        return None

    def _extract_source_tiers(self, citations: List[Dict[str, Any]]) -> List[int]:
        """
        Extract source tiers from citations for analytics.

        Args:
            citations: List of citation dictionaries

        Returns:
            List of unique source tier integers
        """
        tiers = set()
        for citation in citations:
            tier = citation.get('source_tier')
            if tier:
                tiers.add(tier)
        return sorted(list(tiers))

    async def _log_analytics(
        self,
        user_id: Optional[str],
        provider: str,
        model: str,
        tokens_used: int,
        response_time_ms: float,
        search_time_ms: float,
        had_knowledge_gap: bool,
        knowledge_gap_type: Optional[str],
        source_tiers_used: List[int],
        citation_count: int,
        context_sources_count: int,
        query_length: int,
        response_length: int
    ) -> None:
        """
        Log analytics for monitoring dashboard (Phase E1).

        Args:
            Various metrics from chat response
        """
        try:
            def _save_analytics():
                db = SessionLocal()
                try:
                    analytics = ChatAnalytics(
                        user_id=user_id if user_id else None,
                        provider=provider,
                        model=model,
                        tokens_used=tokens_used,
                        response_time_ms=response_time_ms,
                        search_time_ms=search_time_ms,
                        had_knowledge_gap=had_knowledge_gap,
                        knowledge_gap_type=knowledge_gap_type,
                        source_tiers_used=source_tiers_used if source_tiers_used else None,
                        citation_count=citation_count,
                        context_sources_count=context_sources_count,
                        query_length=query_length,
                        response_length=response_length
                    )
                    db.add(analytics)
                    db.commit()
                    logger.debug(f"Logged analytics: {analytics.id}")
                except Exception as e:
                    logger.error(f"Failed to log analytics: {e}")
                    db.rollback()
                finally:
                    db.close()

            # Run in executor to avoid blocking async context
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _save_analytics)

        except Exception as e:
            logger.error(f"Error in _log_analytics: {e}")


# Global singleton
_ai_service: Optional[AIService] = None


def get_ai_service(
    api_key: Optional[str] = None,
    context_builder: Optional[ContextBuilder] = None,
    model: str = AIService.MODEL_SONNET
) -> AIService:
    """
    Get global AI service instance.

    Args:
        api_key: Anthropic API key (defaults to settings.ANTHROPIC_API_KEY)
        context_builder: Context builder instance
        model: Claude model to use

    Returns:
        AIService instance
    """
    global _ai_service

    if _ai_service is None:
        # Use settings API key if not provided
        if api_key is None:
            api_key = settings.ANTHROPIC_API_KEY

        _ai_service = AIService(
            api_key=api_key,
            context_builder=context_builder or get_context_builder(),
            model=model
        )

    return _ai_service
