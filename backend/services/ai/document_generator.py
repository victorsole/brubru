"""
Document Generator Service

AI-powered generation of EU advocacy documents:
- Position Papers
- MEP Briefing Notes
- Talking Points

Priority #3: Position Paper Generator
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from core.config import settings
from schemas.document_generation import (
    GeneratePositionPaperRequest,
    GenerateMEPBriefingRequest,
    GenerateTalkingPointsRequest,
    GenerateResolutionRequest,
    GenerateEPQuestionRequest,
    GeneratedDocument,
    KeyAsk,
)
from services.ai.multi_provider_service import get_multi_provider_service

logger = logging.getLogger(__name__)


class DocumentGenerator:
    """
    AI-powered document generator for EU advocacy documents.

    Generates professional-quality position papers, MEP briefings,
    and talking points using Claude AI with EU-specific prompts.
    """

    # EU Advocacy Writing Style Guidelines
    EU_STYLE_GUIDELINES = """
WRITING STYLE FOR EU ADVOCACY DOCUMENTS:

Language:
- Use British English spelling (analyse, organisation, colour, programme)
- Formal but accessible tone
- Clear, concise sentences
- Avoid jargon or explain it when used

Structure:
- Clear section headings
- Numbered lists for recommendations
- Bullet points for supporting arguments
- Specific article/recital references where applicable

EU Conventions:
- Reference articles as "Article X" not "Art. X"
- Reference recitals as "Recital X"
- Use formal institutional names (European Commission, European Parliament)
- Include procedure references where known (e.g., 2021/0106(COD))

Tone Guidelines:
- CONSTRUCTIVE: Focus on improvement, acknowledge positives, propose solutions
- CRITICAL: Direct concerns, highlight problems, but remain professional
- TECHNICAL: Focus on legal/technical aspects, precise language
- DIPLOMATIC: Balanced, acknowledges multiple perspectives, seeks common ground

Quality Standards:
- Be specific, not vague ("Article 6(2) should be amended" not "changes are needed")
- Support arguments with evidence or examples
- Include clear, actionable recommendations
- Maintain professional credibility
"""

    POSITION_PAPER_PROMPT = """Generate a professional EU advocacy position paper.

ORGANISATION: {organisation_name}
ORGANISATION TYPE: {organisation_type}
ORGANISATION DESCRIPTION: {organisation_description}

LEGISLATION: {legislation_title}
PROCEDURE REFERENCE: {procedure_reference}
CELEX: {celex_number}

POSITION: {position}

KEY ASKS:
{key_asks_formatted}

SECTOR IMPACT: {sector_impact}
ADDITIONAL CONTEXT: {additional_context}

TONE: {tone}

{style_guidelines}

Generate a complete position paper with the following structure:

1. **EXECUTIVE SUMMARY** (2-3 paragraphs)
   - Brief description of legislation
   - Overall position statement
   - Summary of key recommendations

2. **ABOUT {organisation_name}**
   - Brief description of the organisation
   - Relevance to this policy area

3. **CONTEXT AND BACKGROUND**
   - Why this legislation matters
   - Current status in legislative process
   - Key provisions being addressed

4. **OVERALL POSITION**
   - Clear statement of position
   - Key points summary

5. **DETAILED ANALYSIS AND RECOMMENDATIONS**
   For each key ask:
   - Current text analysis
   - Our assessment (concerns or support)
   - Specific recommendation
   - Proposed amendment text (if applicable)
   - Rationale and evidence

6. **IMPACT ASSESSMENT**
   - Economic impact on sector
   - Operational implications
   - Broader EU implications

7. **CONCLUSION**
   - Restate main position
   - Call to action

8. **CONTACT INFORMATION**
   - Placeholder for organisation contact details

Format the output in clean Markdown with proper headings.
Include specific article references where possible.
Make recommendations concrete and actionable.
"""

    MEP_BRIEFING_PROMPT = """Generate a professional MEP briefing note for an EU advocacy meeting.

