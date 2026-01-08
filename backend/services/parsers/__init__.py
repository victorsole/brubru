"""
EU Law Parsers and Fetchers

Parsers for different EU legal document formats:
- formex_parser: Parse Formex XML from EUR-Lex (LEG_2025-11 archive)
- eurlex_parser: Parse EUR-Lex XHTML (web format)
- eurlex_fetcher: Fetch laws from local DB or EUR-Lex web
"""

from .formex_parser import FormexParser, parse_formex_file
from .eurlex_parser import EurlexParser, parse_eurlex_html
from .eurlex_fetcher import EurlexFetcher, LawResult, fetch_law

__all__ = [
    'FormexParser',
    'parse_formex_file',
    'EurlexParser',
    'parse_eurlex_html',
    'EurlexFetcher',
    'LawResult',
    'fetch_law',
]
