"""
Document Generation Schemas

Pydantic models for document generation requests and responses.
Priority #3: Position Paper Generator
"""

from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from datetime import datetime


# Enums for document generation
PositionStance = Literal["support", "support_with_amendments", "oppose", "neutral"]
DocumentTone = Literal["constructive", "critical", "technical", "diplomatic"]
OrganisationType = Literal["company", "industry_association", "ngo", "think_tank", "law_firm", "consultancy"]


class KeyAsk(BaseModel):
    """A specific policy ask/recommendation"""
    summary: str = Field(..., description="Brief summary of the ask (1 sentence)")
    detail: Optional[str] = Field(None, description="More detailed explanation")
    article_reference: Optional[str] = Field(None, description="Specific article/recital reference")


# EU email/letter generation
EUInstitution = Literal[
    "european_commission",
    "european_parliament",
    "council_eu",
    "permanent_representation",
    "eeas",
    "agency",
    "other",
]
EURoleCategory = Literal[
    "commissioner",
    "cabinet_member",
    "director_general",
    "director",
    "head_of_unit",
    "policy_officer",
    "mep",
    "apa",
    "ep_group_advisor",
    "ep_committee_staff",
    "council_attache",
    "permrep_counsellor",
    "ambassador",
    "other",
]
EUEmailPurpose = Literal[
    "meeting_request",
    "follow_up",
    "position_input",
    "invitation",
    "thanks",
    "information_request",
    "amendment_input",
    "other",
]
EUEmailTone = Literal["standard", "warm", "urgent", "formal"]
EUEmailRelationship = Literal["cold", "warm", "established"]


class GenerateEUEmailRequest(BaseModel):
    """Request to generate a Brussels-style EU email or letter"""

    # Recipient
    recipient_name: str = Field(..., min_length=1, max_length=200,
                                description="Full name of the recipient (e.g., 'Margrethe Vestager')")
    recipient_title: Optional[str] = Field(None, max_length=200,
                                           description="Recipient's formal title or role")
    recipient_role: EURoleCategory = Field(default="policy_officer",
                                           description="Category that drives the salutation/register")
    recipient_institution: EUInstitution = Field(default="european_commission")
    recipient_unit: Optional[str] = Field(None, max_length=200,
                                          description="DG / Committee / Unit (e.g., 'DG ENVI', 'IMCO')")

    # Email body / intent
    purpose: EUEmailPurpose = Field(default="meeting_request",
                                    description="What this email is for")
    subject_hint: Optional[str] = Field(None, max_length=200,
                                        description="If empty, the model invents a Brussels-style subject line")
    policy_file_reference: Optional[str] = Field(
        None, max_length=200,
        description="The legislative file / procedure / EUR-Lex reference the email is about (e.g., 'AI Act trilogue', '2021/0106(COD)')")
    the_ask: str = Field(..., min_length=1, max_length=1000,
                         description="The concrete request, in plain language")
    context_notes: Optional[str] = Field(None, max_length=4000,
                                         description="Background, reasons, prior exchanges, evidence to weave in")
    deadline_or_date: Optional[str] = Field(None, max_length=120,
                                            description="Time anchor (e.g., 'before the IMCO vote on 12 June', 'next Tuesday')")

    # Style / register
    tone: EUEmailTone = Field(default="standard")
    relationship: EUEmailRelationship = Field(default="cold",
                                              description="How well the sender knows the recipient")
    language: Literal["en", "fr"] = Field(default="en")

    # Sender
    sender_name: str = Field(..., min_length=1, max_length=200)
    sender_title: Optional[str] = Field(None, max_length=200,
                                        description="Role / title within the sender's organisation")
    sender_org: str = Field(..., min_length=1, max_length=200)
    sender_email: Optional[str] = Field(None, max_length=200)
    sender_phone: Optional[str] = Field(None, max_length=80)
    sender_transparency_register_id: Optional[str] = Field(
        None, max_length=80,
        description="EU Transparency Register identification number, included in the GDPR footer")

    # Branding (uploaded earlier via /api/documents/upload)
    logo_storage_id: Optional[str] = Field(
        None, max_length=80,
        description="storage_document_id returned by /api/documents/upload; embedded in DOCX export")


# -----------------------------------------------------------------------------
# Shared branding / style-reference block used by the new doc types (3, 7, 5, 6, 2, 4)
# -----------------------------------------------------------------------------

