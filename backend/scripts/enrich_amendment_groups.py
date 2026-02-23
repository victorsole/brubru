"""
Enrich MEP amendments with political group data from the EP Open Data API.

Looks up each amendment's author name(s) against the current MEP roster
and fills in the political_group field where missing.

Usage:
    # Preview: show how many amendments would be enriched
    python scripts/enrich_amendment_groups.py --dry-run

    # Run enrichment
    python scripts/enrich_amendment_groups.py

    # Force re-enrich (overwrite existing groups)
    python scripts/enrich_amendment_groups.py --force

Created: February 2026
"""

import asyncio
import argparse
import logging
import ssl
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Group code normalisation (EP API uses different codes)
GROUP_ALIASES = {
    "PPE": "EPP",
    "S&D": "S&D",
    "RE": "Renew",
    "Renew": "Renew",
    "Verts/ALE": "Greens/EFA",
    "Greens/EFA": "Greens/EFA",
    "ID": "PfE",
    "PfE": "PfE",
    "ECR": "ECR",
    "GUE/NGL": "The Left",
    "The Left": "The Left",
    "NI": "NI",
    "ESN": "ESN",
}


def _normalise_group(raw: str) -> str:
    """Normalise EP API group code to Brubru canonical name."""
    if not raw:
        return ""
    # Try direct match first
    if raw in GROUP_ALIASES:
        return GROUP_ALIASES[raw]
    # Try case-insensitive
    for k, v in GROUP_ALIASES.items():
        if k.lower() == raw.lower():
            return v
    return raw


async def fetch_mep_lookup() -> dict:
    """Fetch all current MEPs from EP Open Data API, return name->group dict."""
    import httpx

    # Create SSL context that doesn't verify (workaround for local cert issue)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    lookup = {}
    async with httpx.AsyncClient(timeout=60, follow_redirects=True, verify=ctx) as client:
        offset = 0
        while True:
            r = await client.get(
                'https://data.europarl.europa.eu/api/v2/meps/show-current',
                params={'format': 'application/ld+json', 'offset': offset, 'limit': 100},
                headers={'Accept': 'application/ld+json', 'User-Agent': 'Brubru-1.0'}
            )
            if r.status_code != 200:
                print(f"[ERROR] EP API returned {r.status_code} at offset {offset}")
                break

            data = r.json()
            items = data if isinstance(data, list) else data.get('data', [])
            if not items:
                break

            for m in items:
                raw_group = m.get('api:political-group', m.get('hasPoliticalGroup', ''))
                group = _normalise_group(raw_group) if raw_group else ''
                given = m.get('givenName', '')
                family = m.get('familyName', '')
                if given and family and group:
                    full_name = f'{given} {family}'
                    lookup[full_name] = group

            offset += len(items)
            if len(items) < 100:
                break

    return lookup


def run_enrichment(mep_lookup: dict, force: bool, dry_run: bool):
    """Update amendments in the database with political group from MEP lookup."""
    from core.database import engine, SessionLocal
    engine.echo = False
    from models.mep_amendment import MEPAmendment
    from sqlalchemy import func

    db = SessionLocal()
    try:
        # Query amendments that need enrichment
        if force:
            query = db.query(MEPAmendment).filter(
                func.array_length(MEPAmendment.author_names, 1) > 0
            )
            label = "all amendments with authors"
        else:
            query = db.query(MEPAmendment).filter(
                (MEPAmendment.political_group.is_(None)) | (MEPAmendment.political_group == ''),
                func.array_length(MEPAmendment.author_names, 1) > 0
            )
            label = "amendments missing political group (with authors)"

        total = query.count()
        print(f"\n[INFO] {label}: {total:,}")
        print(f"[INFO] MEP lookup entries: {len(mep_lookup)}")

        if total == 0:
            print("[OK] Nothing to enrich.")
            return

        if dry_run:
            # Sample some to show what would happen
            sample = query.limit(100).all()
            would_match = 0
            for a in sample:
                for author in (a.author_names or []):
                    if author in mep_lookup:
                        would_match += 1
                        break
            match_rate = round(would_match / len(sample) * 100, 1) if sample else 0
            estimated = int(total * match_rate / 100)
            print(f"\n[INFO] Sample match rate: {would_match}/{len(sample)} ({match_rate}%)")
            print(f"[INFO] Estimated enrichments: ~{estimated:,} out of {total:,}")

            # Show group distribution from sample
            groups = {}
            for a in sample:
                for author in (a.author_names or []):
                    g = mep_lookup.get(author)
                    if g:
                        groups[g] = groups.get(g, 0) + 1
                        break
            if groups:
                print(f"\nSample group distribution:")
                for g, c in sorted(groups.items(), key=lambda x: -x[1]):
                    print(f"  {g}: {c}")
            return

        # Process in batches using offset to avoid re-fetching the same records
        print(f"\n[START] Enriching {total:,} amendments...")
        start = time.time()
        batch_size = 500
        enriched = 0
        offset = 0

        while True:
            batch = query.offset(offset).limit(batch_size).all()
            if not batch:
                break

            batch_enriched = 0
            for amendment in batch:
                matched_group = None
                for author in (amendment.author_names or []):
                    g = mep_lookup.get(author)
                    if g:
                        matched_group = g
                        break

                if matched_group:
                    amendment.political_group = matched_group
                    batch_enriched += 1

            db.commit()
            enriched += batch_enriched

            # Enriched rows drop off the query, so only advance offset by
            # the number of unenriched rows (they stay in the result set)
            offset += (len(batch) - batch_enriched)

            processed = offset + enriched
            print(f"  [{processed:,}/{total:,}] Enriched {batch_enriched}/{len(batch)} in this batch (total enriched: {enriched:,})")

        elapsed = time.time() - start
        no_match = total - enriched
        print(f"\n[OK] Enrichment complete ({elapsed:.1f}s)")
        print(f"  Total:     {total:,}")
        print(f"  Enriched:  {enriched:,}")
        print(f"  No match:  {no_match:,} (authors not in current MEP roster)")

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Enrich MEP amendments with political group from EP API"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without changes")
    parser.add_argument("--force", action="store_true", help="Re-enrich all, even those with groups")
    args = parser.parse_args()

    print("[INFO] Fetching current MEP roster from EP Open Data API...")
    mep_lookup = asyncio.run(fetch_mep_lookup())
    print(f"[OK] Built lookup: {len(mep_lookup)} MEPs")

    # Show group counts
    group_counts = {}
    for g in mep_lookup.values():
        group_counts[g] = group_counts.get(g, 0) + 1
    for g, c in sorted(group_counts.items(), key=lambda x: -x[1]):
        print(f"  {g}: {c}")

    run_enrichment(mep_lookup, args.force, args.dry_run)


if __name__ == "__main__":
    main()
