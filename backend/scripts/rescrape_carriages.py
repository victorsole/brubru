"""
Re-scrape Legislative Carriages from Package Pages

This script clears existing carriages and re-populates from package-based
scraping, which provides OEIL procedure references.

Option A: Quick fix for data quality issues.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / '.env')

from sqlalchemy import text
from core.database import SessionLocal
from models.legislative_train import LegislativeCarriage, LegislativeTrain, UserCarriageTrack
from services.scrapers.legislative_train_scraper import LegislativeTrainScraper


async def rescrape_carriages():
    """Clear and re-populate carriages from package-based scraping."""

    db = SessionLocal()
    scraper = LegislativeTrainScraper()

    try:
        print("=" * 60)
        print("LEGISLATIVE CARRIAGE RE-SCRAPE (Package-Based)")
        print("=" * 60)

        # Step 1: Backup user tracking
        print("\n1. Backing up user tracking records...")
        tracks = db.query(UserCarriageTrack).all()
        track_backup = []
        for track in tracks:
            carriage = db.query(LegislativeCarriage).filter(
                LegislativeCarriage.id == track.carriage_id
            ).first()
            if carriage:
                track_backup.append({
                    'user_id': track.user_id,
                    'file_id': carriage.file_id,
                    'oeil_ref': carriage.oeil_procedure_ref,
                    'tracked_at': track.tracked_at
                })
        print(f"   Backed up {len(track_backup)} tracking records")

        # Step 2: Clear existing data
        print("\n2. Clearing existing carriages...")
        db.query(UserCarriageTrack).delete()
        db.query(LegislativeCarriage).delete()
        db.commit()
        print("   Cleared all carriages and tracks")

        # Step 3: Get default train (or create one)
        print("\n3. Setting up train...")
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
        print(f"   Using train: {train.name}")

        # Step 4: Scrape all packages
        print("\n4. Fetching packages from EP website...")
        packages = await scraper.get_all_packages()
        print(f"   Found {len(packages)} packages")

        # Step 5: Scrape files from each package with details
        print("\n5. Fetching files from each package...")
        all_files = {}  # file_id -> data (deduplicate)

        for i, pkg in enumerate(packages):
            try:
                files = await scraper.get_package_files(pkg.slug)
                print(f"   [{i+1}/{len(packages)}] {pkg.slug}: {len(files)} files")

                for f in files:
                    if f.file_id and f.file_id not in all_files:
                        # Get file detail to extract OEIL ref
                        detail = None
                        if f.url:
                            try:
                                detail = await scraper.get_file_detail(f.url)
                            except Exception as e:
                                print(f"      Warning: Could not get detail for {f.file_id}: {e}")

                        all_files[f.file_id] = {
                            'file_id': f.file_id,
                            'title': detail.title if detail else f.title,
                            'description': detail.description if detail else None,
                            'status': (detail.status.value if detail else f.status.value) if hasattr(f.status, 'value') else str(f.status),
                            'oeil_procedure_ref': detail.oeil_procedure_ref if detail else None,
                            'url': f.url,
                            'package_slug': pkg.slug,
                            'committees': detail.committees if detail else f.committees,
                            'lead_committee': detail.lead_committee if detail else None,
                            'celex_numbers': detail.celex_numbers if detail else [],
                            'text_type': detail.text_type.value if detail and detail.text_type else 'unknown',
                            'is_recently_updated': detail.is_recently_updated if detail else f.is_recently_updated,
                            'spotlight_tags': detail.spotlight_tags if detail else [],
                        }

            except Exception as e:
                print(f"   Warning: Failed to process package {pkg.slug}: {e}")
                continue

        print(f"\n   Total unique files: {len(all_files)}")
        oeil_count = sum(1 for f in all_files.values() if f.get('oeil_procedure_ref'))
        print(f"   Files with OEIL refs: {oeil_count} ({100*oeil_count/len(all_files):.1f}%)")

        # Step 6: Insert into database
        print("\n6. Inserting carriages into database...")
        created = 0

        for file_data in all_files.values():
            try:
                # Map status string to enum
                from models.legislative_train import CarriageStatusEnum, TextTypeEnum

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
                status = status_map.get(file_data['status'], CarriageStatusEnum.ANNOUNCED)

                text_type_map = {
                    'legislative': TextTypeEnum.LEGISLATIVE,
                    'non_legislative': TextTypeEnum.NON_LEGISLATIVE,
                    'unknown': TextTypeEnum.UNKNOWN,
                }
                text_type = text_type_map.get(file_data.get('text_type', 'unknown'), TextTypeEnum.UNKNOWN)

                carriage = LegislativeCarriage(
                    train_id=train.id,
                    file_id=file_data['file_id'],
                    package_slug=file_data.get('package_slug'),
                    title=file_data['title'] or file_data['file_id'],
                    description=file_data.get('description'),
                    current_status=status,
                    oeil_procedure_ref=file_data.get('oeil_procedure_ref'),
                    url=file_data.get('url'),
                    committees=file_data.get('committees', []),
                    lead_committee=file_data.get('lead_committee'),
                    celex_numbers=file_data.get('celex_numbers', []),
                    text_type=text_type,
                    is_recently_updated=file_data.get('is_recently_updated', False),
                    spotlight_tags=file_data.get('spotlight_tags', []),
                    first_seen=datetime.now(),
                    last_updated=datetime.now(),
                    scraped_at=datetime.now(),
                )
                db.add(carriage)
                created += 1

                if created % 50 == 0:
                    db.commit()
                    print(f"      Progress: {created}/{len(all_files)}")

            except Exception as e:
                print(f"   Warning: Failed to insert {file_data['file_id']}: {e}")
                continue

        db.commit()
        print(f"   Created {created} carriages")

        # Step 7: Restore user tracking
        print("\n7. Restoring user tracking...")
        restored = 0
        for backup in track_backup:
            # Try to find carriage by file_id or oeil_ref
            carriage = db.query(LegislativeCarriage).filter(
                LegislativeCarriage.file_id == backup['file_id']
            ).first()

            if not carriage and backup['oeil_ref']:
                carriage = db.query(LegislativeCarriage).filter(
                    LegislativeCarriage.oeil_procedure_ref == backup['oeil_ref']
                ).first()

            if carriage:
                track = UserCarriageTrack(
                    user_id=backup['user_id'],
                    carriage_id=carriage.id,
                    tracked_at=backup['tracked_at']
                )
                db.add(track)
                restored += 1

        db.commit()
        print(f"   Restored {restored}/{len(track_backup)} tracking records")

        # Step 8: Final statistics
        print("\n8. Final statistics...")
        total = db.query(LegislativeCarriage).count()
        with_oeil = db.query(LegislativeCarriage).filter(
            LegislativeCarriage.oeil_procedure_ref != None
        ).count()
        with_url = db.query(LegislativeCarriage).filter(
            LegislativeCarriage.url != None
        ).count()

        print(f"   Total carriages: {total}")
        print(f"   With OEIL ref: {with_oeil} ({100*with_oeil/total:.1f}%)")
        print(f"   With URL: {with_url} ({100*with_url/total:.1f}%)")

        print("\n" + "=" * 60)
        print("RE-SCRAPE COMPLETE!")
        print("=" * 60)

    except Exception as e:
        print(f"\nERROR: {e}")
        db.rollback()
        raise
    finally:
        await scraper.close()
        db.close()


if __name__ == "__main__":
    asyncio.run(rescrape_carriages())
