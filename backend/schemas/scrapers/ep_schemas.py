"""
European Parliament Open Data API Schemas

Pydantic models for EP Open Data Portal API v2:
- Vote Results and Decisions
- MEP Votes
- Speeches
- Parliamentary Questions
- Procedure Events
- Meetings
"""

from datetime import datetime, date
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ============================================================================
# Vote-Related Models
# ============================================================================

class EPVoteResult(BaseModel):
    """Single vote result from a plenary/committee meeting"""
    vote_id: Optional[str] = Field(None, description="Vote identifier")
    sitting_id: str = Field(..., description="Meeting/sitting identifier")
    sitting_date: date = Field(..., description="Date of the vote")

    # Vote subject
    title: Optional[str] = Field(None, description="Title or subject of the vote")
    procedure_reference: Optional[str] = Field(None, description="Legislative procedure reference")
    document_reference: Optional[str] = Field(None, description="Document being voted on")

    # Results
    result: str = Field(..., description="Vote outcome: adopted, rejected, etc.")
    votes_for: Optional[int] = Field(None, description="Number of votes in favour")
    votes_against: Optional[int] = Field(None, description="Number of votes against")
    abstentions: Optional[int] = Field(None, description="Number of abstentions")

    # Additional info
    vote_type: Optional[str] = Field(None, description="Type: final, amendment, procedural")
    amendment_number: Optional[str] = Field(None, description="Amendment number if applicable")
    source_url: Optional[str] = None


class EPMepVote(BaseModel):
    """Individual MEP vote on a specific item"""
    mep_id: str = Field(..., description="MEP identifier")
    mep_name: Optional[str] = None
    political_group: Optional[str] = None
    country: Optional[str] = None

    vote: str = Field(..., description="Vote cast: +, -, 0, absent")
    vote_date: date

    # What was voted on
    vote_id: Optional[str] = None
    procedure_reference: Optional[str] = None
    document_reference: Optional[str] = None
    title: Optional[str] = None


class EPDecision(BaseModel):
    """Meeting decision (broader than just votes)"""
    decision_id: Optional[str] = None
    sitting_id: str
    sitting_date: date

    decision_type: str = Field(..., description="Type of decision")
    title: Optional[str] = None
    description: Optional[str] = None

    # Related documents/procedures
    procedure_reference: Optional[str] = None
    documents: List[str] = Field(default_factory=list)

    outcome: Optional[str] = None
    source_url: Optional[str] = None


# ============================================================================
# Meeting Models
# ============================================================================

class EPMeeting(BaseModel):
    """Parliamentary meeting (plenary session or committee meeting)"""
    meeting_id: str = Field(..., description="Meeting identifier")
    meeting_type: str = Field(..., description="plenary, committee, etc.")

    date: date
    start_time: Optional[str] = None
    end_time: Optional[str] = None

    location: Optional[str] = Field(None, description="Strasbourg, Brussels, etc.")
    committee_code: Optional[str] = Field(None, description="Committee code if committee meeting")

    # Content
    title: Optional[str] = None
    agenda_items: List[Dict[str, Any]] = Field(default_factory=list)

    # Related data
    has_vote_results: bool = False
    has_decisions: bool = False

    source_url: Optional[str] = None


class EPActivity(BaseModel):
    """Activity within a meeting"""
    activity_id: Optional[str] = None
    meeting_id: str
    activity_type: str = Field(..., description="debate, vote, presentation, etc.")

    title: Optional[str] = None
    description: Optional[str] = None

    start_time: Optional[str] = None
    procedure_reference: Optional[str] = None

    # Speakers if applicable
    speakers: List[str] = Field(default_factory=list)


# ============================================================================
# Speech Models
# ============================================================================

class EPSpeech(BaseModel):
    """MEP speech/intervention"""
    speech_id: str = Field(..., description="Speech identifier")

    # Speaker
    mep_id: str
    mep_name: Optional[str] = None
    political_group: Optional[str] = None
    country: Optional[str] = None

    # Context
    meeting_id: Optional[str] = None
    meeting_date: Optional[date] = None
    meeting_type: Optional[str] = Field(None, description="plenary, committee")

    # Content
    title: Optional[str] = None
    text: Optional[str] = Field(None, description="Speech text/transcript")
    language: str = Field(default="en")

    # Related
    procedure_reference: Optional[str] = None
    agenda_item: Optional[str] = None

    # Media
    video_url: Optional[str] = None
    duration_seconds: Optional[int] = None

    source_url: Optional[str] = None


