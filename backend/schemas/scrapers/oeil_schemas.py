"""
OEIL Procedure Schemas

Pydantic models for OEIL Legislative Observatory procedure data.
Covers all 7 sections of an OEIL procedure page:
1. Basic Information
2. Key Players
3. Key Events
4. Forecasts
5. Technical Information
6. Documentation Gateway
7. Additional Information
"""

from datetime import datetime, date
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl


# ============================================================================
# Supporting Models
# ============================================================================

class OEILMep(BaseModel):
    """MEP extracted from OEIL procedure page"""
    mep_id: Optional[str] = Field(None, description="MEP ID from URL path")
    name: str = Field(..., description="Full name")
    political_group: Optional[str] = Field(None, description="Political group code (EPP, S&D, etc.)")
    photo_url: Optional[str] = Field(None, description="Photo URL from data-title attribute")
    profile_url: Optional[str] = Field(None, description="Full profile URL")


class OEILCommittee(BaseModel):
    """Committee information from OEIL"""
    code: str = Field(..., description="Committee code (e.g., IMCO, LIBE)")
    name: Optional[str] = Field(None, description="Full committee name")
    role: str = Field(..., description="responsible, opinion, associated")
    rapporteur: Optional[OEILMep] = None
    shadow_rapporteurs: List[OEILMep] = Field(default_factory=list)
    former_rapporteur: Optional[OEILMep] = None
    date_announced: Optional[date] = None
    decision_date: Optional[date] = None


class OEILDocument(BaseModel):
    """Document reference from OEIL"""
    reference: str = Field(..., description="Document reference (e.g., COM(2024)0236)")
    title: Optional[str] = None
    doc_type: Optional[str] = Field(None, description="Document type")
    date: Optional[date] = None
    url: Optional[str] = None
    pdf_url: Optional[str] = None


class OEILEvent(BaseModel):
    """Key event in legislative procedure"""
    date: date
    event_type: str = Field(..., description="Event type (e.g., Legislative proposal)")
    description: Optional[str] = None
    summary: Optional[str] = Field(None, description="Detailed summary if available")
    documents: List[OEILDocument] = Field(default_factory=list)
    result: Optional[str] = Field(None, description="Vote result or outcome")


class OEILForecast(BaseModel):
    """Forecast/upcoming event"""
    event_type: str = Field(..., description="Foreseen event type")
    forecast_date: Optional[date] = None
    committee: Optional[str] = Field(None, description="Committee code if applicable")
    location: Optional[str] = Field(None, description="Plenary or committee")
    notes: Optional[str] = None


class OEILLegalBasis(BaseModel):
    """Legal basis reference"""
    treaty: str = Field(..., description="Treaty (e.g., TFEU)")
    article: str = Field(..., description="Article reference")
    url: Optional[str] = None


class OEILConsultativeBody(BaseModel):
    """Consultative body opinion (EESC, CoR)"""
    body: str = Field(..., description="Body name (EESC, CoR)")
    opinion_mandatory: bool = False
    opinion_date: Optional[date] = None
    rapporteur: Optional[str] = None


class OEILNationalParliamentContribution(BaseModel):
    """National parliament contribution"""
    parliament: str = Field(..., description="Parliament name")
    chamber: Optional[str] = None
    contribution_type: str = Field(..., description="e.g., Reasoned opinion")
    date: Optional[date] = None
    url: Optional[str] = None


# ============================================================================
# Section Models
# ============================================================================

class OEILBasicInfo(BaseModel):
    """Section 1: Basic Information"""
    reference: str = Field(..., description="Procedure reference (e.g., 2024/0176(COD))")
    title: Optional[str] = None
    procedure_type: Optional[str] = Field(None, description="Full procedure type description")
    procedure_type_code: Optional[str] = Field(None, description="COD, CNS, APP, etc.")
    status: Optional[str] = Field(None, description="Current status text")
    subjects: List[str] = Field(default_factory=list, description="Subject matter tags")
    legislative_priorities: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Priority links with text and url"
    )


