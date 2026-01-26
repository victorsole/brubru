"""
Enrich Legislative Carriages with OEIL Procedure References

This script scrapes the EU Legislative Train website and updates
existing database carriages with OEIL procedure references.
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / '.env')

from core.database import SessionLocal
from models.legislative_train import LegislativeCarriage, LegislativeTrain
from services.scrapers.legislative_train_scraper import LegislativeTrainScraper


async def enrich_carriages():
    """Enrich database carriages with OEIL refs from scraper."""

    db = SessionLocal()
    scraper = LegislativeTrainScraper()

    try:
        print("=" * 60)
        print("Legislative Carriage Enrichment")
        print("=" * 60)

        # Get all packages
        print("\n1. Fetching packages from EP website...")
        packages = await scraper.get_all_packages()
        print(f"   Found {len(packages)} packages")

        # Build a mapping of file_id -> scraped data
        print("\n2. Fetching file details from each package...")
        scraped_files = {}

        for i, pkg in enumerate(packages):
            files = await scraper.get_package_files(pkg.slug)
            print(f"   [{i+1}/{len(packages)}] {pkg.slug}: {len(files)} files")

            for f in files:
                if f.url:
                    # Get detail to extract OEIL ref
                    detail = await scraper.get_file_detail(f.url)
                    if detail:
                        # Use title for matching (normalized)
                        title_key = detail.title.lower().strip() if detail.title else None
                        file_id_key = f.file_id

                        scraped_files[file_id_key] = {
                            'title': detail.title,
                            'oeil_procedure_ref': detail.oeil_procedure_ref,
                            'url': f.url,
                            'committees': detail.committees,
                            'celex_numbers': detail.celex_numbers,
                        }

                        if title_key:
                            scraped_files[title_key] = scraped_files[file_id_key]

        print(f"\n   Total scraped files: {len(scraped_files)}")
        oeil_count = sum(1 for f in scraped_files.values() if f.get('oeil_procedure_ref'))
        print(f"   Files with OEIL refs: {oeil_count}")

        # Update database carriages
        print("\n3. Updating database carriages...")
        carriages = db.query(LegislativeCarriage).all()
        print(f"   Database carriages: {len(carriages)}")

        updated = 0
        matched = 0

        for carriage in carriages:
            # Try to match by file_id first, then by title
            scraped = scraped_files.get(carriage.file_id)
            if not scraped:
                title_key = carriage.title.lower().strip() if carriage.title else None
                scraped = scraped_files.get(title_key)

            if scraped:
                matched += 1
                changes = False

                # Update OEIL ref if found
                if scraped.get('oeil_procedure_ref') and not carriage.oeil_procedure_ref:
                    carriage.oeil_procedure_ref = scraped['oeil_procedure_ref']
                    changes = True

                # Update URL if missing
                if scraped.get('url') and not carriage.url:
                    carriage.url = scraped['url']
                    changes = True

                # Update committees if missing
                if scraped.get('committees') and not carriage.committees:
                    carriage.committees = scraped['committees']
                    changes = True

                # Update CELEX if missing
                if scraped.get('celex_numbers') and not carriage.celex_numbers:
                    carriage.celex_numbers = scraped['celex_numbers']
                    changes = True

                if changes:
                    updated += 1

        db.commit()

        print(f"\n   Matched: {matched}")
        print(f"   Updated: {updated}")

        # Final stats
        print("\n4. Final statistics...")
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
        print("Enrichment complete!")
        print("=" * 60)

    finally:
        await scraper.close()
        db.close()


if __name__ == "__main__":
    asyncio.run(enrich_carriages())
