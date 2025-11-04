# Brubru EU Institutional Web Scraping System

## Overview

Comprehensive web scraping infrastructure for all 14 EU institutional data sources used by Brubru. Built with async Python, featuring rate limiting, caching, retry logic, and ethical scraping practices.

## Architecture

```
backend/services/scrapers/
├── base_scraper.py              # Abstract base class (all scrapers inherit)
├── scraper_orchestrator.py     # Coordinates all scrapers
│
├── european_parliament_scraper.py    # ✅ IMPLEMENTED
├── eurlex_scraper.py                 # ✅ IMPLEMENTED
│
├── european_commission_scraper.py    # 📝 Template (to be implemented)
├── council_scraper.py                # 📝 Template
├── oeil_scraper.py                   # 📝 Template
├── legislative_train_scraper.py      # 📝 Template
├── law_tracker_scraper.py            # 📝 Template
├── who_is_who_scraper.py             # 📝 Template
├── assist_eu_scraper.py              # 📝 Template
├── jrc_scraper.py                    # 📝 Template
├── think_tank_scraper.py             # 📝 Template
├── style_guide_scraper.py            # 📝 Template
└── iate_scraper.py                   # 📝 Template
```

## Data Schemas

Located in `backend/schemas/scrapers/scraper_schemas.py`:

- **MEP**: Member of European Parliament data
- **LegislativeDocument**: EU legislation with CELEX numbers
- **LegislativeProcedure**: Procedure tracking with timeline
- **Commissioner**: European Commissioner profiles
- **PolicyInitiative**: Commission initiatives and consultations
- **CouncilDocument**: Council positions and decisions
- **ResearchPublication**: Think Tank and JRC publications
- **TerminologyEntry**: IATE multilingual terminology
- **InstitutionalContact**: Who's Who contacts
- **SearchResult**: Generic search results

## Core Features

### BaseScraper Class

All scrapers inherit from `BaseScraper`, providing:

**HTTP & Networking:**
- Async HTTP requests with aiohttp
- Configurable request timeouts
- Custom User-Agent identification
- Automatic absolute URL resolution

**Rate Limiting:**
- Respects robots.txt conventions
- Configurable delay between requests (default: 1-2 seconds)
- Thread-safe request locking

**Caching:**
- In-memory response caching (TTL: 1 hour default)
- Cache key generation from URL + parameters
- Automatic cache expiration
- Cache hit/miss statistics

**Retry Logic:**
- Exponential backoff (2, 4, 8, 10 seconds)
- Max 3 retry attempts
- Handles timeout and connection errors

**Error Handling:**
- Structured exception hierarchy
- Detailed error logging
- Statistics tracking

**HTML Parsing:**
- BeautifulSoup integration
- lxml parser for performance

### ScraperOrchestrator

Coordinates all scrapers with:

**Parallel Execution:**
- Async concurrent scraping
- Configurable max concurrency (default: 5)
- Semaphore-based rate limiting

**Unified API:**
- `search_all_sources()` - Search across all institutions
- `get_document_from_source()` - Retrieve specific document
- `get_latest_updates_all()` - Latest from all sources
- `track_legislative_procedure()` - Multi-source procedure tracking

**Aggregation:**
- Results from all sources in single response
- Source attribution
- Success/failure status per source
- Execution time tracking

## Usage Examples

### Basic Search

```python
from backend.services.scrapers import ScraperOrchestrator

# Initialize orchestrator
orchestrator = ScraperOrchestrator()

# Search all sources
results = await orchestrator.search_all_sources("artificial intelligence regulation")

# Results structure:
# {
#     'query': 'artificial intelligence regulation',
#     'total_sources': 14,
#     'execution_time_ms': 3542.8,
#     'results': {
#         'european_parliament': {'success': True, 'data': [...]},
#         'eurlex': {'success': True, 'data': [...]},
#         ...
#     }
# }
```

### Search Specific MEPs