class BrandingBlock(BaseModel):
    """Organisation branding to render in DOCX/PDF/PPTX exports."""
    organisation_name: Optional[str] = Field(None, max_length=200)
    organisation_url: Optional[str] = Field(None, max_length=300)
    contact_email: Optional[str] = Field(None, max_length=200)
    contact_phone: Optional[str] = Field(None, max_length=80)
    transparency_register_id: Optional[str] = Field(None, max_length=80)
    logo_storage_id: Optional[str] = Field(
        None, max_length=80,
        description="storage_document_id returned by /api/documents/upload")


# -----------------------------------------------------------------------------
# #3 Position paper one-pager
# -----------------------------------------------------------------------------

class GenerateOnePagerRequest(BaseModel):
    """One-page position paper, strict 600-word ceiling, single-sheet layout."""
    topic: str = Field(..., min_length=1, max_length=300,
                       description="Topic or legislative file the one-pager is about")
    procedure_reference: Optional[str] = Field(None, max_length=120)
    celex_number: Optional[str] = Field(None, max_length=40)
    organisation_name: str = Field(..., min_length=1, max_length=200)
    organisation_pitch: Optional[str] = Field(
        None, max_length=500,
        description="One- or two-sentence elevator pitch for the organisation")
    position: PositionStance = Field(default="support_with_amendments")
    headline_ask: str = Field(..., min_length=1, max_length=300,
                              description="The single most important ask, rendered as the H1")
    key_asks: List[str] = Field(default_factory=list, max_length=5,
                                description="2-5 short bullet asks")
    supporting_evidence: Optional[str] = Field(
        None, max_length=2000,
        description="Data, citations, numbers to ground the asks")
    tone: DocumentTone = Field(default="constructive")
    language: Literal["en", "fr"] = Field(default="en")
    style_reference_storage_id: Optional[str] = Field(
        None, max_length=80,
        description="storage_document_id of a user-uploaded one-pager to learn style from")
    branding: BrandingBlock = Field(default_factory=BrandingBlock)


# -----------------------------------------------------------------------------
# #7 EU press release (Commission / EP / Council styles)
# -----------------------------------------------------------------------------

PressReleaseInstitution = Literal["commission", "parliament", "council", "agency"]

class GenerateEUPressReleaseRequest(BaseModel):
    """EU-format press release in Commission / EP / Council house style."""
    institution_style: PressReleaseInstitution = Field(default="commission")
    headline: str = Field(..., min_length=1, max_length=240,
                          description="Press release headline")
    sub_headline: Optional[str] = Field(None, max_length=300,
                                        description="One-line strap below the headline")
    dateline_city: str = Field(default="Brussels", max_length=80)
    dateline_date: Optional[str] = Field(None, max_length=40,
                                         description="Free-text date (e.g. '20 May 2026'); blank = today")
    lead_paragraph: str = Field(..., min_length=1, max_length=1500,
                                description="The first paragraph (who/what/where/when/why)")
    key_points: List[str] = Field(default_factory=list, max_length=10,
                                  description="3-8 fact bullets to expand in the body")
    quote_text: Optional[str] = Field(None, max_length=600)
    quote_attribution: Optional[str] = Field(None, max_length=200,
                                             description="e.g. 'Margrethe Vestager, Executive Vice-President'")
    background: Optional[str] = Field(None, max_length=2000)
    next_steps: Optional[str] = Field(None, max_length=1000)
    contacts: Optional[str] = Field(None, max_length=600,
                                    description="Press contact block, one contact per line")
    language: Literal["en", "fr"] = Field(default="en")
    branding: BrandingBlock = Field(default_factory=BrandingBlock)


# -----------------------------------------------------------------------------
# #5 Stakeholder mapping & analysis
# -----------------------------------------------------------------------------