class OEILKeyPlayers(BaseModel):
    """Section 2: Key Players"""
    # European Parliament
    committee_responsible: Optional[OEILCommittee] = None
    committees_opinion: List[OEILCommittee] = Field(default_factory=list)
    committees_associated: List[OEILCommittee] = Field(default_factory=list)

    # European Commission
    commission_dg: Optional[str] = Field(None, description="Responsible DG")
    commissioner: Optional[str] = None

    # Council
    council_configuration: Optional[str] = None

    # Consultative bodies
    eesc: Optional[OEILConsultativeBody] = None
    cor: Optional[OEILConsultativeBody] = None


class OEILKeyEvents(BaseModel):
    """Section 3: Key Events"""
    events: List[OEILEvent] = Field(default_factory=list)


class OEILForecasts(BaseModel):
    """Section 4: Forecasts"""
    forecasts: List[OEILForecast] = Field(default_factory=list)


class OEILTechnicalInfo(BaseModel):
    """Section 5: Technical Information"""
    reference: str
    procedure_type: Optional[str] = None
    procedure_subtype: Optional[str] = None
    legal_basis: List[OEILLegalBasis] = Field(default_factory=list)
    stage_reached: Optional[str] = None

    # External references
    commission_reference: Optional[str] = None
    council_reference: Optional[str] = None

    # Additional metadata
    modified_legal_basis: Optional[str] = None
    mandatory_consultation: List[str] = Field(default_factory=list)


class OEILDocumentation(BaseModel):
    """Section 6: Documentation Gateway"""
    ep_documents: List[OEILDocument] = Field(default_factory=list)
    commission_documents: List[OEILDocument] = Field(default_factory=list)
    council_documents: List[OEILDocument] = Field(default_factory=list)
    other_documents: List[OEILDocument] = Field(default_factory=list)
    national_parliament_contributions: List[OEILNationalParliamentContribution] = Field(
        default_factory=list
    )


class OEILAdditionalInfo(BaseModel):
    """Section 7: Additional Information"""
    eurlex_url: Optional[str] = None
    celex_number: Optional[str] = None
    related_procedures: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Related procedure references with title and url"
    )
    other_links: List[Dict[str, str]] = Field(default_factory=list)


# ============================================================================
# Main Procedure Model
# ============================================================================

class OEILProcedure(BaseModel):
    """
    Complete OEIL Legislative Procedure

    Contains all 7 sections from an OEIL procedure page.
    """
    # Metadata
    source_url: str = Field(..., description="OEIL page URL")
    scraped_at: datetime = Field(default_factory=datetime.now)
    language: str = Field(default="en")

    # All 7 sections
    basic_info: OEILBasicInfo
    key_players: OEILKeyPlayers = Field(default_factory=OEILKeyPlayers)
    key_events: OEILKeyEvents = Field(default_factory=OEILKeyEvents)
    forecasts: OEILForecasts = Field(default_factory=OEILForecasts)
    technical_info: Optional[OEILTechnicalInfo] = None
    documentation: OEILDocumentation = Field(default_factory=OEILDocumentation)
    additional_info: OEILAdditionalInfo = Field(default_factory=OEILAdditionalInfo)

    # Convenience accessors
    @property
    def reference(self) -> str:
        return self.basic_info.reference

    @property
    def title(self) -> Optional[str]:
        return self.basic_info.title

    @property
    def status(self) -> Optional[str]:
        return self.basic_info.status

    @property
    def rapporteur(self) -> Optional[OEILMep]:
        if self.key_players.committee_responsible:
            return self.key_players.committee_responsible.rapporteur
        return None

    @property
    def committee_responsible_code(self) -> Optional[str]:
        if self.key_players.committee_responsible:
            return self.key_players.committee_responsible.code
        return None

    class Config:
        json_schema_extra = {
            "example": {
                "source_url": "https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference=2024/0176(COD)&l=en",
                "basic_info": {
                    "reference": "2024/0176(COD)",
                    "title": "Artificial intelligence act, amendment",
                    "procedure_type": "COD - Ordinary legislative procedure",
                    "status": "Awaiting committee decision"
                }
            }
        }
