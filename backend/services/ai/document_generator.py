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

HARD TYPOGRAPHIC RULES (NON-NEGOTIABLE) -- APPLIES TO EVERY OUTPUT:
- NEVER use em-dashes (the Unicode character U+2014, "—").
- NEVER use en-dashes (the Unicode character U+2013, "–") as sentence connectors.
- Use a comma, a period, parentheses, a colon, or a regular hyphen-minus ("-") instead.
- If you are tempted to write "—" or "–" between clauses, rewrite the sentence.
- This is a Brubru style rule. Drafts containing em-dashes are rejected.
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

    PETITION_PROMPT = """Generate a petition to the European Parliament (Committee on Petitions, PETI) in the official structure.

TOPIC / SUBJECT: {topic}

CONTEXT: {context_description}

PETITIONER: {petitioner_name}

{style_guidelines}

Produce the petition in the following EXACT structure and section headers (bold):

---

**Petition to the European Parliament**

**Legal basis:** Articles 24 and 227 of the Treaty on the Functioning of the European Union and Article 44 of the Charter of Fundamental Rights of the European Union.

**Petitioner:** {petitioner_name}

**Subject:** [one clear sentence stating the subject, derived from the topic]

**EU dimension (admissibility):** [explain why the subject falls within an EU field of activity, citing a relevant treaty article, regulation or EU programme, and why it directly affects the petitioner]

**Facts:**
- [factual point 1]
- [factual point 2]
- [factual point 3]

**The petitioner requests that the European Parliament, through its Committee on Petitions:**
1. [specific action];
2. [specific action];
3. [specific action].

**How to submit:** lodge via the Petitions Web Portal (petitions.europarl.europa.eu) in one of the 24 official EU languages.

CRITICAL RULES:
1. The petition MUST establish an EU-competence link (an EU field of activity) - this is the admissibility test. Cite a real, relevant treaty article (for example Article 167 TFEU for culture, Article 168 TFEU for public health, Article 191 TFEU for the environment) or a relevant EU regulation/programme for the topic.
2. ANTI-HALLUCINATION: do NOT invent statistics, dates, named individuals, case numbers or events. Where a specific fact is needed but is not provided in the context, write a clear bracketed placeholder such as "[insert verified figure]" or "[insert date]" for the petitioner to complete. It is better to leave a placeholder than to state an unverified fact.
3. Keep the requests specific and within what the Parliament or Commission can actually do (investigate, clarify, fund, protect a right, ask the Commission to act). A petition raises and investigates an issue; it does NOT by itself change EU law - do not promise legislative outcomes.
4. Use the exact bold section headers above. Keep it factual and proportionate.
5. Do NOT use markdown headers (##); this is a single continuous document. Use bold (**) only for the section headers.
"""

    EU_EMAIL_PROMPT = """Generate a Brussels-style EU email or letter in the exact diplomatic register used inside the EU bubble.

RECIPIENT:
- Name: {recipient_name}
- Title/role: {recipient_title}
- Role category: {recipient_role}
- Institution: {recipient_institution}
- Unit/Committee/DG: {recipient_unit}

SENDER:
- Name: {sender_name}
- Title: {sender_title}
- Organisation: {sender_org}
- Email: {sender_email}
- Phone: {sender_phone}
- EU Transparency Register ID: {transparency_register_id}

INTENT:
- Purpose: {purpose}
- The ask (concrete request, in plain language): {the_ask}
- Subject-line hint (use it if useful, otherwise invent a better one): {subject_hint}
- Policy file / procedure / EUR-Lex reference: {policy_file_reference}
- Background and context to weave in: {context_notes}
- Time anchor (deadline, meeting window, vote): {deadline_or_date}

REGISTER:
- Tone: {tone}
- Relationship with recipient: {relationship} (cold = no prior contact / formal "Dear [Title] [Last name],"; warm = met once or twice; established = first-name basis)
- Output language: {language_label}

STRUCTURE -- 6 BLOCKS, EXACTLY:

1. SUBJECT LINE
   Plain text, no Markdown prefix. Format: "<Action verb / topic> -- <policy file or meeting reference>".
   Example: "Request for a brief exchange: DG ENVI -- Ecodesign implementation"
   Example: "RE: Stakeholder consultation on the EU AI Act -- follow-up and next steps"
   Render as a line starting with "Subject: ".

2. GREETING
   Match the relationship and role:
   - cold + commissioner/director_general/ambassador: "Dear Commissioner [Last name]," / "Dear Director-General [Last name]," / "Dear Ambassador [Last name],"
   - cold + mep: "Dear Member of the European Parliament," then "Dear Mr/Ms [Last name],"
   - cold + other: "Dear Mr/Ms [Last name],"
   - warm: "Dear [First name] [Last name],"
   - established: "Dear [First name],"
   - Multiple recipients: "Dear Colleagues,"

3. THE BRUSSELS SANDWICH HOOK (2 to 3 sentences)
   Open with a polite, warm sentence. Then thank the recipient for something specific (a past meeting, a recent speech, their work on the file). Then transition into the reason for writing. Do NOT be sycophantic; keep it grounded in a real detail from the context_notes if possible.

4. CORE MESSAGE (1 to 3 short paragraphs)
   Euro-English. Process-oriented vocabulary where it fits naturally: "level playing field", "interoperability", "trilogue", "horizontal approach", "stakeholder mapping", "future-proof", "co-decision", "in-built safeguards". Do not stuff them; use only what makes sense.
   State the policy context, the concern or interest, and the specific ask. Reference Article numbers, recital numbers, procedure references (e.g., 2021/0106(COD)) if the input supplies them.

5. THE "I'M SO BUSY" SIGN-OFF (1 to 2 sentences)
   Time-constrained, action-oriented. Examples:
   - "As my agenda is particularly packed this week, would you be available for a brief 15-minute call on [date]?"
   - "I look forward to your feedback at your earliest convenience. Should you require any further clarification, please do not hesitate to reach out."
   Then a polite closing line: "With kind regards," or "Bien cordialement," (French) on its own line.

6. SIGNATURE BLOCK
   Plain text, one item per line:
     [Sender name]
     [Sender title] | [Sender organisation]
     [Sender email] | [Sender phone]
   Then a blank line, then the GDPR + Transparency Register footer in 9-10 small print:
     "This message and any attachments are confidential and intended solely for the named recipient(s). If you have received this in error, please notify the sender and delete it. Personal data is processed in accordance with Regulation (EU) 2016/679 (GDPR). [Organisation] is registered in the EU Transparency Register under ID [transparency_register_id]."
   If transparency_register_id is empty, omit the Transparency Register clause.

STYLE FOR THIS EMAIL TYPE:
- Hyper-polite but action-oriented. Brussels register, not American directness.
- Sentences readable by non-native English speakers across 27 Member States.
- No exclamation marks. No emojis. No marketing language.
- Acronyms on first use spelled out, then abbreviated.
- Keep the whole email under 350 words including the signature.
- If the language is "fr", produce the entire email in French using equivalent formal French register ("Madame la Commissaire,", "Bien cordialement,", "Conformément au règlement (UE) 2016/679", etc.).

{style_guidelines}

OUTPUT FORMAT:
Return the email as plain text (no Markdown). Begin with "Subject: ", then a blank line, then the greeting, then the body, then the closing, then the signature block. Nothing else. No commentary outside the email.

NOW WRITE THE EMAIL.
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

    async def generate_petition(
        self,
        request: "GeneratePetitionRequest",
        legislative_context: Optional[Dict[str, Any]] = None
    ) -> GeneratedDocument:
        """
        Generate a petition to the European Parliament (Committee on Petitions).

        Follows the PETI structure (legal basis, petitioner, subject, EU-competence
        hook, facts, requests, how to submit). Keeps unverified facts as bracketed
        placeholders for the petitioner to complete.
        """
        logger.info(f"Generating EP petition on: {request.topic}")

        prompt = self.PETITION_PROMPT.format(
            topic=request.topic,
            context_description=(
                request.context_description
                or "Infer the EU dimension and a plausible subject from the topic; "
                   "keep every factual claim as a bracketed placeholder for the petitioner to complete."
            ),
            petitioner_name=request.petitioner_name or "[petitioner name / organisation]",
            style_guidelines=self.EU_STYLE_GUIDELINES,
        )

        content = await self._generate(prompt)
        sections = self._parse_sections(content)

        return GeneratedDocument(
            document_type="petition",
            title=f"Petition to the European Parliament on {request.topic}",
            content=content,
            sections=sections,
            word_count=len(content.split()),
            language=request.language,
            legislative_context=legislative_context,
            editable_sections=list(sections.keys()),
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

    async def generate_eu_email(
        self,
        request,  # GenerateEUEmailRequest (typed in caller)
    ):
        """
        Generate a Brussels-style EU email/letter.

        Returns a GeneratedDocument whose content is a plain-text email body
        (Subject line, greeting, body, sign-off, signature block, GDPR + EU
        Transparency Register footer). The 6-section template follows the
        Brussels diplomatic register laid out in EU_EMAIL_PROMPT.
        """
        logger.info(
            f"Generating EU email for {request.recipient_name} ({request.recipient_role}) "
            f"from {request.sender_name} ({request.sender_org})"
        )

        language_label = {
            "en": "English (British)",
            "fr": "French",
        }.get(request.language, "English (British)")

        prompt = self.EU_EMAIL_PROMPT.format(
            recipient_name=request.recipient_name or "[Recipient]",
            recipient_title=request.recipient_title or "(not specified)",
            recipient_role=request.recipient_role,
            recipient_institution=request.recipient_institution,
            recipient_unit=request.recipient_unit or "(not specified)",
            sender_name=request.sender_name,
            sender_title=request.sender_title or "(not specified)",
            sender_org=request.sender_org,
            sender_email=request.sender_email or "(not provided)",
            sender_phone=request.sender_phone or "(not provided)",
            transparency_register_id=request.sender_transparency_register_id or "",
            purpose=request.purpose,
            the_ask=request.the_ask,
            subject_hint=request.subject_hint or "(none, invent one)",
            policy_file_reference=request.policy_file_reference or "(not specified)",
            context_notes=request.context_notes or "(none provided)",
            deadline_or_date=request.deadline_or_date or "(not specified)",
            tone=request.tone,
            relationship=request.relationship,
            language_label=language_label,
            style_guidelines=self.EU_STYLE_GUIDELINES,
        )

        content = await self._generate(prompt)

        # Defence in depth: strip em-dashes and en-dashes the model may have
        # slipped in despite the prompt. Replace with comma + space.
        content = (
            content.replace("—", ", ")
            .replace("–", ", ")
            .replace(" , ", ", ")
        )

        # Pull the subject line for the document title.
        subject = ""
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("subject:"):
                subject = stripped[len("subject:"):].strip()
                break
        if not subject:
            subject = f"Email to {request.recipient_name}"

        sections = self._parse_sections(content)

        return GeneratedDocument(
            document_type="eu_email",
            title=f"Email to {request.recipient_name}: {subject[:140]}",
            content=content,
            sections=sections or {"email": content},
            word_count=len(content.split()),
            language=request.language,
            legislative_context=None,
            editable_sections=list((sections or {"email": content}).keys()),
        )

    # =====================================================================
    # Shared helpers for the 6 new document types
    # =====================================================================

    @staticmethod
    def _scrub_dashes(text: str) -> str:
        """Belt-and-braces removal of em-dashes / en-dashes left in by the model."""
        if not text:
            return text
        return (
            text.replace("—", ", ")
                .replace("–", ", ")
                .replace(" , ", ", ")
        )

    @staticmethod
    def _read_style_reference(storage_id: Optional[str]) -> str:
        """Pull a short excerpt from a user-uploaded style reference. Returns
        '(no style reference uploaded)' on miss so the prompt still formats."""
        if not storage_id:
            return "(no style reference uploaded)"
        try:
            from services.storage.document_storage import get_document_storage
            storage = get_document_storage()
            doc = storage.get_document(storage_id)
            if not doc or not doc.get('has_processed_content'):
                return "(uploaded style reference has no processed content)"
            processed = doc.get('processed_content') or {}
            text = (processed.get('text') or '').strip()
            if not text:
                return "(uploaded style reference is empty)"
            return text[:3500]
        except Exception as exc:
            logger.warning(f"Failed to load style reference {storage_id}: {exc}")
            return "(unable to load style reference)"

    @staticmethod
    def _format_branding_block(branding) -> str:
        if not branding:
            return "(no branding supplied)"
        parts = []
        if getattr(branding, "organisation_name", None):
            parts.append(f"Organisation: {branding.organisation_name}")
        if getattr(branding, "organisation_url", None):
            parts.append(f"URL: {branding.organisation_url}")
        if getattr(branding, "contact_email", None):
            parts.append(f"Email: {branding.contact_email}")
        if getattr(branding, "contact_phone", None):
            parts.append(f"Phone: {branding.contact_phone}")
        if getattr(branding, "transparency_register_id", None):
            parts.append(f"EU Transparency Register: {branding.transparency_register_id}")
        return "\n".join(parts) if parts else "(no branding supplied)"

    # =====================================================================
    # #3 Position paper one-pager
    # =====================================================================

    ONE_PAGER_PROMPT = """Generate a strict ONE-PAGE EU position paper.