class GenerateStakeholderMapRequest(BaseModel):
    """Structured stakeholder mapping for an EU policy file."""
    policy_topic: str = Field(..., min_length=1, max_length=300)
    procedure_reference: Optional[str] = Field(None, max_length=120)
    celex_number: Optional[str] = Field(None, max_length=40)
    scope: Literal["eu", "national", "both"] = Field(default="eu")
    sector: Optional[str] = Field(None, max_length=120,
                                  description="Sector / industry context (e.g. 'medtech', 'fintech')")
    objectives: str = Field(..., min_length=1, max_length=1000,
                            description="What the user wants to achieve on this file")
    known_stakeholders: List[str] = Field(default_factory=list, max_length=30,
                                          description="Pre-seeded names to include in the map")
    institutions_to_cover: List[str] = Field(
        default_factory=lambda: ["European Commission", "European Parliament", "Council of the EU"],
        max_length=10)
    target_count: int = Field(default=12, ge=4, le=40,
                              description="How many stakeholder rows the AI should produce")
    language: Literal["en", "fr"] = Field(default="en")
    branding: BrandingBlock = Field(default_factory=BrandingBlock)


# -----------------------------------------------------------------------------
# #6 Commission-style Impact Assessment
# -----------------------------------------------------------------------------

class GenerateImpactAssessmentRequest(BaseModel):
    """Impact assessment in the European Commission Better Regulation template."""
    initiative_title: str = Field(..., min_length=1, max_length=300)
    policy_area: Optional[str] = Field(None, max_length=200,
                                       description="DG / policy area (e.g. 'DG ENVI', 'Digital Single Market')")
    problem_definition: str = Field(..., min_length=1, max_length=3000,
                                    description="Plain-language description of the problem")
    drivers: List[str] = Field(default_factory=list, max_length=10,
                               description="Causal drivers of the problem")
    objectives_general: Optional[str] = Field(None, max_length=2000)
    objectives_specific: List[str] = Field(default_factory=list, max_length=10)
    baseline_scenario: Optional[str] = Field(None, max_length=2000,
                                             description="What happens if EU takes no further action")
    policy_options: List[str] = Field(
        default_factory=lambda: ["Option 0: Baseline (no EU action)"],
        max_length=8,
        description="Policy options to compare (option 0 = baseline)")
    impact_dimensions: List[str] = Field(
        default_factory=lambda: ["economic", "social", "environmental", "fundamental_rights", "smes"],
        max_length=10,
        description="Dimensions to score in the impact table")
    preferred_option_hint: Optional[str] = Field(None, max_length=400)
    language: Literal["en", "fr"] = Field(default="en")
    style_reference_storage_id: Optional[str] = Field(None, max_length=80)
    branding: BrandingBlock = Field(default_factory=BrandingBlock)


# -----------------------------------------------------------------------------
# #2 Presentation for EU institutions (renders to PPTX)
# -----------------------------------------------------------------------------

PresentationAudience = Literal[
    "commission_official", "commission_cabinet", "mep_office", "ep_committee_staff",
    "council_attache", "permrep", "academic", "industry", "press", "general",
]

class GenerateEUPresentationRequest(BaseModel):
    """Slide deck for an EU-institution audience. Renders to PPTX + PDF."""
    title: str = Field(..., min_length=1, max_length=200)
    subtitle: Optional[str] = Field(None, max_length=240)
    audience: PresentationAudience = Field(default="commission_official")
    audience_label: Optional[str] = Field(None, max_length=200,
                                          description="Free-text refinement, e.g. 'DG ENVI Unit B3'")
    purpose: str = Field(..., min_length=1, max_length=600,
                         description="What this presentation is meant to achieve")
    key_messages: List[str] = Field(default_factory=list, max_length=8,
                                    description="3-7 messages to anchor the deck")
    sections: List[str] = Field(
        default_factory=lambda: ["Context", "Analysis", "Recommendation", "Next steps"],
        max_length=10,
        description="Section headings the deck should follow")
    num_slides: int = Field(default=10, ge=4, le=30)
    language: Literal["en", "fr"] = Field(default="en")
    style_reference_storage_id: Optional[str] = Field(
        None, max_length=80,
        description="storage_document_id of a user-uploaded PPTX/PDF to learn style from")
    branding: BrandingBlock = Field(default_factory=BrandingBlock)


# -----------------------------------------------------------------------------
# #4 Event poster (renders to single-page HTML + PDF + PNG)
# -----------------------------------------------------------------------------

PosterFormat = Literal["a4_portrait", "a4_landscape", "a3_portrait", "instagram_square", "linkedin_landscape"]

