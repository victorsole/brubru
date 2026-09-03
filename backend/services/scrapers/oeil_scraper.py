"""
OEIL Legislative Observatory Scraper

PHASE 4 UPGRADE: Integrated with API clients
- XML export functionality (primary)
- RSS subscriptions for procedure tracking
- api.epdb.eu JSON dumps integration
- Web scraping as fallback

PHASE 5 UPGRADE: Full web scraping implementation
- Complete procedure page parsing (all 7 sections)
- MEP extraction with photos and political groups
- Document gateway parsing
- Timeline and forecast extraction

Scrapes EU legislative procedures, timelines, and status updates
"""

import logging
import re
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup, Tag

from .base_scraper import BaseScraper, ScraperError
from services.api_clients.oeil_client import OEILClient
from schemas.scrapers.oeil_schemas import (
    OEILProcedure, OEILBasicInfo, OEILKeyPlayers, OEILKeyEvents,
    OEILForecasts, OEILTechnicalInfo, OEILDocumentation, OEILAdditionalInfo,
    OEILMep, OEILCommittee, OEILDocument, OEILEvent, OEILForecast,
    OEILLegalBasis, OEILConsultativeBody, OEILNationalParliamentContribution
)

logger = logging.getLogger(__name__)


# Labels that appear on an OEIL procedure page. A value is the line AFTER a
# label, so a value that is itself a label means the extraction slipped and the
# field must stay empty rather than carry the label forward.
_OEIL_LABELS = frozenset({
    "Basic information", "Full procedure", "Status", "Subject", "Legal basis",
    "Other legal basis", "Committee dossier", "Stage reached in procedure",
    "Key players", "Committee responsible", "Rapporteur", "Appointed",
    "Shadow rapporteur", "Committee for opinion", "Key events", "Forecasts",
    "Technical information", "Documentation gateway", "Additional information",
    "Procedure reference", "Procedure type", "Procedure subtype", "Instrument",
    "Amendments and repeals", "Mandatory consultation of other institutions",
    "Document type", "Committee", "Ref", "Date", "Summary", "pdf",
})


def _oeil_lines(soup: BeautifulSoup) -> list:
    """Every visible line of an OEIL page, in order, blanks removed.

    OEIL renders as label line followed by value line. The page is
    server-rendered: the data IS in the HTML (verified 3 Sep 2026 against
    2023/0437(COD), where the raw response carries the committee, the
    rapporteur and the stage). An earlier reading called it a JS SPA; that was
    a bad text extraction, not a JS wall.
    """
    clone = BeautifulSoup(str(soup), "html.parser")
    for t in clone(["script", "style", "noscript"]):
        t.decompose()
    return [ln.strip() for ln in clone.get_text("\n", strip=True).split("\n") if ln.strip()]


def _value_after(lines: list, label: str) -> Optional[str]:
    """The line following `label`, or None when the next line is another label.

    Why this exists: `_parse_basic_info` used to read the LABEL as the value.
    It matched a "Stage reached" regex and then assigned group(0), the
    whole match, so every procedure came back with status
    "Stage reached in procedure" and title "Procedure File: <ref>". Both are the
    page furniture, not the data. Callers relying on OEIL for rapporteur
    identity were reading furniture.
    """
    try:
        i = lines.index(label)
    except ValueError:
        return None
    for candidate in lines[i + 1: i + 3]:
        if candidate in _OEIL_LABELS:
            continue
        return candidate
    return None