TOPIC: {topic}
PROCEDURE: {procedure_reference}
CELEX: {celex_number}

ORGANISATION: {organisation_name}
ORGANISATION PITCH: {organisation_pitch}

POSITION: {position}
HEADLINE ASK: {headline_ask}
KEY ASKS:
{key_asks_block}

SUPPORTING EVIDENCE:
{supporting_evidence}

TONE: {tone}
LANGUAGE: {language_label}

STYLE REFERENCE (from a user-uploaded one-pager):
{style_reference}

BRANDING:
{branding_block}

{style_guidelines}

OUTPUT (strict, must fit on one A4 page, ~500-600 words MAX):

# {headline_ask}

**{organisation_name}** | Position on {topic}

> One-sentence positioning paragraph stating WHAT the paper asks and WHY it matters NOW.

## Key asks
- 2-5 short, sharp bullets (each ≤ 25 words). Reference Articles where relevant.

## Why this matters
2 to 3 short paragraphs combining context, evidence, and the cost of inaction. Cite specific numbers from the supporting evidence above.

## What we recommend
Restate the headline ask in a single short paragraph with the named addressee (Commission, EP rapporteur, Council).

## About {organisation_name}
2 sentences using the organisation pitch.

---
Contact: [email] | [URL] | EU Transparency Register: [ID if present]

