"""
Data Transformer Service

Transforms data from various EU API formats to standardized JSON.
Part of Phase 6: Data Synchronization

Supported formats:
- RDF/XML (SPARQL results, Publications Office)
- XML (EUR-Lex, OEIL exports)
- CSV (TED notices, data exports)
- Akoma Ntoso XML (legislative documents)
- JSON-LD (Open Data Portal)
"""

import logging
import json
import csv
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from io import StringIO

logger = logging.getLogger(__name__)


class DataTransformer:
    """
    Data transformation service for EU API responses.

    Converts various data formats to standardized JSON structure
    for consistent processing across the application.
    """

    # XML namespaces commonly used in EU APIs
    NAMESPACES = {
        'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
        'dc': 'http://purl.org/dc/elements/1.1/',
        'dcterms': 'http://purl.org/dc/terms/',
        'skos': 'http://www.w3.org/2004/02/skos/core#',
        'cdm': 'http://publications.europa.eu/ontology/cdm#',
        'sparql': 'http://www.w3.org/2005/sparql-results#',
        'atom': 'http://www.w3.org/2005/Atom',
        'akn': 'http://docs.oasis-open.org/legaldocml/ns/akn/3.0'
    }

    def __init__(self):
        """Initialize data transformer"""
        logger.info("Initialized Data Transformer")

    def transform_rdf_xml(self, rdf_xml: str) -> List[Dict[str, Any]]:
        """
        Transform RDF/XML to JSON.

        Used for:
        - SPARQL query results from EUR-Lex, Publications Office
        - RDF metadata from European Parliament

        Args:
            rdf_xml: RDF/XML string

        Returns:
            List of transformed records
        """
        try:
            root = ET.fromstring(rdf_xml)

            results = []

            # Handle RDF descriptions
            for description in root.findall('.//rdf:Description', self.NAMESPACES):
                record = {}

                # Get resource URI
                resource = description.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about')
                if resource:
                    record['uri'] = resource

                # Extract all predicates
                for child in description:
                    tag_name = self._strip_namespace(child.tag)
                    value = child.text or child.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource')

                    if value:
                        if tag_name in record:
                            # Multiple values - convert to list
                            if not isinstance(record[tag_name], list):
                                record[tag_name] = [record[tag_name]]
                            record[tag_name].append(value)
                        else:
                            record[tag_name] = value

                if record:
                    results.append(record)

            logger.info(f"Transformed RDF/XML to {len(results)} records")
            return results

        except Exception as e:
            logger.error(f"Failed to transform RDF/XML: {str(e)}")
            return []

    def transform_sparql_results(self, sparql_xml: str) -> List[Dict[str, Any]]:
        """
        Transform SPARQL XML results to JSON.

        Used for:
        - EUR-Lex SPARQL endpoint
        - European Parliament SPARQL queries
        - Publications Office SPARQL API

        Args:
            sparql_xml: SPARQL results XML

        Returns:
            List of result bindings
        """
        try:
            root = ET.fromstring(sparql_xml)

            # Get variable names from header
            variables = []
            for var in root.findall('.//sparql:variable', self.NAMESPACES):
                variables.append(var.get('name'))

            # Parse results
            results = []
            for result in root.findall('.//sparql:result', self.NAMESPACES):
                record = {}

                for binding in result.findall('.//sparql:binding', self.NAMESPACES):
                    var_name = binding.get('name')

                    # Get value based on type
                    uri = binding.find('sparql:uri', self.NAMESPACES)
                    literal = binding.find('sparql:literal', self.NAMESPACES)
                    bnode = binding.find('sparql:bnode', self.NAMESPACES)

                    if uri is not None:
                        record[var_name] = {
                            'type': 'uri',
                            'value': uri.text
                        }
                    elif literal is not None:
                        record[var_name] = {
                            'type': 'literal',
                            'value': literal.text,
                            'lang': literal.get('{http://www.w3.org/XML/1998/namespace}lang'),
                            'datatype': literal.get('datatype')
                        }
                    elif bnode is not None:
                        record[var_name] = {
                            'type': 'bnode',
                            'value': bnode.text
                        }

                if record:
                    results.append(record)

            logger.info(f"Transformed SPARQL results: {len(results)} bindings")
            return results

        except Exception as e:
            logger.error(f"Failed to transform SPARQL results: {str(e)}")
            return []

    def transform_eurlex_xml(self, xml_data: str) -> Dict[str, Any]:
        """
        Transform EUR-Lex XML document to JSON.

        Used for:
        - Cellar API responses
        - EUR-Lex document exports

        Args:
            xml_data: EUR-Lex XML string

        Returns:
            Transformed document
        """
        try:
            root = ET.fromstring(xml_data)

            document = {
                'metadata': {},
                'content': {}
            }

            # Extract CELEX number
            celex = root.find('.//CELEX')
            if celex is not None:
                document['metadata']['celex'] = celex.text

            # Extract title
            title = root.find('.//TITLE')
            if title is not None:
                document['metadata']['title'] = title.text

            # Extract date
            date = root.find('.//DATE_DOCUMENT')
            if date is not None:
                document['metadata']['date'] = date.text

            # Extract subjects
            subjects = []
            for subject in root.findall('.//SUBJECT'):
                if subject.text:
                    subjects.append(subject.text)
            document['metadata']['subjects'] = subjects

            # Extract authors
            authors = []
            for author in root.findall('.//AUTHOR'):
                if author.text:
                    authors.append(author.text)
            document['metadata']['authors'] = authors

            # Extract text content
            text_content = root.find('.//TEXT')
            if text_content is not None:
                document['content']['text'] = ET.tostring(text_content, encoding='unicode', method='text')

            logger.info(f"Transformed EUR-Lex XML document: {document['metadata'].get('celex')}")
            return document

        except Exception as e:
            logger.error(f"Failed to transform EUR-Lex XML: {str(e)}")
            return {}

    def transform_akoma_ntoso(self, akn_xml: str) -> Dict[str, Any]:
        """
        Transform Akoma Ntoso XML to JSON.

        Used for:
        - EUR-Lex amendable documents
        - Legislative procedure documents

        Args:
            akn_xml: Akoma Ntoso XML string

        Returns:
            Structured document with sections
        """
        try:
            root = ET.fromstring(akn_xml)

            document = {
                'metadata': {},
                'content': {
                    'preface': [],
                    'body': [],
                    'conclusions': []
                }
            }

            # Extract metadata
            meta = root.find('.//akn:meta', self.NAMESPACES)
            if meta is not None:
                # Identification
                identification = meta.find('.//akn:identification', self.NAMESPACES)
                if identification is not None:
                    work = identification.find('.//akn:FRBRWork', self.NAMESPACES)
                    if work is not None:
                        uri = work.find('.//akn:FRBRuri', self.NAMESPACES)
                        if uri is not None:
                            document['metadata']['uri'] = uri.get('value')

                # Publication
                publication = meta.find('.//akn:publication', self.NAMESPACES)
                if publication is not None:
                    document['metadata']['publication_date'] = publication.get('date')

            # Extract structural elements
            body = root.find('.//akn:body', self.NAMESPACES)
            if body is not None:
                document['content']['body'] = self._parse_akn_hierarchy(body)

            logger.info("Transformed Akoma Ntoso document")
            return document

        except Exception as e:
            logger.error(f"Failed to transform Akoma Ntoso XML: {str(e)}")
            return {}

    def _parse_akn_hierarchy(self, element: ET.Element) -> List[Dict[str, Any]]:
        """Parse Akoma Ntoso hierarchical structure"""
        items = []

        for child in element:
            tag_name = self._strip_namespace(child.tag)

            if tag_name in ['article', 'section', 'chapter', 'part']:
                item = {
                    'type': tag_name,
                    'num': child.get('num'),
                    'heading': None,
                    'content': [],
                    'children': []
                }

                # Get heading
                heading = child.find('.//akn:heading', self.NAMESPACES)
                if heading is not None:
                    item['heading'] = heading.text

                # Get content
                content = child.find('.//akn:content', self.NAMESPACES)
                if content is not None:
                    item['content'] = [
                        {'type': 'paragraph', 'text': p.text}
                        for p in content.findall('.//akn:p', self.NAMESPACES)
                    ]

                # Recursively parse children
                item['children'] = self._parse_akn_hierarchy(child)

                items.append(item)

        return items

    def transform_csv_to_json(self, csv_data: str) -> List[Dict[str, Any]]:
        """
        Transform CSV to JSON.

        Used for:
        - TED procurement notices exports
        - Data catalogue downloads
        - Statistical data exports

        Args:
            csv_data: CSV string

        Returns:
            List of records
        """
        try:
            reader = csv.DictReader(StringIO(csv_data))
            records = [row for row in reader]

            logger.info(f"Transformed CSV to {len(records)} records")
            return records

        except Exception as e:
            logger.error(f"Failed to transform CSV: {str(e)}")
            return []

    def transform_oeil_xml(self, xml_data: str) -> Dict[str, Any]:
        """
        Transform OEIL XML export to JSON.

        Used for:
        - Legislative procedure exports
        - Procedure timeline data

        Args:
            xml_data: OEIL XML string

        Returns:
            Procedure data
        """
        try:
            root = ET.fromstring(xml_data)

            procedure = {
                'reference': None,
                'title': None,
                'type': None,
                'events': [],
                'documents': [],
                'committees': []
            }

            # Extract procedure reference
            ref = root.find('.//reference')
            if ref is not None:
                procedure['reference'] = ref.text

            # Extract title
            title = root.find('.//title')
            if title is not None:
                procedure['title'] = title.text

            # Extract events
            for event in root.findall('.//event'):
                event_data = {
                    'date': event.get('date'),
                    'type': event.get('type'),
                    'description': event.text
                }
                procedure['events'].append(event_data)

            # Sort events by date
            procedure['events'].sort(key=lambda x: x['date'] or '')

            logger.info(f"Transformed OEIL procedure: {procedure['reference']}")
            return procedure

        except Exception as e:
            logger.error(f"Failed to transform OEIL XML: {str(e)}")
            return {}

    def transform_json_ld(self, json_ld: Union[str, Dict]) -> Dict[str, Any]:
        """
        Transform JSON-LD to simplified JSON.

        Used for:
        - Open Data Portal datasets
        - Linked data from EU APIs

        Args:
            json_ld: JSON-LD string or dict

        Returns:
            Simplified JSON
        """
        try:
            if isinstance(json_ld, str):
                data = json.loads(json_ld)
            else:
                data = json_ld

            # Extract @graph if present
            if '@graph' in data:
                data = data['@graph']

            # Simplify structure by removing @context, @type prefixes
            simplified = self._simplify_json_ld(data)

            logger.info("Transformed JSON-LD")
            return simplified

        except Exception as e:
            logger.error(f"Failed to transform JSON-LD: {str(e)}")
            return {}

    def _simplify_json_ld(self, data: Any) -> Any:
        """Recursively simplify JSON-LD structure"""
        if isinstance(data, dict):
            simplified = {}
            for key, value in data.items():
                # Remove @ prefixes
                clean_key = key.lstrip('@').split(':')[-1]
                simplified[clean_key] = self._simplify_json_ld(value)
            return simplified
        elif isinstance(data, list):
            return [self._simplify_json_ld(item) for item in data]
        else:
            return data

    def transform_atom_feed(self, atom_xml: str) -> List[Dict[str, Any]]:
        """
        Transform Atom feed to JSON.

        Used for:
        - RSS/Atom feeds from various EU institutions

        Args:
            atom_xml: Atom XML string

        Returns:
            List of entries
        """
        try:
            root = ET.fromstring(atom_xml)

            entries = []
            for entry in root.findall('.//atom:entry', self.NAMESPACES):
                entry_data = {}

                # Title
                title = entry.find('atom:title', self.NAMESPACES)
                if title is not None:
                    entry_data['title'] = title.text

                # Link
                link = entry.find('atom:link', self.NAMESPACES)
                if link is not None:
                    entry_data['link'] = link.get('href')

                # Published date
                published = entry.find('atom:published', self.NAMESPACES)
                if published is not None:
                    entry_data['published'] = published.text

                # Summary
                summary = entry.find('atom:summary', self.NAMESPACES)
                if summary is not None:
                    entry_data['summary'] = summary.text

                # Content
                content = entry.find('atom:content', self.NAMESPACES)
                if content is not None:
                    entry_data['content'] = content.text

                # Author
                author = entry.find('atom:author/atom:name', self.NAMESPACES)
                if author is not None:
                    entry_data['author'] = author.text

                entries.append(entry_data)

            logger.info(f"Transformed Atom feed: {len(entries)} entries")
            return entries

        except Exception as e:
            logger.error(f"Failed to transform Atom feed: {str(e)}")
            return []

    def auto_detect_and_transform(self, data: Union[str, bytes, Dict]) -> Union[Dict, List]:
        """
        Auto-detect data format and transform to JSON.

        Args:
            data: Raw data in unknown format

        Returns:
            Transformed JSON data
        """
        # Convert bytes to string
        if isinstance(data, bytes):
            data = data.decode('utf-8')

        # Already JSON/dict
        if isinstance(data, dict):
            return data

        # Try to detect format
        data_str = str(data).strip()

        # Check for JSON
        if data_str.startswith('{') or data_str.startswith('['):
            try:
                return json.loads(data_str)
            except json.JSONDecodeError:
                pass

        # Check for XML
        if data_str.startswith('<?xml') or data_str.startswith('<'):
            # Detect XML type
            if 'sparql-results' in data_str:
                return self.transform_sparql_results(data_str)
            elif 'rdf:RDF' in data_str:
                return self.transform_rdf_xml(data_str)
            elif 'akomaNtoso' in data_str:
                return self.transform_akoma_ntoso(data_str)
            elif 'atom:feed' in data_str or '<feed' in data_str:
                return self.transform_atom_feed(data_str)
            else:
                # Generic XML to dict
                return self._xml_to_dict(ET.fromstring(data_str))

        # Check for CSV
        if ',' in data_str and '\n' in data_str:
            return self.transform_csv_to_json(data_str)

        # Unknown format
        logger.warning("Could not auto-detect data format")
        return {'raw_data': data_str}

    def _xml_to_dict(self, element: ET.Element) -> Dict[str, Any]:
        """Convert XML element to dictionary"""
        result = {}

        # Add attributes
        if element.attrib:
            result['@attributes'] = element.attrib

        # Add text
        if element.text and element.text.strip():
            result['text'] = element.text.strip()

        # Add children
        for child in element:
            tag = self._strip_namespace(child.tag)
            child_data = self._xml_to_dict(child)

            if tag in result:
                # Multiple children with same tag
                if not isinstance(result[tag], list):
                    result[tag] = [result[tag]]
                result[tag].append(child_data)
            else:
                result[tag] = child_data

        return result

    def _strip_namespace(self, tag: str) -> str:
        """Remove XML namespace from tag"""
        if '}' in tag:
            return tag.split('}')[1]
        return tag

    def normalize_date_format(self, date_str: str) -> Optional[str]:
        """
        Normalize various date formats to ISO 8601.

        Args:
            date_str: Date string in various formats

        Returns:
            ISO 8601 date string or None
        """
        if not date_str:
            return None

        # Common EU date formats
        formats = [
            '%Y-%m-%d',
            '%d/%m/%Y',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%d %H:%M:%S',
            '%d.%m.%Y',
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.isoformat()
            except ValueError:
                continue

        logger.warning(f"Could not parse date: {date_str}")
        return None