class GenerateEventPosterRequest(BaseModel):
    """Single-page event poster on an EU-policy topic."""
    event_title: str = Field(..., min_length=1, max_length=200)
    event_tagline: Optional[str] = Field(None, max_length=200)
    event_date: str = Field(..., min_length=1, max_length=80,
                            description="Human-readable date / time")
    event_location: str = Field(..., min_length=1, max_length=160,
                                description="Venue + city")
    event_type: Literal["conference", "panel", "webinar", "roundtable", "workshop", "launch", "other"] = "panel"
    hosts: List[str] = Field(default_factory=list, max_length=8,
                             description="Hosting organisations")
    speakers: List[str] = Field(default_factory=list, max_length=20,
                                description="One per line: 'Name -- Title, Organisation'")
    agenda_points: List[str] = Field(default_factory=list, max_length=12)
    registration_url: Optional[str] = Field(None, max_length=400)
    contact_info: Optional[str] = Field(None, max_length=300)
    format: PosterFormat = Field(default="a4_portrait")
    accent_color: str = Field(default="#0066cc", max_length=12,
                              description="Hex colour for the poster's brand accent")
    language: Literal["en", "fr"] = Field(default="en")
    style_reference_storage_id: Optional[str] = Field(None, max_length=80)
    branding: BrandingBlock = Field(default_factory=BrandingBlock)


class GeneratePositionPaperRequest(BaseModel):
    """Request to generate a position paper"""
    # Legislative file reference
    legislative_file_id: Optional[str] = Field(None, description="ID of tracked legislative file")
    procedure_reference: Optional[str] = Field(None, description="OEIL procedure reference e.g. 2021/0106(COD)")
    celex_number: Optional[str] = Field(None, description="CELEX number if known")
    legislation_title: str = Field(..., description="Title of the legislation")

    # Position details
    position: PositionStance = Field(..., description="Overall position on the legislation")
    key_asks: List[KeyAsk] = Field(..., min_length=1, max_length=5, description="Key policy asks (1-5)")

    # Document customization
    organisation_name: str = Field(..., description="Name of the organisation")
    organisation_type: OrganisationType = Field(..., description="Type of organisation")
    tone: DocumentTone = Field("constructive", description="Tone of the document")

    # Optional context
    organisation_description: Optional[str] = Field(None, description="Brief description of organisation")
    sector_impact: Optional[str] = Field(None, description="How this affects your sector")
    additional_context: Optional[str] = Field(None, description="Any additional context to include")

    # Output preferences
    include_executive_summary: bool = Field(True)
    include_amendments: bool = Field(True, description="Include specific amendment proposals")
    language: str = Field("EN", description="Output language code")


class GenerateMEPBriefingRequest(BaseModel):
    """Request to generate an MEP briefing note"""
    # Target MEP
    mep_name: str = Field(..., description="Name of the MEP")
    political_group: Optional[str] = Field(None, description="Political group (EPP, S&D, etc.)")
    nationality: Optional[str] = Field(None, description="MEP's nationality")
    committee: Optional[str] = Field(None, description="Relevant committee")

    # Legislative file
    legislative_file_id: Optional[str] = Field(None)
    procedure_reference: Optional[str] = Field(None)
    legislation_title: str = Field(...)

    # Position
    position: PositionStance = Field(...)
    the_ask: str = Field(..., description="The specific action you want the MEP to take")
    key_points: List[str] = Field(..., min_length=1, max_length=5, description="Key points (1-5)")
    voting_recommendation: Optional[str] = Field(None, description="Specific voting recommendation")

    # Organisation
    organisation_name: str = Field(...)
    contact_name: Optional[str] = Field(None)
    contact_email: Optional[str] = Field(None)

    # Customization for MEP
    mep_priorities: Optional[List[str]] = Field(None, description="Known priorities of this MEP")
    national_angle: Optional[str] = Field(None, description="How this affects their country")

    language: str = Field("EN")


class GenerateTalkingPointsRequest(BaseModel):
    """Request to generate talking points for a meeting"""
    # Meeting context
    meeting_with: str = Field(..., description="Who the meeting is with (name/title)")
    meeting_institution: Optional[str] = Field(None, description="Institution (Commission, Parliament, etc.)")
    meeting_purpose: str = Field(..., description="Purpose of the meeting")

    # Topic
    legislative_file_id: Optional[str] = Field(None)
    procedure_reference: Optional[str] = Field(None)
    topic: str = Field(..., description="Main topic of discussion")

    # Key messages
    key_messages: List[str] = Field(..., min_length=1, max_length=5, description="Key messages to convey")
    key_asks: List[str] = Field(..., min_length=1, max_length=3, description="Specific asks for the meeting")

    # Organisation
    organisation_name: str = Field(...)

    # Sensitive topics
    topics_to_avoid: Optional[List[str]] = Field(None, description="Topics to avoid or handle carefully")
    anticipated_questions: Optional[List[str]] = Field(None, description="Questions they might ask")

    language: str = Field("EN")