NOW WRITE THE ONE-PAGER. NO em-dashes. NO marketing fluff. NO emojis.
"""

    async def generate_one_pager(self, request):
        logger.info(f"Generating one-pager on {request.topic}")
        key_asks_block = "\n".join(f"- {a}" for a in request.key_asks) if request.key_asks \
            else "(no key asks pre-supplied; infer from topic + position)"
        language_label = {"en": "British English", "fr": "French"}.get(request.language, "British English")
        prompt = self.ONE_PAGER_PROMPT.format(
            topic=request.topic,
            procedure_reference=request.procedure_reference or "(not supplied)",
            celex_number=request.celex_number or "(not supplied)",
            organisation_name=request.organisation_name,
            organisation_pitch=request.organisation_pitch or "(not supplied)",
            position=request.position,
            headline_ask=request.headline_ask,
            key_asks_block=key_asks_block,
            supporting_evidence=request.supporting_evidence or "(none provided)",
            tone=request.tone,
            language_label=language_label,
            style_reference=self._read_style_reference(request.style_reference_storage_id),
            branding_block=self._format_branding_block(request.branding),
            style_guidelines=self.EU_STYLE_GUIDELINES,
        )
        content = self._scrub_dashes(await self._generate(prompt))
        sections = self._parse_sections(content)
        return GeneratedDocument(
            document_type="one_pager",
            title=f"One-pager: {request.headline_ask[:140]}",
            content=content,
            sections=sections or {"one_pager": content},
            word_count=len(content.split()),
            language=request.language,
            legislative_context=None,
            editable_sections=list((sections or {"one_pager": content}).keys()),
        )

    # =====================================================================
    # #7 EU press release
    # =====================================================================

    PRESS_RELEASE_PROMPT = """Generate an EU-format press release in the {institution_label} house style.

