"""
EP Committee Meeting Transcript Database Model.

Stores AI-generated transcripts of EP committee meeting recordings
from the EP Multimedia Centre (multimedia.europarl.europa.eu).

Transcription pipeline: discover meeting -> download audio (ffmpeg) ->
transcribe (OpenAI Whisper API) -> map agenda items -> store.

Created: April 2026
"""

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Enum, JSON, Text,
    ForeignKey, Index, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from datetime import datetime
import enum
import uuid

from core.database import Base


class TranscriptStatusEnum(str, enum.Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class CommitteeMeetingTranscript(Base):
    """
    AI-transcribed EP committee meeting record.

    One record per committee meeting per event_id.
    Source: EP Multimedia Centre webstreaming recordings.
    Transcription: OpenAI Whisper API (verbose_json for timestamps).
    """
    __tablename__ = "committee_meeting_transcripts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Core identifiers
    committee_code = Column(String(20), nullable=False)       # "LIBE", "ENVI", "IMCOJURIPETI"
    meeting_date = Column(DateTime, nullable=False)
    title = Column(String, nullable=False)                     # "ENVI Committee Meeting - 14 April 2026"

    # Source (EP Multimedia Centre)
    multimedia_url = Column(String)                            # URL to EP multimedia page
    video_url = Column(String)                                 # Direct video/audio URL
    event_id = Column(String)                                  # EP multimedia event identifier

    # Transcription output
    transcript_text = Column(Text)                             # Full raw transcript
    transcript_segments = Column(JSON, default=list)           # [{start, end, text, speaker_label}]
    word_count = Column(Integer)
    duration_seconds = Column(Integer)                         # Meeting duration
    language = Column(String(5), default="EN")                 # Original language

    # Agenda mapping
    agenda_items = Column(JSON, default=list)                  # [{title, start_time, end_time, procedure_refs}]
    related_procedure_refs = Column(ARRAY(String), default=list)  # All procedure refs discussed

    # Speaker data (v2: full diarization)
    speakers = Column(JSON, default=list)                      # [{label, name, group, segments_count}]
    speaker_count = Column(Integer)

    # Processing status
    status = Column(
        Enum(TranscriptStatusEnum, name="transcript_status_enum", create_type=False),
        nullable=False,
        default=TranscriptStatusEnum.PENDING,
    )
    transcription_cost = Column(Float)                         # Cost in USD
    transcription_model = Column(String, default="whisper-1")  # Model used
    error_message = Column(Text)

    # Link to published committee minutes (when available)
    committee_minutes_id = Column(
        UUID(as_uuid=True),
        ForeignKey("committee_minutes.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Temporal
    transcribed_at = Column(DateTime)
    first_seen = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint('committee_code', 'meeting_date', 'event_id',
                         name='uq_committee_transcript_code_date_event'),
        Index('ix_committee_transcript_committee_code', 'committee_code'),
        Index('ix_committee_transcript_meeting_date', 'meeting_date'),
        Index('ix_committee_transcript_status', 'status'),
        Index('ix_committee_transcript_procedure_refs', 'related_procedure_refs',
              postgresql_using='gin'),
    )

    def __repr__(self):
        return f"<CommitteeMeetingTranscript {self.committee_code} {self.meeting_date} [{self.status}]>"
