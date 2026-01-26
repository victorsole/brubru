"""
Fast Populate Legislative Carriages

Quickly populates carriages from package listings without fetching
individual file details. Run enrich_carriages.py afterward for OEIL refs.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / '.env')

from core.database import SessionLocal
from models.legislative_train import (
    LegislativeCarriage, LegislativeTrain,
    CarriageStatusEnum, TextTypeEnum
)
from services.scrapers.legislative_train_scraper import LegislativeTrainScraper


async def populate_fast():
    """Fast populate carriages from package listings."""

    db = SessionLocal()
    scraper = LegislativeTrainScraper()

    try:
        print("=" * 60)
        print("FAST POPULATE CARRIAGES")
        print("=" * 60)

        # Get or create train
        print("\n1. Setting up train...")
        train = db.query(LegislativeTrain).filter(
            LegislativeTrain.priority_number == 1
        ).first()
        if not train:
            train = LegislativeTrain(
                priority_number=1,
                name="2024-2029 Commission Priorities",
                commission_term="2024-2029"
            )
            db.add(train)
            db.commit()
            db.refresh(train)
        print(f"   Train: {train.name}")

        # Get all packages
        print("\n2. Fetching packages...")
        packages = await scraper.get_all_packages()
        print(f"   Found {len(packages)} packages")

        # Get files from each package
        print("\n3. Fetching files from packages...")
        all_files = {}

        for i, pkg in enumerate(packages):
            try:
                files = await scraper.get_package_files(pkg.slug)
                file_count = len(files)

                for f in files:
                    if f.file_id and f.file_id not in all_files:
                        all_files[f.file_id] = {
                            'file_id': f.file_id,
                            'title': f.title or f.file_id,
                            'url': f.url,
                            'status': f.status.value if hasattr(f.status, 'value') else str(f.status),
                            'package_slug': pkg.slug,
                            'committees': f.committees or [],
                            'is_recently_updated': f.is_recently_updated,
                        }

                print(f"   [{i+1}/{len(packages)}] {pkg.slug}: {file_count} files")

            except Exception as e:
                print(f"   [{i+1}/{len(packages)}] {pkg.slug}: ERROR - {str(e)[:50]}")
                continue

        print(f"\n   Total unique files: {len(all_files)}")

        # Insert into database
        print("\n4. Inserting into database...")

        status_map = {
            'announced': CarriageStatusEnum.ANNOUNCED,
            'legislative_initiative': CarriageStatusEnum.LEGISLATIVE_INITIATIVE,
            'tabled': CarriageStatusEnum.TABLED,
            'close_to_adoption': CarriageStatusEnum.CLOSE_TO_ADOPTION,
            'completed': CarriageStatusEnum.COMPLETED,
            'adopted': CarriageStatusEnum.ADOPTED,
            'blocked': CarriageStatusEnum.BLOCKED,
            'withdrawn': CarriageStatusEnum.WITHDRAWN,
        }

        created = 0
        for file_data in all_files.values():
            try:
                status = status_map.get(file_data['status'], CarriageStatusEnum.ANNOUNCED)

                carriage = LegislativeCarriage(
                    train_id=train.id,
                    file_id=file_data['file_id'],
                    package_slug=file_data.get('package_slug'),
                    title=file_data['title'],
                    current_status=status,
                    url=file_data.get('url'),
                    committees=file_data.get('committees', []),
                    is_recently_updated=file_data.get('is_recently_updated', False),
                    text_type=TextTypeEnum.UNKNOWN,
                    first_seen=datetime.now(),
                    last_updated=datetime.now(),
                    scraped_at=datetime.now(),
                )
                db.add(carriage)
                created += 1

                if created % 100 == 0:
                    db.commit()
                    print(f"      Progress: {created}")

            except Exception as e:
                print(f"   Error inserting {file_data['file_id']}: {e}")
                continue

        db.commit()
        print(f"   Created {created} carriages")

        # Stats
        print("\n5. Statistics...")
        total = db.query(LegislativeCarriage).count()
        with_url = db.query(LegislativeCarriage).filter(
            LegislativeCarriage.url != None
        ).count()
        print(f"   Total: {total}")
        print(f"   With URL: {with_url}")

        print("\n" + "=" * 60)
        print("DONE! Now run enrich_carriages.py to add OEIL refs.")
        print("=" * 60)

    finally:
        await scraper.close()
        db.close()


if __name__ == "__main__":
    asyncio.run(populate_fast())