HEADLINE: {headline}
SUB-HEADLINE: {sub_headline}
DATELINE: {dateline_city}, {dateline_date}

LEAD PARAGRAPH (set in stone, do not alter): {lead_paragraph}

KEY POINTS:
{key_points_block}

QUOTE: {quote_text}
ATTRIBUTED TO: {quote_attribution}

BACKGROUND:
{background}

NEXT STEPS:
{next_steps}

PRESS CONTACTS:
{contacts}

BRANDING:
{branding_block}

LANGUAGE: {language_label}

{style_guidelines}

HOUSE STYLE RULES FOR {institution_label}:

If Commission (IP/XX/XXXX style):
- Headline in sentence case.
- "(Brussels, [date])" inline dateline.
- 3 to 5 short paragraphs.
- One direct quote attributed to a Commissioner or DG official.
- "For more information" footer with links.
- "Background" section at the end.

If European Parliament:
- Headline in title case.
- Dateline "Brussels, [date] -- " (single hyphen for the en-dash REPLACEMENT, never use --).
- Quote from the lead rapporteur or committee chair.
- Note the legislative procedure reference (e.g., 2021/0106(COD)).
- "Next steps" paragraph indicates the next vote / institution.

If Council:
- Headline in sentence case, neutral and factual.
- "(Brussels)" inline city.
- Reference Council formation (Foreign Affairs Council, ECOFIN, ...).
- "Background" + "Member State positions" if relevant.
- Conservative, diplomatic, never editorialising.

