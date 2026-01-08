"""
EU Data API Router

FastAPI endpoints for accessing EU institutional data.
Part of Phase 10: API Router Implementation

Endpoints:
- GET /api/eu-data/meps - List all MEPs
- GET /api/eu-data/legislation/{celex} - Get legislation by CELEX
- GET /api/eu-data/procedures/{reference} - Get OEIL procedure
- GET /api/eu-data/terminology - Search IATE terminology
- GET /api/eu-data/publications - Search Publications Office
- POST /api/eu-data/sparql - Execute SPARQL query
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Depends, status
from pydantic import BaseModel, Field, HttpUrl

from ..services.scrapers.european_parliament_scraper import EuropeanParliamentScraper
from ..services.scrapers.eurlex_scraper import EURLexScraper
from ..services.scrapers.oeil_scraper import OEILScraper
from ..services.scrapers.iate_scraper import IATEScraper
from ..services.cache.api_cache import APICache, get_or_set
from ..schemas.scrapers.scraper_schemas import (
    MEP, LegislativeDocument, LegislativeProcedure,
    TerminologyEntry, PublicationMetadata, SPARQLQueryResult
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/eu-data",
    tags=["EU Data"],
    responses={404: {"description": "Not found"}}
)


# ============================================================================
# Request/Response Models
# ============================================================================

class MEPListResponse(BaseModel):
    """Response for MEP list endpoint"""
    total: int
    meps: List[MEP]
    filtered_by: Optional[Dict[str, str]] = None


class LegislationResponse(BaseModel):
    """Response for legislation endpoint"""
    document: LegislativeDocument
    cache_hit: bool = False


class ProcedureResponse(BaseModel):
    """Response for OEIL procedure endpoint"""
    procedure: LegislativeProcedure
    cache_hit: bool = False


class TerminologySearchRequest(BaseModel):
    """Request for terminology search"""
    query: str = Field(..., min_length=2, description="Search query")
    source_lang: str = Field("en", description="Source language code")
    target_langs: Optional[List[str]] = Field(None, description="Target language codes")
    domain: Optional[str] = Field(None, description="Subject domain filter")
    limit: int = Field(20, ge=1, le=100, description="Maximum results")


class TerminologySearchResponse(BaseModel):
    """Response for terminology search"""
    query: str
    total_results: int
    entries: List[TerminologyEntry]


class PublicationSearchRequest(BaseModel):
    """Request for publication search"""
    query: Optional[str] = Field(None, description="Search query")
    author: Optional[str] = Field(None, description="Author name")
    date_from: Optional[datetime] = Field(None, description="Publication date from")
    date_to: Optional[datetime] = Field(None, description="Publication date to")
    isbn: Optional[str] = Field(None, description="ISBN")
    limit: int = Field(20, ge=1, le=100, description="Maximum results")


class PublicationSearchResponse(BaseModel):
    """Response for publication search"""
    total_results: int
    publications: List[PublicationMetadata]


class SPARQLRequest(BaseModel):
    """Request for SPARQL query"""
    query: str = Field(..., min_length=10, description="SPARQL query")
    endpoint: str = Field(
        "eurlex",
        description="SPARQL endpoint: 'eurlex', 'ep', or 'publications'"
    )
    format: str = Field("json", description="Response format: 'json' or 'xml'")
    timeout: int = Field(30, ge=5, le=300, description="Query timeout in seconds")


class SPARQLResponse(BaseModel):
    """Response for SPARQL query"""
    results: SPARQLQueryResult
    execution_time_ms: float
    cache_hit: bool = False


class ErrorResponse(BaseModel):
    """Error response"""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


# ============================================================================
# Dependency Injection
# ============================================================================

async def get_cache() -> APICache:
    """Get API cache instance"""
    # In production, would get from app state
    return APICache()


async def get_ep_scraper() -> EuropeanParliamentScraper:
    """Get European Parliament scraper"""
    return EuropeanParliamentScraper()


async def get_eurlex_scraper() -> EURLexScraper:
    """Get EUR-Lex scraper"""
    return EURLexScraper()


async def get_oeil_scraper() -> OEILScraper:
    """Get OEIL scraper"""
    return OEILScraper()


async def get_iate_scraper() -> IATEScraper:
    """Get IATE scraper"""
    return IATEScraper()


# ============================================================================
# MEP Endpoints
# ============================================================================

@router.get(
    "/meps",
    response_model=MEPListResponse,
    summary="List all MEPs",
    description="Get list of all current Members of European Parliament with optional filters"
)
async def list_meps(
    country: Optional[str] = Query(None, description="Filter by country code (e.g., 'BE', 'FR')"),
    political_group: Optional[str] = Query(None, description="Filter by political group code"),
    committee: Optional[str] = Query(None, description="Filter by committee membership"),
    scraper: EuropeanParliamentScraper = Depends(get_ep_scraper),
    cache: APICache = Depends(get_cache)
) -> MEPListResponse:
    """
    Retrieve list of MEPs with optional filters.

    **Caching**: Results cached for 6 hours
    **Rate Limit**: 100 calls/minute
    """
    try:
        # Try cache first
        cache_key = f"meps:{country or 'all'}:{political_group or 'all'}:{committee or 'all'}"
        cached = cache.get("mep_list", cache_key)

        if cached:
            logger.info(f"MEP list cache hit: {cache_key}")
            return MEPListResponse(**cached)

        # Fetch from scraper
        logger.info(f"Fetching MEPs from source (country={country})")
        meps = await scraper.get_all_meps(country=country)

        # Apply additional filters
        if political_group:
            meps = [
                mep for mep in meps
                if mep.political_group and mep.political_group.code == political_group
            ]

        if committee:
            meps = [
                mep for mep in meps
                if committee in mep.committees
            ]

        # Prepare response
        response_data = {
            "total": len(meps),
            "meps": [mep.dict() for mep in meps],
            "filtered_by": {
                k: v for k, v in {
                    "country": country,
                    "political_group": political_group,
                    "committee": committee
                }.items() if v is not None
            }
        }

        # Cache for 6 hours
        cache.set("mep_list", response_data, ttl=21600, cache_key)

        return MEPListResponse(**response_data)

    except Exception as e:
        logger.error(f"Failed to fetch MEPs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch MEPs: {str(e)}"
        )
    finally:
        await scraper.close()


@router.get(
    "/meps/{mep_id}",
    response_model=MEP,
    summary="Get MEP by ID",
    description="Get detailed information about specific MEP"
)
async def get_mep(
    mep_id: str,
    scraper: EuropeanParliamentScraper = Depends(get_ep_scraper),
    cache: APICache = Depends(get_cache)
) -> MEP:
    """
    Retrieve detailed MEP information.

    **Caching**: Results cached for 6 hours
    """
    try:
        # Try cache
        cached = cache.get("mep_profile", mep_id)
        if cached:
            return MEP(**cached)

        # Fetch from scraper
        mep_data = await scraper.get_mep_details(mep_id)

        if not mep_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"MEP {mep_id} not found"
            )

        # Cache for 6 hours
        cache.set("mep_profile", mep_data, ttl=21600, mep_id)

        return MEP(**mep_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch MEP {mep_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch MEP: {str(e)}"
        )
    finally:
        await scraper.close()


# ============================================================================
# Legislation Endpoints
# ============================================================================

@router.get(
    "/legislation/{celex}",
    response_model=LegislationResponse,
    summary="Get legislation by CELEX",
    description="Retrieve EU legislation document by CELEX number"
)
async def get_legislation(
    celex: str,
    scraper: EURLexScraper = Depends(get_eurlex_scraper),
    cache: APICache = Depends(get_cache)
) -> LegislationResponse:
    """
    Retrieve legislation document by CELEX number.

    **Example CELEX**: `32016R0679` (GDPR)
    **Caching**: Results cached for 24 hours
    **Rate Limit**: 100 calls/minute
    """
    try:
        # Validate CELEX format
        if not scraper.CELEX_PATTERN.match(celex):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid CELEX format: {celex}"
            )

        # Try cache
        cached = cache.get("legislation", celex)
        if cached:
            return LegislationResponse(
                document=LegislativeDocument(**cached),
                cache_hit=True
            )

        # Fetch from scraper
        logger.info(f"Fetching legislation: {celex}")
        document = await scraper.get_document_by_celex(celex)

        # Cache for 24 hours (legislation rarely changes)
        cache.set("legislation", document.dict(), ttl=86400, celex)

        return LegislationResponse(
            document=document,
            cache_hit=False
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch legislation {celex}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch legislation: {str(e)}"
        )
    finally:
        await scraper.close()


@router.get(
    "/legislation",
    response_model=List[Dict[str, Any]],
    summary="Search legislation",
    description="Search EUR-Lex for legislation"
)
async def search_legislation(
    query: str = Query(..., min_length=2, description="Search query"),
    document_type: Optional[str] = Query(None, description="Document type filter"),
    date_from: Optional[datetime] = Query(None, description="Date from"),
    date_to: Optional[datetime] = Query(None, description="Date to"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    scraper: EURLexScraper = Depends(get_eurlex_scraper)
):
    """
    Search EUR-Lex database.

    **Rate Limit**: 60 calls/minute
    """
    try:
        results = await scraper.search_legislation(
            query=query,
            document_type=document_type,
            date_from=date_from,
            date_to=date_to,
            limit=limit
        )

        return results

    except Exception as e:
        logger.error(f"Legislation search failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )
    finally:
        await scraper.close()


# ============================================================================
# OEIL Procedure Endpoints
# ============================================================================

@router.get(
    "/procedures/{reference}",
    response_model=ProcedureResponse,
    summary="Get OEIL procedure",
    description="Retrieve legislative procedure by reference"
)
async def get_procedure(
    reference: str,
    scraper: OEILScraper = Depends(get_oeil_scraper),
    cache: APICache = Depends(get_cache)
) -> ProcedureResponse:
    """
    Retrieve OEIL legislative procedure.

    **Example Reference**: `2021/0106(COD)`
    **Caching**: Results cached for 12 hours
    """
    try:
        # Try cache
        cached = cache.get("oeil_procedure", reference)
        if cached:
            return ProcedureResponse(
                procedure=LegislativeProcedure(**cached),
                cache_hit=True
            )

        # Fetch from scraper
        logger.info(f"Fetching procedure: {reference}")
        procedure = await scraper.get_procedure(reference)

        if not procedure:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Procedure {reference} not found"
            )

        # Cache for 12 hours
        cache.set("oeil_procedure", procedure, ttl=43200, reference)

        return ProcedureResponse(
            procedure=LegislativeProcedure(**procedure),
            cache_hit=False
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch procedure {reference}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch procedure: {str(e)}"
        )
    finally:
        await scraper.close()


# ============================================================================
# Terminology Endpoints
# ============================================================================

@router.post(
    "/terminology",
    response_model=TerminologySearchResponse,
    summary="Search IATE terminology",
    description="Search EU terminology database"
)
async def search_terminology(
    request: TerminologySearchRequest,
    scraper: IATEScraper = Depends(get_iate_scraper),
    cache: APICache = Depends(get_cache)
) -> TerminologySearchResponse:
    """
    Search IATE terminology database.

    **Rate Limit**: 50 calls/minute
    **Caching**: Results cached for 24 hours
    """
    try:
        # Try cache
        cache_key = f"{request.query}:{request.source_lang}:{request.domain or 'all'}"
        cached = cache.get("iate_search", cache_key)

        if cached:
            return TerminologySearchResponse(**cached)

        # Search IATE
        logger.info(f"Searching IATE: {request.query}")
        results = await scraper.search(
            query=request.query,
            source_lang=request.source_lang,
            target_langs=request.target_langs,
            domain=request.domain,
            limit=request.limit
        )

        response_data = {
            "query": request.query,
            "total_results": len(results),
            "entries": results
        }

        # Cache for 24 hours
        cache.set("iate_search", response_data, ttl=86400, cache_key)

        return TerminologySearchResponse(**response_data)

    except Exception as e:
        logger.error(f"IATE search failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Terminology search failed: {str(e)}"
        )
    finally:
        await scraper.close()


# ============================================================================
# Publications Office Endpoints
# ============================================================================

@router.post(
    "/publications",
    response_model=PublicationSearchResponse,
    summary="Search Publications Office",
    description="Search EU publications catalogue"
)
async def search_publications(
    request: PublicationSearchRequest,
    cache: APICache = Depends(get_cache)
) -> PublicationSearchResponse:
    """
    Search Publications Office catalogue.

    **Rate Limit**: 60 calls/minute
    **Caching**: Results cached for 6 hours
    """
    try:
        # Build cache key
        cache_key = f"{request.query or ''}:{request.author or ''}:{request.isbn or ''}"
        cached = cache.get("publications_search", cache_key)

        if cached:
            return PublicationSearchResponse(**cached)

        # TODO: Implement Publications Office search
        # For now, return empty results
        response_data = {
            "total_results": 0,
            "publications": []
        }

        # Cache for 6 hours
        cache.set("publications_search", response_data, ttl=21600, cache_key)

        return PublicationSearchResponse(**response_data)

    except Exception as e:
        logger.error(f"Publications search failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Publications search failed: {str(e)}"
        )


# ============================================================================
# SPARQL Query Endpoint
# ============================================================================

@router.post(
    "/sparql",
    response_model=SPARQLResponse,
    summary="Execute SPARQL query",
    description="Execute SPARQL query on EU data endpoints"
)
async def execute_sparql(
    request: SPARQLRequest,
    cache: APICache = Depends(get_cache)
) -> SPARQLResponse:
    """
    Execute SPARQL query.

    **Supported Endpoints**:
    - `eurlex`: EUR-Lex SPARQL endpoint
    - `ep`: European Parliament SPARQL
    - `publications`: Publications Office SPARQL

    **Rate Limit**: 10 queries/minute
    **Max Query Complexity**: 1M rows
    **Caching**: Results cached for 12 hours
    """
    try:
        import time
        start_time = time.time()

        # Validate endpoint
        valid_endpoints = ["eurlex", "ep", "publications"]
        if request.endpoint not in valid_endpoints:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid endpoint. Must be one of: {valid_endpoints}"
            )

        # Generate cache key from query hash
        import hashlib
        query_hash = hashlib.sha256(
            f"{request.query}:{request.endpoint}".encode()
        ).hexdigest()[:16]

        cached = cache.get("sparql_results", query_hash)
        if cached:
            return SPARQLResponse(
                results=SPARQLQueryResult(**cached['results']),
                execution_time_ms=cached['execution_time_ms'],
                cache_hit=True
            )

        # Execute query based on endpoint
        # TODO: Implement actual SPARQL execution
        logger.info(f"Executing SPARQL query on {request.endpoint}")

        # Placeholder results
        results = SPARQLQueryResult(
            bindings=[],
            variables=[],
            total_results=0,
            query=request.query
        )

        execution_time_ms = (time.time() - start_time) * 1000

        response_data = {
            "results": results.dict(),
            "execution_time_ms": execution_time_ms
        }

        # Cache for 12 hours
        cache.set("sparql_results", response_data, ttl=43200, query_hash)

        return SPARQLResponse(
            results=results,
            execution_time_ms=execution_time_ms,
            cache_hit=False
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SPARQL query failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SPARQL query failed: {str(e)}"
        )


# ============================================================================
# Health Check
# ============================================================================

@router.get(
    "/health",
    summary="Health check",
    description="Check API health status"
)
async def health_check():
    """API health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "EU Data API"
    }
