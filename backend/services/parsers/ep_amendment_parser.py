"""
EP Amendment DOCX Parser

Parses European Parliament committee amendment documents (DOCX format)
into structured amendment records.

Document types supported:
- AM (Amendments tabled in committee): Individual MEP amendments
- PR (Committee draft report): Rapporteur's proposed changes

The EP DOCX format uses XML-like tags within paragraph text:
- <Amend>Amendment<NumAm>35</NumAm>  -- amendment block start
- <Members>Name</Members>             -- author
- <AuNomDe>{Group}on behalf of...</AuNomDe> -- political group
- <Article>Recital 8</Article>         -- element reference
- Or. <Original>{EN}en</Original>      -- original language
- <TitreJust>Justification</TitreJust> -- justification header
- </Amend>                             -- amendment block end

See docs/amendmenttraining.md for full specification.

Created: February 2026
"""

import io
import re
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from docx import Document
from docx.oxml.ns import qn

logger = logging.getLogger(__name__)

# EP political group aliases -> canonical codes
GROUP_ALIASES = {
    'epp': 'EPP', 'ppe': 'EPP',
    's&d': 'S&D', 'sd': 'S&D',
    'renew': 'Renew', 'renew europe': 'Renew',
    'ecr': 'ECR',
    'greens/efa': 'Greens/EFA', 'greens': 'Greens/EFA', 'verts/ale': 'Greens/EFA',
    'the left': 'The Left', 'gue/ngl': 'The Left',
    'pfe': 'PfE', 'id': 'PfE',
    'esn': 'ESN',
    'ni': 'NI',
}

# Regex patterns for the EP's XML-tagged paragraph format
RE_NUM_AM = re.compile(r'<NumAm>(\d+)</NumAm>')
RE_MEMBERS = re.compile(r'<Members>(.*?)</Members>')
RE_AU_NOM_DE = re.compile(r'<AuNomDe>\{([^}]*)\}(.*?)</AuNomDe>')
RE_ARTICLE = re.compile(r'<Article>(.*?)</Article>')
RE_ORIGINAL = re.compile(r'<Original>\{([^}]*)\}([^<]*)</Original>')
RE_TITRE_JUST = re.compile(r'<TitreJust>')
RE_AMEND_START = re.compile(r'<Amend>')
RE_AMEND_END = re.compile(r'</Amend>')

# Element reference detection for the <Article> tag content
RE_ELEMENT_PATTERNS = [
    (re.compile(r'^(Article\s+\d+(?:\s*[a-z])?(?:\s*\(\d+\))?)(.*)$', re.IGNORECASE), 'article'),
    (re.compile(r'^(Recital\s+\d+(?:\s*[a-z])?)(.*)$', re.IGNORECASE), 'recital'),
    (re.compile(r'^(Annex(?:\s+[IVXLC]+|\s+\d+)?)(.*)$', re.IGNORECASE), 'annex'),
    (re.compile(r'^(Citation\s+\d+)(.*)$', re.IGNORECASE), 'citation'),
    (re.compile(r'^(Title(?:\s+[IVXLC]+|\s+\d+)?)(.*)$', re.IGNORECASE), 'title'),
    (re.compile(r'^(Chapter\s+[IVXLC]+)(.*)$', re.IGNORECASE), 'chapter'),
    (re.compile(r'^(Paragraph\s+\d+)(.*)$', re.IGNORECASE), 'paragraph'),
]


@dataclass
class ParsedAmendment:
    """Structured output of a parsed amendment."""
    amendment_number: int
    authors: List[str] = field(default_factory=list)
    political_group: Optional[str] = None
    on_behalf_of_group: bool = False
    committee: str = ""
    procedure_reference: str = ""

    # What is being amended
    element_type: str = "unknown"
    element_number: str = ""
    element_reference_text: str = ""

    # Amendment content
    amendment_type: str = "modification"
    original_text: str = ""
    proposed_text: str = ""
    added_text_fragments: List[str] = field(default_factory=list)
    deleted_text_fragments: List[str] = field(default_factory=list)

    # Metadata
    original_language: str = "en"
    justification: Optional[str] = None
    pe_reference: str = ""
    source_page: Optional[int] = None
    parsing_confidence: float = 1.0