If Agency:
- Compact, technical tone.
- Headline in sentence case.
- Quote from the agency executive director.
- Agency acronym in the dateline.

OUTPUT FORMAT (markdown):

# {headline}
{sub_headline_block}

**{dateline_city}, {dateline_date}**

[Lead paragraph here, expanded to 2 short sentences max.]

## Key points
- Bullets from KEY POINTS, polished.

> "{quote_text_inline}"
> -- {quote_attribution_or_blank}

## Background
[Background paragraph in 3-5 sentences.]

## Next steps
[1 short paragraph on what happens next and when.]

## Press contacts
[Contacts block, one per line.]

NOW WRITE THE PRESS RELEASE. NO em-dashes. NO promotional adjectives.
"""

    async def generate_eu_press_release(self, request):
        logger.info(f"Generating EU press release in {request.institution_style} style: {request.headline}")
        institution_label = {
            "commission": "European Commission",
            "parliament": "European Parliament",
            "council": "Council of the EU",
            "agency": "EU Agency",
        }.get(request.institution_style, "European Commission")
        from datetime import date
        date_str = request.dateline_date or date.today().strftime("%d %B %Y")
        key_points = "\n".join(f"- {p}" for p in request.key_points) if request.key_points else "(none supplied)"
        sub_headline_block = f"_{request.sub_headline}_" if request.sub_headline else ""
        language_label = {"en": "British English", "fr": "French"}.get(request.language, "British English")
        prompt = self.PRESS_RELEASE_PROMPT.format(
            institution_label=institution_label,
            headline=request.headline,
            sub_headline=request.sub_headline or "(no sub-headline)",
            sub_headline_block=sub_headline_block,
            dateline_city=request.dateline_city,
            dateline_date=date_str,
            lead_paragraph=request.lead_paragraph,
            key_points_block=key_points,
            quote_text=request.quote_text or "(no quote supplied; invent one in line with the lead paragraph)",
            quote_text_inline=(request.quote_text or "...")[:280],
            quote_attribution=request.quote_attribution or "(unspecified)",
            quote_attribution_or_blank=request.quote_attribution or "spokesperson",
            background=request.background or "(none supplied; infer from headline and key points)",
            next_steps=request.next_steps or "(infer 1 short paragraph)",
            contacts=request.contacts or "(none supplied; insert a placeholder press contact line)",
            branding_block=self._format_branding_block(request.branding),
            language_label=language_label,
            style_guidelines=self.EU_STYLE_GUIDELINES,
        )
        content = self._scrub_dashes(await self._generate(prompt))
        sections = self._parse_sections(content)
        return GeneratedDocument(
            document_type="press_release",
            title=f"{institution_label} press release: {request.headline[:120]}",
            content=content,
            sections=sections or {"press_release": content},
            word_count=len(content.split()),
            language=request.language,
            legislative_context=None,
            editable_sections=list((sections or {"press_release": content}).keys()),
        )

    # =====================================================================
    # #5 Stakeholder mapping & analysis
    # =====================================================================

    STAKEHOLDER_MAP_PROMPT = """Generate a structured EU stakeholder map and analysis.

POLICY TOPIC: {policy_topic}
PROCEDURE: {procedure_reference}
CELEX: {celex_number}
SCOPE: {scope}
SECTOR: {sector}

USER OBJECTIVES:
{objectives}

INSTITUTIONS TO COVER: {institutions_to_cover_block}
KNOWN STAKEHOLDERS TO INCLUDE: {known_stakeholders_block}
TARGET COUNT: {target_count} stakeholders

LANGUAGE: {language_label}

{style_guidelines}

OUTPUT FORMAT (markdown):

# Stakeholder map: {policy_topic}

## Executive overview
2 short paragraphs on the political landscape, the contested lines, and the
biggest leverage points.

## Stakeholder table
A markdown table with {target_count} rows and these EXACT columns:

| Stakeholder | Institution / Org | Role | Position (support / amend / oppose / undecided) | Influence (high / medium / low) | Recommended approach |
|---|---|---|---|---|---|

