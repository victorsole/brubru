"""
EP Committees API Endpoints

Provides access to European Parliament committee information and membership.
"""

import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.scrapers.european_parliament_scraper import EuropeanParliamentScraper

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/committees", tags=["committees"])


class Committee(BaseModel):
    """Committee information"""
    code: str
    name: str
    url: str
    type: str


class CommitteeMember(BaseModel):
    """Committee member information"""
    mep_id: str
    name: str
    country: str
    political_group: str
    role: str
    profile_url: str


class CommitteeDetails(BaseModel):
    """Detailed committee information"""
    code: str
    name: str
    description: str
    members: List[CommitteeMember]
    member_count: int
    url: str
    last_updated: str


@router.get("/", response_model=List[Committee])
async def get_all_committees():
    """
    Get list of all EP committees.

    Returns:
        List of committees with code, name, and URL

    Example:
        GET /api/committees/

        Response:
        [
            {
                "code": "ENVI",
                "name": "Environment, Public Health and Food Safety",
                "url": "https://www.europarl.europa.eu/committees/en/envi/home",
                "type": "standing"
            },
            ...
        ]
    """
    try:
        scraper = EuropeanParliamentScraper()
        committees = await scraper.get_all_committees()
        await scraper.close()

        return [Committee(**c) for c in committees]

    except Exception as e:
        logger.error(f"Failed to fetch committees: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch committees: {str(e)}")


@router.get("/{committee_code}", response_model=CommitteeDetails)
async def get_committee_details(
    committee_code: str,
    include_substitutes: bool = Query(True, description="Include substitute members")
):
    """
    Get detailed information about a specific committee.

    Args:
        committee_code: Committee code (e.g., ENVI, ITRE)
        include_substitutes: Whether to include substitute members

    Returns:
        Committee details including all members

    Example:
        GET /api/committees/ENVI

        Response:
        {
            "code": "ENVI",
            "name": "Environment, Public Health and Food Safety",
            "description": "...",
            "members": [
                {
                    "mep_id": "123456",
                    "name": "John Doe",
                    "country": "BE",
                    "political_group": "EPP",
                    "role": "Chair",
                    "profile_url": "..."
                },
                ...
            ],
            "member_count": 85,
            "url": "...",
            "last_updated": "2025-01-11T..."
        }
    """
    try:
        scraper = EuropeanParliamentScraper()
        details = await scraper.get_committee_details(committee_code.upper())
        await scraper.close()

        # Filter out substitutes if requested
        if not include_substitutes:
            details['members'] = [m for m in details['members'] if m['role'] != 'Substitute']
            details['member_count'] = len(details['members'])

        return CommitteeDetails(**details)

    except Exception as e:
        logger.error(f"Failed to fetch committee {committee_code}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch committee details: {str(e)}")


@router.get("/{committee_code}/members", response_model=List[CommitteeMember])
async def get_committee_members(
    committee_code: str,
    role: Optional[str] = Query(None, description="Filter by role (Chair, Vice-Chair, Member, Substitute)")
):
    """
    Get members of a specific committee.

    Args:
        committee_code: Committee code (e.g., ENVI, ITRE)
        role: Optional role filter

    Returns:
        List of committee members

    Example:
        GET /api/committees/ENVI/members?role=Chair

        Response:
        [
            {
                "mep_id": "123456",
                "name": "John Doe",
                "country": "BE",
                "political_group": "EPP",
                "role": "Chair",
                "profile_url": "..."
            }
        ]
    """
    try:
        scraper = EuropeanParliamentScraper()
        members = await scraper.get_committee_members(committee_code.upper())
        await scraper.close()

        # Filter by role if specified
        if role:
            members = [m for m in members if m['role'].lower() == role.lower()]

        return [CommitteeMember(**m) for m in members]

    except Exception as e:
        logger.error(f"Failed to fetch members for {committee_code}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch committee members: {str(e)}")


@router.get("/search")
async def search_committees(
    query: str = Query(..., description="Search query (committee name or code)"),
    limit: int = Query(10, description="Maximum results")
):
    """
    Search for committees by name or code.

    Args:
        query: Search query
        limit: Maximum results

    Returns:
        Matching committees

    Example:
        GET /api/committees/search?query=environment

        Response:
        [
            {
                "code": "ENVI",
                "name": "Environment, Public Health and Food Safety",
                "url": "...",
                "type": "standing"
            }
        ]
    """
    try:
        scraper = EuropeanParliamentScraper()
        all_committees = await scraper.get_all_committees()
        await scraper.close()

        # Simple text search
        query_lower = query.lower()
        results = [
            c for c in all_committees
            if query_lower in c['code'].lower() or query_lower in c['name'].lower()
        ]

        return results[:limit]

    except Exception as e:
        logger.error(f"Failed to search committees: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to search committees: {str(e)}")