# ============================================================================
# Parliamentary Questions Models
# ============================================================================

class EPParliamentaryQuestion(BaseModel):
    """Written or oral parliamentary question"""
    question_id: str = Field(..., description="Question identifier")
    question_reference: Optional[str] = Field(None, description="Official reference number")

    question_type: str = Field(..., description="written, oral, priority, etc.")

    # Author(s)
    author_mep_ids: List[str] = Field(default_factory=list)
    author_names: List[str] = Field(default_factory=list)
    political_group: Optional[str] = None

    # Addressee
    addressee: str = Field(..., description="Commission, Council, etc.")
    addressee_portfolio: Optional[str] = Field(None, description="Commissioner portfolio")

    # Content
    title: str
    text: Optional[str] = Field(None, description="Question text")
    language: str = Field(default="en")

    # Dates
    date_submitted: Optional[date] = None
    date_answered: Optional[date] = None

    # Answer
    answer_text: Optional[str] = None
    answer_by: Optional[str] = None

    # Related
    procedure_reference: Optional[str] = None
    subjects: List[str] = Field(default_factory=list)

    source_url: Optional[str] = None


# ============================================================================
# Procedure Event Models
# ============================================================================

class EPProcedureEvent(BaseModel):
    """Event in a legislative procedure timeline"""
    event_id: Optional[str] = None
    procedure_reference: str = Field(..., description="e.g., 2025/0102(COD)")

    event_date: date
    event_type: str = Field(..., description="committee_vote, plenary_vote, etc.")

    title: Optional[str] = None
    description: Optional[str] = None

    # Institution
    institution: Optional[str] = Field(None, description="EP, Council, Commission")
    committee_code: Optional[str] = None

    # Outcome
    outcome: Optional[str] = None

    # Related documents
    documents: List[str] = Field(default_factory=list)

    # Links
    meeting_id: Optional[str] = None
    vote_id: Optional[str] = None

    source_url: Optional[str] = None


# ============================================================================
# MEP Declaration Models
# ============================================================================

class EPMepDeclaration(BaseModel):
    """MEP declaration of financial interests"""
    declaration_id: Optional[str] = None
    mep_id: str
    mep_name: Optional[str] = None

    declaration_type: str = Field(..., description="financial_interests, gifts, etc.")
    date_declared: Optional[date] = None

    # Content varies by type
    content: Dict[str, Any] = Field(default_factory=dict)

    source_url: Optional[str] = None


# ============================================================================
# Aggregation Models
# ============================================================================

class EPVotingRecord(BaseModel):
    """Complete voting record for a procedure or MEP"""
    # Context
    procedure_reference: Optional[str] = None
    mep_id: Optional[str] = None

    # Period
    date_from: Optional[date] = None
    date_to: Optional[date] = None

    # Votes
    total_votes: int = 0
    votes: List[EPMepVote] = Field(default_factory=list)

    # Statistics
    votes_for: int = 0
    votes_against: int = 0
    abstentions: int = 0
    absences: int = 0

    generated_at: datetime = Field(default_factory=datetime.now)


class EPProcedureTimeline(BaseModel):
    """Complete timeline for a legislative procedure from EP perspective"""
    procedure_reference: str
    process_id: Optional[str] = Field(None, description="EP internal process ID")

    title: Optional[str] = None
    procedure_type: Optional[str] = None

    # Events
    events: List[EPProcedureEvent] = Field(default_factory=list)

    # Key dates
    committee_vote_date: Optional[date] = None
    plenary_vote_date: Optional[date] = None

    # Key players
    rapporteur_mep_id: Optional[str] = None
    rapporteur_name: Optional[str] = None
    committee_responsible: Optional[str] = None

    # Status
    current_stage: Optional[str] = None

    source_url: Optional[str] = None
    generated_at: datetime = Field(default_factory=datetime.now)