Populate every row with a real person where known (use the known list); otherwise
fill with named roles (e.g., "Lead rapporteur, IMCO committee"). Mix:
- 1 to 3 EU Commission contacts (Commissioner / cabinet / DG / unit)
- 3 to 6 European Parliament contacts (rapporteur, shadows, committee chair, group advisors)
- 1 to 3 Council contacts (presidency attaché, COREPER, relevant Council working party)
- 1 to 2 agency contacts (if relevant)
- 1 to 3 stakeholder-side contacts (allied trade associations, NGOs, think tanks)

## Engagement priorities
A numbered list (3 to 5 items) of the most strategic next moves, each as a short paragraph linking back to a row in the table.

## Risk map
3 to 5 short bullets describing political / procedural risks to watch.

NOW WRITE. NO em-dashes. Use British English. Be specific, not generic.
"""

    async def generate_stakeholder_map(self, request):
        logger.info(f"Generating stakeholder map for {request.policy_topic}")
        institutions_block = ", ".join(request.institutions_to_cover) or "European Commission, European Parliament, Council of the EU"
        known_block = "\n".join(f"- {s}" for s in request.known_stakeholders) if request.known_stakeholders \
            else "(none supplied; invent named roles)"
        language_label = {"en": "British English", "fr": "French"}.get(request.language, "British English")
        prompt = self.STAKEHOLDER_MAP_PROMPT.format(
            policy_topic=request.policy_topic,
            procedure_reference=request.procedure_reference or "(not supplied)",
            celex_number=request.celex_number or "(not supplied)",
            scope=request.scope,
            sector=request.sector or "(not specified)",
            objectives=request.objectives,
            institutions_to_cover_block=institutions_block,
            known_stakeholders_block=known_block,
            target_count=request.target_count,
            language_label=language_label,
            style_guidelines=self.EU_STYLE_GUIDELINES,
        )
        content = self._scrub_dashes(await self._generate(prompt))
        sections = self._parse_sections(content)
        return GeneratedDocument(
            document_type="stakeholder_map",
            title=f"Stakeholder map: {request.policy_topic[:140]}",
            content=content,
            sections=sections or {"stakeholder_map": content},
            word_count=len(content.split()),
            language=request.language,
            legislative_context=None,
            editable_sections=list((sections or {"stakeholder_map": content}).keys()),
        )

    # =====================================================================
    # #6 Commission-style impact assessment
    # =====================================================================

    IMPACT_ASSESSMENT_PROMPT = """Generate a European Commission style Impact Assessment following the Better Regulation template.

INITIATIVE: {initiative_title}
POLICY AREA: {policy_area}

PROBLEM DEFINITION:
{problem_definition}

DRIVERS:
{drivers_block}

OBJECTIVES (GENERAL):
{objectives_general}

OBJECTIVES (SPECIFIC):
{objectives_specific_block}

BASELINE (no further EU action):
{baseline_scenario}

POLICY OPTIONS TO COMPARE:
{policy_options_block}

IMPACT DIMENSIONS TO SCORE: {impact_dimensions_block}
PREFERRED OPTION HINT: {preferred_option_hint}
LANGUAGE: {language_label}

STYLE REFERENCE (from a user-uploaded IA):
{style_reference}

{style_guidelines}

STRUCTURE (follow EXACTLY -- this is the Commission Better Regulation IA template):

# Impact Assessment: {initiative_title}

## 1. Problem definition
1.1. What is the problem? (use the input above; cite drivers)
1.2. Who is affected and how?
1.3. How likely is the problem to persist or worsen under the baseline?

## 2. Why should the EU act?
2.1. Legal basis (cite the Treaty article range where appropriate)
2.2. Subsidiarity and proportionality

## 3. Objectives
3.1. General objective
3.2. Specific objectives (bullet list)

## 4. Policy options
A numbered list of the supplied options. For each option:
- One short paragraph describing the intervention.
- Bullet expected mechanism.

## 5. Impacts of the options
A markdown table comparing options against the impact dimensions:

| Option | Economic | Social | Environmental | Fundamental rights | SMEs / Competitiveness | Administrative burden |
|---|---|---|---|---|---|---|

Fill each cell with a short qualitative score ("positive / neutral / negative / mixed") followed by one sentence of reasoning. Use only the dimensions actually requested.

