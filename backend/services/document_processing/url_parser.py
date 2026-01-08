"""
EUR-Lex URL Parser

Extracts CELEX numbers and metadata from EUR-Lex URLs.
Supports multiple EUR-Lex URL formats.
"""

import re
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


class URLParser:
    """
    Parse EUR-Lex URLs to extract CELEX numbers and metadata.

    Supported URL formats:
    - https://eur-lex.europa.eu/legal-content/{lang}/TXT/?uri=CELEX:{celex}
    - https://eur-lex.europa.eu/legal-content/{lang}/TXT/?uri=celex:{celex}
    - https://eur-lex.europa.eu/eli/{type}/{year}/{number}/oj
    - https://eur-lex.europa.eu/eli/{type}/{year}/{number}
    """

    # CELEX pattern: 5 digits + 1-2 letters (e.g., R, L, D, PC, DC) + 4+ digits
    # Examples: 32016R0679 (GDPR), 52023PC0278 (Proposal)
    CELEX_PATTERN = re.compile(r'\b([0-9]{5}[A-Z]{1,2}[0-9]{4,})\b')

    # EUR-Lex base domains
    EURLEX_DOMAINS = ['eur-lex.europa.eu', 'publications.europa.eu']

    # Supported languages
    LANGUAGES = [
        'EN', 'FR', 'DE', 'IT', 'ES', 'PT', 'NL', 'EL', 'PL', 'CS',
        'RO', 'HU', 'BG', 'SV', 'DA', 'FI', 'SK', 'LT', 'LV', 'ET',
        'SL', 'MT', 'GA', 'HR'
    ]

    def parse_eurlex_url(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Parse EUR-Lex URL to extract CELEX number and metadata.

        Args:
            url: EUR-Lex URL

        Returns:
            Dict with:
            - celex: CELEX number (uppercase)
            - language: Language code (uppercase)
            - format: Document format (html, pdf, xml)
            - valid: Whether URL is valid EUR-Lex URL
            - url_type: Type of URL (celex_uri, eli)

        Example:
            >>> parser = URLParser()
            >>> result = parser.parse_eurlex_url(
            ...     "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679"
            ... )
            >>> result['celex']
            '32016R0679'
        """
        try:
            parsed = urlparse(url)

            # Check if EUR-Lex domain
            if not any(domain in parsed.netloc for domain in self.EURLEX_DOMAINS):
                logger.warning(f"Not a EUR-Lex URL: {url}")
                return {
                    'valid': False,
                    'error': 'Not a EUR-Lex URL'
                }

            # Extract language from path
            language = self._extract_language_from_path(parsed.path)

            # Extract format from path
            doc_format = self._extract_format_from_path(parsed.path)

            # Try to extract CELEX from query parameters
            celex = self._extract_celex_from_query(parsed.query)

            if celex:
                return {
                    'celex': celex.upper(),
                    'language': language or 'EN',
                    'format': doc_format or 'html',
                    'valid': True,
                    'url_type': 'celex_uri',
                    'original_url': url
                }

            # Try to extract CELEX from ELI path format
            celex = self._extract_celex_from_eli_path(parsed.path)

            if celex:
                return {
                    'celex': celex.upper(),
                    'language': language or 'EN',
                    'format': doc_format or 'html',
                    'valid': True,
                    'url_type': 'eli',
                    'original_url': url
                }

            # Try to find CELEX anywhere in URL
            celex_match = self.CELEX_PATTERN.search(url.upper())
            if celex_match:
                return {
                    'celex': celex_match.group(1),
                    'language': language or 'EN',
                    'format': doc_format or 'html',
                    'valid': True,
                    'url_type': 'pattern_match',
                    'original_url': url
                }

            logger.warning(f"Could not extract CELEX from URL: {url}")
            return {
                'valid': False,
                'error': 'Could not extract CELEX number from URL'
            }

        except Exception as e:
            logger.error(f"Error parsing URL {url}: {str(e)}")
            return {
                'valid': False,
                'error': str(e)
            }

    def _extract_celex_from_query(self, query_string: str) -> Optional[str]:
        """Extract CELEX from query parameters"""
        try:
            params = parse_qs(query_string)

            # Look for uri parameter
            if 'uri' in params:
                uri = params['uri'][0]

                # Check if it contains CELEX:
                if 'CELEX:' in uri.upper():
                    celex = uri.upper().split('CELEX:')[1]
                    return celex.strip()

                # Check if it contains celex:
                if 'celex:' in uri.lower():
                    celex = uri.split(':')[1]
                    return celex.strip()

            return None

        except Exception as e:
            logger.error(f"Error extracting CELEX from query: {str(e)}")
            return None

    def _extract_celex_from_eli_path(self, path: str) -> Optional[str]:
        """
        Extract CELEX from ELI path format.

        Example: /eli/reg/2016/679/oj -> 32016R0679
        """
        try:
            # Remove leading/trailing slashes
            path = path.strip('/')

            # Split path
            parts = path.split('/')

            # Check if it's ELI format
            if parts[0] != 'eli':
                return None

            # Need at least: eli/type/year/number
            if len(parts) < 4:
                return None

            doc_type = parts[1]
            year = parts[2]
            number = parts[3]

            # Map ELI document types to CELEX codes
            type_map = {
                'reg': 'R',      # Regulation
                'dir': 'L',      # Directive
                'dec': 'D',      # Decision
                'rec': 'X',      # Recommendation
                'opin': 'X',     # Opinion
            }

            celex_type = type_map.get(doc_type.lower())
            if not celex_type:
                return None

            # Construct CELEX: 3{year}{type}{number}
            celex = f"3{year}{celex_type}{number.zfill(4)}"

            return celex

        except Exception as e:
            logger.error(f"Error extracting CELEX from ELI path: {str(e)}")
            return None

    def _extract_language_from_path(self, path: str) -> Optional[str]:
        """Extract language code from path"""
        try:
            # Look for language codes in path
            for lang in self.LANGUAGES:
                if f'/{lang}/' in path.upper():
                    return lang

            return None

        except Exception:
            return None

    def _extract_format_from_path(self, path: str) -> Optional[str]:
        """Extract document format from path"""
        try:
            path_upper = path.upper()

            if '/PDF/' in path_upper:
                return 'pdf'
            elif '/XML/' in path_upper:
                return 'xml'
            elif '/HTML/' in path_upper or '/TXT/' in path_upper:
                return 'html'

            return None

        except Exception:
            return None

    def validate_celex(self, celex: str) -> bool:
        """
        Validate CELEX number format.

        Args:
            celex: CELEX number to validate

        Returns:
            True if valid CELEX format
        """
        if not celex:
            return False

        return bool(self.CELEX_PATTERN.match(celex.upper()))

    def build_eurlex_url(
        self,
        celex: str,
        language: str = 'EN',
        format: str = 'html'
    ) -> str:
        """
        Build EUR-Lex URL from CELEX number.

        Args:
            celex: CELEX number
            language: Language code (default: EN)
            format: Document format (html, pdf, xml)

        Returns:
            EUR-Lex URL
        """
        celex = celex.upper()
        language = language.upper()

        if format == 'pdf':
            return f"https://eur-lex.europa.eu/legal-content/{language}/TXT/PDF/?uri=CELEX:{celex}"
        elif format == 'xml':
            return f"https://eur-lex.europa.eu/legal-content/{language}/TXT/XML/?uri=CELEX:{celex}"
        else:  # html
            return f"https://eur-lex.europa.eu/legal-content/{language}/TXT/?uri=CELEX:{celex}"


# Global singleton
_url_parser: Optional[URLParser] = None


def get_url_parser() -> URLParser:
    """Get global URL parser instance"""
    global _url_parser

    if _url_parser is None:
        _url_parser = URLParser()

    return _url_parser
