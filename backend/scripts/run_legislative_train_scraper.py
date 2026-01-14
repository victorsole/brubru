"""
Run Legislative Train Scraper

Scrapes all legislative files from the European Parliament's Legislative Train Schedule
and saves them to the database.

Usage:
    python -m backend.scripts.run_legislative_train_scraper
"""

import asyncio
import logging
from datetime import datetime

from services.scrapers.legislative_train_scraper import LegislativeTrainScraper
from core.database import SessionLocal
from models.legislative_train import LegislativeTrain, LegislativeCarriage, CarriageStatusEnum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_scraper():
    """Run the Legislative Train scraper and save results to database."""

    logger.info("=" * 80)
    logger.info("LEGISLATIVE TRAIN SCRAPER")
    logger.info("=" * 80)

    # Initialize scraper
    scraper = LegislativeTrainScraper()

    try:
        # Get all trains (EC priorities)
        logger.info("\n📋 Fetching all EC priority trains...")
        trains_data = await scraper.get_all_trains()
        logger.info(f"✅ Found {len(trains_data)} priority trains")

        # Get all carriages (legislative files)
        logger.info("\n🚂 Fetching all legislative carriages...")
        carriages_data = await scraper.get_all_carriages()
        logger.info(f"✅ Found {len(carriages_data)} legislative files")

        # Save to database
        db = SessionLocal()

        try:
            logger.info("\n💾 Saving to database...")

            # Create/update trains
            train_map = {}
            for train_data in trains_data:
                train = db.query(LegislativeTrain).filter_by(
                    priority_number=train_data['priority_number']
                ).first()

                if not train:
                    train = LegislativeTrain(
                        priority_number=train_data['priority_number'],
                        name=train_data['name'],
                        description=train_data.get('description'),
                        commission_term="2024-2029"
                    )
                    db.add(train)
                else:
                    train.name = train_data['name']
                    train.description = train_data.get('description')

                db.commit()
                db.refresh(train)
                train_map[train_data['priority_number']] = train
                logger.info(f"  ✓ Priority {train.priority_number}: {train.name}")

            # Create/update carriages
            created_count = 0
            updated_count = 0

            for carriage_data in carriages_data:
                # Scraper returns 'id', not 'file_id'
                file_id = carriage_data.get('id')
                if not file_id:
                    logger.warning(f"Skipping carriage without ID: {carriage_data.get('title', 'unknown')}")
                    continue

                carriage = db.query(LegislativeCarriage).filter_by(
                    file_id=file_id
                ).first()

                # Map priority to train
                priority_num = carriage_data.get('train_priority')
                train_id = train_map[priority_num].id if priority_num in train_map else None

                # Parse status enum - scraper returns 'status', not 'current_status'
                status_str = carriage_data.get('status', 'announced')
                try:
                    status_enum = CarriageStatusEnum(status_str)
                except ValueError:
                    logger.warning(f"Unknown status '{status_str}' for {file_id}, using ANNOUNCED")
                    status_enum = CarriageStatusEnum.ANNOUNCED

                if not carriage:
                    carriage = LegislativeCarriage(
                        file_id=file_id,
                        train_id=train_id,
                        title=carriage_data.get('title', 'Unknown'),
                        description=carriage_data.get('description'),
                        current_status=status_enum,
                        oeil_procedure_ref=carriage_data.get('oeil_procedure_ref'),
                        committees=carriage_data.get('committees', []),
                        first_seen=datetime.now(),
                        last_updated=datetime.now()
                    )
                    db.add(carriage)
                    created_count += 1
                else:
                    carriage.train_id = train_id
                    carriage.title = carriage_data.get('title', carriage.title)
                    carriage.description = carriage_data.get('description', carriage.description)
                    carriage.current_status = status_enum
                    carriage.oeil_procedure_ref = carriage_data.get('oeil_procedure_ref', carriage.oeil_procedure_ref)
                    carriage.committees = carriage_data.get('committees', carriage.committees)
                    carriage.last_updated = datetime.now()
                    updated_count += 1

                if (created_count + updated_count) % 50 == 0:
                    db.commit()
                    logger.info(f"  Progress: {created_count + updated_count}/{len(carriages_data)} files processed...")

            db.commit()

            logger.info(f"\n✅ Database updated successfully!")
            logger.info(f"  • Created: {created_count} new files")
            logger.info(f"  • Updated: {updated_count} existing files")
            logger.info(f"  • Total: {created_count + updated_count} files")

        finally:
            db.close()

    except Exception as e:
        logger.error(f"\n❌ Scraping failed: {str(e)}")
        raise

    logger.info("\n" + "=" * 80)
    logger.info("SCRAPING COMPLETE")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_scraper())
