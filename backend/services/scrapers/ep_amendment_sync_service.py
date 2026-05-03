"""
EP Amendment Sync Service

Orchestrates the fetching and parsing of EP committee amendment documents
for a given legislative procedure.

Workflow:
1. Query OEIL Documentation Gateway for amendment documents (AM, PR)
2. For each document, check if already parsed in the database
3. Download DOCX from doceo
4. Parse with EPAmendmentParser
5. Upsert MEPAmendment records

Created: February 2026
"""

import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import uuid4

import httpx
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from models.mep_amendment import AmendmentDocument, MEPAmendment
from services.api_clients.oeil_client import OEILClient
from services.parsers.ep_amendment_parser import EPAmendmentParser, ParsedAmendment, GROUP_ALIASES

logger = logging.getLogger(__name__)

# EP API group codes -> canonical Brubru codes
_EP_API_GROUP_MAP = {v.lower(): v for v in GROUP_ALIASES.values()}
_EP_API_GROUP_MAP.update({k: v for k, v in GROUP_ALIASES.items()})


async def _build_mep_group_lookup() -> Dict[str, str]:
    """Fetch all current MEPs from EP Open Data API and build name -> group lookup."""
    lookup: Dict[str, str] = {}
    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            offset = 0
            while True:
                r = await client.get(
                    'https://data.europarl.europa.eu/api/v2/meps/show-current',
                    params={'format': 'application/ld+json', 'offset': offset, 'limit': 100},
                    headers={'Accept': 'application/ld+json', 'User-Agent': 'Brubru-1.0'}
                )
                if r.status_code != 200:
                    break
                data = r.json()
                items = data if isinstance(data, list) else data.get('data', [])
                if not items:
                    break
                for m in items:
                    raw_group = m.get('api:political-group', m.get('hasPoliticalGroup', ''))
                    group = _EP_API_GROUP_MAP.get(raw_group.lower(), raw_group) if raw_group else ''
                    given = m.get('givenName', '')
                    family = m.get('familyName', '')
                    if given and family and group:
                        lookup[f'{given} {family}'] = group
                offset += len(items)
                if len(items) < 100:
                    break
        logger.info(f"[OK] MEP group lookup built: {len(lookup)} entries")
    except Exception as e:
        logger.warning(f"[WARN] Failed to build MEP group lookup: {e}")
    return lookup


