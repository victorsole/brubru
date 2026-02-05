"""
EP Voting Schemas - API Response Models

Pydantic schemas for EP voting data API responses.
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field


# --- Enums ---

class VotePosition(str, Enum):
    FOR = "FOR"
    AGAINST = "AGAINST"
    ABSTENTION = "ABSTENTION"
    DID_NOT_VOTE = "DID_NOT_VOTE"


class VoteResult(str, Enum):
    ADOPTED = "ADOPTED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


class ProcedureType(str, Enum):
    COD = "COD"
    CNS = "CNS"
    APP = "APP"
    NLE = "NLE"
    INI = "INI"
    INL = "INL"
    RSP = "RSP"
    BUD = "BUD"
    DEC = "DEC"
    OTHER = "OTHER"


# --- Political Groups ---

class EPPoliticalGroupBase(BaseModel):
    code: str
    official_label: str
    label: str
    short_label: Optional[str] = None


class EPPoliticalGroupResponse(EPPoliticalGroupBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Sections ---

class EPSectionBase(BaseModel):
    group_code: str
    code: str
    name: str
    description: Optional[str] = None


class EPSectionResponse(EPSectionBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Delegations ---

class EPDelegationBase(BaseModel):
    group_code: str
    country_code: str
    name: str
    parties_included: Optional[List[str]] = None
    num_meps: int = 0
    delegation_chair: Optional[str] = None
    notes: Optional[str] = None


class EPDelegationResponse(EPDelegationBase):
    id: UUID
    section_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- MEPs ---

class EPMemberBase(BaseModel):
    first_name: str
    last_name: str
    full_name: str
    country_code: str
    date_of_birth: Optional[date] = None
    national_party: Optional[str] = None
    national_party_abbrev: Optional[str] = None
    email: Optional[str] = None
    twitter: Optional[str] = None
    facebook: Optional[str] = None


class EPMemberSummary(BaseModel):
    """Minimal MEP info for list views"""
    id: UUID
    htv_id: int
    full_name: str
    country_code: str
    current_group_code: Optional[str] = None
    national_party_abbrev: Optional[str] = None
    is_active: bool = True

    class Config:
        from_attributes = True


class EPMemberResponse(EPMemberBase):
    id: UUID
    htv_id: int
    ep_id: Optional[int] = None
    current_group_code: Optional[str] = None
    delegation_id: Optional[UUID] = None
    is_active: bool = True
    term: int = 10
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EPMemberDetailResponse(EPMemberResponse):
    """Full MEP detail with group history"""
    group_memberships: List["EPGroupMembershipResponse"] = []
    recent_votes: List["EPMemberVoteSummary"] = []


# --- Group Memberships ---

class EPGroupMembershipBase(BaseModel):
    group_code: str
    term: int
    start_date: date
    end_date: Optional[date] = None


class EPGroupMembershipResponse(EPGroupMembershipBase):
    id: UUID
    member_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


# --- Votes ---

class EPVoteBase(BaseModel):
    timestamp: datetime
    display_title: str
    reference: Optional[str] = None
    description: Optional[str] = None
    amendment_subject: Optional[str] = None
    amendment_number: Optional[str] = None
    is_main: bool = False
    procedure_reference: Optional[str] = None
    procedure_title: Optional[str] = None
    procedure_type: Optional[ProcedureType] = None
    procedure_stage: Optional[str] = None


class EPVoteSummary(BaseModel):
    """Minimal vote info for list views"""
    id: UUID
    htv_id: int
    timestamp: datetime
    display_title: str
    reference: Optional[str] = None
    procedure_reference: Optional[str] = None
    is_main: bool = False
    count_for: int = 0
    count_against: int = 0
    count_abstention: int = 0
    result: VoteResult = VoteResult.UNKNOWN

    class Config:
        from_attributes = True


class EPVoteResponse(EPVoteBase):
    id: UUID
    htv_id: int
    count_for: int = 0
    count_against: int = 0
    count_abstention: int = 0
    count_did_not_vote: int = 0
    result: VoteResult = VoteResult.UNKNOWN
    texts_adopted_reference: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @property
    def total_votes(self) -> int:
        return self.count_for + self.count_against + self.count_abstention

    @property
    def participation_rate(self) -> float:
        total = self.total_votes + self.count_did_not_vote
        return self.total_votes / total if total > 0 else 0.0


class EPVoteDetailResponse(EPVoteResponse):
    """Full vote detail with breakdown by group"""
    group_breakdown: Dict[str, Dict[str, int]] = {}
    country_breakdown: Dict[str, Dict[str, int]] = {}
    committee_codes: List[str] = []


# --- Member Votes ---

class EPMemberVoteBase(BaseModel):
    position: VotePosition
    country_code: str
    group_code: str


class EPMemberVoteSummary(BaseModel):
    """Minimal member vote for list views"""
    vote_id: UUID
    member_id: UUID
    position: VotePosition
    vote_title: Optional[str] = None
    vote_date: Optional[datetime] = None

    class Config:
        from_attributes = True


class EPMemberVoteResponse(EPMemberVoteBase):
    id: UUID
    vote_id: UUID
    member_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


# --- List Responses ---

class EPMembersListResponse(BaseModel):
    items: List[EPMemberSummary]
    total: int
    limit: int
    offset: int


class EPVotesListResponse(BaseModel):
    items: List[EPVoteSummary]
    total: int
    limit: int
    offset: int


class EPGroupsListResponse(BaseModel):
    items: List[EPPoliticalGroupResponse]
    total: int


# --- Import/Sync ---

class ImportResultResponse(BaseModel):
    """Result of a data import operation"""
    source: str
    import_type: str
    status: str
    records_processed: int = 0
    records_added: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    errors: int = 0
    duration_seconds: float = 0.0
    error_details: Optional[List[str]] = None


class SyncAllResultResponse(BaseModel):
    """Result of full sync operation"""
    groups: ImportResultResponse
    members: ImportResultResponse
    group_memberships: ImportResultResponse
    votes: ImportResultResponse
    member_votes: ImportResultResponse
    total_duration_seconds: float = 0.0


# --- Voting Statistics ---

class MEPVotingStats(BaseModel):
    """Voting statistics for an MEP"""
    mep_id: UUID
    total_votes: int = 0
    votes_for: int = 0
    votes_against: int = 0
    votes_abstention: int = 0
    did_not_vote: int = 0
    participation_rate: float = 0.0
    loyalty_rate: float = 0.0  # % aligned with group majority


class GroupVotingStats(BaseModel):
    """Voting statistics for a political group"""
    group_code: str
    total_votes: int = 0
    cohesion_rate: float = 0.0  # % of members voting same way
    participation_rate: float = 0.0


# Forward refs
EPMemberDetailResponse.model_rebuild()