## 6. Comparison of options
2 short paragraphs that synthesise the impact table and explain which option scores best on which criterion.

## 7. Preferred option and justification
1 paragraph naming the preferred option and the trade-offs accepted.

## 8. Monitoring and evaluation
Short bullet list of indicators and review cadence.

NOW WRITE THE IA. NO em-dashes. Avoid hedging like "may possibly contribute"; be specific.
"""

    async def generate_impact_assessment(self, request):
        logger.info(f"Generating impact assessment for {request.initiative_title}")
        drivers_block = "\n".join(f"- {d}" for d in request.drivers) if request.drivers else "(none supplied)"
        objs_specific = "\n".join(f"- {o}" for o in request.objectives_specific) if request.objectives_specific \
            else "(none supplied)"
        options_block = "\n".join(f"{i+1}. {o}" for i, o in enumerate(request.policy_options))
        dims_block = ", ".join(request.impact_dimensions)
        language_label = {"en": "British English", "fr": "French"}.get(request.language, "British English")
        prompt = self.IMPACT_ASSESSMENT_PROMPT.format(
            initiative_title=request.initiative_title,
            policy_area=request.policy_area or "(not specified)",
            problem_definition=request.problem_definition,
            drivers_block=drivers_block,
            objectives_general=request.objectives_general or "(infer from the problem)",
            objectives_specific_block=objs_specific,
            baseline_scenario=request.baseline_scenario or "(infer 1 paragraph)",
            policy_options_block=options_block,
            impact_dimensions_block=dims_block,
            preferred_option_hint=request.preferred_option_hint or "(no hint; pick based on the analysis)",
            language_label=language_label,
            style_reference=self._read_style_reference(request.style_reference_storage_id),
            style_guidelines=self.EU_STYLE_GUIDELINES,
        )
        content = self._scrub_dashes(await self._generate(prompt))
        sections = self._parse_sections(content)
        return GeneratedDocument(
            document_type="impact_assessment",
            title=f"Impact Assessment: {request.initiative_title[:140]}",
            content=content,
            sections=sections or {"impact_assessment": content},
            word_count=len(content.split()),
            language=request.language,
            legislative_context=None,
            editable_sections=list((sections or {"impact_assessment": content}).keys()),
        )

    # =====================================================================
    # #2 EU institutions presentation
    # =====================================================================

    PRESENTATION_PROMPT = """Generate a slide-by-slide outline for an EU-institution presentation.

TITLE: {title}
SUBTITLE: {subtitle}
AUDIENCE: {audience_label} ({audience})
PURPOSE: {purpose}

KEY MESSAGES:
{key_messages_block}

SECTIONS REQUESTED:
{sections_block}

TARGET SLIDE COUNT: {num_slides}
LANGUAGE: {language_label}

STYLE REFERENCE (from a user-uploaded deck):
{style_reference}

BRANDING:
{branding_block}

{style_guidelines}

OUTPUT FORMAT (strict, slide-by-slide markdown):

For each slide, produce exactly:

## Slide N: <slide title>
- 3 to 5 short bullets, each ≤ 14 words.
- Optional 1-line speaker note prefixed with "Notes: " on the last line.

Slides 1 and 2:
- Slide 1 = Title slide ("{title}" + "{subtitle}").
- Slide 2 = Agenda (one bullet per section).

Final slide:
- Slide N = "Thank you" + contact line built from BRANDING.

Stay STRICTLY within {num_slides} slides. NO em-dashes. NO emojis. NO clip-art instructions.
"""

    async def generate_presentation(self, request):
        logger.info(f"Generating EU presentation: {request.title} ({request.num_slides} slides)")
        key_messages = "\n".join(f"- {m}" for m in request.key_messages) if request.key_messages else "(none supplied)"
        sections_block = "\n".join(f"- {s}" for s in request.sections) if request.sections else "(use the default outline)"
        audience_label = request.audience_label or {
            "commission_official": "European Commission policy officials",
            "commission_cabinet": "Commissioner cabinet members",
            "mep_office": "MEP office",
            "ep_committee_staff": "European Parliament committee staff",
            "council_attache": "Council attaché",
            "permrep": "Permanent Representation",
            "academic": "Academic audience",
            "industry": "Industry stakeholders",
            "press": "Press / journalists",
            "general": "General audience",
        }.get(request.audience, "European Commission policy officials")
        language_label = {"en": "British English", "fr": "French"}.get(request.language, "British English")
        prompt = self.PRESENTATION_PROMPT.format(
            title=request.title,
            subtitle=request.subtitle or "",
            audience=request.audience,
            audience_label=audience_label,
            purpose=request.purpose,
            key_messages_block=key_messages,
            sections_block=sections_block,
            num_slides=request.num_slides,
            language_label=language_label,
            style_reference=self._read_style_reference(request.style_reference_storage_id),
            branding_block=self._format_branding_block(request.branding),
            style_guidelines=self.EU_STYLE_GUIDELINES,
        )
        content = self._scrub_dashes(await self._generate(prompt))
        sections = self._parse_sections(content)
        return GeneratedDocument(
            document_type="presentation",
            title=f"Presentation: {request.title[:140]}",
            content=content,
            sections=sections or {"presentation": content},
            word_count=len(content.split()),
            language=request.language,
            legislative_context=None,
            editable_sections=list((sections or {"presentation": content}).keys()),
        )

    # =====================================================================
    # #4 Event poster
    # =====================================================================

    POSTER_PROMPT = """Generate copy for a single-page event poster on an EU policy topic.