class GenerateResolutionRequest(BaseModel):
    """Request to generate a European Parliament Resolution draft"""
    # Topic
    topic: str = Field(..., description="Title/topic of the resolution (e.g., 'The situation of human rights in Iran')")

    # Context for recitals
    context_description: str = Field(
        ...,
        description="Background context for generating 'whereas' recitals (A., B., C., ...)"
    )

    # Key demands for resolution points (optional - AI infers from context if not provided)
    key_demands: Optional[List[str]] = Field(
        None,
        max_length=10,
        description="Key demands (each becomes a numbered resolution point with an active verb). Optional - AI infers from context."
    )

    # Optional fields
    procedure_reference: Optional[str] = Field(None, description="Procedure reference if known (e.g., 2025/2500(RSP))")
    additional_references: Optional[List[str]] = Field(
        None,
        description="Specific treaties, regulations, or previous resolutions to cite in 'having regard to' section"
    )

    language: str = Field("EN", description="Output language code")


class GeneratePetitionRequest(BaseModel):
    """Request to generate a petition to the European Parliament (Committee on Petitions, PETI)"""
    topic: str = Field(..., description="Subject of the petition")
    context_description: Optional[str] = Field(
        None,
        description="Background and facts for the petition (optional; the AI keeps unverified facts as bracketed placeholders for the petitioner to complete)"
    )
    petitioner_name: Optional[str] = Field(None, description="Name or organisation of the petitioner")
    language: str = Field("en", description="Language code (en, es, ca, fr, it, nl)")


class GenerateEPQuestionRequest(BaseModel):
    """Request to generate a European Parliament written question"""
    # Topic and addressee
    topic: str = Field(..., description="What the question is about (becomes the title)")
    addressee: Literal["commission", "council", "vp_hr"] = Field(
        "commission", description="Institution addressed: commission, council, or vp_hr"
    )
    question_type: Literal["standard", "priority"] = Field(
        "standard", description="Standard (E-) or priority (P-) question"
    )

    # Context and evidence
    context_description: str = Field(
        ..., description="Background facts, evidence, and concerns to include in the introductory section"
    )
    legislation_references: Optional[List[str]] = Field(
        None, description="Specific EU legislation to cite (e.g., 'Regulation (EU) 2021/2116')"
    )
    sources: Optional[List[str]] = Field(
        None, description="URLs or descriptions of evidence sources (news articles, audits, reports)"
    )

    # Sub-questions
    num_sub_questions: int = Field(
        3, ge=1, le=3, description="Number of sub-questions to generate (1-3)"
    )

    # Optional context
    policy_area: Optional[str] = Field(None, description="Policy area for auto-detecting relevant legislation")
    tone: Literal["assertive", "diplomatic", "technical"] = Field(
        "assertive", description="Tone: assertive (default), diplomatic, or technical"
    )
    procedure_reference: Optional[str] = Field(None, description="OEIL procedure reference if known")
    celex_number: Optional[str] = Field(None, description="CELEX number if known")
    language: str = Field("EN", description="Output language code")


class GeneratedDocument(BaseModel):
    """Response containing generated document"""
    document_type: str = Field(..., description="Type of document generated")
    title: str = Field(..., description="Document title")
    content: str = Field(..., description="Full document content in markdown")
    sections: dict = Field(..., description="Document broken into named sections")

    # Metadata
    generated_at: datetime = Field(default_factory=datetime.now)
    word_count: int = Field(...)
    language: str = Field(...)

    # Context used
    legislative_context: Optional[dict] = Field(None, description="Legislative context that was used")

    # For further editing
    editable_sections: List[str] = Field(..., description="List of section names that can be edited")


class ExportDocumentRequest(BaseModel):
    """Request to export a document to Word/PDF"""
    document_content: str = Field(..., description="Document content in markdown")
    document_title: str = Field(...)
    export_format: Literal["docx", "pdf"] = Field("docx")
    organisation_name: Optional[str] = Field(None)
    include_header: bool = Field(True)
    include_footer: bool = Field(True)
