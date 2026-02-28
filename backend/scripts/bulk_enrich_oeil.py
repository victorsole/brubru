"""
Bulk OEIL Enrichment for Legislative Carriages

Fetches OEIL procedure data (documentation gateway + rapporteur/shadow info)
for all carriages that have an oeil_procedure_ref but no oeil_procedure_data.

This is the same enrichment the context builder does on-demand during chat,
but applied in bulk so chatbot queries benefit from pre-cached data.

Usage:
    # Enrich all unenriched carriages (default: 2s delay between requests)
    python3.12 scripts/bulk_enrich_oeil.py

    # Dry run - show what would be enriched without fetching
    python3.12 scripts/bulk_enrich_oeil.py --dry-run

    # Limit to first N carriages
    python3.12 scripts/bulk_enrich_oeil.py --limit 50

    # Also re-enrich stale data (older than 7 days)
    python3.12 scripts/bulk_enrich_oeil.py --refresh-stale

    # Custom delay between requests (seconds)
    python3.12 scripts/bulk_enrich_oeil.py --delay 3

    # Verbose logging
    python3.12 scripts/bulk_enrich_oeil.py --verbose
"""

import asyncio
import argparse
import logging
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / '.env')

from core.database import SessionLocal
from models.legislative_train import LegislativeCarriage
from services.api_clients.oeil_client import OEILClient
from sqlalchemy.orm.attributes import flag_modified

logger = logging.getLogger(__name__)


def parse_rapporteur_text(rap_text: str) -> dict:
    """Parse 'LASTNAME Firstname (Group)' into {name, political_group}."""
    group_match = re.search(r'\(([^)]+)\)', rap_text)
    name = re.sub(r'\s*\([^)]*\)\s*', '', rap_text).strip()
    group = group_match.group(1) if group_match else None
    return {'name': name, 'political_group': group}


async def enrich_single_carriage(
    client: OEILClient,
    carriage: LegislativeCarriage,
    db,
    verbose: bool = False
) -> dict:
    """
    Enrich a single carriage with OEIL data.

    Returns stats dict: {success, rapporteur_found, shadow_count, doc_count, error}
    """
    ref = carriage.oeil_procedure_ref
    stats = {
        'success': False,
        'rapporteur_found': False,
        'shadow_count': 0,
        'doc_count': 0,
        'error': None,
    }

    try:
        # Fetch documentation gateway AND procedure lookup in parallel
        gateway_result, lookup_result = await asyncio.gather(
            client.get_documentation_gateway(ref),
            client.lookup_procedure(ref),
            return_exceptions=True,
        )

        # Build enriched data
        existing_data = carriage.oeil_procedure_data or {}

        # Documentation gateway
        if isinstance(gateway_result, Exception):
            logger.warning(f"  [WARN] Gateway failed for {ref}: {gateway_result}")
            stats['error'] = f"gateway: {gateway_result}"
        else:
            existing_data['documentation_gateway'] = gateway_result
            existing_data['documentation_gateway_fetched_at'] = datetime.now(timezone.utc).isoformat()
            stats['doc_count'] = len(gateway_result) if gateway_result else 0

        # Procedure lookup (rapporteur + title + committees)
        if isinstance(lookup_result, Exception):
            logger.warning(f"  [WARN] Lookup failed for {ref}: {lookup_result}")
            if not stats['error']:
                stats['error'] = f"lookup: {lookup_result}"
        elif lookup_result:
            # Extract rapporteur
            if lookup_result.rapporteurs:
                rap_info = parse_rapporteur_text(lookup_result.rapporteurs[0])
                existing_data.setdefault('key_players', {})
                committee_data = existing_data['key_players'].get('committee_responsible', {})
                committee_data['rapporteur'] = rap_info
                committee_data['code'] = carriage.lead_committee
                existing_data['key_players']['committee_responsible'] = committee_data
                stats['rapporteur_found'] = True

                if verbose:
                    logger.info(f"  [OK] Rapporteur: {rap_info['name']} ({rap_info['political_group']})")

            # Extract shadow rapporteurs
            if lookup_result.shadow_rapporteurs:
                shadow_list = [parse_rapporteur_text(s) for s in lookup_result.shadow_rapporteurs]
                existing_data.setdefault('key_players', {})
                committee_data = existing_data['key_players'].get('committee_responsible', {})
                committee_data['shadow_rapporteurs'] = shadow_list
                existing_data['key_players']['committee_responsible'] = committee_data
                stats['shadow_count'] = len(shadow_list)

                if verbose:
                    logger.info(f"  [OK] Shadows: {len(shadow_list)}")
            else:
                # Ensure shadow_rapporteurs key exists
                existing_data.setdefault('key_players', {})
                committee_data = existing_data['key_players'].get('committee_responsible', {})
                if 'shadow_rapporteurs' not in committee_data:
                    committee_data['shadow_rapporteurs'] = []
                existing_data['key_players']['committee_responsible'] = committee_data

            # Update title if better
            if lookup_result.title and lookup_result.title != f"Procedure {ref}":
                if not carriage.title or len(lookup_result.title) > len(carriage.title):
                    existing_data['lookup_title'] = lookup_result.title

            # Update committees from lookup
            if lookup_result.committees:
                existing_data['lookup_committees'] = lookup_result.committees

        # Count shadows already in data
        shadows = (
            existing_data.get('key_players', {})
            .get('committee_responsible', {})
            .get('shadow_rapporteurs', [])
        )
        stats['shadow_count'] = len(shadows)

        # Write back to DB
        carriage.oeil_procedure_data = existing_data
        carriage.enriched_at = datetime.now(timezone.utc)
        flag_modified(carriage, 'oeil_procedure_data')

        try:
            db.commit()
            stats['success'] = True
        except Exception as e:
            logger.error(f"  [ERROR] DB commit failed for {ref}: {e}")
            db.rollback()
            stats['error'] = f"db: {e}"

    except Exception as e:
        logger.error(f"  [ERROR] Enrichment failed for {ref}: {e}")
        stats['error'] = str(e)
        db.rollback()

    return stats


