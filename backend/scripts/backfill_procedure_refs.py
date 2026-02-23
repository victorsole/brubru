"""
Backfill procedure_reference for mep_amendments and amendment_documents.

The bulk backfill populated amendments from DOCX files but never fetched
the procedure_reference from the EP Open Data API. This script:

1. Gets all amendment_documents with empty procedure_reference
2. For each PR/PA doc, fetches the document detail from EP Open Data API
3. Extracts procedure_reference from the title_alternative field
4. For AM docs, inherits from the nearby PR doc
5. Updates amendment_documents.procedure_reference
6. Propagates to mep_amendments via pe_reference JOIN

Usage:
    python scripts/backfill_procedure_refs.py
    python scripts/backfill_procedure_refs.py --dry-run
    python scripts/backfill_procedure_refs.py --limit 10

Created: February 2026
"""

import asyncio
import argparse
import logging
import re
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def _resolve_am_from_cache(pe_ref: str, committee: str, pe_to_proc: dict) -> str:
    """
    Try to resolve an AM document's procedure_reference from nearby PE numbers.
    AM documents typically have PE numbers close to their parent PR.
    """
    pe_match = re.match(r'PE(\d{3})\.(\d{3})', pe_ref)
    if not pe_match:
        return ""

    pe_num = int(pe_match.group(1) + pe_match.group(2))

    for delta in range(-5, 6):
        if delta == 0:
            continue
        nearby_num = pe_num + delta
        nearby_pe = f"PE{nearby_num // 1000}.{nearby_num % 1000:03d}"

        if nearby_pe in pe_to_proc and pe_to_proc[nearby_pe]:
            return pe_to_proc[nearby_pe]

    return ""


async def fetch_batch(client, identifiers, semaphore):
    """Fetch document details concurrently with semaphore-based rate limiting."""
    import httpx

    results = {}

    async def fetch_one(ep_id):
        async with semaphore:
            try:
                detail = await client.get_document_detail(
                    ep_id, endpoint="committee-documents"
                )
                proc_ref = detail.get("procedure_reference", "")
                results[ep_id] = proc_ref
                await asyncio.sleep(0.5)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    results[ep_id] = None  # Not found
                else:
                    results[ep_id] = None
                await asyncio.sleep(0.3)
            except Exception:
                results[ep_id] = None
                await asyncio.sleep(0.3)

    tasks = [fetch_one(ep_id) for ep_id in identifiers]
    await asyncio.gather(*tasks)
    return results


