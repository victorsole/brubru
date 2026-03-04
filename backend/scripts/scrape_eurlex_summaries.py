"""
EUR-Lex Summary Scraper CLI

Scrapes EUR-Lex summaries by policy chapter and generates knowledge guide
markdown files for the AI context builder.

Usage:
    python3.12 scripts/scrape_eurlex_summaries.py --chapters 2,3,4
    python3.12 scripts/scrape_eurlex_summaries.py --all
    python3.12 scripts/scrape_eurlex_summaries.py --chapters 2 --dry-run
    python3.12 scripts/scrape_eurlex_summaries.py --all --verbose
"""

import asyncio
import argparse
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    import httpx
except ImportError:
    print("[ERROR] Required packages: pip install httpx beautifulsoup4")
    sys.exit(1)

from services.scrapers.eurlex_summary_scraper import (
    EURLexSummaryScraper,
    CHAPTERS_TO_SCRAPE,
    HEADERS,
)

GUIDES_DIR = Path(__file__).parent.parent / "knowledge_base" / "guides"


async def main():
    parser = argparse.ArgumentParser(description='Scrape EUR-Lex summaries and generate knowledge guides')
    parser.add_argument('--chapters', '-c', type=str, default=None,
                        help='Comma-separated chapter IDs (e.g., 2,3,4). Use --all for all 20.')
    parser.add_argument('--all', action='store_true',
                        help='Scrape all 20 uncovered chapters')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be scraped without making requests')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show detailed progress')
    parser.add_argument('--delay', type=float, default=3.0,
                        help='Delay between requests in seconds (default: 3.0)')
    parser.add_argument('--max-summaries', type=int, default=20,
                        help='Max summary pages to scrape per chapter (default: 20)')
    args = parser.parse_args()

    # Determine which chapters to scrape
    if args.all:
        chapter_ids = sorted(CHAPTERS_TO_SCRAPE.keys())
    elif args.chapters:
        try:
            chapter_ids = [int(c.strip()) for c in args.chapters.split(',')]
            for cid in chapter_ids:
                if cid not in CHAPTERS_TO_SCRAPE:
                    valid = sorted(CHAPTERS_TO_SCRAPE.keys())
                    print(f"[ERROR] Chapter {cid} not in CHAPTERS_TO_SCRAPE. Valid: {valid}")
                    sys.exit(1)
        except ValueError:
            print("[ERROR] --chapters must be comma-separated integers (e.g., 2,3,4)")
            sys.exit(1)
    else:
        print("[ERROR] Specify --chapters or --all")
        parser.print_help()
        sys.exit(1)

    print(f"[START] EUR-Lex Summary Scraper")
    print(f"  Chapters: {chapter_ids}")
    print(f"  Output: {GUIDES_DIR}")
    print()

    if args.dry_run:
        print("[DRY-RUN] Would scrape the following chapters:")
        for cid in chapter_ids:
            info = CHAPTERS_TO_SCRAPE[cid]
            output_file = GUIDES_DIR / f"{info['filename']}.md"
            exists = output_file.exists()
            status = "EXISTS (will overwrite)" if exists else "NEW"
            print(f"  Chapter {cid:2d}: {info['topic']:<45} -> {info['filename']}.md [{status}]")
        return

    # Create scraper
    scraper = EURLexSummaryScraper(delay=args.delay)
    GUIDES_DIR.mkdir(parents=True, exist_ok=True)

    results = []

    async with httpx.AsyncClient(
        headers=HEADERS,
        follow_redirects=True,
        timeout=args.delay * 2 + 30
    ) as client:
        for i, chapter_id in enumerate(chapter_ids, 1):
            info = CHAPTERS_TO_SCRAPE[chapter_id]
            print(f"[{i}/{len(chapter_ids)}] Scraping Chapter {chapter_id}: {info['topic']}")

            try:
                chapter_data = await scraper.scrape_chapter(
                    chapter_id=chapter_id,
                    client=client,
                    max_summaries=args.max_summaries,
                    verbose=args.verbose
                )

                # Generate markdown
                markdown = scraper.generate_guide_markdown(chapter_data)

                # Write to file
                output_file = GUIDES_DIR / f"{info['filename']}.md"
                output_file.write_text(markdown, encoding='utf-8')

                line_count = len(markdown.splitlines())
                leg_count = len(chapter_data.key_legislation)
                sum_count = len(chapter_data.summaries)

                print(f"  [OK] {output_file.name}: {line_count} lines, "
                      f"{leg_count} legislation entries, {sum_count} summaries")

                results.append({
                    'chapter': chapter_id,
                    'topic': info['topic'],
                    'filename': info['filename'],
                    'legislation': leg_count,
                    'summaries': sum_count,
                    'lines': line_count,
                    'status': 'OK'
                })

            except Exception as e:
                print(f"  [ERROR] Chapter {chapter_id} failed: {e}")
                results.append({
                    'chapter': chapter_id,
                    'topic': info['topic'],
                    'filename': info['filename'],
                    'status': f'FAILED: {str(e)[:80]}'
                })

            # Extra delay between chapters
            if i < len(chapter_ids):
                await asyncio.sleep(args.delay)

    # Summary
    print()
    print("=" * 60)
    print("SCRAPING SUMMARY")
    print("=" * 60)

    ok_count = sum(1 for r in results if r['status'] == 'OK')
    fail_count = len(results) - ok_count
    total_leg = sum(r.get('legislation', 0) for r in results)

    print(f"  Chapters scraped: {len(results)}")
    print(f"  Succeeded: {ok_count}")
    print(f"  Failed: {fail_count}")
    print(f"  Total legislation entries: {total_leg}")
    print()

    for r in results:
        status = r['status']
        if status == 'OK':
            print(f"  [OK] Ch.{r['chapter']:2d} {r['topic']:<40} "
                  f"-> {r['filename']}.md ({r['legislation']} leg, {r['lines']} lines)")
        else:
            print(f"  [FAIL] Ch.{r['chapter']:2d} {r['topic']:<40} -> {status}")

    if fail_count:
        print(f"\n[WARN] {fail_count} chapter(s) failed. Re-run with --verbose for details.")


if __name__ == '__main__':
    asyncio.run(main())