class OEILScraper(BaseScraper):
    """
    Scraper for OEIL Legislative Observatory.

    PHASE 4 UPGRADE:
    - Primary: XML export functionality
    - RSS feeds for real-time procedure updates
    - Third-party: api.epdb.eu integration
    - Fallback: Web scraping

    PHASE 5 UPGRADE:
    - Full web scraping of procedure pages
    - All 7 sections extraction
    - MEP data with photos
    - Complete document gateway

    Key Features:
    - Legislative procedure tracking
    - Document status and timeline
    - RSS monitoring for updates
    - Committee opinions and amendments
    """

    # URL patterns (updated January 2025)
    PROCEDURE_URL = "https://oeil.europarl.europa.eu/oeil/en/procedure-file"
    PROCEDURE_URL_LEGACY = "https://oeil.secure.europarl.europa.eu/oeil/popups/ficheprocedure.do"
    MEP_URL_PATTERN = re.compile(r'/meps/en/(\d+)')
    DATE_PATTERN = re.compile(r'(\d{2})/(\d{2})/(\d{4})')

    def __init__(self, use_api: bool = True, **kwargs):
        # use_api is consumed HERE and never forwarded. BaseScraper does not
        # accept it, so while it rode in **kwargs any caller writing the
        # apparently-harmless OEILScraper(use_api=True) got a TypeError -- and
        # the one caller that did, the on-demand OEIL fetch in the context
        # builder, lost its entire legislative-files block to the outer
        # handler (audit 17 Aug 2026).
        super().__init__(
            base_url="https://oeil.secure.europarl.europa.eu/oeil/en",
            name="OEIL",
            rate_limit_delay=2.0,
            **kwargs
        )

        # PHASE 4: Initialize API client
        self.api_client = OEILClient()
        self.use_api = use_api

        logger.info("OEIL Scraper initialized with API client")

    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Search OEIL legislative procedures.

        PHASE 4: RSS feeds for search

        Args:
            query: Search query
            **kwargs: Additional parameters

        Returns:
            List of procedures
        """
        if self.use_api:
            try:
                logger.info(f"Searching OEIL procedures: {query}")
                # Would use RSS feeds or XML export
                procedures = await self.api_client.get_latest_procedures(hours=168)  # 1 week

                # Filter by query
                results = [p for p in procedures if query.lower() in p['title'].lower()]
                return results
            except Exception as e:
                logger.error(f"OEIL search failed: {str(e)}")

        return []

    async def get_document(self, document_id: str) -> Dict[str, Any]:
        """
        Get procedure document by ID.

        Args:
            document_id: Document identifier

        Returns:
            Document data
        """
        # Would use XML export or web scraping
        logger.info(f"Fetching OEIL document: {document_id}")
        return {}

    async def get_latest_updates(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get latest procedure updates via RSS.

        PHASE 4: RSS feeds

        Args:
            limit: Maximum results

        Returns:
            Latest updates
        """
        if self.use_api:
            try:
                logger.info("Fetching latest OEIL updates via RSS")
                procedures = await self.api_client.get_latest_procedures(hours=24)
                return procedures[:limit]
            except Exception as e:
                logger.error(f"RSS fetch failed: {str(e)}")

        return []

    async def get_procedure(self, procedure_ref: str) -> Dict[str, Any]:
        """
        Get specific legislative procedure by reference.

        PHASE 5: Now uses full web scraping implementation.

        Args:
            procedure_ref: Procedure reference (e.g., "2021/0106(COD)")

        Returns:
            Procedure data with timeline as dictionary
        """
        try:
            procedure = await self.get_procedure_full(procedure_ref)
            return procedure.model_dump()
        except Exception as e:
            logger.error(f"Failed to get procedure {procedure_ref}: {e}")
            return {"error": str(e), "reference": procedure_ref}

    async def get_procedures_by_type(
        self,
        procedure_type: str,
        hours: int = 168
    ) -> List[Dict[str, Any]]:
        """
        PHASE 4: New method - Get procedures by type using RSS

        Args:
            procedure_type: Type (ordinary_legislative, consultation, consent, etc.)
            hours: Time window in hours

        Returns:
            List of procedures
        """
        if not self.use_api:
            raise NotImplementedError("RSS feeds require API client")

        try:
            logger.info(f"Fetching {procedure_type} procedures")
            procedures = await self.api_client.get_latest_procedures(
                hours=hours,
                procedure_type=procedure_type
            )
            return procedures
        except Exception as e:
            logger.error(f"Failed to fetch procedures: {str(e)}")
            return []

    async def export_procedures(
        self,
        date_from: datetime,
        date_to: Optional[datetime] = None
    ) -> Optional[str]:
        """
        PHASE 4: New method - Export procedure data as XML

        Args:
            date_from: Start date
            date_to: End date

        Returns:
            XML data
        """
        if not self.use_api:
            raise NotImplementedError("XML export requires API client")

        try:
            logger.info(f"Exporting OEIL data from {date_from}")
            xml_data = await self.api_client.export_procedure_data(date_from, date_to)
            return xml_data
        except Exception as e:
            logger.error(f"Export failed: {str(e)}")
            return None

    async def close(self):
        """Close API client connections"""
        if hasattr(self, 'api_client'):
            await self.api_client.close()
            logger.info("Closed OEIL API client")

    # =========================================================================
    # PHASE 5: Full Procedure Web Scraping
    # =========================================================================

    async def get_procedure_full(self, procedure_ref: str) -> OEILProcedure:
        """
        Fetch and parse complete OEIL procedure page.

        Extracts all 7 sections:
        1. Basic Information
        2. Key Players
        3. Key Events
        4. Forecasts
        5. Technical Information
        6. Documentation Gateway
        7. Additional Information

        Args:
            procedure_ref: Procedure reference (e.g., "2024/0176(COD)")

        Returns:
            OEILProcedure with all sections populated

        Raises:
            ScraperError: On fetch or parse failure
        """
        logger.info(f"Fetching full procedure: {procedure_ref}")

        # Build URL (new format as of January 2025)
        url = f"{self.PROCEDURE_URL}?reference={procedure_ref}"

        try:
            # Fetch page
            html = await self._fetch(url)
            soup = self._parse_html(html)

            # Parse all sections
            basic_info = self._parse_basic_info(soup, procedure_ref)
            key_players = self._parse_key_players(soup)
            key_events = self._parse_key_events(soup)
            forecasts = self._parse_forecasts(soup)
            technical_info = self._parse_technical_info(soup, procedure_ref)
            documentation = self._parse_documentation(soup)
            additional_info = self._parse_additional_info(soup)

            procedure = OEILProcedure(
                source_url=url,
                basic_info=basic_info,
                key_players=key_players,
                key_events=key_events,
                forecasts=forecasts,
                technical_info=technical_info,
                documentation=documentation,
                additional_info=additional_info
            )

            logger.info(f"Successfully parsed procedure {procedure_ref}")
            return procedure

        except Exception as e:
            logger.error(f"Failed to parse procedure {procedure_ref}: {str(e)}")
            raise ScraperError(f"Failed to parse procedure {procedure_ref}: {str(e)}") from e

    # =========================================================================
    # Section Parsers
    # =========================================================================

    def _parse_basic_info(self, soup: BeautifulSoup, procedure_ref: str) -> OEILBasicInfo:
        """Parse Section 1: Basic Information - Direct search approach"""
        basic_info = OEILBasicInfo(reference=procedure_ref)

        try:
            # Line-based extraction FIRST (fixed 3 Sep 2026). OEIL renders
            # label-then-value, and the real procedure title is the line after
            # "Full procedure". The <title> tag is only ever
            # "Procedure File: <ref> | Legislative Observatory | ...", which is
            # the page furniture; taking it produced a title of
            # "Procedure File: 2023/0437(COD)" for every single procedure.
            lines = _oeil_lines(soup)
            real_title = _value_after(lines, "Full procedure")
            if real_title and len(real_title) > 10 and not real_title.startswith("20"):
                basic_info.title = real_title
            else:
                title_tag = soup.find('title')
                if title_tag:
                    title_text = title_tag.get_text(strip=True)
                    if '|' in title_text:
                        title_text = title_text.split('|')[0].strip()
                    if title_text and not title_text.startswith('20'):
                        basic_info.title = title_text

            # Search entire page text for key patterns
            page_text = soup.get_text()

            # Procedure type (COD, CNS, etc.)
            type_match = re.search(r'(COD|CNS|APP|BUD|NLE)\s*[-–:]\s*([A-Z][^\n]{10,80})', page_text)
            if type_match:
                basic_info.procedure_type_code = type_match.group(1)
                basic_info.procedure_type = f"{type_match.group(1)} - {type_match.group(2).strip()}"

            # Status: the line after the "Status" label, or after
            # "Stage reached in procedure" on the technical-information block.
            # The old code matched a regex and then assigned group(0) -- the
            # WHOLE match, label included -- so every procedure reported its
            # status as the literal string "Stage reached in procedure".
            status = (_value_after(lines, "Status")
                      or _value_after(lines, "Stage reached in procedure"))
            if status:
                basic_info.status = status

            # Subjects - look for subject/theme links anywhere in page
            subject_links = soup.find_all('a', href=re.compile(r'subject|theme|policy-area'))
            for link in subject_links:
                subject = link.get_text(strip=True)
                if subject and len(subject) > 3 and subject not in basic_info.subjects:
                    basic_info.subjects.append(subject)

            # Also look for list items containing subject codes like "3.40.01"
            for li in soup.find_all('li'):
                li_text = li.get_text(strip=True)
                if re.match(r'\d+\.\d+(?:\.\d+)?', li_text):
                    if li_text not in basic_info.subjects:
                        basic_info.subjects.append(li_text)

        except Exception as e:
            logger.warning(f"Error parsing basic info: {e}")

        return basic_info

    def _parse_key_players(self, soup: BeautifulSoup) -> OEILKeyPlayers:
        """Parse Section 2: Key Players - Direct search approach"""
        key_players = OEILKeyPlayers()

        try:
            page_text = soup.get_text()

            # Committee codes pattern
            committee_codes = ['IMCO', 'LIBE', 'JURI', 'ITRE', 'ENVI', 'AFET', 'AFCO', 'BUDG',
                              'CONT', 'ECON', 'EMPL', 'INTA', 'TRAN', 'REGI', 'AGRI', 'PECH',
                              'CULT', 'DROI', 'PETI', 'FEMM', 'DEVE', 'SEDE']

            # Find all MEP links on the page
            mep_links = soup.find_all('a', href=re.compile(r'/meps/en/\d+'))

            # First MEP is usually the rapporteur for main committee
            if mep_links:
                first_mep = self._parse_mep_from_link(mep_links[0])

                # The committee RESPONSIBLE is the one printed under that
                # label, not the first code that happens to appear on the page.
                #
                # The old code walked a hardcoded list in fixed order and took
                # the first member found anywhere in the text. IMCO is first in
                # that list, so every page mentioning IMCO for any reason -- an
                # opinion committee, a cross-reference, a related procedure --
                # reported IMCO as responsible. Measured 3 Sep 2026: passenger
                # rights came back IMCO when its dossier is TRAN/10/00285, and
                # the psychosocial-risks file came back JURI when the
                # responsible committee is EMPL. The rapporteur was right in
                # both cases, so a correct name was being paired with the wrong
                # committee. [[feedback_first_match_on_a_page_is_a_related_entity]]
                lines = _oeil_lines(soup)
                committee_code = None
                committee_name = None
                try:
                    idx = lines.index('Committee responsible')
                except ValueError:
                    idx = None
                if idx is not None:
                    for j in range(idx + 1, min(idx + 8, len(lines))):
                        if lines[j] in committee_codes:
                            committee_code = lines[j]
                            if j + 1 < len(lines) and lines[j + 1] not in _OEIL_LABELS:
                                committee_name = lines[j + 1]
                            break
                if not committee_code:
                    # Fall back to the old scan, but say so rather than pass a
                    # guess off as a reading.
                    for code in committee_codes:
                        if code in page_text:
                            committee_code = code
                            logger.warning(
                                "OEIL: no 'Committee responsible' block found; "
                                "fell back to first code on page (%s)", code)
                            break

                if first_mep:
                    committee = OEILCommittee(
                        code=committee_code or 'UNKNOWN',
                        name=committee_name,
                        role='responsible',
                        rapporteur=first_mep,
                        shadow_rapporteurs=[]
                    )

                    # Remaining MEPs could be shadows
                    for link in mep_links[1:]:
                        shadow = self._parse_mep_from_link(link)
                        if shadow:
                            committee.shadow_rapporteurs.append(shadow)

                    key_players.committee_responsible = committee

            # Commission DG - search for pattern like "DG SANTE", "DG GROW"
            dg_match = re.search(r'DG\s+([A-Z]{3,})', page_text)
            if dg_match:
                key_players.commission_dg = f"DG {dg_match.group(1)}"

            # Also look for "Directorate-General" pattern
            if not key_players.commission_dg:
                dg_match = re.search(r'Directorate-General\s+(?:for\s+)?([A-Z][^,\n]+)', page_text)
                if dg_match:
                    key_players.commission_dg = dg_match.group(0).strip()

            # Commissioner - try multiple patterns
            # Pattern 1: "Commissioner Name SURNAME" or "Commissioner: Name SURNAME"
            commissioner_match = re.search(
                r'Commissioner[:\s]+([A-ZÀÁÂÄÉÈÊËÍÎÏÓÔÖÚÛÜ][a-zàáâäéèêëíîïóôöúûü]+(?:\s+[A-ZÀÁÂÄÉÈÊËÍÎÏÓÔÖÚÛÜ][A-ZÀÁÂÄÉÈÊËÍÎÏÓÔÖÚÛÜa-zàáâäéèêëíîïóôöúûü]+)+)',
                page_text
            )
            if commissioner_match:
                name = commissioner_match.group(1).strip()
                # Skip if it's just a portfolio like "Justice" or "Internal Market"
                portfolio_words = ['justice', 'internal', 'market', 'digital', 'economy', 'trade',
                                   'environment', 'health', 'transport', 'energy', 'agriculture',
                                   'budget', 'cohesion', 'democracy', 'values', 'transparency']
                if not name.lower().split()[0] in portfolio_words:
                    key_players.commissioner = name

            # Pattern 2: "Name SURNAME, Commissioner" or "Name SURNAME (Commissioner)"
            if not key_players.commissioner:
                commissioner_match2 = re.search(
                    r'([A-ZÀÁÂÄÉÈÊËÍÎÏÓÔÖÚÛÜ][a-zàáâäéèêëíîïóôöúûü]+(?:\s+[A-ZÀÁÂÄÉÈÊËÍÎÏÓÔÖÚÛÜ]+)+)[,\s]+(?:\()?Commissioner',
                    page_text
                )
                if commissioner_match2:
                    key_players.commissioner = commissioner_match2.group(1).strip()

            # Pattern 3: Look for Commission section with responsible Commissioner
            if not key_players.commissioner:
                # Try to find in structured sections
                commission_section = re.search(
                    r'European Commission[:\s]*([A-ZÀÁÂÄÉÈÊËÍÎÏÓÔÖÚÛÜ][a-zàáâäéèêëíîïóôöúûü]+\s+[A-ZÀÁÂÄÉÈÊËÍÎÏÓÔÖÚÛÜ]+)',
                    page_text
                )
                if commission_section:
                    key_players.commissioner = commission_section.group(1).strip()

            # Council configuration
            council_match = re.search(r'Council\s*(?:of\s+the\s+EU)?[:\s]+([A-Z][^,\n]+)', page_text)
            if council_match:
                key_players.council_configuration = council_match.group(1).strip()

            # Consultative bodies - EESC
            if 'Economic and Social Committee' in page_text or 'EESC' in page_text:
                key_players.eesc = OEILConsultativeBody(body='EESC')

            # Committee of the Regions
            if 'Committee of the Regions' in page_text or 'CoR' in page_text:
                key_players.cor = OEILConsultativeBody(body='CoR')

        except Exception as e:
            logger.warning(f"Error parsing key players: {e}")

        return key_players

    def _parse_key_events(self, soup: BeautifulSoup) -> OEILKeyEvents:
        """Parse Section 3: Key Events - Direct search approach"""
        key_events = OEILKeyEvents()

        try:
            page_text = soup.get_text()

            # Find all dates in the page (DD/MM/YYYY format)
            date_pattern = re.compile(r'(\d{2}/\d{2}/\d{4})')
            dates_found = date_pattern.findall(page_text)

            # Common event types to look for
            event_types = [
                'Legislative proposal',
                'Committee referral',
                'Vote in committee',
                'Committee report',
                'Debate in plenary',
                'Decision by Parliament',
                'Act adopted by Council',
                'Final act signed',
                'Final act published',
                'Entry into force',
            ]

            # Search for events near dates
            for date_str in dates_found[:20]:  # Limit to first 20 dates
                try:
                    d, m, y = date_str.split('/')
                    event_date = date(int(y), int(m), int(d))

                    # Look for context around this date
                    date_idx = page_text.find(date_str)
                    if date_idx >= 0:
                        # Get surrounding text
                        context_start = max(0, date_idx - 100)
                        context_end = min(len(page_text), date_idx + 150)
                        context = page_text[context_start:context_end]

                        # Try to identify event type
                        event_type = 'Event'
                        for etype in event_types:
                            if etype.lower() in context.lower():
                                event_type = etype
                                break

                        # Create event if we found something meaningful
                        if event_type != 'Event' or len(dates_found) <= 10:
                            event = OEILEvent(
                                date=event_date,
                                event_type=event_type,
                                description=context.strip()[:100] if event_type == 'Event' else None
                            )
                            key_events.events.append(event)

                except ValueError:
                    continue

            # Remove duplicates by date
            seen_dates = set()
            unique_events = []
            for event in key_events.events:
                if event.date not in seen_dates:
                    seen_dates.add(event.date)
                    unique_events.append(event)
            key_events.events = sorted(unique_events, key=lambda x: x.date)

        except Exception as e:
            logger.warning(f"Error parsing key events: {e}")

        return key_events

    def _parse_forecasts(self, soup: BeautifulSoup) -> OEILForecasts:
        """Parse Section 4: Forecasts"""
        forecasts = OEILForecasts()

        try:
            forecast_section = self._find_section(soup, 'Forecasts')
            if not forecast_section:
                return forecasts

            # Find forecast table
            forecast_table = forecast_section.find('table')
            if not forecast_table:
                return forecasts

            rows = forecast_table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    forecast = self._parse_forecast_row(cells)
                    if forecast:
                        forecasts.forecasts.append(forecast)

        except Exception as e:
            logger.warning(f"Error parsing forecasts: {e}")

        return forecasts

    def _parse_technical_info(self, soup: BeautifulSoup, procedure_ref: str) -> OEILTechnicalInfo:
        """Parse Section 5: Technical Information"""
        tech_info = OEILTechnicalInfo(reference=procedure_ref)

        try:
            tech_section = self._find_section(soup, 'Technical information')
            if not tech_section:
                return tech_info

            # Procedure type
            type_row = self._find_row_by_label(tech_section, 'Procedure type')
            if type_row:
                tech_info.procedure_type = type_row.get_text(strip=True)

            # Procedure subtype
            subtype_row = self._find_row_by_label(tech_section, 'Procedure subtype')
            if subtype_row:
                tech_info.procedure_subtype = subtype_row.get_text(strip=True)

            # Legal basis
            legal_row = self._find_row_by_label(tech_section, 'Legal basis')
            if legal_row:
                legal_links = legal_row.find_all('a')
                for link in legal_links:
                    text = link.get_text(strip=True)
                    href = link.get('href', '')
                    # Parse treaty and article
                    treaty_match = re.match(r'(TFEU|TEU|Euratom)', text)
                    if treaty_match:
                        tech_info.legal_basis.append(OEILLegalBasis(
                            treaty=treaty_match.group(1),
                            article=text,
                            url=href
                        ))

            # Stage reached
            stage_row = self._find_row_by_label(tech_section, 'Stage reached')
            if stage_row:
                tech_info.stage_reached = stage_row.get_text(strip=True)

            # Commission reference
            comm_ref_row = self._find_row_by_label(tech_section, 'Commission DG')
            if comm_ref_row:
                tech_info.commission_reference = comm_ref_row.get_text(strip=True)

        except Exception as e:
            logger.warning(f"Error parsing technical info: {e}")

        return tech_info

    def _parse_documentation(self, soup: BeautifulSoup) -> OEILDocumentation:
        """Parse Section 6: Documentation Gateway - Direct search approach"""
        docs = OEILDocumentation()

        try:
            # Find all document links by their patterns
            # COM documents (Commission)
            com_links = soup.find_all('a', string=re.compile(r'COM\(\d{4}\)\d+'))
            for link in com_links:
                ref = link.get_text(strip=True)
                url = link.get('href', '')
                docs.commission_documents.append(OEILDocument(
                    reference=ref,
                    url=self._make_absolute_url(url) if url else None,
                    doc_type='COM'
                ))

            # EP documents (A9-xxx, PE-xxx)
            ep_patterns = [
                r'A\d+-\d+/\d+',  # Report: A9-0123/2024
                r'PE\d+\.\d+',    # PE number
            ]
            for pattern in ep_patterns:
                ep_links = soup.find_all('a', string=re.compile(pattern))
                for link in ep_links:
                    ref = link.get_text(strip=True)
                    url = link.get('href', '')
                    docs.ep_documents.append(OEILDocument(
                        reference=ref,
                        url=self._make_absolute_url(url) if url else None,
                        doc_type='EP'
                    ))

            # Council documents (ST xxx)
            council_links = soup.find_all('a', string=re.compile(r'ST\s*\d+'))
            for link in council_links:
                ref = link.get_text(strip=True)
                url = link.get('href', '')
                docs.council_documents.append(OEILDocument(
                    reference=ref,
                    url=self._make_absolute_url(url) if url else None,
                    doc_type='Council'
                ))

            # PDF links
            pdf_links = soup.find_all('a', href=re.compile(r'\.pdf'))
            for link in pdf_links:
                text = link.get_text(strip=True)
                url = link.get('href', '')
                if text and len(text) > 3:
                    docs.other_documents.append(OEILDocument(
                        reference=text[:50],
                        url=self._make_absolute_url(url),
                        pdf_url=self._make_absolute_url(url)
                    ))

            # National parliament contributions
            page_text = soup.get_text()
            parliament_names = [
                'German Bundestag', 'French Senate', 'French National Assembly',
                'Italian Senate', 'Italian Chamber', 'Spanish Congress',
                'Polish Sejm', 'Polish Senate', 'Dutch Senate', 'Dutch House',
                'Portuguese Parliament', 'Czech Senate', 'Czech Chamber',
                'Romanian Senate', 'Romanian Chamber', 'Austrian Parliament',
                'Belgian Senate', 'Belgian Chamber', 'Swedish Riksdag',
                'Danish Folketing', 'Finnish Parliament', 'Irish Houses',
            ]
            for parliament in parliament_names:
                if parliament in page_text:
                    docs.national_parliament_contributions.append(
                        OEILNationalParliamentContribution(
                            parliament=parliament,
                            contribution_type='Contribution'
                        )
                    )

        except Exception as e:
            logger.warning(f"Error parsing documentation: {e}")

        return docs

    def _parse_additional_info(self, soup: BeautifulSoup) -> OEILAdditionalInfo:
        """Parse Section 7: Additional Information - Direct search approach"""
        additional = OEILAdditionalInfo()

        try:
            # Find EUR-Lex link anywhere on the page
            eurlex_links = soup.find_all('a', href=re.compile(r'eur-lex\.europa\.eu'))
            for link in eurlex_links:
                url = link.get('href', '')
                if url:
                    additional.eurlex_url = url
                    # Extract CELEX from URL
                    celex_match = re.search(r'/(\d{5}[A-Z]\d{4})/', url)
                    if celex_match:
                        additional.celex_number = celex_match.group(1)
                    # Also try other CELEX patterns
                    if not additional.celex_number:
                        celex_match = re.search(r'CELEX[=:](\d+[A-Z]\d+)', url)
                        if celex_match:
                            additional.celex_number = celex_match.group(1)
                    break

            # Find related procedures - both old and new URL formats
            procedure_patterns = [
                r'ficheprocedure\.do',
                r'procedure-file\?reference=',
            ]
            for pattern in procedure_patterns:
                related_links = soup.find_all('a', href=re.compile(pattern))
                for link in related_links:
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    # Extract procedure reference from URL
                    ref_match = re.search(r'reference=([^&]+)', href)
                    if ref_match:
                        ref = ref_match.group(1)
                        # Don't add the current procedure as related
                        if ref not in [p.get('reference') for p in additional.related_procedures]:
                            additional.related_procedures.append({
                                'reference': ref,
                                'title': text,
                                'url': self._make_absolute_url(href)
                            })

            # Find other useful links (EP Research, etc.)
            research_links = soup.find_all('a', href=re.compile(r'epthinktank|europarl\.europa\.eu/thinktank'))
            for link in research_links:
                text = link.get_text(strip=True)
                url = link.get('href', '')
                if text and url:
                    additional.other_links.append({
                        'text': text,
                        'url': self._make_absolute_url(url)
                    })

        except Exception as e:
            logger.warning(f"Error parsing additional info: {e}")

        return additional

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _find_section(self, soup: BeautifulSoup, section_title: str) -> Optional[Tag]:
        """Find a main section by its title and return all content until next section"""
        # New OEIL format (2025): sections use h2 headings
        for h2 in soup.find_all('h2'):
            if section_title.lower() in h2.get_text(strip=True).lower():
                # Collect all siblings until next h2
                content_elements = []
                for sibling in h2.find_next_siblings():
                    if sibling.name == 'h2':
                        break  # Stop at next section
                    content_elements.append(sibling)

                if content_elements:
                    # Create a wrapper to hold all content
                    from bs4 import NavigableString
                    wrapper = soup.new_tag('div')
                    for elem in content_elements:
                        if not isinstance(elem, NavigableString) or elem.strip():
                            wrapper.append(elem.extract() if hasattr(elem, 'extract') else elem)
                    # Re-insert elements (they were extracted)
                    for elem in content_elements:
                        try:
                            h2.insert_after(elem)
                        except:
                            pass
                    return wrapper if wrapper.contents else content_elements[0]

                # Fallback: return next sibling
                next_elem = h2.find_next_sibling()
                if next_elem:
                    return next_elem

                # Or return the parent container
                parent = h2.find_parent(['div', 'section', 'article'])
                if parent:
                    return parent

        # Look for headers with class containing section title
        headers = soup.find_all(['h2', 'h3', 'div'], class_=re.compile(r'section|header|title'))
        for header in headers:
            if section_title.lower() in header.get_text(strip=True).lower():
                parent = header.find_parent(['div', 'section', 'table'])
                if parent:
                    return parent
                return header.find_next_sibling()

        # Fallback: look for text containing section title
        for elem in soup.find_all(string=re.compile(section_title, re.IGNORECASE)):
            parent = elem.find_parent(['div', 'section', 'table', 'tr'])
            if parent:
                return parent

        return None

    def _find_subsection(self, section: Tag, subsection_title: str) -> Optional[Tag]:
        """Find a subsection within a section"""
        if not section:
            return None

        for elem in section.find_all(string=re.compile(subsection_title, re.IGNORECASE)):
            parent = elem.find_parent(['div', 'table', 'tr'])
            if parent:
                return parent

        return None

    def _find_row_by_label(self, container: Tag, label: str) -> Optional[Tag]:
        """Find a table row by its label text"""
        if not container:
            return None

        rows = container.find_all('tr')
        for row in rows:
            cells = row.find_all(['th', 'td'])
            if cells and label.lower() in cells[0].get_text(strip=True).lower():
                # Return the value cell
                return cells[1] if len(cells) > 1 else cells[0]

        return None

    def _parse_mep_from_link(self, link: Tag) -> Optional[OEILMep]:
        """Extract MEP data from an anchor tag"""
        if not link:
            return None

        try:
            href = link.get('href', '')
            raw_name = link.get_text(strip=True)

            if not raw_name:
                return None

            # Clean name: remove political group if it's in the name text
            # Format is often "SURNAME Name (GROUP)" or just "SURNAME Name"
            name = raw_name
            political_group = None

            # Extract political group from name if present
            group_match = re.search(r'\(([A-Z&/]+(?:/[A-Z]+)?)\)$', raw_name)
            if group_match:
                political_group = group_match.group(1)
                name = raw_name[:group_match.start()].strip()

            mep = OEILMep(name=name, political_group=political_group)

            # Extract MEP ID from URL
            id_match = self.MEP_URL_PATTERN.search(href)
            if id_match:
                mep.mep_id = id_match.group(1)
                mep.profile_url = f"https://www.europarl.europa.eu/meps/en/{mep.mep_id}"
                # New format: photo URL from MEP ID
                mep.photo_url = f"https://www.europarl.europa.eu/mepphoto/{mep.mep_id}.jpg"

            # Also check for photo in data-title (legacy format)
            data_title = link.get('data-title', '')
            if data_title:
                img_match = re.search(r"src='([^']+)'", data_title)
                if img_match:
                    mep.photo_url = img_match.group(1)

            # Look for <img> tag inside or nearby (new format)
            img = link.find('img')
            if img and img.get('src'):
                mep.photo_url = img.get('src')

            # Extract political group from surrounding text if not found in name
            if not political_group:
                next_text = link.next_sibling
                if next_text and isinstance(next_text, str):
                    group_match = re.search(r'\(([A-Z&/]+(?:/[A-Z]+)?)\)', next_text)
                    if group_match:
                        mep.political_group = group_match.group(1)

            return mep

        except Exception as e:
            logger.debug(f"Error parsing MEP from link: {e}")
            return None

    def _parse_committee_from_table(self, table: Tag, role: str) -> Optional[OEILCommittee]:
        """Parse committee information from a table"""
        if not table:
            return None

        try:
            # Find committee code - usually in first cell
            first_cell = table.find('td')
            if not first_cell:
                return None

            code_text = first_cell.get_text(strip=True)
            code_match = re.match(r'^([A-Z]{4})', code_text)
            if not code_match:
                return None

            committee = OEILCommittee(
                code=code_match.group(1),
                role=role
            )

            # Find rapporteur link
            rapporteur_links = table.find_all('a', href=re.compile(r'/meps/'))
            if rapporteur_links:
                committee.rapporteur = self._parse_mep_from_link(rapporteur_links[0])

                # Remaining links are shadow rapporteurs
                for link in rapporteur_links[1:]:
                    shadow = self._parse_mep_from_link(link)
                    if shadow:
                        committee.shadow_rapporteurs.append(shadow)

            # Parse dates from text
            text = table.get_text()
            date_matches = self.DATE_PATTERN.findall(text)
            if date_matches:
                # First date is usually announcement date
                d, m, y = date_matches[0]
                committee.date_announced = date(int(y), int(m), int(d))

            return committee

        except Exception as e:
            logger.debug(f"Error parsing committee: {e}")
            return None

    def _parse_event_row(self, cells: List[Tag]) -> Optional[OEILEvent]:
        """Parse an event from table cells"""
        if len(cells) < 2:
            return None

        try:
            # First cell usually contains date
            date_text = cells[0].get_text(strip=True)
            date_match = self.DATE_PATTERN.search(date_text)
            if not date_match:
                return None

            d, m, y = date_match.groups()
            event_date = date(int(y), int(m), int(d))

            # Second cell contains event type/description
            event_type = cells[1].get_text(strip=True) if len(cells) > 1 else ''

            event = OEILEvent(
                date=event_date,
                event_type=event_type
            )

            # Look for additional details in remaining cells
            if len(cells) > 2:
                event.description = cells[2].get_text(strip=True)

            # Extract any document links
            for cell in cells:
                doc_links = cell.find_all('a')
                for link in doc_links:
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    if text and href:
                        event.documents.append(OEILDocument(
                            reference=text,
                            url=self._make_absolute_url(href)
                        ))

            return event

        except Exception as e:
            logger.debug(f"Error parsing event: {e}")
            return None

    def _parse_forecast_row(self, cells: List[Tag]) -> Optional[OEILForecast]:
        """Parse a forecast from table cells"""
        if len(cells) < 2:
            return None

        try:
            event_type = cells[0].get_text(strip=True)
            if not event_type:
                return None

            forecast = OEILForecast(event_type=event_type)

            # Parse date from second cell
            date_text = cells[1].get_text(strip=True) if len(cells) > 1 else ''
            date_match = self.DATE_PATTERN.search(date_text)
            if date_match:
                d, m, y = date_match.groups()
                forecast.forecast_date = date(int(y), int(m), int(d))

            # Check for committee or plenary
            full_text = ' '.join(c.get_text(strip=True) for c in cells)
            if 'plenary' in full_text.lower():
                forecast.location = 'Plenary'
            else:
                comm_match = re.search(r'\b([A-Z]{4})\b', full_text)
                if comm_match:
                    forecast.committee = comm_match.group(1)
                    forecast.location = 'Committee'

            return forecast

        except Exception as e:
            logger.debug(f"Error parsing forecast: {e}")
            return None

    def _parse_document_row(self, row: Tag) -> Optional[OEILDocument]:
        """Parse a document from a table row"""
        if not row:
            return None

        try:
            cells = row.find_all('td')
            if not cells:
                return None

            # Find document reference - usually in a link
            link = row.find('a')
            if link:
                reference = link.get_text(strip=True)
                url = link.get('href', '')
            else:
                reference = cells[0].get_text(strip=True) if cells else ''
                url = ''

            if not reference:
                return None

            doc = OEILDocument(
                reference=reference,
                url=self._make_absolute_url(url) if url else None
            )

            # Parse date if present
            text = row.get_text()
            date_match = self.DATE_PATTERN.search(text)
            if date_match:
                d, m, y = date_match.groups()
                doc.date = date(int(y), int(m), int(d))

            # Look for PDF link
            pdf_link = row.find('a', href=re.compile(r'\.pdf'))
            if pdf_link:
                doc.pdf_url = self._make_absolute_url(pdf_link.get('href', ''))

            return doc

        except Exception as e:
            logger.debug(f"Error parsing document: {e}")
            return None

    def _parse_consultative_body(self, row: Tag, body: str) -> Optional[OEILConsultativeBody]:
        """Parse consultative body information"""
        if not row:
            return None

        try:
            text = row.get_text(strip=True)

            body_info = OEILConsultativeBody(
                body=body,
                opinion_mandatory='mandatory' in text.lower()
            )

            # Parse date
            date_match = self.DATE_PATTERN.search(text)
            if date_match:
                d, m, y = date_match.groups()
                body_info.opinion_date = date(int(y), int(m), int(d))

            return body_info

        except Exception as e:
            logger.debug(f"Error parsing consultative body: {e}")
            return None

    def _parse_national_parliament_contribution(self, item: Tag) -> Optional[OEILNationalParliamentContribution]:
        """Parse national parliament contribution"""
        if not item:
            return None

        try:
            text = item.get_text(strip=True)
            if not text:
                return None

            # Try to extract parliament name (usually at the start)
            # Common patterns: "German Bundestag", "French Senate", etc.
            contribution = OEILNationalParliamentContribution(
                parliament=text.split(':')[0].strip() if ':' in text else text[:50],
                contribution_type='Contribution'
            )

            # Check for specific contribution types
            if 'reasoned opinion' in text.lower():
                contribution.contribution_type = 'Reasoned opinion'
            elif 'political dialogue' in text.lower():
                contribution.contribution_type = 'Political dialogue'

            # Parse date
            date_match = self.DATE_PATTERN.search(text)
            if date_match:
                d, m, y = date_match.groups()
                contribution.date = date(int(y), int(m), int(d))

            # Look for link
            link = item.find('a')
            if link:
                contribution.url = self._make_absolute_url(link.get('href', ''))

            return contribution

        except Exception as e:
            logger.debug(f"Error parsing national parliament contribution: {e}")
            return None

    def _parse_date(self, text: str) -> Optional[date]:
        """Parse date from DD/MM/YYYY format"""
        if not text:
            return None

        match = self.DATE_PATTERN.search(text)
        if match:
            d, m, y = match.groups()
            try:
                return date(int(y), int(m), int(d))
            except ValueError:
                return None
        return None