```python
# Search for MEPs
meps = await orchestrator.search_meps("Vestager", country="DK")

# Get MEP details
mep_details = await orchestrator.scrapers['european_parliament'].get_mep_details("124936")

# Get committee members
members = await orchestrator.scrapers['european_parliament'].get_committee_members("ENVI")
```

### Retrieve Legislation

```python
# Get document by CELEX number
gdpr = await orchestrator.get_legislation_by_celex("32016R0679")

# Search EUR-Lex
results = await orchestrator.scrapers['eurlex'].search_legislation(
    query="data protection",
    document_type="regulation",
    date_from=datetime(2020, 1, 1),
    limit=10
)

# Download Akoma Ntoso XML for amendment tool
xml_content = await orchestrator.scrapers['eurlex'].download_akoma_ntoso_xml("32016R0679")
```

### Track Legislative Procedure

```python
# Multi-source procedure tracking
procedure_data = await orchestrator.track_legislative_procedure("2021/0106(COD)")

# Returns data from:
# - OEIL (legislative observatory)
# - Legislative Train (visual timeline)
# - Law Tracker (implementation status)
```

### Get Latest Updates

```python
# Latest from all sources
updates = await orchestrator.get_latest_updates_all(limit=5)

# Latest from specific source
eurlex_latest = await orchestrator.scrapers['eurlex'].get_latest_updates(10)
```

### Statistics & Monitoring

```python
# Get statistics from all scrapers
stats = orchestrator.get_all_stats()

# Example output:
# {
#     'european_parliament': {
#         'name': 'EuropeanParliament',
#         'base_url': 'https://www.europarl.europa.eu',
#         'stats': {
#             'requests_made': 42,
#             'cache_hits': 18,
#             'cache_misses': 24,
#             'errors': 2,
#             'total_bytes': 1048576
#         },
#         'cache_size': 18
#     },
#     ...
# }

# Clear all caches
orchestrator.clear_all_caches()
```

## Integration with Brubru

### Chat Interface Integration

```python
# In backend/api/chat.py

from backend.services.scrapers import ScraperOrchestrator

orchestrator = ScraperOrchestrator()

@router.post("/chat/query")
async def process_chat_query(query: str):
    """Process user query by searching EU sources"""

    # Search relevant sources
    results = await orchestrator.search_all_sources(query)

    # Send to AI (Anthropic/OpenAI) for analysis
    ai_response = await ai_service.analyze_with_context(
        user_query=query,
        eu_data=results
    )

    return {
        'ai_response': ai_response,
        'sources': results,
        'citations': extract_citations(results)
    }
```

### Amendator Integration

```python
# In backend/api/amendments.py

@router.get("/documents/{celex_number}")
async def get_document_for_amendment(celex_number: str):
    """Retrieve legislative document for amendment editing"""

    # Get document from EUR-Lex
    document = await orchestrator.get_legislation_by_celex(celex_number)

    # Download Akoma Ntoso XML
    xml_content = await orchestrator.scrapers['eurlex'].download_akoma_ntoso_xml(celex_number)

    # Parse for amendable elements
    amendable_elements = xml_service.parse_amendable_elements(xml_content)

    return {
        'document': document,
        'xml': xml_content,
        'amendable_elements': amendable_elements
    }
```

### Background Data Sync

```python
# In backend/tasks/sync_tasks.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('interval', hours=6)
async def sync_latest_legislation():
    """Sync latest EU legislation every 6 hours"""
    updates = await orchestrator.get_latest_updates_all(limit=20)

    # Store in database
    for source, data in updates['sources'].items():
        if data['success']:
            await db_service.upsert_documents(data['data'])
```

## Configuration

### Environment Variables

```bash
# .env

# Scraper Configuration
SCRAPER_RATE_LIMIT_DELAY=1.5
SCRAPER_CACHE_TTL=3600
SCRAPER_REQUEST_TIMEOUT=30
SCRAPER_MAX_RETRIES=3
SCRAPER_MAX_CONCURRENT=5

# User Agent
SCRAPER_USER_AGENT="Brubru/1.0 (EU Policy Intelligence; +https://brubru.world)"
```

