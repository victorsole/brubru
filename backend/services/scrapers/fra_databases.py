"""European Union Agency for Fundamental Rights — databases.
FRA is behind an Anubis proof-of-work wall, so the listings are walked through a
real browser (eu_agency_listing.walk_browser). One database per ingestor.
"""
from __future__ import annotations

from services.scrapers.economy_common import Item
from services.scrapers.eu_agency_listing import ingest_browser

_BASE = "https://fra.europa.eu"


def ingest_fra_case_law(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return ingest_browser(_BASE, "/en/case-law-database", "fra", "case_law",
                          "/en/caselaw-reference/", "fra_caselaw")