TARGET MEP: {mep_name}
POLITICAL GROUP: {political_group}
NATIONALITY: {nationality}
COMMITTEE: {committee}

LEGISLATION: {legislation_title}
PROCEDURE REFERENCE: {procedure_reference}

POSITION: {position}
THE ASK: {the_ask}
VOTING RECOMMENDATION: {voting_recommendation}

KEY POINTS:
{key_points_formatted}

ORGANISATION: {organisation_name}
CONTACT: {contact_name} ({contact_email})

MEP'S KNOWN PRIORITIES: {mep_priorities}
NATIONAL ANGLE: {national_angle}

{style_guidelines}

Generate a concise, impactful MEP briefing note with:

1. **KEY MESSAGES** (30 seconds read)
   - THE ASK: One clear sentence of what you want
   - WHY IT MATTERS: One sentence on impact
   - POSITION IN ONE LINE: Concise statement

2. **EXECUTIVE SUMMARY** (2 minutes read)
   - The issue (2-3 sentences)
   - What's at stake (for citizens, businesses, MEP's constituency)
   - Our recommendation
   - Supporting evidence (2-3 data points)

3. **BACKGROUND AND CONTEXT**
   - Legislative procedure status
   - Why this file matters
   - Current stage and upcoming milestones

4. **DETAILED POSITION**
   - What we support (with rationale)
   - What we oppose (with alternatives)

5. **SPECIFIC AMENDMENT PROPOSALS** (if applicable)
   - Current text
   - Proposed amendment
   - Justification

6. **ARGUMENTS TAILORED TO {mep_name}**
   - Political group priorities
   - National interest angle
   - Personal focus areas

7. **KEY FACTS AND FIGURES**
   - Compelling data points
   - Statistics supporting position

8. **Q&A PREPARATION**
   - Likely questions and responses

9. **WHY YOUR VOTE MATTERS**
   - Personalised message about their influence

10. **NEXT STEPS**
    - Immediate action requested
    - Timeline
    - Contact for follow-up

Keep it concise - MEPs have limited time.
Make the ask crystal clear.
Tailor arguments to their known priorities.
"""

    TALKING_POINTS_PROMPT = """Generate professional talking points for an EU advocacy meeting.

MEETING WITH: {meeting_with}
INSTITUTION: {meeting_institution}
PURPOSE: {meeting_purpose}

TOPIC: {topic}
PROCEDURE REFERENCE: {procedure_reference}

KEY MESSAGES:
{key_messages_formatted}

KEY ASKS:
{key_asks_formatted}

ORGANISATION: {organisation_name}

TOPICS TO AVOID: {topics_to_avoid}
ANTICIPATED QUESTIONS: {anticipated_questions}

{style_guidelines}

Generate structured talking points with:

1. **QUICK REFERENCE CARD** (one-page summary)
   - TOP 3 MESSAGES (brief bullet points)
   - TOP 3 ASKS (specific requests)
   - DON'T FORGET (critical reminders)
   - RED LINES (non-negotiable positions)
   - LIKELY DIFFICULT QUESTION + RESPONSE

2. **MEETING OBJECTIVES**
   - Primary objective
   - Secondary objectives
   - Success criteria

3. **CORE MESSAGES**
   For each key message:
   - Full message (2-3 sentences)
   - Supporting points
   - Why this matters to them

4. **SPECIFIC ASKS**
   For each ask:
   - What we want (precise description)
   - Why (rationale)
   - How they can help
   - If they say no (fallback)

5. **Q&A PREPARATION**
   For anticipated questions:
   - Recommended response
   - Key points to include
   - What NOT to say

6. **ARGUMENTS AND COUNTER-ARGUMENTS**
   - Our key arguments with evidence
   - Their likely counter-arguments
   - Our rebuttals

7. **DOS AND DON'TS**
   - Specific guidance for this meeting
   - Topics to avoid
   - How to handle sensitive issues