### Per-Scraper Configuration

```python
# Custom configuration for specific scraper
eurlex_scraper = EURLexScraper(
    rate_limit_delay=2.0,      # 2 seconds between requests
    cache_ttl=7200,            # 2-hour cache
    timeout=60,                # 60-second timeout
    max_retries=5,             # 5 retry attempts
)
```

## Ethical Scraping Guidelines

✅ **DO:**
- Respect rate limits (1-2 seconds minimum delay)
- Use descriptive User-Agent with contact info
- Cache responses to minimize requests
- Handle errors gracefully
- Monitor request volume
- Follow robots.txt

❌ **DON'T:**
- Scrape during peak hours (9am-5pm CET)
- Make parallel requests to same domain
- Ignore HTTP 429 (Rate Limit) responses
- Scrape private/restricted content
- Overwhelm servers with requests

## Performance Optimization

**Caching Strategy:**
- Static content (legislation): 24-hour cache
- Dynamic content (news): 1-hour cache
- Frequently accessed: Redis cache (future)

**Concurrency:**
- Max 5 scrapers running simultaneously
- Semaphore-based throttling
- Async I/O for efficiency

**Monitoring:**
- Request counting per scraper
- Cache hit rates
- Error rates
- Response times

## Development Roadmap

### Phase 1: Foundation ✅
- [x] Base scraper architecture
- [x] Data schemas with Pydantic
- [x] European Parliament scraper
- [x] EUR-Lex scraper
- [x] Scraper orchestrator

### Phase 2: Core Scrapers (Next)
- [ ] OEIL procedure tracking
- [ ] Legislative Train timeline scraping
- [ ] EU Law Tracker implementation
- [ ] Commission initiatives scraper

### Phase 3: Intelligence Sources
- [ ] Who's Who contact scraping
- [ ] Think Tank publications
- [ ] JRC research papers
- [ ] IATE terminology database

### Phase 4: Advanced Features
- [ ] Redis caching layer
- [ ] Elasticsearch indexing
- [ ] Real-time WebSocket updates
- [ ] ML-powered result ranking
- [ ] Automatic data validation

### Phase 5: Production Hardening
- [ ] Distributed scraping (Celery)
- [ ] Circuit breakers
- [ ] Rate limit respecting (429 handling)
- [ ] Comprehensive logging (Sentry)
- [ ] Prometheus metrics

## Testing

```bash
# Run scraper tests
pytest backend/tests/services/scrapers/

# Test specific scraper
pytest backend/tests/services/scrapers/test_european_parliament_scraper.py

# Test with coverage
pytest --cov=backend/services/scrapers --cov-report=html
```

## Troubleshooting

**"RateLimitError: Rate limit exceeded"**
- Increase `rate_limit_delay` parameter
- Reduce concurrency in orchestrator

**"ScraperError: Request timeout"**
- Increase `timeout` parameter
- Check network connectivity
- Verify target website is online

**"Cache not working"**
- Check cache TTL configuration
- Verify `use_cache=True` in fetch calls
- Clear cache if stale: `scraper.clear_cache()`

**"HTML parsing errors"**
- Website structure may have changed
- Update CSS selectors in scraper
- Check HTML with browser DevTools

## Contributing

When implementing new scrapers:

1. Inherit from `BaseScraper`
2. Implement three abstract methods:
   - `search(query, **kwargs)`
   - `get_document(document_id)`
   - `get_latest_updates(limit)`
3. Add Pydantic model to `scraper_schemas.py`
4. Register in `ScraperOrchestrator`
5. Write unit tests
6. Update this README

## License

EUPL-1.1 (European Union Public Licence) - Same as original AT4AM project

## Contact

For questions about the scraping system: dev@brubru.world
