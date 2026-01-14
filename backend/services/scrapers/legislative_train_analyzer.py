"""
Legislative Train Analyzer

Analytics for legislative progress tracking.
Provides insights into blocking patterns, timelines, and committee workloads.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from collections import defaultdict, Counter
from sqlalchemy import func
from sqlalchemy.orm import Session

from models.legislative_train import (
    LegislativeTrain,
    LegislativeCarriage,
    CarriageStatusEnum,
    CarriageStatusHistory
)
from schemas.scrapers.legislative_train_schemas import (
    TrainStatistics,
    CommitteeWorkload,
    BlockedFileAlert,
    TimelinePrediction,
    CarriageStatus
)

logger = logging.getLogger(__name__)


class LegislativeTrainAnalyzer:
    """
    Analytics for legislative progress tracking.

    Features:
    - Identify blocked files
    - Track committee workloads
    - Predict timelines (ML-based)
    - Analyze status progression patterns
    """

    def __init__(self, db: Session):
        """
        Initialize analyzer.

        Args:
            db: Database session
        """
        self.db = db
        logger.info("Initialized LegislativeTrainAnalyzer")

    def get_train_statistics(self, train_id: str) -> Optional[TrainStatistics]:
        """
        Get comprehensive statistics for a train.

        Args:
            train_id: Train ID

        Returns:
            TrainStatistics with file counts and averages
        """
        logger.info(f"Calculating statistics for train {train_id}")

        try:
            # Get train
            train = self.db.query(LegislativeTrain).filter(
                LegislativeTrain.id == train_id
            ).first()

            if not train:
                logger.warning(f"Train {train_id} not found")
                return None

            # Get all carriages
            carriages = self.db.query(LegislativeCarriage).filter(
                LegislativeCarriage.train_id == train_id
            ).all()

            # Count by status
            status_counts = Counter([c.current_status for c in carriages])
            files_by_status = {
                status: count for status, count in status_counts.items()
            }

            # Calculate average days per status
            average_days = {}
            for status in CarriageStatusEnum:
                status_carriages = [
                    c for c in carriages
                    if c.current_status == status and c.days_in_current_status
                ]

                if status_carriages:
                    avg = sum(c.days_in_current_status for c in status_carriages) / len(status_carriages)
                    average_days[status] = round(avg, 1)
                else:
                    average_days[status] = 0.0

            # Count blocked files
            blocked_count = sum(1 for c in carriages if c.is_blocked)

            # Calculate completion rate
            completed_count = status_counts.get(CarriageStatusEnum.COMPLETED, 0)
            completion_rate = completed_count / len(carriages) if carriages else 0.0

            stats = TrainStatistics(
                train_id=str(train_id),
                train_name=train.name,
                total_files=len(carriages),
                files_by_status=files_by_status,
                average_days_per_status=average_days,
                blocked_files_count=blocked_count,
                completion_rate=completion_rate
            )

            logger.info(f"Statistics calculated for {train.name}: {len(carriages)} files")
            return stats

        except Exception as e:
            logger.error(f"Failed to calculate statistics: {str(e)}")
            return None

    def get_committee_workload(self, committee_code: str) -> Optional[CommitteeWorkload]:
        """
        Analyze workload for a specific committee.

        Args:
            committee_code: Committee code (e.g., "LIBE")

        Returns:
            CommitteeWorkload with file counts and metrics
        """
        logger.info(f"Calculating workload for committee {committee_code}")

        try:
            # Find all carriages involving this committee
            carriages = self.db.query(LegislativeCarriage).filter(
                LegislativeCarriage.committees.contains([committee_code])
            ).all()

            if not carriages:
                logger.warning(f"No files found for committee {committee_code}")
                return None

            # Count by status
            status_counts = Counter([c.current_status for c in carriages])
            files_by_status = {
                status: count for status, count in status_counts.items()
            }

            # Count lead vs opinion files
            lead_files = sum(1 for c in carriages if c.lead_committee == committee_code)
            opinion_files = sum(
                1 for c in carriages
                if committee_code in c.opinion_committees
            )

            # Calculate average processing time
            completed_carriages = [
                c for c in carriages
                if c.current_status == CarriageStatusEnum.COMPLETED
            ]

            avg_processing_time = None
            if completed_carriages:
                # Sum all days in status history
                total_days = 0
                count = 0
                for carriage in completed_carriages:
                    if carriage.status_history:
                        for status_change in carriage.status_history:
                            if status_change.get('duration_days'):
                                total_days += status_change['duration_days']
                                count += 1

                if count > 0:
                    avg_processing_time = round(total_days / count, 1)

            # Count blocked files
            blocked_count = sum(1 for c in carriages if c.is_blocked)

            workload = CommitteeWorkload(
                committee_code=committee_code,
                active_files=len(carriages),
                files_by_status=files_by_status,
                average_processing_time_days=avg_processing_time,
                blocked_files=blocked_count,
                lead_files=lead_files,
                opinion_files=opinion_files
            )

            logger.info(f"Workload calculated for {committee_code}: {len(carriages)} files")
            return workload

        except Exception as e:
            logger.error(f"Failed to calculate workload: {str(e)}")
            return None

    def get_blocked_files(self, min_days: int = 270) -> List[BlockedFileAlert]:
        """
        Find files blocked for 9+ months.

        Args:
            min_days: Minimum days to consider blocked

        Returns:
            List of blocked file alerts
        """
        logger.info(f"Finding files blocked for {min_days}+ days")

        try:
            # Query blocked files
            blocked_carriages = self.db.query(LegislativeCarriage).filter(
                (LegislativeCarriage.is_blocked == True) |
                (LegislativeCarriage.days_in_current_status >= min_days)
            ).all()

            alerts = []

            for carriage in blocked_carriages:
                # Get train name
                train_name = "Unknown"
                if carriage.train:
                    train_name = carriage.train.name

                # Determine severity
                days_blocked = carriage.days_in_current_status or 0
                if days_blocked >= 540:  # 18 months
                    severity = "high"
                elif days_blocked >= 360:  # 12 months
                    severity = "medium"
                else:
                    severity = "low"

                # Find last activity
                last_activity = None
                if carriage.status_history:
                    last_change = max(
                        carriage.status_history,
                        key=lambda x: x.get('changed_at', datetime.min)
                    )
                    last_activity = last_change.get('changed_at')

                alert = BlockedFileAlert(
                    carriage_id=str(carriage.id),
                    title=carriage.title,
                    train_name=train_name,
                    status=carriage.current_status,
                    days_blocked=days_blocked,
                    last_activity=last_activity,
                    alert_severity=severity
                )

                alerts.append(alert)

            # Sort by days blocked (descending)
            alerts.sort(key=lambda x: x.days_blocked, reverse=True)

            logger.info(f"Found {len(alerts)} blocked files")
            return alerts

        except Exception as e:
            logger.error(f"Failed to get blocked files: {str(e)}")
            return []

    def predict_timeline(self, carriage_id: str) -> Optional[TimelinePrediction]:
        """
        Predict completion timeline for a file.

        Uses historical data to estimate remaining time.

        Args:
            carriage_id: Carriage ID

        Returns:
            TimelinePrediction with estimated completion date
        """
        logger.info(f"Predicting timeline for carriage {carriage_id}")

        try:
            # Get carriage
            carriage = self.db.query(LegislativeCarriage).filter(
                LegislativeCarriage.id == carriage_id
            ).first()

            if not carriage:
                logger.warning(f"Carriage {carriage_id} not found")
                return None

            # Already completed?
            if carriage.current_status == CarriageStatusEnum.COMPLETED:
                return TimelinePrediction(
                    carriage_id=str(carriage_id),
                    current_status=carriage.current_status,
                    estimated_completion_date=carriage.last_updated,
                    confidence=1.0,
                    remaining_steps=[],
                    based_on_historical_avg=False
                )

            # Calculate historical averages
            historical_averages = self._calculate_historical_averages()

            # Determine remaining steps
            status_order = [
                CarriageStatusEnum.ANNOUNCED,
                CarriageStatusEnum.LEGISLATIVE_INITIATIVE,
                CarriageStatusEnum.TABLED,
                CarriageStatusEnum.CLOSE_TO_ADOPTION,
                CarriageStatusEnum.COMPLETED
            ]

            current_index = status_order.index(carriage.current_status)
            remaining_steps = status_order[current_index + 1:]

            # Estimate days per remaining step
            estimated_days = {}
            total_estimated_days = 0

            for status in remaining_steps:
                avg_days = historical_averages.get(status, 60)  # Default 60 days
                estimated_days[status] = avg_days
                total_estimated_days += avg_days

            # Calculate estimated completion date
            estimated_completion = datetime.now() + timedelta(days=total_estimated_days)

            # Determine confidence
            # Lower confidence if file is blocked or has unusual history
            confidence = 0.7  # Base confidence

            if carriage.is_blocked:
                confidence = 0.3
            elif carriage.days_in_current_status and carriage.days_in_current_status > 180:
                confidence = 0.5

            prediction = TimelinePrediction(
                carriage_id=str(carriage_id),
                current_status=carriage.current_status,
                estimated_completion_date=estimated_completion,
                confidence=confidence,
                remaining_steps=remaining_steps,
                estimated_days_per_step=estimated_days,
                based_on_historical_avg=True
            )

            logger.info(
                f"Timeline predicted for {carriage.title}: "
                f"~{total_estimated_days} days remaining (confidence: {confidence:.0%})"
            )

            return prediction

        except Exception as e:
            logger.error(f"Failed to predict timeline: {str(e)}")
            return None

    def _calculate_historical_averages(self) -> Dict[CarriageStatusEnum, int]:
        """
        Calculate average days per status from historical data.

        Returns:
            Dict mapping status to average days
        """
        try:
            averages = {}

            for status in CarriageStatusEnum:
                # Get all carriages that passed through this status
                carriages = self.db.query(LegislativeCarriage).all()

                days_list = []
                for carriage in carriages:
                    if carriage.status_history:
                        for status_change in carriage.status_history:
                            if (status_change.get('status') == status
                                    and status_change.get('duration_days')):
                                days_list.append(status_change['duration_days'])

                if days_list:
                    avg = sum(days_list) / len(days_list)
                    averages[status] = int(avg)
                else:
                    # Default estimates
                    averages[status] = 60

            return averages

        except Exception as e:
            logger.error(f"Failed to calculate averages: {str(e)}")
            return {}

    def get_status_transition_matrix(self) -> Dict[str, Dict[str, int]]:
        """
        Calculate status transition probabilities.

        Returns:
            Matrix showing transitions: {from_status: {to_status: count}}
        """
        logger.info("Calculating status transition matrix")

        try:
            matrix = defaultdict(lambda: defaultdict(int))

            # Get all status history records
            all_carriages = self.db.query(LegislativeCarriage).all()

            for carriage in all_carriages:
                if not carriage.status_history or len(carriage.status_history) < 2:
                    continue

                # Sort history by changed_at
                sorted_history = sorted(
                    carriage.status_history,
                    key=lambda x: x.get('changed_at', datetime.min)
                )

                # Count transitions
                for i in range(len(sorted_history) - 1):
                    from_status = sorted_history[i].get('status')
                    to_status = sorted_history[i + 1].get('status')

                    if from_status and to_status:
                        matrix[from_status][to_status] += 1

            logger.info("Transition matrix calculated")
            return dict(matrix)

        except Exception as e:
            logger.error(f"Failed to calculate transition matrix: {str(e)}")
            return {}
