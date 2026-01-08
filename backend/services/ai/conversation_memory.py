"""
Conversation Memory Service

Phase D3: Enhanced conversation memory with entity extraction and summarization.
Improves context continuity across long conversations.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ConversationMemory:
    """
    Structured memory for a conversation.

    Stores:
    - Extracted entities (MEPs, laws, dates, committees)
    - User preferences detected in conversation
    - Summary of older messages
    """
    conversation_id: str
    entities: Dict[str, Set[str]] = field(default_factory=lambda: {
        'meps': set(),
        'laws': set(),
        'committees': set(),
        'dates': set(),
        'policy_areas': set(),
        'celex_numbers': set()
    })
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    summary: Optional[str] = None
    message_count: int = 0
    last_updated: datetime = field(default_factory=datetime.now)


class ConversationMemoryService:
    """
    Service for managing conversation memory.

    Features:
    - Entity extraction from messages using regex patterns
    - Preference detection (language, detail level)
    - Conversation summarization for long chats
    """

    # Entity extraction patterns
    PATTERNS = {
        # CELEX numbers: 32024R1689, 32016R0679
        'celex_numbers': r'\b3\d{4}[A-Z]\d{4}\b',

        # MEP name patterns: First LAST or LAST, First
        'meps': r'\b[A-Z][a-z]+\s+[A-Z]{2,}(?:\s+[A-Z]{2,})?\b',

        # Committee codes: ENVI, ITRE, LIBE, JURI, etc.
        'committees': r'\b(?:AFET|DEVE|INTA|BUDG|CONT|ECON|EMPL|ENVI|ITRE|IMCO|TRAN|REGI|AGRI|PECH|CULT|JURI|LIBE|AFCO|FEMM|PETI)\b',

        # Dates: various formats
        'dates': r'\b(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2}|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})\b',

        # Law acronyms
        'laws': r'\b(?:GDPR|AI Act|DSA|DMA|NIS2?|CBAM|CSRD|CSDDD|ETS|MiCA|DORA|Data Act|Cyber Resilience Act|Digital Services Act|Digital Markets Act|Green Deal)\b',
    }

    # Policy area keywords
    POLICY_AREAS = {
        'Digital': ['digital', 'ai', 'data', 'cyber', 'platform', 'algorithm'],
        'Environment': ['climate', 'green', 'emissions', 'carbon', 'sustainability', 'biodiversity'],
        'Trade': ['trade', 'tariff', 'customs', 'export', 'import'],
        'Finance': ['finance', 'banking', 'euro', 'monetary', 'fiscal'],
        'Energy': ['energy', 'electricity', 'renewable', 'nuclear', 'gas'],
        'Health': ['health', 'pharmaceutical', 'medicine', 'vaccine'],
        'Agriculture': ['agriculture', 'farming', 'food', 'rural', 'cap'],
        'Transport': ['transport', 'aviation', 'maritime', 'rail'],
        'Justice': ['justice', 'asylum', 'migration', 'border', 'police'],
    }

    # User preference patterns
    PREFERENCE_PATTERNS = {
        'wants_detail': [
            r'(?:give me|provide|explain|elaborate|more) (?:more )?(?:detail|information|context)',
            r'(?:in|with) (?:more )?detail',
            r'(?:comprehensive|thorough|detailed) (?:answer|explanation|analysis)',
        ],
        'wants_summary': [
            r'(?:brief|short|quick|concise) (?:answer|summary|overview)',
            r'(?:summarize|summarise|tldr|tl;dr)',
            r'(?:in|keep it) (?:brief|short|simple)',
        ],
        'language_preference': [
            r'(?:respond|answer|reply) in (\w+)',
            r'(?:in|use|speak) (\w+) (?:please|language)?',
        ],
    }

    def __init__(self):
        self._memories: Dict[str, ConversationMemory] = {}

    def get_memory(self, conversation_id: str) -> ConversationMemory:
        """Get or create memory for a conversation."""
        if conversation_id not in self._memories:
            self._memories[conversation_id] = ConversationMemory(
                conversation_id=conversation_id
            )
        return self._memories[conversation_id]

    def process_message(
        self,
        conversation_id: str,
        message: str,
        role: str = 'user'
    ) -> ConversationMemory:
        """
        Process a message and update conversation memory.

        Args:
            conversation_id: The conversation identifier
            message: The message text
            role: 'user' or 'assistant'

        Returns:
            Updated ConversationMemory
        """
        memory = self.get_memory(conversation_id)
        memory.message_count += 1
        memory.last_updated = datetime.now()

        # Extract entities
        self._extract_entities(message, memory)

        # Detect user preferences (only from user messages)
        if role == 'user':
            self._detect_preferences(message, memory)

        # Detect policy areas
        self._detect_policy_areas(message, memory)

        logger.debug(
            f"Processed message for {conversation_id}: "
            f"{len(memory.entities['meps'])} MEPs, "
            f"{len(memory.entities['laws'])} laws, "
            f"{len(memory.entities['celex_numbers'])} CELEX numbers"
        )

        return memory

    def _extract_entities(self, text: str, memory: ConversationMemory) -> None:
        """Extract entities from text and add to memory."""
        for entity_type, pattern in self.PATTERNS.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Normalize: uppercase for codes, title case for names
                if entity_type in ['committees', 'celex_numbers']:
                    memory.entities[entity_type].add(match.upper())
                elif entity_type == 'meps':
                    # Title case for MEP names
                    memory.entities[entity_type].add(match.title())
                else:
                    memory.entities[entity_type].add(match)

    def _detect_preferences(self, text: str, memory: ConversationMemory) -> None:
        """Detect user preferences from message text."""
        text_lower = text.lower()

        # Check for detail preference
        for pattern in self.PREFERENCE_PATTERNS['wants_detail']:
            if re.search(pattern, text_lower):
                memory.user_preferences['detail_level'] = 'high'
                break

        for pattern in self.PREFERENCE_PATTERNS['wants_summary']:
            if re.search(pattern, text_lower):
                memory.user_preferences['detail_level'] = 'low'
                break

        # Check for language preference
        for pattern in self.PREFERENCE_PATTERNS['language_preference']:
            match = re.search(pattern, text_lower)
            if match:
                lang = match.group(1).capitalize()
                if lang in ['English', 'French', 'German', 'Spanish', 'Italian',
                           'Dutch', 'Polish', 'Portuguese', 'Greek', 'Swedish']:
                    memory.user_preferences['language'] = lang
                break

    def _detect_policy_areas(self, text: str, memory: ConversationMemory) -> None:
        """Detect policy areas mentioned in text."""
        text_lower = text.lower()

        for area, keywords in self.POLICY_AREAS.items():
            if any(keyword in text_lower for keyword in keywords):
                memory.entities['policy_areas'].add(area)

    def get_context_enhancement(self, conversation_id: str) -> str:
        """
        Get context enhancement string for AI prompt.

        Returns a formatted string with extracted entities and preferences
        to be injected into the system prompt or context.
        """
        memory = self.get_memory(conversation_id)

        if memory.message_count == 0:
            return ""

        parts = []

        # Add entity context
        if memory.entities['meps']:
            meps_list = ', '.join(list(memory.entities['meps'])[:5])
            parts.append(f"MEPs mentioned: {meps_list}")

        if memory.entities['laws']:
            laws_list = ', '.join(list(memory.entities['laws'])[:5])
            parts.append(f"Laws/regulations discussed: {laws_list}")

        if memory.entities['celex_numbers']:
            celex_list = ', '.join(list(memory.entities['celex_numbers'])[:3])
            parts.append(f"CELEX references: {celex_list}")

        if memory.entities['committees']:
            committees_list = ', '.join(memory.entities['committees'])
            parts.append(f"EP Committees: {committees_list}")

        if memory.entities['policy_areas']:
            areas_list = ', '.join(memory.entities['policy_areas'])
            parts.append(f"Policy areas: {areas_list}")

        # Add preference context
        if memory.user_preferences.get('detail_level'):
            level = memory.user_preferences['detail_level']
            if level == 'high':
                parts.append("User preference: detailed explanations")
            else:
                parts.append("User preference: brief/concise answers")

        if memory.user_preferences.get('language'):
            parts.append(f"User language preference: {memory.user_preferences['language']}")

        if not parts:
            return ""

        return "CONVERSATION CONTEXT:\n" + "\n".join(f"- {p}" for p in parts)

    def get_entities_for_search(self, conversation_id: str) -> Dict[str, List[str]]:
        """
        Get extracted entities for search enhancement.

        Returns entities in a format suitable for boosting search queries.
        """
        memory = self.get_memory(conversation_id)

        return {
            'meps': list(memory.entities['meps']),
            'laws': list(memory.entities['laws']),
            'celex_numbers': list(memory.entities['celex_numbers']),
            'committees': list(memory.entities['committees']),
            'policy_areas': list(memory.entities['policy_areas']),
        }

    def summarize_old_messages(
        self,
        conversation_id: str,
        messages: List[Dict[str, str]],
        keep_recent: int = 6
    ) -> Dict[str, Any]:
        """
        Prepare messages for context, summarizing older ones.

        For conversations longer than keep_recent messages,
        returns recent messages plus a summary of older ones.

        Args:
            conversation_id: The conversation ID
            messages: Full list of messages
            keep_recent: Number of recent messages to keep in full

        Returns:
            Dict with 'summary' (if any) and 'recent_messages'
        """
        if len(messages) <= keep_recent:
            return {
                'summary': None,
                'recent_messages': messages
            }

        old_messages = messages[:-keep_recent]
        recent_messages = messages[-keep_recent:]

        # Create a simple summary of old messages
        # (In production, you might use an LLM for this)
        topics_discussed = set()
        questions_asked = []

        for msg in old_messages:
            content = msg.get('content', '')

            # Extract topics from user questions
            if msg.get('role') == 'user':
                # Simple extraction of main topics
                if len(content) < 200:
                    questions_asked.append(content[:100])

            # Extract entities from all messages
            self.process_message(conversation_id, content, msg.get('role', 'user'))

        memory = self.get_memory(conversation_id)

        summary_parts = [
            f"Earlier in this conversation ({len(old_messages)} messages):"
        ]

        if memory.entities['laws']:
            summary_parts.append(f"- Discussed: {', '.join(list(memory.entities['laws'])[:3])}")

        if memory.entities['policy_areas']:
            summary_parts.append(f"- Topics: {', '.join(memory.entities['policy_areas'])}")

        if questions_asked:
            summary_parts.append(f"- User asked about: {'; '.join(questions_asked[:3])}")

        summary = '\n'.join(summary_parts)

        return {
            'summary': summary,
            'recent_messages': recent_messages
        }

    def clear_memory(self, conversation_id: str) -> None:
        """Clear memory for a conversation."""
        if conversation_id in self._memories:
            del self._memories[conversation_id]


# Global singleton
_memory_service: Optional[ConversationMemoryService] = None


def get_conversation_memory_service() -> ConversationMemoryService:
    """Get global ConversationMemoryService instance."""
    global _memory_service
    if _memory_service is None:
        _memory_service = ConversationMemoryService()
    return _memory_service