8. **FOLLOW-UP ACTIONS**
   - Immediate follow-up
   - Materials to send
   - Next engagement

Keep talking points concise and memorable.
Make messages punchy and impactful.
Prepare for pushback.
"""

    RESOLUTION_PROMPT = """Generate a European Parliament Resolution in the exact official EP format.

TOPIC/TITLE: {topic}

CONTEXT FOR RECITALS: {context_description}

KEY DEMANDS:
{key_demands_formatted}

ADDITIONAL REFERENCES TO CITE: {additional_references}

{style_guidelines}

You MUST produce the resolution in the following EXACT structure and formatting:

---

**European Parliament resolution on {topic}**

**The European Parliament,**

-- having regard to [relevant Treaty articles, e.g., Articles 2 and 3 of the Treaty on European Union],

-- having regard to [relevant existing EU legislation, e.g., Regulation (EU) 2024/... on ...],

-- having regard to [previous EP resolutions on the subject, with dates],

-- having regard to [relevant Commission communications, proposals, or reports],

-- having regard to [relevant international instruments, UN resolutions, or conventions if applicable],

-- having regard to Rule 132(2) of its Rules of Procedure,

[Generate 5-10 "having regard to" references. Use real, plausible treaty articles and legislation names relevant to the topic. Each starts with a lowercase "-- having regard to" and ends with a comma.]

A.  whereas [first contextual statement establishing the situation];

B.  whereas [second contextual statement with relevant facts or data];

C.  whereas [third contextual statement linking to EU values or competences];

[Generate 5-10 lettered recitals (A. through J. approximately). Each starts with "whereas" (lowercase) and ends with a semicolon. They establish the factual and legal context for the resolution. Base them on the context_description provided.]

1.  Calls on [the Commission/Council/Member States] to [specific action from key demands];

2.  Urges [institution] to [specific action];

3.  Condemns [if applicable, strong negative statement];

4.  Expresses [concern/solidarity/support] regarding [issue];

5.  Welcomes [positive development if any];

6.  Stresses that [important principle];

7.  Requests [the Commission] to [specific technical/legislative request];

8.  Emphasises [key policy point];

[Generate numbered resolution points based on the key_demands provided. Each point MUST start with an active verb in the third person singular: Calls, Urges, Condemns, Expresses, Welcomes, Stresses, Requests, Emphasises, Proposes, Underlines, Recalls, Notes, Considers, Insists, Invites, Deplores, Regrets, Recommends, Reiterates, Demands, Takes note of. End each with a semicolon except the last two.]

[Second-to-last point]:  Instructs its President to forward this resolution to the Council, the Commission[, the Vice-President of the Commission / High Representative of the Union for Foreign Affairs and Security Policy][, the governments and parliaments of the Member States][, and any other relevant addressees].

