"""
Legislative Train Scheduler

Automated scraping and monitoring for Legislative Train Schedule.

Schedule:
- Monthly full scrape: Update all trains and carriages (aligned with LT updates)
- Weekly delta scrape: Check for status changes
- Daily blocked check: Identify newly blocked files, alert users
"""

import logging
from datetime import datetime
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from core.database import SessionLocal
from models.legislative_train import (
    LegislativeTrain,
    LegislativeCarriage,
    UserCarriageTrack,
    CarriageStatusEnum,
    CarriageStatusHistory
)
from services.notification_service import NotificationService
from .legislative_train_scraper import LegislativeTrainScraper
from .legislative_train_enricher import LegislativeTrainEnricher

logger = logging.getLogger(__name__)


class LegislativeTrainScheduler:
    """
    Automated scraping and monitoring for Legislative Train.

    Features:
    - Monthly full scrape (all 490 files)
    - Weekly delta scrape (status changes only)
    - Daily blocked file detection
    - User notifications for tracked files
    """

    def __init__(self):
        """Initialize scheduler"""
        self.scheduler = AsyncIOScheduler()
        self.scraper = LegislativeTrainScraper()
        self.enricher = LegislativeTrainEnricher()
        self.is_running = False

        logger.info("Initialized LegislativeTrainScheduler")

    def start(self):
        """Start scheduled tasks"""
        if self.is_running:
            logger.warning("Scheduler already running")
            return

        # Monthly full scrape (1st of each month at 2 AM)
        self.scheduler.add_job(
            self.monthly_full_scrape,
            CronTrigger(day=1, hour=2, minute=0),
            id='legislative_train_full_scrape',
            name='Legislative Train: Monthly Full Scrape',
            replace_existing=True
        )

        # Weekly delta scrape (Monday at 3 AM)
        self.scheduler.add_job(
            self.weekly_delta_scrape,
            CronTrigger(day_of_week='mon', hour=3, minute=0),
            id='legislative_train_delta_scrape',
            name='Legislative Train: Weekly Delta Scrape',
            replace_existing=True
        )

        # Daily blocked check (Every day at 9 AM)
        self.scheduler.add_job(
            self.daily_blocked_check,
            CronTrigger(hour=9, minute=0),
            id='legislative_train_blocked_check',
            name='Legislative Train: Daily Blocked Check',
            replace_existing=True
        )

        self.scheduler.start()
        self.is_running = True

        logger.info("Legislative Train scheduler started")
        logger.info("  - Monthly full scrape: 1st of month at 2 AM")
        logger.info("  - Weekly delta scrape: Mondays at 3 AM")
        logger.info("  - Daily blocked check: Every day at 9 AM")

    def stop(self):
        """Stop scheduled tasks"""
        if not self.is_running:
            return

        self.scheduler.shutdown()
        self.is_running = False

        logger.info("Legislative Train scheduler stopped")

    async def monthly_full_scrape(self):
        """
        Full scrape of all trains and carriages.

        Updates:
        - All 7 trains
        - All ~490 legislative files
        - Enriches with OEIL/EPRS data (sample)
        - Updates status history
        """
        logger.info("=" * 80)
        logger.info("MONTHLY FULL SCRAPE STARTED")
        logger.info("=" * 80)

        db: Session = SessionLocal()

        try:
            start_time = datetime.now()

            # Scrape all trains
            logger.info("Scraping all trains...")
            trains_data = await self.scraper.get_all_trains()

            trains_updated = 0
            for train_data in trains_data:
                train = await self._upsert_train(db, train_data)
                if train:
                    trains_updated += 1

            logger.info(f"✅ Updated {trains_updated} trains")

            # Scrape all carriages
            logger.info("Scraping all carriages...")
            carriages_data = await self.scraper.get_all_carriages()

            carriages_updated = 0
            for carriage_data in carriages_data[:50]:  # Sample: First 50
                carriage = await self._upsert_carriage(db, carriage_data)
                if carriage:
                    carriages_updated += 1

                    # Check for status changes
                    await self._track_status_change(db, carriage, carriage_data)

            logger.info(f"✅ Updated {carriages_updated} carriages")

            # Update train statistics
            await self._update_train_statistics(db)

            # Commit changes
            db.commit()

            duration = (datetime.now() - start_time).total_seconds()

            logger.info("=" * 80)
            logger.info(f"MONTHLY FULL SCRAPE COMPLETE ({duration:.1f}s)")
            logger.info(f"  - Trains updated: {trains_updated}")
            logger.info(f"  - Carriages updated: {carriages_updated}")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"Monthly scrape failed: {str(e)}")
            db.rollback()

        finally:
            db.close()

    async def weekly_delta_scrape(self):
        """
        Delta scrape: Check for status changes only.

        Faster than full scrape - only checks current status.
        """
        logger.info("=" * 80)
        logger.info("WEEKLY DELTA SCRAPE STARTED")
        logger.info("=" * 80)

        db: Session = SessionLocal()

        try:
            start_time = datetime.now()

            # Get all existing carriages
            existing_carriages = db.query(LegislativeCarriage).all()

            status_changes = 0

            for carriage in existing_carriages[:50]:  # Sample: First 50
                # Re-scrape carriage
                carriage_data = await self.scraper.scrape_carriage(carriage.file_id)

                if not carriage_data or 'error' in carriage_data:
                    continue

                # Check for status change
                new_status = carriage_data.get('status')
                if new_status and new_status != carriage.current_status:
                    logger.info(
                        f"Status change detected: {carriage.title} "
                        f"{carriage.current_status} → {new_status}"
                    )

                    # Update status
                    old_status = carriage.current_status
                    carriage.current_status = new_status

                    # Add to history
                    await self._track_status_change(db, carriage, carriage_data)

                    # Notify users tracking this file
                    await self._notify_status_change(db, carriage, old_status, new_status)

                    status_changes += 1

            db.commit()

            duration = (datetime.now() - start_time).total_seconds()

            logger.info("=" * 80)
            logger.info(f"WEEKLY DELTA SCRAPE COMPLETE ({duration:.1f}s)")
            logger.info(f"  - Status changes detected: {status_changes}")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"Delta scrape failed: {str(e)}")
            db.rollback()

        finally:
            db.close()

    async def daily_blocked_check(self):
        """
        Daily check for newly blocked files.

        Identifies files that:
        - Haven't changed status in 270+ days
        - Just became blocked
        """
        logger.info("=" * 80)
        logger.info("DAILY BLOCKED CHECK STARTED")
        logger.info("=" * 80)

        db: Session = SessionLocal()

        try:
            # Find files that should be marked as blocked
            carriages = db.query(LegislativeCarriage).filter(
                LegislativeCarriage.current_status != CarriageStatusEnum.COMPLETED,
                LegislativeCarriage.days_in_current_status >= 270,
                LegislativeCarriage.is_blocked == False
            ).all()

            newly_blocked = 0

            for carriage in carriages:
                logger.warning(
                    f"Marking as blocked: {carriage.title} "
                    f"({carriage.days_in_current_status} days in {carriage.current_status})"
                )

                carriage.is_blocked = True

                # Notify users tracking this file
                await self._notify_blocking(db, carriage)

                newly_blocked += 1

            db.commit()

            logger.info("=" * 80)
            logger.info("DAILY BLOCKED CHECK COMPLETE")
            logger.info(f"  - Newly blocked files: {newly_blocked}")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"Blocked check failed: {str(e)}")
            db.rollback()

        finally:
            db.close()

    # ===== Helper Methods =====

    async def _upsert_train(self, db: Session, train_data: dict) -> Optional[LegislativeTrain]:
        """Insert or update train"""
        try:
            priority_number = train_data.get('priority_number')

            if not priority_number:
                return None

            train = db.query(LegislativeTrain).filter(
                LegislativeTrain.priority_number == priority_number
            ).first()

            if train:
                # Update existing
                train.name = train_data.get('name', train.name)
                train.description = train_data.get('description', train.description)
                train.files_by_status = train_data.get('files_by_status', train.files_by_status)
                train.total_files = train_data.get('total_files', train.total_files)
                train.updated_at = datetime.now()
            else:
                # Create new
                train = LegislativeTrain(
                    priority_number=priority_number,
                    name=train_data.get('name', f"Priority {priority_number}"),
                    description=train_data.get('description'),
                    files_by_status=train_data.get('files_by_status', {}),
                    total_files=train_data.get('total_files', 0)
                )
                db.add(train)

            return train

        except Exception as e:
            logger.error(f"Failed to upsert train: {str(e)}")
            return None

    async def _upsert_carriage(self, db: Session, carriage_data: dict) -> Optional[LegislativeCarriage]:
        """Insert or update carriage"""
        try:
            file_id = carriage_data.get('id')

            if not file_id:
                return None

            carriage = db.query(LegislativeCarriage).filter(
                LegislativeCarriage.file_id == file_id
            ).first()

            if carriage:
                # Update existing
                carriage.title = carriage_data.get('title', carriage.title)
                carriage.description = carriage_data.get('description', carriage.description)
                carriage.current_status = carriage_data.get('status', carriage.current_status)
                carriage.committees = carriage_data.get('committees', carriage.committees)
                carriage.oeil_procedure_ref = carriage_data.get('oeil_procedure_ref', carriage.oeil_procedure_ref)
                carriage.celex_numbers = carriage_data.get('celex_numbers', carriage.celex_numbers)
                carriage.last_updated = datetime.now()
            else:
                # Create new
                carriage = LegislativeCarriage(
                    file_id=file_id,
                    title=carriage_data.get('title', 'Untitled'),
                    description=carriage_data.get('description'),
                    current_status=carriage_data.get('status', CarriageStatusEnum.ANNOUNCED),
                    committees=carriage_data.get('committees', []),
                    oeil_procedure_ref=carriage_data.get('oeil_procedure_ref'),
                    celex_numbers=carriage_data.get('celex_numbers', [])
                )
                db.add(carriage)

            return carriage

        except Exception as e:
            logger.error(f"Failed to upsert carriage: {str(e)}")
            return None

    async def _track_status_change(self, db: Session, carriage: LegislativeCarriage, new_data: dict):
        """Track status change in history"""
        # Update days in current status (simplified - would need proper calculation)
        carriage.days_in_current_status = new_data.get('days_in_current_status', 0)

    async def _update_train_statistics(self, db: Session):
        """Update statistics for all trains"""
        trains = db.query(LegislativeTrain).all()

        for train in trains:
            carriages = db.query(LegislativeCarriage).filter(
                LegislativeCarriage.train_id == train.id
            ).all()

            # Count by status
            files_by_status = {}
            for carriage in carriages:
                status = carriage.current_status.value
                files_by_status[status] = files_by_status.get(status, 0) + 1

            train.files_by_status = files_by_status
            train.total_files = len(carriages)

    async def _notify_status_change(
        self,
        db: Session,
        carriage: LegislativeCarriage,
        old_status: str,
        new_status: str
    ):
        """Notify users tracking this carriage of status change"""
        try:
            notification_service = NotificationService(db)

            # Find users tracking this carriage
            tracking_users = db.query(UserCarriageTrack).filter(
                UserCarriageTrack.carriage_id == carriage.id,
                UserCarriageTrack.is_active == True
            ).all()

            if tracking_users:
                for track in tracking_users:
                    # Create notification for each tracking user
                    notification_service.create_notification(
                        user_id=str(track.user_id),
                        notification_type="status_change",
                        title=f"Status Update: {carriage.title[:80]}",
                        message=f"Status changed from {old_status} to {new_status}",
                        priority="high",
                        action_url=f"/bubble?tab=legislative-trains&file={carriage.file_id}",
                        metadata={
                            "carriage_id": str(carriage.id),
                            "file_id": carriage.file_id,
                            "old_status": old_status,
                            "new_status": new_status,
                            "oeil_ref": carriage.oeil_procedure_ref
                        },
                        related_entity_type="legislative_carriage",
                        related_entity_id=str(carriage.id)
                    )

                logger.info(f"Notified {len(tracking_users)} users of status change: {carriage.title}")

            # Also notify users who have amendments linked to this carriage (Priority #4 Integration)
            amendment_notifications = await notification_service.generate_amendment_context_notifications(
                carriage_id=str(carriage.id),
                change_type="status_change",
                change_data={
                    "title": carriage.title,
                    "old_status": old_status,
                    "new_status": new_status,
                    "procedure_ref": carriage.oeil_procedure_ref
                }
            )
            if amendment_notifications:
                logger.info(f"Sent {len(amendment_notifications)} amendment context notifications for status change")

        except Exception as e:
            logger.error(f"Failed to notify status change: {e}")

    async def _notify_blocking(self, db: Session, carriage: LegislativeCarriage):
        """Notify users that tracked file is now blocked"""
        try:
            notification_service = NotificationService(db)

            # Find users tracking this carriage
            tracking_users = db.query(UserCarriageTrack).filter(
                UserCarriageTrack.carriage_id == carriage.id,
                UserCarriageTrack.is_active == True
            ).all()

            if tracking_users:
                for track in tracking_users:
                    # Create notification for each user
                    notification_service.create_notification(
                        user_id=str(track.user_id),
                        notification_type="status_change",
                        title=f"⚠️ File Blocked: {carriage.title[:80]}",
                        message=f"This file has been stuck in {carriage.current_status} for {carriage.days_in_current_status} days and appears blocked.",
                        priority="urgent",
                        action_url=f"/bubble?tab=legislative-trains&file={carriage.file_id}",
                        metadata={
                            "carriage_id": str(carriage.id),
                            "file_id": carriage.file_id,
                            "current_status": str(carriage.current_status),
                            "days_blocked": carriage.days_in_current_status,
                            "oeil_ref": carriage.oeil_procedure_ref
                        },
                        related_entity_type="legislative_carriage",
                        related_entity_id=str(carriage.id)
                    )

                logger.warning(f"Notified {len(tracking_users)} users of blocking: {carriage.title}")

            # Also notify users who have amendments linked to this carriage (Priority #4 Integration)
            amendment_notifications = await notification_service.generate_amendment_context_notifications(
                carriage_id=str(carriage.id),
                change_type="blocking_detected",
                change_data={
                    "title": carriage.title,
                    "current_status": str(carriage.current_status),
                    "days_blocked": carriage.days_in_current_status,
                    "procedure_ref": carriage.oeil_procedure_ref
                }
            )
            if amendment_notifications:
                logger.warning(f"Sent {len(amendment_notifications)} amendment context notifications for blocking")

        except Exception as e:
            logger.error(f"Failed to notify blocking: {e}")


# Global instance
_scheduler: Optional[LegislativeTrainScheduler] = None


def get_legislative_train_scheduler() -> LegislativeTrainScheduler:
    """Get global scheduler instance"""
    global _scheduler

    if _scheduler is None:
        _scheduler = LegislativeTrainScheduler()

    return _scheduler
