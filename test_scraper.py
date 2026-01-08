#!/usr/bin/env python3
"""Test legislative train scraper"""
import asyncio
import sys
sys.path.insert(0, '/Users/victorsole/Documents/GitHub/brubru')

from backend.services.scrapers.legislative_train_scraper import LegislativeTrainScraper

async def main():
    scraper = LegislativeTrainScraper()

    # Test get_train_carriages for priority-1
    print("Testing get_train_carriages for priority-1...")
    carriages = await scraper.get_train_carriages('priority-1')
    print(f"\nFound {len(carriages)} carriages")

    if carriages:
        print(f"\nFirst carriage:")
        print(carriages[0])
    else:
        print("\nNo carriages found!")

    print(f"\nScraper stats: {scraper.get_stats()}")

if __name__ == '__main__':
    asyncio.run(main())
