"""
Document Indexer

Indexes EU documents into vector database for semantic search.
Part of Phase 13: AI Context Injection - Task 13.2

Indexes:
- EUR-Lex legislation (full text + metadata)
- MEP profiles (bio, committees, voting records)
- OEIL procedures (timeline, status, documents)
- IATE terminology (24 languages)
- RSS feed entries (for incremental updates)
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime
from dataclasses import dataclass

from services.vector_db.vector_store import VectorStore, get_vector_store
from services.embeddings.embedding_service import EmbeddingService, get_embedding_service
from .metadata_extractor import MetadataExtractor, get_metadata_extractor

logger = logging.getLogger(__name__)


@dataclass
class IndexingResult:
    """Result of indexing operation"""
    success: int
    failed: int
    skipped: int
    total_processed: int
    errors: List[Dict[str, str]]
    duration_seconds: float


class DocumentIndexer:
    """
    Index EU documents into vector database.

    Features:
    - Batch processing for efficiency
    - Automatic chunking for long documents
    - Metadata extraction and enrichment
    - Incremental updates from RSS feeds
    - Duplicate detection and skipping
    - Progress tracking and error reporting
    """

    def __init__(
        self,
        vector_store: VectorStore,
        embeddings_service: EmbeddingService,
        metadata_extractor: MetadataExtractor,
        batch_size: int = 50
    ):
        """
        Initialize document indexer.

        Args:
            vector_store: Vector database instance
            embeddings_service: Embeddings generation service
            metadata_extractor: Metadata extraction service
            batch_size: Number of documents to process in each batch
        """
        self.vector_store = vector_store
        self.embeddings_service = embeddings_service
        self.metadata_extractor = metadata_extractor
        self.batch_size = batch_size

        logger.info(f"Initialized DocumentIndexer (batch_size={batch_size})")

    async def index_legislation(
        self,
        documents: List[Dict[str, Any]],
        force_reindex: bool = False
    ) -> IndexingResult:
        """
        Index EUR-Lex legislation documents.

        Args:
            documents: List of legislation documents with fields:
                - celex: CELEX number (e.g., '32016R0679')
                - title: Document title
                - text: Full document text
                - date: Publication date
                - type: Document type (Regulation, Directive, etc.)
                - url: EUR-Lex URL
            force_reindex: If True, reindex even if already exists

        Returns:
            IndexingResult with success/failure stats
        """
        start_time = datetime.now()
        success_count = 0
        failed_count = 0
        skipped_count = 0
        errors = []

        logger.info(f"Indexing {len(documents)} legislation documents")

        # Check for existing documents
        if not force_reindex:
            existing_ids = self._get_existing_ids(
                [doc.get('celex', doc.get('id', '')) for doc in documents],
                VectorStore.COLLECTION_LEGISLATION
            )
            logger.info(f"Found {len(existing_ids)} existing documents")
        else:
            existing_ids = set()

        # Process in batches
        for i in range(0, len(documents), self.batch_size):
            batch = documents[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (len(documents) + self.batch_size - 1) // self.batch_size

            logger.info(f"Processing batch {batch_num}/{total_batches}")

            try:
                result = await self._process_legislation_batch(
                    batch,
                    existing_ids,
                    force_reindex
                )

                success_count += result['success']
                failed_count += result['failed']
                skipped_count += result['skipped']
                errors.extend(result['errors'])

            except Exception as e:
                logger.error(f"Batch {batch_num} failed: {str(e)}")
                failed_count += len(batch)
                errors.append({
                    'batch': batch_num,
                    'error': str(e)
                })

        duration = (datetime.now() - start_time).total_seconds()

        logger.info(
            f"Legislation indexing complete: "
            f"{success_count} success, {failed_count} failed, {skipped_count} skipped "
            f"in {duration:.2f}s"
        )

        return IndexingResult(
            success=success_count,
            failed=failed_count,
            skipped=skipped_count,
            total_processed=len(documents),
            errors=errors,
            duration_seconds=duration
        )

    async def _process_legislation_batch(
        self,
        batch: List[Dict[str, Any]],
        existing_ids: Set[str],
        force_reindex: bool
    ) -> Dict[str, Any]:
        """Process a batch of legislation documents"""
        success = 0
        failed = 0
        skipped = 0
        errors = []

        # Prepare documents for indexing
        documents_to_index = []
        chunk_documents = []

        for doc in batch:
            doc_id = doc.get('celex', doc.get('id', ''))

            if not doc_id:
                failed += 1
                errors.append({'id': 'unknown', 'error': 'Missing CELEX/ID'})
                continue

            # Skip if already indexed
            if not force_reindex and doc_id in existing_ids:
                skipped += 1
                continue

            try:
                # Extract metadata
                text = doc.get('text', '')
                if not text:
                    text = doc.get('title', '') + '\n' + doc.get('summary', '')

                enhanced_metadata = self.metadata_extractor.extract_metadata_for_legislation({
                    'text': text,
                    'metadata': {
                        'celex': doc_id,
                        'title': doc.get('title', ''),
                        'date': doc.get('date', ''),
                        'type': doc.get('type', ''),
                        'url': doc.get('url', ''),
                        'subjects': doc.get('subjects', []),
                        'author': doc.get('author', ''),
                        'in_force': doc.get('in_force', True)
                    }
                })

                # Create chunks for long documents
                doc_chunks = await self.embeddings_service.embed_document_with_chunks(
                    document_text=text,
                    document_id=doc_id,
                    metadata=enhanced_metadata
                )

                chunk_documents.extend(doc_chunks)

            except Exception as e:
                logger.error(f"Failed to process document {doc_id}: {str(e)}")
                failed += 1
                errors.append({'id': doc_id, 'error': str(e)})

        # Add to vector store
        if chunk_documents:
            try:
                self.vector_store.add_legislation(
                    documents=chunk_documents,
                    embeddings=[doc['embedding'] for doc in chunk_documents]
                )
                success = len(set(doc['metadata']['document_id'] for doc in chunk_documents))
                logger.info(f"Indexed {success} documents ({len(chunk_documents)} chunks)")

            except Exception as e:
                logger.error(f"Failed to add documents to vector store: {str(e)}")
                failed = len(chunk_documents)
                errors.append({'batch': 'vector_store', 'error': str(e)})

        return {
            'success': success,
            'failed': failed,
            'skipped': skipped,
            'errors': errors
        }

    async def index_mep_profiles(
        self,
        profiles: List[Dict[str, Any]],
        force_reindex: bool = False
    ) -> IndexingResult:
        """
        Index MEP profiles.

        Args:
            profiles: List of MEP profiles with fields:
                - id: MEP ID
                - name: Full name
                - bio: Biography text
                - committees: List of committees
                - voting_records: Voting history
                - country: Country represented
                - party: Political party
                - group: Political group
                - url: Profile URL
            force_reindex: If True, reindex even if already exists

        Returns:
            IndexingResult with success/failure stats
        """
        start_time = datetime.now()
        success_count = 0
        failed_count = 0
        skipped_count = 0
        errors = []

        logger.info(f"Indexing {len(profiles)} MEP profiles")

        # Check for existing profiles
        if not force_reindex:
            existing_ids = self._get_existing_ids(
                [profile.get('id', '') for profile in profiles],
                VectorStore.COLLECTION_MEPS
            )
        else:
            existing_ids = set()

        # Process in batches
        for i in range(0, len(profiles), self.batch_size):
            batch = profiles[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (len(profiles) + self.batch_size - 1) // self.batch_size

            logger.info(f"Processing batch {batch_num}/{total_batches}")

            try:
                result = await self._process_mep_batch(batch, existing_ids, force_reindex)
                success_count += result['success']
                failed_count += result['failed']
                skipped_count += result['skipped']
                errors.extend(result['errors'])

            except Exception as e:
                logger.error(f"Batch {batch_num} failed: {str(e)}")
                failed_count += len(batch)
                errors.append({'batch': batch_num, 'error': str(e)})

        duration = (datetime.now() - start_time).total_seconds()

        logger.info(
            f"MEP indexing complete: "
            f"{success_count} success, {failed_count} failed, {skipped_count} skipped "
            f"in {duration:.2f}s"
        )

        return IndexingResult(
            success=success_count,
            failed=failed_count,
            skipped=skipped_count,
            total_processed=len(profiles),
            errors=errors,
            duration_seconds=duration
        )

    async def _process_mep_batch(
        self,
        batch: List[Dict[str, Any]],
        existing_ids: Set[str],
        force_reindex: bool
    ) -> Dict[str, Any]:
        """Process a batch of MEP profiles"""
        success = 0
        failed = 0
        skipped = 0
        errors = []

        documents_to_index = []
        texts_to_embed = []

        for profile in batch:
            mep_id = profile.get('id', '')

            if not mep_id:
                failed += 1
                errors.append({'id': 'unknown', 'error': 'Missing MEP ID'})
                continue

            # Skip if already indexed
            if not force_reindex and mep_id in existing_ids:
                skipped += 1
                continue

            try:
                # Build searchable text from profile
                text_parts = [
                    f"MEP: {profile.get('name', '')}",
                    f"Country: {profile.get('country', '')}",
                    f"Party: {profile.get('party', '')}",
                    f"Group: {profile.get('group', '')}",
                    profile.get('bio', ''),
                    f"Committees: {', '.join(profile.get('committees', []))}",
                ]

                # Add voting records summary
                voting_records = profile.get('voting_records', [])
                if voting_records:
                    text_parts.append(f"Recent votes: {len(voting_records)} recorded")

                text = '\n'.join(filter(None, text_parts))

                # Extract metadata
                enhanced_metadata = self.metadata_extractor.extract_metadata_for_mep({
                    'text': text,
                    'metadata': {
                        'mep_id': mep_id,
                        'name': profile.get('name', ''),
                        'country': profile.get('country', ''),
                        'party': profile.get('party', ''),
                        'group': profile.get('group', ''),
                        'url': profile.get('url', ''),
                        'committees': profile.get('committees', []),
                        'active': profile.get('active', True)
                    }
                })

                documents_to_index.append({
                    'id': mep_id,
                    'text': text,
                    'metadata': enhanced_metadata
                })
                texts_to_embed.append(text)

            except Exception as e:
                logger.error(f"Failed to process MEP {mep_id}: {str(e)}")
                failed += 1
                errors.append({'id': mep_id, 'error': str(e)})

        # Generate embeddings in batch
        if texts_to_embed:
            try:
                embeddings = await self.embeddings_service.generate_batch_embeddings(texts_to_embed)

                # Add to vector store
                self.vector_store.add_mep_profiles(
                    documents=documents_to_index,
                    embeddings=embeddings
                )

                success = len(documents_to_index)
                logger.info(f"Indexed {success} MEP profiles")

            except Exception as e:
                logger.error(f"Failed to add MEPs to vector store: {str(e)}")
                failed = len(documents_to_index)
                errors.append({'batch': 'vector_store', 'error': str(e)})

        return {
            'success': success,
            'failed': failed,
            'skipped': skipped,
            'errors': errors
        }

    async def index_procedures(
        self,
        procedures: List[Dict[str, Any]],
        force_reindex: bool = False
    ) -> IndexingResult:
        """
        Index OEIL legislative procedures.

        Args:
            procedures: List of OEIL procedures with fields:
                - reference: Procedure reference (e.g., '2021/0106(COD)')
                - title: Procedure title
                - type: Procedure type
                - status: Current status
                - date: Start date
                - timeline: List of events
                - documents: Related documents
                - committees: Involved committees
                - url: OEIL URL
            force_reindex: If True, reindex even if already exists

        Returns:
            IndexingResult with success/failure stats
        """
        start_time = datetime.now()
        success_count = 0
        failed_count = 0
        skipped_count = 0
        errors = []

        logger.info(f"Indexing {len(procedures)} OEIL procedures")

        # Check for existing procedures
        if not force_reindex:
            existing_ids = self._get_existing_ids(
                [proc.get('reference', proc.get('id', '')) for proc in procedures],
                VectorStore.COLLECTION_PROCEDURES
            )
        else:
            existing_ids = set()

        # Process in batches
        for i in range(0, len(procedures), self.batch_size):
            batch = procedures[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (len(procedures) + self.batch_size - 1) // self.batch_size

            logger.info(f"Processing batch {batch_num}/{total_batches}")

            try:
                result = await self._process_procedure_batch(batch, existing_ids, force_reindex)
                success_count += result['success']
                failed_count += result['failed']
                skipped_count += result['skipped']
                errors.extend(result['errors'])

            except Exception as e:
                logger.error(f"Batch {batch_num} failed: {str(e)}")
                failed_count += len(batch)
                errors.append({'batch': batch_num, 'error': str(e)})

        duration = (datetime.now() - start_time).total_seconds()

        logger.info(
            f"Procedure indexing complete: "
            f"{success_count} success, {failed_count} failed, {skipped_count} skipped "
            f"in {duration:.2f}s"
        )

        return IndexingResult(
            success=success_count,
            failed=failed_count,
            skipped=skipped_count,
            total_processed=len(procedures),
            errors=errors,
            duration_seconds=duration
        )

    async def _process_procedure_batch(
        self,
        batch: List[Dict[str, Any]],
        existing_ids: Set[str],
        force_reindex: bool
    ) -> Dict[str, Any]:
        """Process a batch of OEIL procedures"""
        success = 0
        failed = 0
        skipped = 0
        errors = []

        documents_to_index = []
        texts_to_embed = []

        for procedure in batch:
            proc_ref = procedure.get('reference', procedure.get('id', ''))

            if not proc_ref:
                failed += 1
                errors.append({'id': 'unknown', 'error': 'Missing procedure reference'})
                continue

            # Skip if already indexed
            if not force_reindex and proc_ref in existing_ids:
                skipped += 1
                continue

            try:
                # Build searchable text
                text_parts = [
                    f"Procedure: {proc_ref}",
                    f"Title: {procedure.get('title', '')}",
                    f"Type: {procedure.get('type', '')}",
                    f"Status: {procedure.get('status', '')}",
                ]

                # Add timeline
                timeline = procedure.get('timeline', [])
                if timeline:
                    text_parts.append("\nTimeline:")
                    for event in timeline[:10]:  # Last 10 events
                        date = event.get('date', '')
                        description = event.get('description', '')
                        text_parts.append(f"- {date}: {description}")

                # Add committees
                committees = procedure.get('committees', [])
                if committees:
                    text_parts.append(f"\nCommittees: {', '.join(committees)}")

                text = '\n'.join(filter(None, text_parts))

                # Extract metadata
                enhanced_metadata = self.metadata_extractor.extract_metadata_for_procedure({
                    'text': text,
                    'metadata': {
                        'procedure_reference': proc_ref,
                        'title': procedure.get('title', ''),
                        'type': procedure.get('type', ''),
                        'status': procedure.get('status', ''),
                        'date': procedure.get('date', ''),
                        'url': procedure.get('url', ''),
                        'committees': committees,
                        'documents': procedure.get('documents', [])
                    }
                })

                documents_to_index.append({
                    'id': proc_ref,
                    'text': text,
                    'metadata': enhanced_metadata
                })
                texts_to_embed.append(text)

            except Exception as e:
                logger.error(f"Failed to process procedure {proc_ref}: {str(e)}")
                failed += 1
                errors.append({'id': proc_ref, 'error': str(e)})

        # Generate embeddings and index
        if texts_to_embed:
            try:
                embeddings = await self.embeddings_service.generate_batch_embeddings(texts_to_embed)

                self.vector_store.add_procedures(
                    documents=documents_to_index,
                    embeddings=embeddings
                )

                success = len(documents_to_index)
                logger.info(f"Indexed {success} procedures")

            except Exception as e:
                logger.error(f"Failed to add procedures to vector store: {str(e)}")
                failed = len(documents_to_index)
                errors.append({'batch': 'vector_store', 'error': str(e)})

        return {
            'success': success,
            'failed': failed,
            'skipped': skipped,
            'errors': errors
        }

    async def index_terminology(
        self,
        terms: List[Dict[str, Any]],
        force_reindex: bool = False
    ) -> IndexingResult:
        """
        Index IATE terminology.

        Args:
            terms: List of IATE terms with fields:
                - term_id: IATE term ID
                - term: Term in different languages (dict: {lang: term})
                - definition: Definition in different languages
                - domain: Subject domain
                - subdomain: Subject subdomain
                - url: IATE URL
            force_reindex: If True, reindex even if already exists

        Returns:
            IndexingResult with success/failure stats
        """
        start_time = datetime.now()
        success_count = 0
        failed_count = 0
        skipped_count = 0
        errors = []

        logger.info(f"Indexing {len(terms)} IATE terms")

        # Check for existing terms
        if not force_reindex:
            existing_ids = self._get_existing_ids(
                [term.get('term_id', term.get('id', '')) for term in terms],
                VectorStore.COLLECTION_TERMINOLOGY
            )
        else:
            existing_ids = set()

        # Process in batches
        for i in range(0, len(terms), self.batch_size):
            batch = terms[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (len(terms) + self.batch_size - 1) // self.batch_size

            logger.info(f"Processing batch {batch_num}/{total_batches}")

            try:
                result = await self._process_terminology_batch(batch, existing_ids, force_reindex)
                success_count += result['success']
                failed_count += result['failed']
                skipped_count += result['skipped']
                errors.extend(result['errors'])

            except Exception as e:
                logger.error(f"Batch {batch_num} failed: {str(e)}")
                failed_count += len(batch)
                errors.append({'batch': batch_num, 'error': str(e)})

        duration = (datetime.now() - start_time).total_seconds()

        logger.info(
            f"Terminology indexing complete: "
            f"{success_count} success, {failed_count} failed, {skipped_count} skipped "
            f"in {duration:.2f}s"
        )

        return IndexingResult(
            success=success_count,
            failed=failed_count,
            skipped=skipped_count,
            total_processed=len(terms),
            errors=errors,
            duration_seconds=duration
        )

    async def _process_terminology_batch(
        self,
        batch: List[Dict[str, Any]],
        existing_ids: Set[str],
        force_reindex: bool
    ) -> Dict[str, Any]:
        """Process a batch of IATE terminology"""
        success = 0
        failed = 0
        skipped = 0
        errors = []

        documents_to_index = []
        texts_to_embed = []

        for term_entry in batch:
            term_id = term_entry.get('term_id', term_entry.get('id', ''))

            if not term_id:
                failed += 1
                errors.append({'id': 'unknown', 'error': 'Missing term ID'})
                continue

            # Skip if already indexed
            if not force_reindex and term_id in existing_ids:
                skipped += 1
                continue

            try:
                # Build multilingual searchable text
                text_parts = []

                # Add terms in all languages
                terms = term_entry.get('term', {})
                if isinstance(terms, dict):
                    for lang, term_text in terms.items():
                        text_parts.append(f"[{lang.upper()}] {term_text}")
                else:
                    text_parts.append(str(terms))

                # Add definitions
                definitions = term_entry.get('definition', {})
                if isinstance(definitions, dict):
                    for lang, def_text in definitions.items():
                        text_parts.append(f"Definition ({lang}): {def_text}")
                else:
                    text_parts.append(str(definitions))

                # Add domain info
                domain = term_entry.get('domain', '')
                subdomain = term_entry.get('subdomain', '')
                if domain:
                    text_parts.append(f"Domain: {domain}")
                if subdomain:
                    text_parts.append(f"Subdomain: {subdomain}")

                text = '\n'.join(filter(None, text_parts))

                metadata = {
                    'term_id': term_id,
                    'domain': domain,
                    'subdomain': subdomain,
                    'url': term_entry.get('url', ''),
                    'languages': list(terms.keys()) if isinstance(terms, dict) else []
                }

                documents_to_index.append({
                    'id': term_id,
                    'text': text,
                    'metadata': metadata
                })
                texts_to_embed.append(text)

            except Exception as e:
                logger.error(f"Failed to process term {term_id}: {str(e)}")
                failed += 1
                errors.append({'id': term_id, 'error': str(e)})

        # Generate embeddings and index
        if texts_to_embed:
            try:
                embeddings = await self.embeddings_service.generate_batch_embeddings(texts_to_embed)

                self.vector_store.add_terminology(
                    documents=documents_to_index,
                    embeddings=embeddings
                )

                success = len(documents_to_index)
                logger.info(f"Indexed {success} terminology entries")

            except Exception as e:
                logger.error(f"Failed to add terminology to vector store: {str(e)}")
                failed = len(documents_to_index)
                errors.append({'batch': 'vector_store', 'error': str(e)})

        return {
            'success': success,
            'failed': failed,
            'skipped': skipped,
            'errors': errors
        }

    async def index_rss_entry(
        self,
        entry: Dict[str, Any]
    ) -> bool:
        """
        Index single RSS feed entry (for incremental updates).

        Args:
            entry: RSS entry with fields:
                - id: Entry ID (usually GUID)
                - title: Entry title
                - summary: Entry summary/description
                - link: URL to full content
                - published: Publication date
                - source: RSS feed source
                - categories: Categories/tags

        Returns:
            True if successfully indexed, False otherwise
        """
        try:
            entry_id = entry.get('id', entry.get('guid', ''))
            if not entry_id:
                logger.warning("RSS entry missing ID, skipping")
                return False

            # Build searchable text
            text = '\n'.join([
                f"Title: {entry.get('title', '')}",
                f"Summary: {entry.get('summary', '')}",
                f"Source: {entry.get('source', '')}",
                f"Categories: {', '.join(entry.get('categories', []))}"
            ])

            # Generate embedding
            embedding = await self.embeddings_service.generate_embedding(text)

            # Prepare metadata
            metadata = {
                'entry_id': entry_id,
                'title': entry.get('title', ''),
                'link': entry.get('link', ''),
                'published': entry.get('published', ''),
                'source': entry.get('source', ''),
                'categories': entry.get('categories', [])
            }

            # Add to vector store
            self.vector_store.add_rss_entries(
                documents=[{
                    'id': entry_id,
                    'text': text,
                    'metadata': metadata
                }],
                embeddings=[embedding]
            )

            logger.info(f"Indexed RSS entry: {entry_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to index RSS entry: {str(e)}")
            return False

    def _get_existing_ids(
        self,
        ids: List[str],
        collection_name: str
    ) -> Set[str]:
        """
        Check which IDs already exist in vector store.

        Args:
            ids: List of IDs to check
            collection_name: Collection to check in

        Returns:
            Set of existing IDs
        """
        try:
            collection = self.vector_store.collections[collection_name]
            existing = collection.get(ids=ids, include=[])
            return set(existing['ids'])
        except Exception as e:
            logger.warning(f"Failed to check existing IDs: {str(e)}")
            return set()

    async def get_indexing_stats(self) -> Dict[str, Any]:
        """
        Get statistics about indexed documents.

        Returns:
            Statistics dict with counts per collection
        """
        stats = {}

        for collection_name, collection in self.vector_store.collections.items():
            try:
                count = collection.count()
                stats[collection_name] = {
                    'count': count,
                    'name': collection_name
                }
            except Exception as e:
                logger.error(f"Failed to get stats for {collection_name}: {str(e)}")
                stats[collection_name] = {
                    'count': 0,
                    'error': str(e)
                }

        return stats

    async def reindex_all(
        self,
        legislation: Optional[List[Dict[str, Any]]] = None,
        meps: Optional[List[Dict[str, Any]]] = None,
        procedures: Optional[List[Dict[str, Any]]] = None,
        terminology: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, IndexingResult]:
        """
        Reindex all documents (full rebuild).

        Args:
            legislation: Legislation documents
            meps: MEP profiles
            procedures: OEIL procedures
            terminology: IATE terminology

        Returns:
            Dict mapping collection name to IndexingResult
        """
        results = {}

        logger.info("Starting full reindex of all collections")

        if legislation:
            results['legislation'] = await self.index_legislation(legislation, force_reindex=True)

        if meps:
            results['meps'] = await self.index_mep_profiles(meps, force_reindex=True)

        if procedures:
            results['procedures'] = await self.index_procedures(procedures, force_reindex=True)

        if terminology:
            results['terminology'] = await self.index_terminology(terminology, force_reindex=True)

        logger.info("Full reindex complete")
        return results


# Global singleton
_document_indexer: Optional[DocumentIndexer] = None


def get_document_indexer(
    vector_store: Optional[VectorStore] = None,
    embeddings_service: Optional[EmbeddingService] = None,
    metadata_extractor: Optional[MetadataExtractor] = None,
    batch_size: int = 50
) -> DocumentIndexer:
    """
    Get global document indexer instance.

    Args:
        vector_store: Vector store instance (default: global singleton)
        embeddings_service: Embeddings service (default: global singleton)
        metadata_extractor: Metadata extractor (default: global singleton)
        batch_size: Batch size for processing

    Returns:
        DocumentIndexer instance
    """
    global _document_indexer

    if _document_indexer is None:
        _document_indexer = DocumentIndexer(
            vector_store=vector_store or get_vector_store(),
            embeddings_service=embeddings_service or get_embedding_service(),
            metadata_extractor=metadata_extractor or get_metadata_extractor(),
            batch_size=batch_size
        )

    return _document_indexer