async def run_backfill(dry_run: bool = False, limit: int = 0):
    """Fetch procedure references from EP Open Data API and backfill."""
    from core.database import SessionLocal
    from sqlalchemy import text
    from services.api_clients.ep_open_data_client import EPOpenDataClient

    db = SessionLocal()
    client = EPOpenDataClient()

    try:
        # Get all amendment_documents with empty procedure_reference
        # Process PR/PA docs first, then AM docs
        r = db.execute(text(
            "SELECT id, ep_identifier, pe_reference, committee_code "
            "FROM amendment_documents "
            "WHERE procedure_reference IS NULL OR procedure_reference = '' "
            "ORDER BY "
            "  CASE WHEN ep_identifier LIKE '%-AM-%' THEN 1 ELSE 0 END, "
            "  ep_identifier"
        ))
        docs = r.fetchall()

        if limit > 0:
            docs = docs[:limit]

        total = len(docs)
        pr_pa_docs = [d for d in docs if "-AM-" not in d[1]]
        am_docs = [d for d in docs if "-AM-" in d[1]]

        print(f"[INFO] Found {total} amendment_documents without procedure_reference")
        print(f"  PR/PA docs: {len(pr_pa_docs)}")
        print(f"  AM docs: {len(am_docs)}")

        if dry_run:
            print("[INFO] Dry run -- sample documents:")
            for doc in pr_pa_docs[:10]:
                print(f"  {doc[1]} (PE: {doc[2]}, committee: {doc[3]})")
            if len(pr_pa_docs) > 10:
                print(f"  ... and {len(pr_pa_docs) - 10} more PR/PA docs")
            await client.close()
            db.close()
            return

        # Track results
        updated = 0
        no_ref = 0
        failed = 0
        pe_to_proc: dict = {}

        start = time.time()

        # Phase 1: Fetch PR/PA docs in batches of 5 (concurrent with rate limiting)
        print(f"\n[INFO] Phase 1: Fetching {len(pr_pa_docs)} PR/PA documents...")
        semaphore = asyncio.Semaphore(3)  # Max 3 concurrent requests
        batch_size = 20

        for batch_start in range(0, len(pr_pa_docs), batch_size):
            batch = pr_pa_docs[batch_start:batch_start + batch_size]
            identifiers = [d[1] for d in batch]

            batch_results = await fetch_batch(client, identifiers, semaphore)

            for doc in batch:
                doc_id, ep_id, pe_ref, committee = doc

                # Check PE cache first
                if pe_ref in pe_to_proc:
                    proc_ref = pe_to_proc[pe_ref]
                    if proc_ref:
                        db.execute(text(
                            "UPDATE amendment_documents SET procedure_reference = :proc_ref "
                            "WHERE id = :doc_id"
                        ), {"proc_ref": proc_ref, "doc_id": doc_id})
                        updated += 1
                    else:
                        no_ref += 1
                    continue

                proc_ref = batch_results.get(ep_id)
                if proc_ref is None:
                    failed += 1
                    pe_to_proc[pe_ref] = ""
                    continue

                pe_to_proc[pe_ref] = proc_ref

                if proc_ref:
                    db.execute(text(
                        "UPDATE amendment_documents SET procedure_reference = :proc_ref "
                        "WHERE id = :doc_id"
                    ), {"proc_ref": proc_ref, "doc_id": doc_id})
                    updated += 1
                else:
                    no_ref += 1

            # Commit and report progress
            db.commit()
            processed = min(batch_start + batch_size, len(pr_pa_docs))
            elapsed = time.time() - start
            rate = processed / elapsed if elapsed > 0 else 1
            remaining = (len(pr_pa_docs) - processed) / rate if rate > 0 else 0
            print(f"  [{processed}/{len(pr_pa_docs)}] {updated} updated, ~{int(remaining)}s remaining")

        # Phase 2: Resolve AM docs from PE cache (no API calls needed)
        print(f"\n[INFO] Phase 2: Resolving {len(am_docs)} AM documents from PE cache...")
        am_resolved = 0
        for doc in am_docs:
            doc_id, ep_id, pe_ref, committee = doc
            proc_ref = _resolve_am_from_cache(pe_ref, committee, pe_to_proc)
            if proc_ref:
                db.execute(text(
                    "UPDATE amendment_documents SET procedure_reference = :proc_ref "
                    "WHERE id = :doc_id"
                ), {"proc_ref": proc_ref, "doc_id": doc_id})
                pe_to_proc[pe_ref] = proc_ref
                am_resolved += 1
                updated += 1

        db.commit()
        print(f"  Resolved {am_resolved}/{len(am_docs)} AM documents from nearby PRs")

        # Phase 3: Propagate to mep_amendments
        print(f"\n[INFO] Phase 3: Propagating to mep_amendments...")
        result = db.execute(text("""
            UPDATE mep_amendments ma
            SET procedure_reference = ad.procedure_reference
            FROM amendment_documents ad
            WHERE ma.pe_reference = ad.pe_reference
              AND ad.procedure_reference IS NOT NULL
              AND ad.procedure_reference <> ''
              AND (ma.procedure_reference IS NULL OR ma.procedure_reference = '')
        """))
        amendments_updated = result.rowcount
        db.commit()

        elapsed = time.time() - start
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)

        print(f"\n{'=' * 60}")
        print(f"[OK] Backfill complete ({minutes}m {seconds}s)")
        print(f"  Documents updated:    {updated}")
        print(f"  Documents no ref:     {no_ref}")
        print(f"  Documents failed:     {failed}")
        print(f"  AM docs resolved:     {am_resolved}")
        print(f"  Amendments updated:   {amendments_updated}")

        # Summary
        r = db.execute(text(
            "SELECT procedure_reference, COUNT(*) as cnt "
            "FROM mep_amendments "
            "WHERE procedure_reference IS NOT NULL AND procedure_reference <> '' "
            "GROUP BY procedure_reference "
            "ORDER BY cnt DESC LIMIT 20"
        ))
        rows = r.fetchall()
        if rows:
            total_resolved = sum(r[1] for r in rows)
            print(f"\nTop procedures by amendment count (total resolved: {total_resolved}):")
            for row in rows:
                print(f"  {row[0]}: {row[1]} amendments")

    finally:
        await client.close()
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Backfill procedure_reference for MEP amendments"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--limit", type=int, default=0, help="Limit docs to process")
    args = parser.parse_args()

    asyncio.run(run_backfill(dry_run=args.dry_run, limit=args.limit))


if __name__ == "__main__":
    main()