class EPAmendmentSyncService:
    """
    Fetches, parses, and stores EP committee amendments for legislative procedures.
    """

    def __init__(self, db: Session):
        self.db = db
        self.oeil_client = OEILClient()
        self.parser = EPAmendmentParser()
        self._mep_groups: Optional[Dict[str, str]] = None

    async def sync_amendments_for_procedure(
        self,
        procedure_ref: str,
        force_refetch: bool = False
    ) -> Dict[str, Any]:
        """
        Discover and parse all amendment documents for a procedure.

        Args:
            procedure_ref: Procedure reference (e.g. "2023/0089(COD)")
            force_refetch: Re-parse documents even if already done

        Returns:
            Summary dict with documents_found, documents_parsed, amendments_stored, errors
        """
        start_time = time.time()
        errors: List[str] = []
        documents_parsed = 0
        amendments_stored = 0

        # Step 1: Discover documents from OEIL Documentation Gateway
        logger.info(f"[START] Discovering amendment documents for {procedure_ref}")
        gateway_docs = await self.oeil_client.get_documentation_gateway(procedure_ref)

        # Filter to amendment + report + opinion document types. The /opinions
        # endpoint queries amendment_documents for ('AD','PA'); without 'AD'
        # here, AD-type opinions never make it into the table and the endpoint
        # returns empty.
        amendment_docs = [
            d for d in gateway_docs
            if d['doc_type_code'] in ('AM', 'PR', 'PA', 'AD', 'RD')
        ]

        logger.info(f"Found {len(amendment_docs)} amendment documents out of {len(gateway_docs)} total")

        # Build MEP name -> political group lookup (once per sync)
        if self._mep_groups is None:
            self._mep_groups = await _build_mep_group_lookup()

        # Step 2: Process each document
        for doc_entry in amendment_docs:
            pe_ref = doc_entry.get('pe_reference')
            if not pe_ref:
                continue

            # Check if already parsed
            if not force_refetch:
                existing = self.db.query(AmendmentDocument).filter(
                    AmendmentDocument.pe_reference == pe_ref,
                    AmendmentDocument.status == 'parsed'
                ).first()
                if existing:
                    logger.info(f"Skipping {pe_ref}: already parsed")
                    continue

            try:
                count = await self._fetch_and_parse_document(doc_entry, procedure_ref)
                documents_parsed += 1
                amendments_stored += count
            except Exception as e:
                error_msg = f"Failed to process {pe_ref}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

                # Record failure in database
                self._upsert_document_record(
                    doc_entry, procedure_ref,
                    status='failed', error_message=str(e),
                    total_amendments=0
                )

        await self.oeil_client.close()

        duration = time.time() - start_time
        logger.info(
            f"[OK] Sync complete for {procedure_ref}: "
            f"{documents_parsed} documents parsed, {amendments_stored} amendments stored "
            f"({len(errors)} errors) in {duration:.1f}s"
        )

        return {
            'procedure_reference': procedure_ref,
            'documents_found': len(amendment_docs),
            'documents_parsed': documents_parsed,
            'amendments_stored': amendments_stored,
            'errors': errors,
            'duration_seconds': round(duration, 2),
        }

    async def _fetch_and_parse_document(
        self,
        doc_entry: Dict[str, Any],
        procedure_ref: str
    ) -> int:
        """
        Download, parse, and store a single amendment document.

        Returns:
            Number of amendments stored
        """
        pe_reference = doc_entry['pe_reference']
        doceo_url = doc_entry['doceo_url']
        committee = doc_entry.get('committee', '')
        doc_type = doc_entry['doc_type_code']
        doc_date_str = doc_entry.get('date', '')

        logger.info(f"Fetching {doc_type} document: {pe_reference} from {doceo_url}")

        # Download DOCX
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            response = await client.get(doceo_url)
            response.raise_for_status()
            docx_bytes = response.content

        # Parse date if available
        doc_date = None
        if doc_date_str:
            try:
                doc_date = datetime.strptime(doc_date_str, '%d/%m/%Y').date()
            except ValueError:
                pass

        # Parse DOCX
        parsed_amendments = self.parser.parse_docx(
            docx_bytes=docx_bytes,
            committee=committee,
            pe_reference=pe_reference,
            procedure_ref=procedure_ref,
            rapporteur_name=None  # Could be extracted from PR docs
        )

        # Enrich political groups from MEP lookup
        if self._mep_groups:
            enriched = 0
            for pa in parsed_amendments:
                if not pa.political_group and pa.authors:
                    # Use the first author's group
                    for author in pa.authors:
                        group = self._mep_groups.get(author)
                        if group:
                            pa.political_group = group
                            enriched += 1
                            break
            if enriched:
                logger.info(f"  Enriched {enriched}/{len(parsed_amendments)} amendments with political groups")

        # Store amendments in database
        stored_count = 0
        for pa in parsed_amendments:
            try:
                self._upsert_amendment(pa, doceo_url, doc_date)
                stored_count += 1
            except Exception as e:
                logger.warning(f"Failed to store AM{pa.amendment_number}: {str(e)}")

        # Record document as parsed
        self._upsert_document_record(
            doc_entry, procedure_ref,
            status='parsed', error_message=None,
            total_amendments=stored_count
        )

        self.db.commit()
        logger.info(f"[OK] Stored {stored_count}/{len(parsed_amendments)} amendments from {pe_reference}")

        return stored_count

    def _upsert_amendment(
        self,
        pa: ParsedAmendment,
        source_url: str,
        doc_date: Optional[Any] = None
    ) -> None:
        """Insert or update a single amendment record."""
        stmt = pg_insert(MEPAmendment).values(
            id=uuid4(),
            procedure_reference=pa.procedure_reference,
            committee_code=pa.committee,
            pe_reference=pa.pe_reference,
            amendment_number=pa.amendment_number,
            author_names=pa.authors,
            political_group=pa.political_group,
            on_behalf_of_group=pa.on_behalf_of_group,
            element_type=pa.element_type,
            element_number=pa.element_number,
            element_reference=pa.element_reference_text,
            amendment_type=pa.amendment_type,
            original_text=pa.original_text,
            proposed_text=pa.proposed_text,
            justification=pa.justification,
            original_language=pa.original_language,
            source_url=source_url,
            source_format='docx',
            parsing_confidence=pa.parsing_confidence,
            document_date=doc_date,
        ).on_conflict_do_update(
            constraint='uq_mep_amendment_pe_num',
            set_={
                'author_names': pa.authors,
                'political_group': pa.political_group,
                'on_behalf_of_group': pa.on_behalf_of_group,
                'element_type': pa.element_type,
                'element_number': pa.element_number,
                'element_reference': pa.element_reference_text,
                'amendment_type': pa.amendment_type,
                'original_text': pa.original_text,
                'proposed_text': pa.proposed_text,
                'justification': pa.justification,
                'parsing_confidence': pa.parsing_confidence,
                'updated_at': datetime.now(),
            }
        )
        self.db.execute(stmt)

    def _upsert_document_record(
        self,
        doc_entry: Dict[str, Any],
        procedure_ref: str,
        status: str,
        error_message: Optional[str],
        total_amendments: int
    ) -> None:
        """Insert or update a document tracking record."""
        pe_reference = doc_entry.get('pe_reference', '')
        doc_date_str = doc_entry.get('date', '')
        doc_date = None
        if doc_date_str:
            try:
                doc_date = datetime.strptime(doc_date_str, '%d/%m/%Y').date()
            except ValueError:
                pass

        stmt = pg_insert(AmendmentDocument).values(
            id=uuid4(),
            procedure_reference=procedure_ref,
            committee_code=doc_entry.get('committee', ''),
            pe_reference=pe_reference,
            document_type=doc_entry['doc_type_code'],
            document_date=doc_date,
            doceo_url=doc_entry['doceo_url'],
            total_amendments=total_amendments,
            status=status,
            error_message=error_message,
        ).on_conflict_do_update(
            index_elements=['pe_reference'],
            set_={
                'total_amendments': total_amendments,
                'status': status,
                'error_message': error_message,
                'scraped_at': datetime.now(),
            }
        )
        self.db.execute(stmt)
        self.db.commit()
