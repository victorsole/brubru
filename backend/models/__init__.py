"""
Models Package

SQLAlchemy models for Brubru application.
"""

from .user import User
from .api_key import ApiKey
from .rss_feed import RSSFeed
from .rss_entry import RSSEntry
from .user_feed_subscription import UserFeedSubscription
from .user_feed_read import UserFeedRead
from .user_saved_entry import UserSavedEntry
from .user_document import UserDocument
from .notification import Notification
from .chat_example_prompt import ChatExamplePrompt
from .legislative_train import LegislativeTrain, LegislativeCarriage
from .amendment import Amendment
from .tender import Tender, TenderProfile, TenderMatch, TenderFetchJob
from .committee_work import (
    CommitteeWorkItem,
    UserCommitteeWorkTrack,
    CommitteeWorkStatusHistory,
    ProcedureTypeEnum,
    CommitteeRoleEnum,
    CommitteeWorkStatusEnum,
)
from .public_consultation import (
    PublicConsultation,
    ConsultationDocument,
    UserConsultationTrack,
    UserConsultationInput,
    ConsultationStatusHistory,
    ConsultationTypeEnum,
    ConsultationStatusEnum,
    DocumentTypeEnum,
)
from .mep_amendment import AmendmentDocument, MEPAmendment
from .alignment_score import AlignmentScore
from .eprs_publication import EPRSPublication, EPRSPublicationTypeEnum
from .catalan_translation import CatalanTranslation
from .committee_minutes import CommitteeMinutes
from .eu_calendar import (
    EUCalendarEvent,
    UserCalendarSubscription,
    InstitutionEnum,
    EventTypeEnum,
    EventStatusEnum,
    ReminderPeriodEnum,
)

__all__ = [
    "User",
    "RSSFeed",
    "RSSEntry",
    "UserFeedSubscription",
    "UserFeedRead",
    "UserSavedEntry",
    "UserDocument",
    "Notification",
    "ChatExamplePrompt",
    "LegislativeTrain",
    "LegislativeCarriage",
    "Amendment",
    "Tender",
    "TenderProfile",
    "TenderMatch",
    "TenderFetchJob",
    "CommitteeWorkItem",
    "UserCommitteeWorkTrack",
    "CommitteeWorkStatusHistory",
    "ProcedureTypeEnum",
    "CommitteeRoleEnum",
    "CommitteeWorkStatusEnum",
    "PublicConsultation",
    "ConsultationDocument",
    "UserConsultationTrack",
    "UserConsultationInput",
    "ConsultationStatusHistory",
    "ConsultationTypeEnum",
    "ConsultationStatusEnum",
    "DocumentTypeEnum",
    "AmendmentDocument",
    "MEPAmendment",
    "AlignmentScore",
    "EPRSPublication",
    "EPRSPublicationTypeEnum",
    "EUCalendarEvent",
    "UserCalendarSubscription",
    "InstitutionEnum",
    "EventTypeEnum",
    "EventStatusEnum",
    "ReminderPeriodEnum",
    "CatalanTranslation",
    "CommitteeMinutes",
]