async def bulk_enrich(args):
    """Main bulk enrichment function."""
    db = SessionLocal()
    client = OEILClient()

    try:
        # Query carriages that need enrichment
        query = db.query(LegislativeCarriage).filter(
            LegislativeCarriage.oeil_procedure_ref != None
        )

        if args.refresh_stale:
            # Include both unenriched AND stale (>7 days old)
            stale_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            query = query.filter(
                (LegislativeCarriage.oeil_procedure_data == None) |
                (LegislativeCarriage.enriched_at == None) |
                (LegislativeCarriage.enriched_at < stale_cutoff)
            )
        else:
            # Only unenriched
            query = query.filter(
                LegislativeCarriage.oeil_procedure_data == None
            )

        carriages = query.order_by(LegislativeCarriage.id).all()
        total = len(carriages)

        if args.limit and args.limit < total:
            carriages = carriages[:args.limit]
            total_to_process = args.limit
        else:
            total_to_process = total

        print("=" * 65)
        print("OEIL Bulk Enrichment")
        print("=" * 65)
        print(f"Carriages needing enrichment: {total}")
        print(f"Will process: {total_to_process}")
        print(f"Delay between requests: {args.delay}s")
        print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
        if args.refresh_stale:
            print("Including stale data (>7 days old)")
        print("=" * 65)

        if args.dry_run:
            print("\n[DRY RUN] Would enrich these carriages:\n")
            for i, c in enumerate(carriages):
                status = "stale" if c.oeil_procedure_data else "unenriched"
                print(f"  {i+1:3d}. [{status:11s}] {c.oeil_procedure_ref:20s} {(c.title or '')[:60]}")
            print(f"\nTotal: {total_to_process} carriages")
            return

        # Process
        totals = {
            'success': 0,
            'failed': 0,
            'rapporteurs': 0,
            'shadows': 0,
            'documents': 0,
        }
        start_time = time.time()

        for i, carriage in enumerate(carriages):
            ref = carriage.oeil_procedure_ref
            title_short = (carriage.title or 'No title')[:55]

            print(f"\n[{i+1}/{total_to_process}] {ref} - {title_short}")

            stats = await enrich_single_carriage(
                client, carriage, db, verbose=args.verbose
            )

            if stats['success']:
                totals['success'] += 1
                if stats['rapporteur_found']:
                    totals['rapporteurs'] += 1
                totals['shadows'] += stats['shadow_count']
                totals['documents'] += stats['doc_count']
                status_parts = []
                if stats['rapporteur_found']:
                    status_parts.append("rapporteur")
                if stats['doc_count']:
                    status_parts.append(f"{stats['doc_count']} docs")
                if stats['shadow_count']:
                    status_parts.append(f"{stats['shadow_count']} shadows")
                status_str = ", ".join(status_parts) if status_parts else "no data found"
                print(f"  [OK] {status_str}")
            else:
                totals['failed'] += 1
                print(f"  [FAIL] {stats['error']}")

            # Rate limit: wait between requests (each enrichment makes 2 HTTP calls)
            if i < total_to_process - 1:
                await asyncio.sleep(args.delay)

        elapsed = time.time() - start_time

        # Final report
        print("\n" + "=" * 65)
        print("ENRICHMENT COMPLETE")
        print("=" * 65)
        print(f"Processed:    {totals['success'] + totals['failed']}")
        print(f"Succeeded:    {totals['success']}")
        print(f"Failed:       {totals['failed']}")
        print(f"Rapporteurs:  {totals['rapporteurs']}")
        print(f"Shadows:      {totals['shadows']}")
        print(f"Documents:    {totals['documents']}")
        print(f"Time:         {elapsed:.0f}s ({elapsed/60:.1f}m)")
        print(f"Avg per item: {elapsed/max(1, totals['success']+totals['failed']):.1f}s")

        # Updated DB stats
        total_carriages = db.query(LegislativeCarriage).count()
        with_data = db.query(LegislativeCarriage).filter(
            LegislativeCarriage.oeil_procedure_data != None
        ).count()
        print(f"\nDB state: {with_data}/{total_carriages} carriages now have OEIL data ({100*with_data/total_carriages:.1f}%)")
        print("=" * 65)

    finally:
        await client.close()
        db.close()


def main():
    parser = argparse.ArgumentParser(description='Bulk enrich legislative carriages with OEIL data')
    parser.add_argument('--limit', type=int, help='Max carriages to process')
    parser.add_argument('--delay', type=float, default=2.0, help='Delay between requests in seconds (default: 2)')
    parser.add_argument('--refresh-stale', action='store_true', help='Also re-enrich data older than 7 days')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be enriched without fetching')
    parser.add_argument('--verbose', action='store_true', help='Show detailed per-carriage info')
    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
        datefmt='%H:%M:%S'
    )
    # Quiet SQLAlchemy unless verbose
    if not args.verbose:
        logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('httpcore').setLevel(logging.WARNING)

    asyncio.run(bulk_enrich(args))


if __name__ == '__main__':
    main()