class EPAmendmentParser:
    """
    Parses EP committee amendment DOCX documents.

    The EP DOCX format embeds XML-like tags within the paragraph text
    (not standard Word styles). The parser detects these tags to identify
    amendment boundaries, authors, groups, and element references.
    """

    def parse_docx(
        self,
        docx_bytes: bytes,
        committee: str,
        pe_reference: str,
        procedure_ref: str,
        rapporteur_name: Optional[str] = None
    ) -> List[ParsedAmendment]:
        """
        Parse a DOCX amendment document into structured amendments.

        Args:
            docx_bytes: Raw DOCX file content
            committee: Committee code (e.g. "JURI")
            pe_reference: PE reference (e.g. "PE753.448")
            procedure_ref: Procedure reference (e.g. "2023/0089(COD)")
            rapporteur_name: For PR documents, the rapporteur's name

        Returns:
            List of ParsedAmendment objects
        """
        doc = Document(io.BytesIO(docx_bytes))
        amendments = []

        body_elements = list(doc.element.body)
        current: Optional[ParsedAmendment] = None
        in_justification = False

        for elem in body_elements:
            tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag

            if tag == 'p':
                text = self._get_paragraph_text(elem).strip()
                if not text:
                    continue

                # Check for amendment end marker
                if RE_AMEND_END.search(text):
                    if current:
                        amendments.append(current)
                        current = None
                    in_justification = False
                    continue

                # Check for amendment start with number
                num_match = RE_NUM_AM.search(text)
                if num_match and RE_AMEND_START.search(text):
                    # Finalise previous if not ended by </Amend>
                    if current:
                        amendments.append(current)

                    current = ParsedAmendment(
                        amendment_number=int(num_match.group(1)),
                        committee=committee,
                        pe_reference=pe_reference,
                        procedure_reference=procedure_ref,
                    )
                    in_justification = False
                    continue

                if not current:
                    continue

                # Check for author (Members tag)
                members_match = RE_MEMBERS.search(text)
                if members_match:
                    author_text = members_match.group(1).strip()
                    # Split multiple authors by comma
                    for name in re.split(r'\s*,\s*', author_text):
                        name = name.strip()
                        if name and name not in current.authors:
                            current.authors.append(name)
                    continue

                # Check for political group (AuNomDe tag)
                group_match = RE_AU_NOM_DE.search(text)
                if group_match:
                    group_code = group_match.group(1).strip()
                    current.political_group = self._normalise_group(group_code)
                    current.on_behalf_of_group = True
                    continue

                # Check for element reference (Article tag)
                article_match = RE_ARTICLE.search(text)
                if article_match:
                    ref_text = article_match.group(1).strip()
                    current.element_reference_text = ref_text
                    el_type, el_num = self._classify_element(ref_text)
                    current.element_type = el_type
                    current.element_number = el_num
                    continue

                # Check for original language
                orig_match = RE_ORIGINAL.search(text)
                if orig_match:
                    current.original_language = orig_match.group(1).strip().lower()
                    continue

                # Check for justification header
                if RE_TITRE_JUST.search(text):
                    in_justification = True
                    continue

                # Collect justification text
                if in_justification:
                    # Strip any remaining XML tags
                    clean = re.sub(r'<[^>]+>', '', text).strip()
                    if clean:
                        if current.justification:
                            current.justification += '\n' + clean
                        else:
                            current.justification = clean

            elif tag == 'tbl' and current:
                # Parse the amendment table (original vs proposed)
                self._parse_amendment_table(elem, current)

                # Determine amendment type from content
                current.amendment_type = self._classify_amendment_type(
                    current.original_text,
                    current.proposed_text
                )

        # Finalise last amendment
        if current:
            amendments.append(current)

        logger.info(
            f"[OK] Parsed {len(amendments)} amendments from {pe_reference} "
            f"({committee}, {procedure_ref})"
        )
        return amendments

    def _get_paragraph_text(self, p_elem) -> str:
        """Extract plain text from a paragraph XML element, preserving tag-like content."""
        texts = []
        for r in p_elem.iter(qn('w:r')):
            t = r.find(qn('w:t'))
            if t is not None and t.text:
                texts.append(t.text)
        return ''.join(texts)

    def _get_cell_text_with_formatting(self, cell_elem) -> Tuple[str, List[str], List[str]]:
        """
        Extract text from a table cell with formatting detection.

        Returns:
            (plain_text, added_fragments, deleted_fragments)
        """
        plain_parts = []
        added = []
        deleted = []

        for p in cell_elem.iter(qn('w:p')):
            p_texts = []
            for r in p.iter(qn('w:r')):
                t = r.find(qn('w:t'))
                if t is None or not t.text:
                    continue

                rpr = r.find(qn('w:rPr'))
                is_bold = False
                is_italic = False
                is_strike = False

                if rpr is not None:
                    b = rpr.find(qn('w:b'))
                    if b is not None:
                        val = b.get(qn('w:val'))
                        is_bold = val is None or val != '0'

                    i = rpr.find(qn('w:i'))
                    if i is not None:
                        val = i.get(qn('w:val'))
                        is_italic = val is None or val != '0'

                    strike = rpr.find(qn('w:strike'))
                    if strike is not None:
                        val = strike.get(qn('w:val'))
                        is_strike = val is None or val != '0'

                    dstrike = rpr.find(qn('w:dstrike'))
                    if dstrike is not None:
                        val = dstrike.get(qn('w:val'))
                        if val is None or val != '0':
                            is_strike = True

                text_content = t.text

                if is_strike:
                    deleted.append(text_content)
                elif is_bold and is_italic:
                    added.append(text_content)

                p_texts.append(text_content)

            if p_texts:
                plain_parts.append(''.join(p_texts))

        return '\n'.join(plain_parts), added, deleted

    def _parse_amendment_table(self, tbl_elem, amendment: ParsedAmendment) -> None:
        """Parse a two-column amendment table."""
        rows = list(tbl_elem.iter(qn('w:tr')))
        if not rows:
            amendment.parsing_confidence *= 0.5
            return

        # Skip header row if it contains "Text proposed" or "Amendment"
        start_idx = 0
        if rows:
            first_row_cells = list(rows[0].iter(qn('w:tc')))
            if first_row_cells:
                first_text = ''
                for r in first_row_cells[0].iter(qn('w:r')):
                    t = r.find(qn('w:t'))
                    if t is not None and t.text:
                        first_text += t.text
                if 'text proposed' in first_text.lower() or 'amendment' in first_text.lower():
                    start_idx = 1

        original_parts = []
        proposed_parts = []
        all_added = []
        all_deleted = []

        for row in rows[start_idx:]:
            cells = list(row.iter(qn('w:tc')))
            if len(cells) < 2:
                continue

            orig_text, _, orig_deleted = self._get_cell_text_with_formatting(cells[0])
            prop_text, prop_added, prop_deleted = self._get_cell_text_with_formatting(cells[1])

            if orig_text.strip():
                original_parts.append(orig_text.strip())
            if prop_text.strip():
                proposed_parts.append(prop_text.strip())

            all_added.extend(prop_added)
            all_deleted.extend(prop_deleted)

        amendment.original_text = '\n'.join(original_parts)
        amendment.proposed_text = '\n'.join(proposed_parts)
        amendment.added_text_fragments = all_added
        amendment.deleted_text_fragments = all_deleted

    def _classify_element(self, ref_text: str) -> Tuple[str, str]:
        """Classify element type and extract number from reference text."""
        for pattern, el_type in RE_ELEMENT_PATTERNS:
            match = pattern.match(ref_text.strip())
            if match:
                main_part = match.group(1).strip()
                number = re.sub(
                    r'^(?:Article|Recital|Annex|Citation|Title|Chapter|Paragraph)\s*',
                    '', main_part, flags=re.IGNORECASE
                ).strip()
                return el_type, number

        # Fallback: use the full text as reference
        return 'unknown', ref_text

    def _normalise_group(self, text: str) -> Optional[str]:
        """Normalise a political group name to its canonical code."""
        clean = text.strip().lower()
        clean = re.sub(r'\s*group\s*$', '', clean).strip()

        if clean in GROUP_ALIASES:
            return GROUP_ALIASES[clean]

        for alias, canonical in GROUP_ALIASES.items():
            if alias in clean or clean in alias:
                return canonical

        # Return original if no match (capitalised)
        return text.strip() if text.strip() else None

    def _classify_amendment_type(self, original: str, proposed: str) -> str:
        """Classify amendment type from the two-column content."""
        orig_clean = original.strip().lower()
        prop_clean = proposed.strip().lower()

        if orig_clean and (not prop_clean or prop_clean in ('deleted', 'suppressed', 'delete')):
            return 'suppression'

        if (not orig_clean or orig_clean in ('new', 'new text')) and prop_clean:
            return 'addition'

        return 'modification'
