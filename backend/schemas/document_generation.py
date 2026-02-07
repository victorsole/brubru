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