CRITICAL FORMATTING RULES:
1. "Having regard to" lines start with "-- having regard to" (two dashes, space, lowercase h)
2. Recital letters are uppercase followed by a period and TWO spaces: "A.  whereas"
3. Resolution points are numbers followed by a period and TWO spaces: "1.  Calls"
4. "whereas" is ALWAYS lowercase at the start of recitals
5. Active verbs at the start of resolution points are ALWAYS capitalised
6. Each "having regard to" line ends with a COMMA
7. Each recital ends with a SEMICOLON
8. Each resolution point ends with a SEMICOLON except the final point which ends with a PERIOD
9. The final point about forwarding to institutions always ends with a period
10. Do NOT use markdown headers (##) within the resolution body -- this is a single continuous document
11. Use markdown bold (**) only for the title and "The European Parliament," opening
12. Generate at least as many resolution points as there are key demands, plus 2-3 standard procedural points
"""

    EP_QUESTION_PROMPT = """Generate a European Parliament written parliamentary question in the exact official EP format.

TOPIC/TITLE: {topic}
ADDRESSEE: {addressee}
QUESTION TYPE: {question_type}
NUMBER OF SUB-QUESTIONS: {num_sub_questions}
TONE: {tone}

CONTEXT AND EVIDENCE PROVIDED BY THE USER:
{context_description}

LEGISLATION REFERENCES TO CITE:
{legislation_references}

EVIDENCE SOURCES:
{sources}

{style_guidelines}

STRUCTURAL RULES (derived from analysis of real EP written questions):

1. TITLE: A descriptive headline, maximum 200 characters. Formal and specific, never vague.

2. HEADER BLOCK (generate this exactly):
   "Question for written answer {ref_prefix}-DRAFT-2026-XXX"
   "to the {addressee_full}"
   "Rule 144"

3. CONTEXT/INTRODUCTION (the bulk of the question):
   - Write 2-4 paragraphs of factual background
   - Lead with evidence: facts, statistics, audit findings, news reports, court rulings
   - Anchor in EU legislation: cite specific Regulations, Directives, Treaty articles
   - Use footnoted references marked [1], [2], [3] etc.
   - The ratio should be approximately 80% context, 20% question
   - Total context section: 200-400 words

4. BRIDGE PHRASE: After the context paragraphs, write one of these transitions:
   - "In the light of the above:"
   - "With the above in mind:"
   - "In connection with the above:"
   - "In view of the above:"

5. SUB-QUESTIONS: Generate exactly {num_sub_questions} numbered sub-questions.
   - Each must be direct, specific, and demand a concrete answer
   - Each should be 1-2 sentences
   - They must be answerable by the Commission with facts or commitments
   - Good patterns: "Can the Commission clarify...", "What steps does the Commission intend to take...",
     "Does the Commission consider that...", "Is the Commission aware of...", "What assessment has the Commission made of..."

6. FOOTNOTES: List all sources as numbered footnotes at the end:
   [1] Description or URL
   [2] Description or URL

REGISTER AND TONE:
- Formal institutional voice, third-person perspective
- Politically loaded but factual: "raises serious concerns", "significant security risk"
- Never "I think" -- always "the above raises concerns regarding..."
- British English spelling (analyse, organisation, programme)

TONE VARIANTS:
- ASSERTIVE: Direct pressure, strong framing ("raises serious concerns", "undermines", "violates")
- DIPLOMATIC: Measured but probing ("it would be helpful to understand", "the Commission may wish to consider")
- TECHNICAL: Focus on legal/procedural precision ("pursuant to Article X", "in accordance with")

OUTPUT FORMAT:
Produce the question in clean markdown. Do NOT use ## headers within the question body.
Use **bold** for the title and header block only.
The output should look like a real EP written question that could be submitted.

EXAMPLE OF CORRECT FORMAT:

**Security risks associated with flush car door handles**

Question for written answer P-DRAFT-2026-XXX
to the Commission
Rule 144

There has been a significant increase in flush door handles built into the body of vehicles over the past 10 years. While this feature may improve aesthetics and aerodynamics, it nevertheless raises safety concerns. These mechanisms often rely upon an electrical system and may jam if there is a power failure or malfunction after an impact, making it difficult for passengers to escape the vehicle or for emergency services to intervene[1].

Several regulatory initiatives have emerged worldwide as of late. China will make it mandatory for all vehicles to have a mechanical door release from 1 January 2027. In the US, a legislative proposal entitled the 'SAFE Exit Act' was submitted to Congress that would require manufacturers to fit all vehicles with manual door handles accessible in all circumstances.

In the light of the above:

1. Is the Commission aware of the safety risks associated with flush car door handles, and has it carried out or commissioned any assessment of the risks posed by these mechanisms in the event of power failure or collision?

2. Does the Commission intend to propose legislative measures to require that all vehicles sold in the EU be equipped with a mechanical door release system accessible in all circumstances?

---

[1] News report on vehicle safety incidents, 2025

NOW GENERATE THE QUESTION BASED ON THE USER'S INPUT ABOVE.
"""

    def __init__(
        self,
        max_tokens: int = 4000,
        temperature: float = 0.4
    ):
        """
        Initialize Document Generator.

        Uses MultiProviderService for resilient AI generation with fallback chain.

        Args:
            max_tokens: Maximum response length
            temperature: Sampling temperature
        """
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.provider_service = get_multi_provider_service()

        logger.info(f"Initialized Document Generator (multi-provider: {self.provider_service.primary_provider})")

    async def generate_position_paper(
        self,
        request: GeneratePositionPaperRequest,
        legislative_context: Optional[Dict[str, Any]] = None
    ) -> GeneratedDocument:
        """
        Generate a position paper.

        Args:
            request: Position paper generation request
            legislative_context: Optional additional context from legislative tracker

        Returns:
            Generated document
        """
        logger.info(f"Generating position paper for: {request.legislation_title}")

        # Format key asks
        key_asks_formatted = "\n".join([
            f"- {i+1}. {ask.summary}"
            + (f"\n     Detail: {ask.detail}" if ask.detail else "")
            + (f"\n     Article: {ask.article_reference}" if ask.article_reference else "")
            for i, ask in enumerate(request.key_asks)
        ])

        # Enrich with legal framework from 28K+ law database
        legal_framework_text = ""
        try:
            from core.database import SessionLocal
            from services.eu_law_search import EULawSearchService

            db = SessionLocal()
            try:
                search = EULawSearchService(db)
                framework_laws = search.get_legal_framework(
                    policy_area="",  # Don't filter by area, let TSVECTOR rank
                    keywords=request.legislation_title,
                    limit=5,
                )
                if framework_laws:
                    legal_framework_text = "\n\nRELEVANT EU LEGAL FRAMEWORK (from Brubru's database of 28,505 laws):\n"
                    for law in framework_laws:
                        celex = law.get('celex', 'N/A')
                        legal_framework_text += f"- {law.get('title', 'Unknown')} (CELEX: {celex}, {law.get('doc_type', '')}, {law.get('date', 'N/A')})\n"
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Could not fetch legal framework: {e}")

        # Build prompt
        prompt = self.POSITION_PAPER_PROMPT.format(
            organisation_name=request.organisation_name,
            organisation_type=request.organisation_type.replace("_", " ").title(),
            organisation_description=request.organisation_description or "Not provided",
            legislation_title=request.legislation_title,
            procedure_reference=request.procedure_reference or "Not specified",
            celex_number=request.celex_number or "Not specified",
            position=request.position.replace("_", " ").title(),
            key_asks_formatted=key_asks_formatted,
            sector_impact=request.sector_impact or "Not specified",
            additional_context=(request.additional_context or "None") + legal_framework_text,
            tone=request.tone.upper(),
            style_guidelines=self.EU_STYLE_GUIDELINES
        )

        # Generate
        content = await self._generate(prompt)

        # Parse sections
        sections = self._parse_sections(content)

        return GeneratedDocument(
            document_type="position_paper",
            title=f"Position Paper: {request.legislation_title}",
            content=content,
            sections=sections,
            word_count=len(content.split()),
            language=request.language,
            legislative_context=legislative_context,
            editable_sections=list(sections.keys())
        )

    async def generate_mep_briefing(
        self,
        request: GenerateMEPBriefingRequest,
        legislative_context: Optional[Dict[str, Any]] = None
    ) -> GeneratedDocument:
        """
        Generate an MEP briefing note.

        Args:
            request: MEP briefing generation request
            legislative_context: Optional additional context

        Returns:
            Generated document
        """
        logger.info(f"Generating MEP briefing for: {request.mep_name} on {request.legislation_title}")

        key_points_formatted = "\n".join([f"- {point}" for point in request.key_points])

        # Enrich with legal framework from 28K+ law database
        legal_framework_text = ""
        try:
            from core.database import SessionLocal
            from services.eu_law_search import EULawSearchService

            db = SessionLocal()
            try:
                search = EULawSearchService(db)
                framework_laws = search.get_legal_framework(
                    policy_area="",  # Don't filter by area, let TSVECTOR rank
                    keywords=request.legislation_title,
                    limit=5,
                )
                if framework_laws:
                    legal_framework_text = "\n\nRELEVANT EU LEGAL FRAMEWORK (from Brubru's database of 28,505 laws):\n"
                    for law in framework_laws:
                        celex = law.get('celex', 'N/A')
                        legal_framework_text += f"- {law.get('title', 'Unknown')} (CELEX: {celex}, {law.get('doc_type', '')}, {law.get('date', 'N/A')})\n"
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Could not fetch legal framework: {e}")

        prompt = self.MEP_BRIEFING_PROMPT.format(
            mep_name=request.mep_name,
            political_group=request.political_group or "Not specified",
            nationality=request.nationality or "Not specified",
            committee=request.committee or "Not specified",
            legislation_title=request.legislation_title,
            procedure_reference=request.procedure_reference or "Not specified",
            position=request.position.replace("_", " ").title(),
            the_ask=request.the_ask,
            voting_recommendation=request.voting_recommendation or "Not specified",
            key_points_formatted=key_points_formatted,
            organisation_name=request.organisation_name,
            contact_name=request.contact_name or "[Contact Name]",
            contact_email=request.contact_email or "[contact@email.com]",
            mep_priorities=", ".join(request.mep_priorities) if request.mep_priorities else "Not specified",
            national_angle=request.national_angle or "Not specified",
            style_guidelines=self.EU_STYLE_GUIDELINES
        )

        # Append legal framework to the prompt
        if legal_framework_text:
            prompt += legal_framework_text

        content = await self._generate(prompt)
        sections = self._parse_sections(content)

        return GeneratedDocument(
            document_type="mep_briefing",
            title=f"MEP Briefing: {request.mep_name} - {request.legislation_title}",
            content=content,
            sections=sections,
            word_count=len(content.split()),
            language=request.language,
            legislative_context=legislative_context,
            editable_sections=list(sections.keys())
        )

    async def generate_talking_points(
        self,
        request: GenerateTalkingPointsRequest,
        legislative_context: Optional[Dict[str, Any]] = None
    ) -> GeneratedDocument:
        """
        Generate talking points for a meeting.

        Args:
            request: Talking points generation request
            legislative_context: Optional additional context

        Returns:
            Generated document
        """
        logger.info(f"Generating talking points for meeting with: {request.meeting_with}")

        key_messages_formatted = "\n".join([f"- {msg}" for msg in request.key_messages])
        key_asks_formatted = "\n".join([f"- {ask}" for ask in request.key_asks])

        prompt = self.TALKING_POINTS_PROMPT.format(
            meeting_with=request.meeting_with,
            meeting_institution=request.meeting_institution or "Not specified",
            meeting_purpose=request.meeting_purpose,
            topic=request.topic,
            procedure_reference=request.procedure_reference or "Not specified",
            key_messages_formatted=key_messages_formatted,
            key_asks_formatted=key_asks_formatted,
            organisation_name=request.organisation_name,
            topics_to_avoid=", ".join(request.topics_to_avoid) if request.topics_to_avoid else "None specified",
            anticipated_questions="\n".join([f"- {q}" for q in request.anticipated_questions]) if request.anticipated_questions else "None specified",
            style_guidelines=self.EU_STYLE_GUIDELINES
        )

        content = await self._generate(prompt)
        sections = self._parse_sections(content)

        return GeneratedDocument(
            document_type="talking_points",
            title=f"Talking Points: Meeting with {request.meeting_with}",
            content=content,
            sections=sections,
            word_count=len(content.split()),
            language=request.language,
            legislative_context=legislative_context,
            editable_sections=list(sections.keys())
        )

    async def generate_resolution(
        self,
        request: GenerateResolutionRequest,
        legislative_context: Optional[Dict[str, Any]] = None
    ) -> GeneratedDocument:
        """
        Generate a European Parliament Resolution draft.

        Args:
            request: Resolution generation request
            legislative_context: Optional additional context

        Returns:
            Generated document
        """
        logger.info(f"Generating EP resolution on: {request.topic}")

        key_demands_formatted = "\n".join([
            f"- {demand}" for demand in request.key_demands
        ]) if request.key_demands else "Infer appropriate demands and resolution points based on the topic and context"
        additional_references = "\n".join([
            f"- {ref}" for ref in request.additional_references
        ]) if request.additional_references else "Infer appropriate references based on the topic"

        prompt = self.RESOLUTION_PROMPT.format(
            topic=request.topic,
            context_description=request.context_description,
            key_demands_formatted=key_demands_formatted,
            additional_references=additional_references,
            style_guidelines=self.EU_STYLE_GUIDELINES
        )

        content = await self._generate(prompt)
        content = self._format_ep_resolution(content)
        sections = self._parse_sections(content)

        return GeneratedDocument(
            document_type="resolution",
            title=f"EP Resolution on {request.topic}",
            content=content,
            sections=sections,
            word_count=len(content.split()),
            language=request.language,
            legislative_context=legislative_context,
            editable_sections=list(sections.keys())
        )

    async def generate_ep_question(
        self,
        request: GenerateEPQuestionRequest,
        legislative_context: Optional[Dict[str, Any]] = None
    ) -> GeneratedDocument:
        """
        Generate a European Parliament written question.

        Args:
            request: EP question generation request
            legislative_context: Optional additional context

        Returns:
            Generated document
        """
        logger.info(f"Generating EP written question on: {request.topic}")

        # Map addressee codes to full names
        addressee_map = {
            "commission": "Commission",
            "council": "Council",
            "vp_hr": "Vice-President of the Commission / High Representative of the Union for Foreign Affairs and Security Policy",
        }
        ref_prefix_map = {"standard": "E", "priority": "P"}

        legislation_references = "\n".join([
            f"- {ref}" for ref in request.legislation_references
        ]) if request.legislation_references else "Infer appropriate EU legislation references from the context"

        sources = "\n".join([
            f"- {src}" for src in request.sources
        ]) if request.sources else "No specific sources provided -- infer from context"

        prompt = self.EP_QUESTION_PROMPT.format(
            topic=request.topic,
            addressee=request.addressee,
            addressee_full=addressee_map.get(request.addressee, "Commission"),
            question_type=request.question_type.title(),
            ref_prefix=ref_prefix_map.get(request.question_type, "E"),
            num_sub_questions=request.num_sub_questions,
            tone=request.tone.upper(),
            context_description=request.context_description,
            legislation_references=legislation_references,
            sources=sources,
            style_guidelines=self.EU_STYLE_GUIDELINES,
        )

        content = await self._generate(prompt)
        sections = self._parse_sections(content)

        return GeneratedDocument(
            document_type="ep_question",
            title=f"EP Question: {request.topic[:150]}",
            content=content,
            sections=sections,
            word_count=len(content.split()),
            language=request.language,
            legislative_context=legislative_context,
            editable_sections=list(sections.keys())
        )

    def _format_ep_resolution(self, text: str) -> str:
        """
        Post-process an EP resolution to fix formatting issues where the AI
        collapses line breaks between structural elements.

        Fixes:
        1. Each "-- having regard to" on its own line
        2. Each lettered recital (A. whereas, B. whereas) on its own line
        3. Operative paragraphs numbered (1., 2., 3., ...)
        4. Last operative paragraph ends with a period
        """
        import re

        # Step 1: Ensure each "-- having regard to" starts on a new line
        # Match cases where they're concatenated without line breaks
        text = re.sub(r',\s*--\s*having regard to', ',\n\n-- having regard to', text)

        # Step 2: Ensure each lettered recital starts on a new line
        # Match "A. whereas", "B. whereas", etc. that are not at line start
        text = re.sub(r';\s*([A-Z])\.\s{1,2}whereas', r';\n\n\1.  whereas', text)

        # Step 3: Number operative paragraphs if unnumbered
        # Detect operative verbs at the start of what should be numbered points
        operative_verbs = [
            'Calls', 'Urges', 'Condemns', 'Expresses', 'Welcomes', 'Stresses',
            'Requests', 'Emphasises', 'Proposes', 'Underlines', 'Recalls',
            'Notes', 'Considers', 'Insists', 'Invites', 'Deplores', 'Regrets',
            'Recommends', 'Reiterates', 'Demands', 'Takes note of', 'Instructs',
            'Highlights', 'Supports', 'Acknowledges', 'Affirms', 'Believes',
        ]
        verb_pattern = '|'.join(re.escape(v) for v in operative_verbs)

        # First, ensure line breaks before operative paragraphs
        text = re.sub(r';\s*(' + verb_pattern + r')', r';\n\n\1', text)

        # Check if operative paragraphs are already numbered
        lines = text.split('\n')
        has_numbering = any(re.match(r'^\d+\.\s{1,2}(' + verb_pattern + ')', line.strip()) for line in lines)

        if not has_numbering:
            # Number the operative paragraphs
            counter = 0
            new_lines = []
            for line in lines:
                stripped = line.strip()
                if re.match(r'^(' + verb_pattern + r')\b', stripped):
                    counter += 1
                    new_lines.append(f'{counter}.  {stripped}')
                else:
                    new_lines.append(line)
            text = '\n'.join(new_lines)

        # Step 4: Ensure last operative paragraph ends with a period
        # Find the last numbered point (the "Instructs its President" line)
        text = re.sub(r'(Instructs its President[^.;]*?)(Observatory|States|bodies|institutions)([.;]?\s*)$',
                      r'\1\2.', text, flags=re.MULTILINE)

        # Generic: ensure the very last line with a numbered point ends with "."
        lines = text.rstrip().split('\n')
        for i in range(len(lines) - 1, -1, -1):
            stripped = lines[i].strip()
            if re.match(r'^\d+\.\s', stripped):
                if stripped.endswith(';'):
                    lines[i] = lines[i].rstrip()[:-1] + '.'
                elif not stripped.endswith('.'):
                    lines[i] = lines[i].rstrip() + '.'
                break
        text = '\n'.join(lines)

        return text

    async def _generate(self, prompt: str) -> str:
        """
        Generate content using the multi-provider fallback chain.

        Args:
            prompt: The generation prompt

        Returns:
            Generated text content
        """
        try:
            response = await self.provider_service.generate(
                system_prompt="You are an expert EU public affairs consultant who writes professional advocacy documents.",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )

            return response.message

        except Exception as e:
            logger.error(f"Document generation failed: {str(e)}")
            raise

    def _parse_sections(self, content: str) -> Dict[str, str]:
        """
        Parse generated content into named sections.

        Args:
            content: Full document content

        Returns:
            Dictionary of section name -> section content
        """
        sections = {}
        current_section = "preamble"
        current_content = []

        lines = content.split("\n")

        for line in lines:
            # Detect section headers (## or **HEADER**)
            if line.startswith("## ") or (line.startswith("**") and line.endswith("**")):
                # Save previous section
                if current_content:
                    sections[current_section] = "\n".join(current_content).strip()

                # Start new section
                current_section = line.strip("#* ").lower().replace(" ", "_")
                current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_content:
            sections[current_section] = "\n".join(current_content).strip()

        return sections


# Global singleton
_document_generator: Optional[DocumentGenerator] = None


def get_document_generator() -> DocumentGenerator:
    """
    Get global Document Generator instance.

    Returns:
        DocumentGenerator instance
    """
    global _document_generator

    if _document_generator is None:
        _document_generator = DocumentGenerator()

    return _document_generator