EVENT TITLE: {event_title}
TAGLINE: {event_tagline}
TYPE: {event_type}
DATE: {event_date}
LOCATION: {event_location}

HOSTS:
{hosts_block}

SPEAKERS:
{speakers_block}

AGENDA POINTS:
{agenda_block}

REGISTRATION URL: {registration_url}
CONTACT INFO: {contact_info}

FORMAT: {format_label}
ACCENT COLOR: {accent_color}
LANGUAGE: {language_label}

STYLE REFERENCE (from a user-uploaded poster):
{style_reference}

BRANDING:
{branding_block}

{style_guidelines}

OUTPUT FORMAT (markdown, one-page poster copy, no slide markers):

# {event_title}
**{event_tagline}**

📅 {event_date}   📍 {event_location}

## About the event
1 short paragraph (~50 words) describing the event purpose.

## Programme
- 4 to 8 short agenda bullets (each ≤ 14 words).

## Speakers
- Format each speaker as "**Name** -- Title, Organisation" (a single hyphen, never an em-dash).

## Hosted by
- One host per line.

## Register
[Registration URL or "Email [contact] to attend"]

---
Contact: [contact info]

NOW WRITE THE POSTER COPY. NO em-dashes. NO emojis other than the date/location pin above. Keep it visual-design-ready.
"""

    async def generate_event_poster(self, request):
        logger.info(f"Generating event poster: {request.event_title}")
        hosts_block = "\n".join(f"- {h}" for h in request.hosts) if request.hosts else "(none supplied)"
        speakers_block = "\n".join(f"- {s}" for s in request.speakers) if request.speakers else "(none supplied; suggest 3 plausible profiles)"
        agenda_block = "\n".join(f"- {p}" for p in request.agenda_points) if request.agenda_points else "(none supplied; suggest a typical agenda)"
        format_label = {
            "a4_portrait": "A4 portrait",
            "a4_landscape": "A4 landscape",
            "a3_portrait": "A3 portrait",
            "instagram_square": "Instagram square (1080x1080)",
            "linkedin_landscape": "LinkedIn landscape (1200x627)",
        }.get(request.format, "A4 portrait")
        language_label = {"en": "British English", "fr": "French"}.get(request.language, "British English")
        prompt = self.POSTER_PROMPT.format(
            event_title=request.event_title,
            event_tagline=request.event_tagline or "",
            event_type=request.event_type,
            event_date=request.event_date,
            event_location=request.event_location,
            hosts_block=hosts_block,
            speakers_block=speakers_block,
            agenda_block=agenda_block,
            registration_url=request.registration_url or "(none supplied)",
            contact_info=request.contact_info or "(none supplied)",
            format_label=format_label,
            accent_color=request.accent_color,
            language_label=language_label,
            style_reference=self._read_style_reference(request.style_reference_storage_id),
            branding_block=self._format_branding_block(request.branding),
            style_guidelines=self.EU_STYLE_GUIDELINES,
        )
        content = self._scrub_dashes(await self._generate(prompt))
        sections = self._parse_sections(content)
        return GeneratedDocument(
            document_type="event_poster",
            title=f"Event poster: {request.event_title[:140]}",
            content=content,
            sections=sections or {"poster": content},
            word_count=len(content.split()),
            language=request.language,
            legislative_context=None,
            editable_sections=list((sections or {"poster": content}).keys()),
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
