"""
Feature Extractor - Phase 2.1

Extracts ML features from legislative carriages for timeline and outcome prediction.

Features extracted:
- Procedure characteristics (type, lead committee, text type)
- Political context (rapporteur group, committee composition)
- Temporal features (days in status, month, year)
- Complexity indicators (number of committees, amendments)
- Historical patterns (similar procedure outcomes)
"""

import logging
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import func

from core.database import SessionLocal

logger = logging.getLogger(__name__)


# Feature categories for organization
class FeatureCategory(str, Enum):
    PROCEDURE = "procedure"
    POLITICAL = "political"
    TEMPORAL = "temporal"
    COMPLEXITY = "complexity"
    HISTORICAL = "historical"


@dataclass
class CarriageFeatures:
    """
    Feature vector for a legislative carriage.

    All features are numeric or categorical (encoded as strings).
    """
    # Identifiers (not features, for reference)
    carriage_id: str
    procedure_ref: Optional[str] = None

    # Procedure features
    procedure_type: str = "UNKNOWN"  # COD, CNS, APP, etc.
    text_type: str = "unknown"  # legislative, non_legislative
    is_recast: bool = False
    is_codification: bool = False

    # Committee features
    lead_committee: str = "UNKNOWN"
    num_opinion_committees: int = 0
    total_committees: int = 0

    # Political features (filled from EP data if available)
    rapporteur_group: Optional[str] = None
    rapporteur_country: Optional[str] = None
    has_rapporteur: bool = False

    # Temporal features
    days_in_current_status: int = 0
    days_since_first_seen: int = 0
    month_of_year: int = 1  # 1-12
    quarter: int = 1  # 1-4
    is_election_year: bool = False
    is_pre_summer_break: bool = False  # May-July
    is_end_of_term: bool = False  # Last year before EP elections

    # Status features
    current_status: str = "announced"
    num_status_changes: int = 0
    avg_days_per_status: float = 0.0

    # Complexity indicators
    title_length: int = 0
    title_word_count: int = 0
    has_celex: bool = False
    num_celex_refs: int = 0
    has_eprs_briefing: bool = False
    num_policy_areas: int = 0

    # EC Priority features
    ec_priority_number: Optional[int] = None
    is_spotlight: bool = False

    # Historical/similar procedure features
    similar_adoption_rate: Optional[float] = None  # % of similar procedures adopted
    similar_avg_days: Optional[float] = None  # Avg days for similar procedures

    # --- Phase 3 trajectory features (from procedure_snapshots) ---------------
    # The first signals the predictor ever gets about ACTIVITY and its trend, not just
    # static metadata. Default 0 (graceful) when the carriage has no snapshots yet.
    snapshot_history_len: int = 0          # how many snapshots we hold for this carriage
    total_procedural_events: int = 0       # cumulative OEIL key-events (real, from snapshots)
    events_last_90d: int = 0               # procedural events in the last 90 days (recent velocity)
    events_last_180d: int = 0
    event_acceleration: int = 0            # events_last_90d minus the prior 90-day window
    avg_days_between_events: float = 0.0   # mean gap between milestones (cadence)
    days_since_last_event: int = 0         # staleness: days since the latest milestone
    # measured fast-signal counts (NEW to the predictor — it had none of these)
    num_amendments: int = 0
    num_commission_documents: int = 0
    num_committee_work: int = 0
    num_lobby_meetings: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for ML processing."""
        return asdict(self)

    def get_numeric_features(self) -> Dict[str, float]:
        """Get only numeric features for ML models."""
        d = self.to_dict()
        numeric = {}
        for k, v in d.items():
            if isinstance(v, (int, float)):
                numeric[k] = float(v)
            elif isinstance(v, bool):
                numeric[k] = 1.0 if v else 0.0
        return numeric

    def get_categorical_features(self) -> Dict[str, str]:
        """Get categorical features for encoding."""
        d = self.to_dict()
        categorical = {}
        for k, v in d.items():
            if isinstance(v, str) and k not in ('carriage_id', 'procedure_ref'):
                categorical[k] = v
        return categorical


class FeatureExtractor:
    """
    Extracts ML features from legislative carriages.

    Usage:
        extractor = FeatureExtractor()
        features = extractor.extract_features(carriage)
        # or
        all_features = extractor.extract_all_features(status_filter=['ADOPTED', 'WITHDRAWN'])
    """

    # EP election years (for temporal features)
    EP_ELECTION_YEARS = {2019, 2024, 2029}

    # Procedure type weights (for complexity estimation)
    PROCEDURE_COMPLEXITY = {
        'COD': 1.0,  # Ordinary legislative - most complex
        'APP': 0.8,  # Consent
        'CNS': 0.6,  # Consultation
        'NLE': 0.4,  # Non-legislative
        'INI': 0.3,  # Own-initiative
        'RSP': 0.2,  # Resolution
    }

    def __init__(self, db: Optional[Session] = None):
        self._db = db
        self._owns_db = db is None
        self._committee_stats_cache: Dict[str, Dict] = {}

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def close(self):
        """Close database session if we own it."""
        if self._owns_db and self._db:
            self._db.close()
            self._db = None

    def _extract_procedure_type(self, procedure_ref: Optional[str]) -> str:
        """Extract procedure type from OEIL reference."""
        if not procedure_ref:
            return "UNKNOWN"
        match = re.search(r"\(([A-Z]{3})\)", procedure_ref)
        return match.group(1) if match else "UNKNOWN"

    def _extract_year(self, procedure_ref: Optional[str]) -> Optional[int]:
        """Extract year from OEIL reference."""
        if not procedure_ref:
            return None
        match = re.search(r"(\d{4})/", procedure_ref)
        return int(match.group(1)) if match else None

    def _is_recast(self, title: str) -> bool:
        """Check if title indicates a recast."""
        recast_keywords = ['recast', 'recasting', 'codification', 'codifying']
        title_lower = title.lower()
        return any(kw in title_lower for kw in recast_keywords)

    def _is_codification(self, title: str) -> bool:
        """Check if title indicates a codification."""
        return 'codification' in title.lower() or 'codifying' in title.lower()

    def _get_temporal_features(self, carriage) -> Dict[str, Any]:
        """Extract temporal features from carriage."""
        now = datetime.now(timezone.utc)

        # Days calculations
        days_in_status = carriage.days_in_current_status or 0

        first_seen = carriage.first_seen
        if first_seen:
            if first_seen.tzinfo is None:
                first_seen = first_seen.replace(tzinfo=timezone.utc)
            days_since_first_seen = (now - first_seen).days
        else:
            days_since_first_seen = days_in_status

        # Current time features
        month = now.month
        quarter = (month - 1) // 3 + 1
        year = now.year

        # Calendar-based features
        is_election_year = year in self.EP_ELECTION_YEARS
        is_pre_summer = month in (5, 6, 7)
        is_end_of_term = year in {y - 1 for y in self.EP_ELECTION_YEARS}

        return {
            'days_in_current_status': days_in_status,
            'days_since_first_seen': days_since_first_seen,
            'month_of_year': month,
            'quarter': quarter,
            'is_election_year': is_election_year,
            'is_pre_summer_break': is_pre_summer,
            'is_end_of_term': is_end_of_term,
        }

    def _get_status_features(self, carriage) -> Dict[str, Any]:
        """Extract status-related features."""
        status_history = carriage.status_history or []
        num_changes = len(status_history)

        # Calculate average days per status
        total_days = 0
        for entry in status_history:
            if isinstance(entry, dict) and 'duration_days' in entry:
                total_days += entry.get('duration_days', 0)

        avg_days = total_days / num_changes if num_changes > 0 else 0

        current_status = carriage.current_status
        if hasattr(current_status, 'value'):
            current_status = current_status.value

        return {
            'current_status': current_status,
            'num_status_changes': num_changes,
            'avg_days_per_status': avg_days,
        }

    def _get_complexity_features(self, carriage) -> Dict[str, Any]:
        """Extract complexity indicator features."""
        title = carriage.title or ""

        return {
            'title_length': len(title),
            'title_word_count': len(title.split()),
            'has_celex': bool(carriage.celex_numbers),
            'num_celex_refs': len(carriage.celex_numbers or []),
            'has_eprs_briefing': bool(carriage.eprs_briefing_ids),
            'num_policy_areas': len(carriage.policy_areas or []),
        }

    def _get_committee_features(self, carriage) -> Dict[str, Any]:
        """Extract committee-related features."""
        return {
            'lead_committee': carriage.lead_committee or "UNKNOWN",
            'num_opinion_committees': len(carriage.opinion_committees or []),
            'total_committees': len(carriage.committees or []),
        }

    # default-zero trajectory block (no snapshots yet -> graceful, never None)
    _EMPTY_TRAJECTORY = {
        'snapshot_history_len': 0, 'total_procedural_events': 0,
        'events_last_90d': 0, 'events_last_180d': 0, 'event_acceleration': 0,
        'avg_days_between_events': 0.0, 'days_since_last_event': 0,
        'num_amendments': 0, 'num_commission_documents': 0,
        'num_committee_work': 0, 'num_lobby_meetings': 0,
    }

    def _get_trajectory_features(self, carriage) -> Dict[str, Any]:
        """Trajectory features from procedure_snapshots: procedural-event velocity /
        acceleration / cadence (real, reconstructed) plus the latest measured fast-signal
        counts. All default 0 when the carriage has no snapshots, so the predictor degrades
        gracefully on cold rows."""
        from models.procedure_snapshot import ProcedureSnapshot

        rows = (
            self.db.query(ProcedureSnapshot)
            .filter(ProcedureSnapshot.carriage_id == carriage.id)
            .order_by(ProcedureSnapshot.snapshot_date.asc())
            .all()
        )
        if not rows:
            return dict(self._EMPTY_TRAJECTORY)

        feats = dict(self._EMPTY_TRAJECTORY)
        feats['snapshot_history_len'] = len(rows)
        feats['total_procedural_events'] = max((r.num_status_changes or 0) for r in rows)

        # event dates = the distinct snapshot dates that represent a milestone (bootstrap
        # rows are one-per-event; the daily row reuses the latest date). Use all dates.
        dates = sorted({r.snapshot_date for r in rows})
        latest = dates[-1]
        feats['days_since_last_event'] = max((latest - dates[-1]).days, 0)  # 0 by def; kept explicit

        # the daily (measured) row carries the live counts and the real days_since_last_event
        daily = [r for r in rows if r.snapshot_source == 'daily']
        if daily:
            d = daily[-1]
            feats['days_since_last_event'] = d.days_in_current_status or 0
            feats['num_amendments'] = d.num_amendments or 0
            feats['num_commission_documents'] = d.num_documents or 0
            feats['num_committee_work'] = d.num_committee_work or 0
            feats['num_lobby_meetings'] = d.num_lobby_meetings or 0

        # event-timeline windows: count milestone dates inside [latest-90, latest] etc.
        event_dates = sorted({r.snapshot_date for r in rows if r.snapshot_source == 'bootstrap'})
        if event_dates:
            w90 = sum(1 for dt in event_dates if (latest - dt).days <= 90)
            w180 = sum(1 for dt in event_dates if (latest - dt).days <= 180)
            prior90 = sum(1 for dt in event_dates if 90 < (latest - dt).days <= 180)
            feats['events_last_90d'] = w90
            feats['events_last_180d'] = w180
            feats['event_acceleration'] = w90 - prior90
            if len(event_dates) > 1:
                span = (event_dates[-1] - event_dates[0]).days
                feats['avg_days_between_events'] = round(span / (len(event_dates) - 1), 1)
        return feats

    def _get_ec_features(self, carriage) -> Dict[str, Any]:
        """Extract EC priority features."""
        ec_priority = None
        if carriage.ec_priority_ids:
            # Try to extract priority number
            for p in carriage.ec_priority_ids:
                match = re.search(r'(\d+)', str(p))
                if match:
                    ec_priority = int(match.group(1))
                    break

        is_spotlight = bool(carriage.spotlight_tags)

        return {
            'ec_priority_number': ec_priority,
            'is_spotlight': is_spotlight,
        }

    def extract_features(self, carriage) -> CarriageFeatures:
        """
        Extract all features from a single carriage.

        Args:
            carriage: LegislativeCarriage model instance

        Returns:
            CarriageFeatures dataclass with all extracted features
        """
        procedure_ref = carriage.oeil_procedure_ref
        proc_type = self._extract_procedure_type(procedure_ref)

        # Get text type
        text_type = carriage.text_type
        if hasattr(text_type, 'value'):
            text_type = text_type.value
        text_type = text_type or "unknown"

        # Temporal features
        temporal = self._get_temporal_features(carriage)

        # Status features
        status = self._get_status_features(carriage)

        # Complexity features
        complexity = self._get_complexity_features(carriage)

        # Committee features
        committee = self._get_committee_features(carriage)

        # EC features
        ec = self._get_ec_features(carriage)

        # Phase 3 trajectory features (procedure_snapshots)
        traj = self._get_trajectory_features(carriage)

        # Title-based features
        title = carriage.title or ""
        is_recast = self._is_recast(title)
        is_codification = self._is_codification(title)

        # Rapporteur features (basic - can be enriched with EP data)
        has_rapporteur = bool(carriage.rapporteur_mep_id)

        return CarriageFeatures(
            carriage_id=str(carriage.id),
            procedure_ref=procedure_ref,
            procedure_type=proc_type,
            text_type=text_type,
            is_recast=is_recast,
            is_codification=is_codification,
            lead_committee=committee['lead_committee'],
            num_opinion_committees=committee['num_opinion_committees'],
            total_committees=committee['total_committees'],
            has_rapporteur=has_rapporteur,
            days_in_current_status=temporal['days_in_current_status'],
            days_since_first_seen=temporal['days_since_first_seen'],
            month_of_year=temporal['month_of_year'],
            quarter=temporal['quarter'],
            is_election_year=temporal['is_election_year'],
            is_pre_summer_break=temporal['is_pre_summer_break'],
            is_end_of_term=temporal['is_end_of_term'],
            current_status=status['current_status'],
            num_status_changes=status['num_status_changes'],
            avg_days_per_status=status['avg_days_per_status'],
            title_length=complexity['title_length'],
            title_word_count=complexity['title_word_count'],
            has_celex=complexity['has_celex'],
            num_celex_refs=complexity['num_celex_refs'],
            has_eprs_briefing=complexity['has_eprs_briefing'],
            num_policy_areas=complexity['num_policy_areas'],
            ec_priority_number=ec['ec_priority_number'],
            is_spotlight=ec['is_spotlight'],
            snapshot_history_len=traj['snapshot_history_len'],
            total_procedural_events=traj['total_procedural_events'],
            events_last_90d=traj['events_last_90d'],
            events_last_180d=traj['events_last_180d'],
            event_acceleration=traj['event_acceleration'],
            avg_days_between_events=traj['avg_days_between_events'],
            days_since_last_event=traj['days_since_last_event'],
            num_amendments=traj['num_amendments'],
            num_commission_documents=traj['num_commission_documents'],
            num_committee_work=traj['num_committee_work'],
            num_lobby_meetings=traj['num_lobby_meetings'],
        )

    def extract_all_features(
        self,
        status_filter: Optional[List[str]] = None,
        procedure_type_filter: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[CarriageFeatures]:
        """
        Extract features from all carriages matching filters.

        Args:
            status_filter: List of statuses to include (e.g., ['ADOPTED', 'WITHDRAWN'])
            procedure_type_filter: Procedure type to filter (e.g., 'COD')
            limit: Maximum number of carriages to process

        Returns:
            List of CarriageFeatures for matching carriages
        """
        try:
            from models.legislative_train import LegislativeCarriage, CarriageStatusEnum

            query = self.db.query(LegislativeCarriage)

            # Apply status filter
            if status_filter:
                # Convert string statuses to enum values
                status_enums = []
                for s in status_filter:
                    try:
                        status_enums.append(CarriageStatusEnum(s.lower()))
                    except ValueError:
                        logger.warning(f"Unknown status: {s}")

                if status_enums:
                    query = query.filter(LegislativeCarriage.current_status.in_(status_enums))

            # Apply procedure type filter
            if procedure_type_filter:
                query = query.filter(
                    LegislativeCarriage.oeil_procedure_ref.contains(f"({procedure_type_filter})")
                )

            # Apply limit
            if limit:
                query = query.limit(limit)

            carriages = query.all()

            features_list = []
            for carriage in carriages:
                try:
                    features = self.extract_features(carriage)
                    features_list.append(features)
                except Exception as e:
                    logger.warning(f"Failed to extract features for {carriage.id}: {e}")

            return features_list

        except ImportError:
            logger.error("LegislativeCarriage model not available")
            return []

    def get_feature_statistics(
        self,
        features_list: List[CarriageFeatures]
    ) -> Dict[str, Any]:
        """
        Calculate statistics for a list of features.

        Useful for understanding feature distributions.
        """
        if not features_list:
            return {}

        # Collect numeric values
        numeric_stats: Dict[str, List[float]] = {}
        categorical_counts: Dict[str, Dict[str, int]] = {}

        for features in features_list:
            numeric = features.get_numeric_features()
            categorical = features.get_categorical_features()

            for k, v in numeric.items():
                if k not in numeric_stats:
                    numeric_stats[k] = []
                numeric_stats[k].append(v)

            for k, v in categorical.items():
                if k not in categorical_counts:
                    categorical_counts[k] = {}
                categorical_counts[k][v] = categorical_counts[k].get(v, 0) + 1

        # Calculate statistics
        stats = {
            'count': len(features_list),
            'numeric': {},
            'categorical': {}
        }

        for k, values in numeric_stats.items():
            if values:
                values.sort()
                n = len(values)
                stats['numeric'][k] = {
                    'min': values[0],
                    'max': values[-1],
                    'mean': sum(values) / n,
                    'median': values[n // 2],
                }

        for k, counts in categorical_counts.items():
            stats['categorical'][k] = {
                'unique': len(counts),
                'top_values': sorted(counts.items(), key=lambda x: -x[1])[:5]
            }

        return stats


# Singleton instance
_extractor_instance: Optional[FeatureExtractor] = None


def get_feature_extractor() -> FeatureExtractor:
    """Get or create the feature extractor instance."""
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = FeatureExtractor()
    return _extractor_instance
