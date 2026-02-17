"""
Beresol Knowledge Bundle Loader

Loads open reports and monitors from Beresol (Brubru's company) for use in AI chat context.
All content should be attributed to Beresol with link: https://beresol.eu/public-affairs

Content types:
- Reports: In-depth analysis on EU policy topics (markdown files)
- Monitors: Live dashboards tracking EU policy areas (metadata only for context)

Source: backend/knowledge_base/brubru-knowledge-bundle/
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Beresol attribution
BERESOL_ATTRIBUTION = {
    'source': 'Beresol Open Report',
    'publisher': 'Beresol',
    'url': 'https://beresol.eu/public-affairs',
    'note': 'This is an open report/monitor published by Beresol, Brubru\'s company.'
}


class BeresolKnowledgeLoader:
    """
    Load and manage Beresol's open reports and monitors.

    These are curated analysis pieces from Beresol that provide
    deep-dive context on EU policy topics.
    """

    def __init__(self, bundle_dir: str = None):
        """
        Initialize Beresol knowledge loader.

        Args:
            bundle_dir: Path to brubru-knowledge-bundle directory
        """
        if bundle_dir is None:
            current_dir = Path(__file__).parent
            bundle_dir = str(current_dir / "brubru-knowledge-bundle")

        self.bundle_dir = Path(bundle_dir)
        self.reports_dir = self.bundle_dir / "reports"
        self.monitors_dir = self.bundle_dir / "monitors"

        # In-memory storage
        self.reports: Dict[str, Dict[str, Any]] = {}
        self.monitors: Dict[str, Dict[str, Any]] = {}

        # Metadata
        self.last_loaded: Optional[datetime] = None
        self.stats: Dict[str, int] = {}

        logger.info(f"Initialized BeresolKnowledgeLoader at {self.bundle_dir}")

    def load_all(self) -> Dict[str, Any]:
        """
        Load all Beresol content.

        Returns:
            Statistics about loaded content
        """
        logger.info("Loading Beresol knowledge bundle...")
        start_time = datetime.now()

        self._load_reports()
        self._load_monitors_metadata()

        self.last_loaded = datetime.now()
        load_time = (self.last_loaded - start_time).total_seconds()

        self.stats = {
            'reports': len(self.reports),
            'monitors': len(self.monitors),
            'load_time_seconds': load_time
        }

        logger.info(f"Loaded Beresol bundle in {load_time:.2f}s: {self.stats}")
        return self.stats

    def _load_reports(self):
        """Load all markdown report files."""
        if not self.reports_dir.exists():
            logger.warning(f"Reports directory not found: {self.reports_dir}")
            return

        for md_file in self.reports_dir.glob("*.md"):
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Extract metadata from content
                metadata = self._extract_report_metadata(content, md_file.stem)

                self.reports[md_file.stem] = {
                    'id': md_file.stem,
                    'slug': md_file.stem,
                    'content': content,
                    **metadata,
                    **BERESOL_ATTRIBUTION
                }

                logger.debug(f"Loaded Beresol report: {md_file.stem}")

            except Exception as e:
                logger.error(f"Failed to load report {md_file}: {str(e)}")

    def _extract_report_metadata(self, content: str, filename: str) -> Dict[str, Any]:
        """
        Extract metadata from report markdown content.

        Args:
            content: Markdown content
            filename: Original filename (used as fallback)

        Returns:
            Dictionary with title, author, date, policy_area, etc.
        """
        metadata = {
            'title': filename.replace('-', ' ').replace('_', ' ').title(),
            'author': 'Victor Sole Ferioli',
            'date': None,
            'policy_area': self._infer_policy_area(filename, content),
            'keywords': [],
            'executive_summary': ''
        }

        # Extract title (first H1)
        title_match = re.search(r'^#\s+(.+?)(?:\n|$)', content, re.MULTILINE)
        if title_match:
            metadata['title'] = title_match.group(1).strip()

        # Extract subtitle (if exists after title)
        subtitle_match = re.search(r'^#\s+.+?\n+\*\*(.+?)\*\*', content)
        if subtitle_match:
            metadata['subtitle'] = subtitle_match.group(1).strip()

        # Extract author
        author_match = re.search(r'\*\*Author:\*\*\s*(.+?)(?:\n|$)', content)
        if author_match:
            metadata['author'] = author_match.group(1).strip()

        # Extract date
        date_match = re.search(r'\*\*Date:\*\*\s*(.+?)(?:\n|$)', content)
        if date_match:
            metadata['date'] = date_match.group(1).strip()

        # Extract executive summary
        exec_match = re.search(
            r'##\s*Executive Summary\s*\n+([\s\S]+?)(?=\n##|\n---|\Z)',
            content,
            re.IGNORECASE
        )
        if exec_match:
            # Get first 1000 chars of executive summary
            summary = exec_match.group(1).strip()
            # Remove markdown formatting for cleaner text
            summary = re.sub(r'\*\*([^*]+)\*\*', r'\1', summary)
            summary = re.sub(r'\*([^*]+)\*', r'\1', summary)
            metadata['executive_summary'] = summary[:1500]

        # Extract key findings if present
        findings_match = re.search(
            r'\*\*Key Findings:\*\*\s*\n+([\s\S]+?)(?=\n##|\n---|\Z)',
            content
        )
        if findings_match:
            metadata['key_findings'] = findings_match.group(1).strip()[:1000]

        # Extract keywords from content
        metadata['keywords'] = self._extract_keywords(content)

        return metadata

    def _infer_policy_area(self, filename: str, content: str) -> str:
        """Infer policy area from filename and content."""
        filename_lower = filename.lower()
        content_lower = content.lower()[:3000]  # Check first 3000 chars

        # Check filename first (most reliable)
        filename_mappings = {
            'ai-act': 'digital',
            'digital-omnibus': 'digital',
            'omnibus-ai': 'digital',
            'cbam': 'trade',
            'carbon-border': 'trade',
            'mercosur': 'trade',
            'aci': 'trade',
            'anti-coercion': 'trade',
            'blackout': 'energy',
            'iberian': 'energy',
            'agri': 'agriculture',
            'food': 'agriculture',
            'fisheries': 'agriculture',
            'mediterranean': 'agriculture',
            'ferroviaria': 'transport',
            'rail': 'transport',
            'crisi': 'transport',
            'ukraine': 'enlargement',
            'rff': 'economic',
            'rrf': 'economic',
            'recovery': 'economic',
            'draghi': 'economic',
            'letta': 'economic',
            'niinisto': 'defence',
            'dora': 'finance',
            'mica': 'finance',
            'crypto': 'finance',
            'sfdr': 'finance',
            'sustainable-finance': 'finance',
            'aifmd': 'finance',
            'alternative-investment': 'finance',
            'us-eu-ai': 'digital',
            'regulatory-divergence': 'digital',
            'venture-capital': 'finance',
            'ec-venture': 'finance',
            'euveca': 'finance',
            'citizens-initiative': 'democracy',
            'european-citizens': 'democracy',
        }

        for pattern, area in filename_mappings.items():
            if pattern in filename_lower:
                return area

        # Then check content for broader patterns
        content_mappings = {
            'finance': ['dora', 'digital operational resilience', 'mica', 'crypto-asset', 'stablecoin',
                        'sfdr', 'sustainable finance disclosure', 'eba ', 'esma ', 'eiopa',
                        'casp', 'asset-referenced token', 'e-money token', 'aifmd', 'psd3',
                        'crd vi', 'banking union', 'ict risk management', 'ict third-party',
                        'alternative investment fund', 'loan origination', 'ucits',
                        'liquidity management tool', 'private credit',
                        'venture capital', 'euveca', 'eusef', 'growth capital',
                        'aum threshold', 'cross-border fundraising'],
            'trade': ['mercosur', 'cbam', 'tariff', 'trade agreement', 'anti-coercion', 'wto'],
            'energy': ['blackout', 'grid', 'electricity', 'power outage', 'interconnection'],
            'agriculture': ['agri-food', 'fisheries', 'cap ', 'common agricultural', 'farming', 'trawling'],
            'transport': ['railway', 'ferrocarril', 'rodalies', 'renfe', 'train'],
            'digital': ['ai act', 'artificial intelligence', 'digital omnibus', 'digital', 'gpai', 'ai office'],
            'defence': ['defence', 'defense', 'military', 'edip', 'edis', 'rearm'],
            'economic': ['rrf', 'recovery and resilience', 'competitiveness', 'single market', 'draghi report'],
            'enlargement': ['ukraine', 'enlargement', 'accession', 'membership', 'candidate country'],
            'democracy': ['citizens initiative', 'eci ', 'participatory democracy', 'petition',
                          'regulation 2019/788', 'right2water', 'statement of support',
                          'direct democracy', 'citizens\' initiative']
        }

        for area, keywords in content_mappings.items():
            for keyword in keywords:
                if keyword in content_lower:
                    return area

        return 'general'

    def _extract_keywords(self, content: str) -> List[str]:
        """Extract relevant EU policy keywords from content."""
        # Common EU policy terms to look for
        eu_terms = [
            'AI Act', 'Digital Omnibus', 'CBAM', 'ETS', 'Green Deal', 'Fit for 55',
            'CAP', 'CMU', 'Single Market', 'GDPR', 'DSA', 'DMA',
            'MiCA', 'CSRD', 'CSDDD', 'NIS2', 'CER', 'REACH',
            'REPowerEU', 'RRF', 'MFF', 'Horizon Europe',
            'OEIL', 'EUR-Lex', 'CELEX', 'trilogue', 'codecision',
            'directive', 'regulation', 'decision',
            'Commission', 'Parliament', 'Council', 'COREPER',
            'Mercosur', 'WTO', 'FTA', 'tariff', 'trade war',
            'DORA', 'SFDR', 'AIFMD', 'PSD2', 'PSD3', 'CRD',
            'EBA', 'ESMA', 'EIOPA', 'Solvency II', 'MiFID',
            'EMIR', 'UCITS', 'EU Taxonomy', 'ESG',
            'stablecoin', 'crypto-asset', 'CASP',
            'ICT risk', 'cyber resilience', 'fintech',
            'ECI', 'European Citizens\' Initiative', 'participatory democracy',
            'Right2Water', 'petition', 'EESC', 'Ombudsman'
        ]

        found_keywords = []
        content_text = content[:10000]  # Search first 10k chars

        for term in eu_terms:
            if term.lower() in content_text.lower():
                found_keywords.append(term)

        return found_keywords[:15]  # Limit to 15 keywords

    def _load_monitors_metadata(self):
        """
        Load monitor metadata (not full React components).

        Monitors are React dashboards, so we extract descriptive metadata
        for AI context rather than the code itself.
        """
        # Define monitors based on the monitorRelationships.ts data
        monitor_definitions = [
            {
                'id': 'defence',
                'name': 'EU Defence Monitor',
                'description': 'Tracks EU defence spending, EDIP, EDIS, and ReArm Europe initiatives. Covers defence industrial policy, procurement, and NATO-EU coordination.',
                'policy_area': 'defence',
                'keywords': ['defence', 'EDIP', 'EDIS', 'ReArm Europe', 'NATO', 'military', 'procurement']
            },
            {
                'id': 'cmu',
                'name': 'Capital Markets Union Monitor',
                'description': 'Tracks progress on EU Capital Markets Union and Savings & Investment Union. Covers securitisation, listing rules, retail investment, and cross-border capital flows.',
                'policy_area': 'economic',
                'keywords': ['CMU', 'SIU', 'capital markets', 'securitisation', 'IPO', 'retail investment', 'Eurogroup']
            },
            {
                'id': 'tariffs',
                'name': 'Tariff & Trade War Monitor',
                'description': 'Monitors US-EU trade tensions, tariff rates, and retaliatory measures. Covers Section 301, Liberation Day tariffs, and EU response mechanisms.',
                'policy_area': 'trade',
                'keywords': ['tariffs', 'trade war', 'Section 301', 'Liberation Day', 'retaliation', 'steel', 'aluminium']
            },
            {
                'id': 'ai',
                'name': 'AI Market Monitor',
                'description': 'Tracks AI investment, regulation implementation, and market dynamics in Europe. Covers AI Act compliance, VC funding, and EU vs US/China comparisons.',
                'policy_area': 'digital',
                'keywords': ['AI', 'artificial intelligence', 'AI Act', 'GPAI', 'AI Office', 'compute', 'foundation models']
            },
            {
                'id': 'quantum',
                'name': 'EU Quantum Monitor',
                'description': 'Monitors EU quantum technology development and investment. Covers Quantum Flagship, post-quantum cryptography, and quantum computing applications.',
                'policy_area': 'digital',
                'keywords': ['quantum', 'QCI', 'post-quantum', 'cryptography', 'quantum computing', 'Quantum Flagship']
            },
            {
                'id': 'startups',
                'name': 'EU Startup Monitor',
                'description': 'Tracks European startup ecosystem, VC funding, and regulatory environment. Covers unicorns, scale-ups, ESOP regimes, and EIC funding.',
                'policy_area': 'economic',
                'keywords': ['startups', 'unicorns', 'VC', 'venture capital', 'scale-up', 'EIC', 'ESOP']
            },
            {
                'id': 'gold',
                'name': 'Gold Trading Monitor',
                'description': 'Monitors gold prices, central bank reserves, and tokenised gold under MiCA. Tracks gold ETFs, mining production, and safe-haven dynamics.',
                'policy_area': 'economic',
                'keywords': ['gold', 'PAXG', 'XAUT', 'MiCA', 'central bank reserves', 'ETF', 'commodities']
            }
        ]

        for monitor in monitor_definitions:
            self.monitors[monitor['id']] = {
                **monitor,
                **BERESOL_ATTRIBUTION
            }
            logger.debug(f"Loaded Beresol monitor metadata: {monitor['id']}")

    # =========================================================================
    # Query Methods
    # =========================================================================

    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a report by ID (filename without extension).

        Args:
            report_id: Report identifier (e.g., 'ai-act-implementation')

        Returns:
            Report data or None
        """
        return self.reports.get(report_id)

    def list_reports(self) -> List[Dict[str, Any]]:
        """
        List all available reports with metadata (without full content).

        Returns:
            List of report metadata
        """
        return [
            {
                'id': r['id'],
                'slug': r['slug'],
                'title': r['title'],
                'author': r['author'],
                'date': r.get('date'),
                'policy_area': r['policy_area'],
                'keywords': r['keywords'],
                'source': r['source'],
                'url': r['url']
            }
            for r in self.reports.values()
        ]

    def search_reports(self, query: str, policy_area: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search reports by keyword.

        Args:
            query: Search query
            policy_area: Optional policy area filter

        Returns:
            List of matching reports with relevance context
        """
        query_lower = query.lower()
        matches = []

        for report_id, report in self.reports.items():
            # Filter by policy area if specified
            if policy_area and report.get('policy_area') != policy_area:
                continue

            # Search in title, keywords, and content
            searchable = (
                report.get('title', '').lower() + ' ' +
                report.get('subtitle', '').lower() + ' ' +
                ' '.join(report.get('keywords', [])).lower() + ' ' +
                report.get('executive_summary', '').lower() + ' ' +
                report.get('content', '')[:5000].lower()
            )

            # Match if full query is a substring, or if enough significant words match
            query_words = [w for w in re.split(r'\W+', query_lower) if len(w) > 3]
            full_match = query_lower in searchable
            word_matches = sum(1 for w in query_words if w in searchable) if query_words else 0
            word_ratio = word_matches / len(query_words) if query_words else 0
            matched = full_match or (len(query_words) >= 2 and word_ratio >= 0.5)

            if matched:
                # Find context snippet around match
                content = report.get('content', '')
                idx = content.lower().find(query_lower)

                if idx != -1:
                    start = max(0, idx - 100)
                    end = min(len(content), idx + len(query) + 200)
                    snippet = content[start:end].strip()
                    if start > 0:
                        snippet = "..." + snippet
                    if end < len(content):
                        snippet = snippet + "..."
                else:
                    snippet = report.get('executive_summary', '')[:300]

                matches.append({
                    'id': report_id,
                    'title': report['title'],
                    'subtitle': report.get('subtitle', ''),
                    'author': report['author'],
                    'date': report.get('date'),
                    'policy_area': report['policy_area'],
                    'snippet': snippet,
                    'keywords': report.get('keywords', []),
                    'source': report['source'],
                    'url': report['url'],
                    'note': report['note']
                })

        return matches

    def get_report_content(self, report_id: str, max_length: int = 5000) -> Optional[str]:
        """
        Get report content (truncated for AI context).

        Args:
            report_id: Report identifier
            max_length: Maximum content length

        Returns:
            Truncated report content or None
        """
        report = self.reports.get(report_id)
        if not report:
            return None

        content = report.get('content', '')
        if len(content) > max_length:
            content = content[:max_length] + "\n\n[Content truncated - full report available at Beresol]"

        return content

    def get_monitor(self, monitor_id: str) -> Optional[Dict[str, Any]]:
        """Get monitor metadata by ID."""
        return self.monitors.get(monitor_id)

    def list_monitors(self) -> List[Dict[str, Any]]:
        """List all monitor metadata."""
        return list(self.monitors.values())

    def search_all(self, query: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search across all Beresol content.

        Args:
            query: Search query

        Returns:
            Dictionary with 'reports' and 'monitors' matches
        """
        return {
            'reports': self.search_reports(query),
            'monitors': self._search_monitors(query)
        }

    def _search_monitors(self, query: str) -> List[Dict[str, Any]]:
        """Search monitors by keyword."""
        query_lower = query.lower()
        matches = []

        for monitor in self.monitors.values():
            searchable = (
                monitor['name'].lower() + ' ' +
                monitor['description'].lower() + ' ' +
                ' '.join(monitor['keywords']).lower()
            )

            if query_lower in searchable:
                matches.append(monitor)

        return matches

    def get_relevant_content_for_query(
        self,
        query: str,
        max_reports: int = 2,
        max_content_length: int = 3000
    ) -> List[Dict[str, Any]]:
        """
        Get relevant Beresol content for an AI query.

        This is the main method used by ContextBuilder.

        Args:
            query: User query
            max_reports: Maximum number of reports to return
            max_content_length: Maximum content length per report

        Returns:
            List of relevant content items with proper attribution
        """
        results = []

        # Search reports
        matching_reports = self.search_reports(query)

        for report in matching_reports[:max_reports]:
            full_report = self.reports.get(report['id'])
            if not full_report:
                continue

            # Get truncated content
            content = full_report.get('content', '')
            if len(content) > max_content_length:
                content = content[:max_content_length] + "\n\n[...]"

            results.append({
                'type': 'beresol_report',
                'id': report['id'],
                'title': report['title'],
                'subtitle': report.get('subtitle', ''),
                'author': report['author'],
                'date': report.get('date'),
                'policy_area': report['policy_area'],
                'executive_summary': full_report.get('executive_summary', ''),
                'key_findings': full_report.get('key_findings', ''),
                'content_excerpt': content,
                'keywords': report.get('keywords', []),
                # Attribution
                'source': BERESOL_ATTRIBUTION['source'],
                'publisher': BERESOL_ATTRIBUTION['publisher'],
                'source_url': BERESOL_ATTRIBUTION['url'],
                'attribution_note': BERESOL_ATTRIBUTION['note']
            })

        # Search monitors (add as supplementary context)
        matching_monitors = self._search_monitors(query)

        for monitor in matching_monitors[:2]:
            results.append({
                'type': 'beresol_monitor',
                'id': monitor['id'],
                'name': monitor['name'],
                'description': monitor['description'],
                'policy_area': monitor['policy_area'],
                'keywords': monitor['keywords'],
                # Attribution
                'source': BERESOL_ATTRIBUTION['source'],
                'publisher': BERESOL_ATTRIBUTION['publisher'],
                'source_url': BERESOL_ATTRIBUTION['url'],
                'attribution_note': BERESOL_ATTRIBUTION['note']
            })

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get loader statistics."""
        return {
            **self.stats,
            'last_loaded': self.last_loaded.isoformat() if self.last_loaded else None,
            'bundle_dir': str(self.bundle_dir),
            'report_titles': [r['title'] for r in self.reports.values()],
            'monitor_names': [m['name'] for m in self.monitors.values()],
            'attribution': BERESOL_ATTRIBUTION
        }

    def reload(self) -> Dict[str, Any]:
        """Reload all content."""
        logger.info("Reloading Beresol knowledge bundle...")
        self.reports.clear()
        self.monitors.clear()
        return self.load_all()


# Global singleton
_beresol_loader: Optional[BeresolKnowledgeLoader] = None


def get_beresol_knowledge_loader(bundle_dir: str = None) -> BeresolKnowledgeLoader:
    """
    Get global Beresol knowledge loader instance.

    Args:
        bundle_dir: Path to brubru-knowledge-bundle directory

    Returns:
        BeresolKnowledgeLoader instance
    """
    global _beresol_loader

    if _beresol_loader is None:
        _beresol_loader = BeresolKnowledgeLoader(bundle_dir)
        _beresol_loader.load_all()

    return _beresol_loader
