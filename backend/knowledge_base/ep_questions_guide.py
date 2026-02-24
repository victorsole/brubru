"""
EP Written Questions Knowledge Base

Encodes the structural rules, Commissioner-to-policy-area mapping,
and writing conventions for European Parliament written questions,
derived from analysis of real questions (February 2026).

Used by:
- Document generator (system prompt enrichment)
- Chatbot context builder (intent detection + knowledge injection)
"""

# Commissioner-to-policy-area mapping (10th EP term, Von der Leyen II Commission)
# When generating a question, this predicts which Commissioner will respond
COMMISSIONER_POLICY_MAP = {
    "digital": {
        "commissioner": "EVP Virkkunen",
        "title": "Executive Vice-President for Tech Sovereignty, Security and Democracy",
        "topics": ["eID", "digital identity", "AI Act", "DSA", "DMA", "cybersecurity", "NIS2", "eIDAS"],
    },
    "trade": {
        "commissioner": "Mr Sefcovic",
        "title": "Executive Vice-President for the European Green Deal, Interinstitutional Relations and Foresight",
        "topics": ["trade agreements", "Mercosur", "India FTA", "tariffs", "antidumping", "ceramics", "critical raw materials"],
    },
    "industry": {
        "commissioner": "EVP Sejourne",
        "title": "Executive Vice-President for Prosperity and Industrial Strategy",
        "topics": ["Clean Industrial Deal", "competitiveness", "SMEs", "single market", "KPIs", "industry"],
    },
    "justice": {
        "commissioner": "Mr McGrath",
        "title": "Commissioner for Democracy, Justice, the Rule of Law and Consumer Protection",
        "topics": ["GDPR", "data protection", "rule of law", "consumer protection", "broadcasting"],
    },
    "humanitarian": {
        "commissioner": "Ms Lahbib",
        "title": "Commissioner for Preparedness and Crisis Management, Equality",
        "topics": ["humanitarian aid", "NGO funding", "Gaza", "crisis management", "civil protection"],
    },
    "agriculture": {
        "commissioner": "Mr Hansen",
        "title": "Commissioner for Agriculture and Food",
        "topics": ["CAP", "agriculture", "food safety", "farming", "rural development"],
    },
    "environment": {
        "commissioner": "Mr Hoekstra",
        "title": "Commissioner for Climate, Net Zero and Clean Growth",
        "topics": ["climate", "emissions", "CBAM", "ETS", "green deal", "environment"],
    },
    "transport": {
        "commissioner": "Mr Tzitzikostas",
        "title": "Commissioner for Sustainable Transport and Tourism",
        "topics": ["transport", "vehicle safety", "aviation", "rail", "road safety", "tourism"],
    },
    "health": {
        "commissioner": "Mr Lahbib",
        "title": "Commissioner for Health and Animal Welfare",
        "topics": ["health", "pharmaceuticals", "medicines", "pharmacy", "medical devices"],
    },
    "foreign_affairs": {
        "commissioner": "VP/HR Kallas",
        "title": "Vice-President / High Representative for Foreign Affairs and Security Policy",
        "topics": ["foreign policy", "sanctions", "defence", "NATO", "geopolitics", "international order"],
    },
}


# Common Commission response strategies (so users can anticipate deflections)
COMMISSION_RESPONSE_STRATEGIES = {
    "deflect_to_member_states": {
        "description": "Commission cites 'primarily the responsibility of Member States'",
        "topics": ["national implementation", "enforcement", "prison labour", "pharmacy regulation"],
        "counter_tip": "Frame the question around the Commission's monitoring duty or treaty obligations, not national implementation.",
    },
    "cite_existing_frameworks": {
        "description": "Commission points to existing legislation as sufficient",
        "topics": ["digital identity", "security standards", "product safety"],
        "counter_tip": "Ask specifically about gaps or failures in existing frameworks, citing concrete evidence of inadequacy.",
    },
    "acknowledge_without_committing": {
        "description": "Commission acknowledges concerns but makes no commitments",
        "topics": ["energy-intensive industries", "competitiveness", "SME burden"],
        "counter_tip": "Ask for specific timelines, concrete measures, or quantified targets rather than general acknowledgements.",
    },
    "redirect_to_reports": {
        "description": "Commission points to annual reports or scoreboards",
        "topics": ["KPIs", "implementation monitoring", "progress tracking"],
        "counter_tip": "Ask about specific deficiencies identified in those reports and what corrective action the Commission will take.",
    },
    "under_negotiation": {
        "description": "Commission says the matter is under legislative negotiation",
        "topics": ["proposals", "ongoing procedures", "trilogue"],
        "counter_tip": "Ask about the Commission's position within the negotiation rather than the outcome.",
    },
}


# Question structure rules for AI prompt injection
EP_QUESTION_STRUCTURE_RULES = """
EUROPEAN PARLIAMENT WRITTEN QUESTION FORMAT:

A written parliamentary question (also called "EP question" or "written question to the Commission")
is a formal tool used by MEPs to hold the European Commission accountable.

STRUCTURE:
1. Title: Descriptive, max 200 characters, formal and specific
2. Header: Reference number, addressee (Commission/Council/VP-HR), Rule 144
3. Context: 2-4 paragraphs of evidence-based background (200-400 words)
   - Must cite EU legislation (Regulations, Directives, Treaty articles)
   - Must include factual evidence (statistics, audits, news reports)
   - Footnoted sources [1], [2], [3]
4. Bridge phrase: "In the light of the above:" or similar
5. Sub-questions: 1-3 numbered, direct, specific questions

CONVENTIONS:
- Formal institutional voice, third-person
- British English (analyse, organisation, programme)
- Reference "Article X" not "Art. X"
- Two types: Standard (E-, 6-week deadline) and Priority (P-, 3-week deadline)
- Questions addressed to Commission, Council, or VP/HR

GOOD SUB-QUESTION PATTERNS:
- "Can the Commission clarify..."
- "What steps does the Commission intend to take..."
- "Does the Commission consider that..."
- "Is the Commission aware of..."
- "What assessment has the Commission made of..."
"""


def get_commissioner_for_topic(topic_keywords: str) -> dict:
    """
    Predict which Commissioner will respond based on topic keywords.

    Args:
        topic_keywords: Space-separated keywords from the question topic

    Returns:
        Dict with commissioner info or empty dict if no match
    """
    keywords_lower = topic_keywords.lower()
    best_match = None
    best_score = 0

    for area, info in COMMISSIONER_POLICY_MAP.items():
        score = sum(1 for kw in info["topics"] if kw.lower() in keywords_lower)
        if score > best_score:
            best_score = score
            best_match = info

    return best_match or {}


def get_response_strategy_warning(topic_keywords: str) -> str:
    """
    Warn users about likely Commission response strategies.

    Args:
        topic_keywords: Space-separated keywords from the question topic

    Returns:
        Warning string or empty string
    """
    keywords_lower = topic_keywords.lower()
    warnings = []

    for strategy_id, strategy in COMMISSION_RESPONSE_STRATEGIES.items():
        if any(kw.lower() in keywords_lower for kw in strategy["topics"]):
            warnings.append(
                f"[{strategy['description']}] Tip: {strategy['counter_tip']}"
            )

    return "\n".join(warnings) if warnings else ""
