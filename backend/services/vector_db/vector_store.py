"""
Vector Database Store

ChromaDB integration for semantic search over EU institutional data.
Part of Phase 13: AI Context Injection - Task 13.1

Collections:
- eu_legislation: EUR-Lex documents (full text + metadata)
- mep_profiles: MEP information (bio, committees, voting records)
- procedures: OEIL legislative procedures (timeline, status)
- terminology: IATE terms (24 languages)
- rss_entries: Recent EU news and updates
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import chromadb
from chromadb.utils import embedding_functions

from .hf_embedding_function import get_hf_embedding_function
from .hybrid_embedding_function import get_hybrid_embedding_function

logger = logging.getLogger(__name__)


class VectorStore:
    """
    Vector database for EU institutional data.

    Uses ChromaDB for local/persistent vector storage with:
    - Multiple collections for different data types
    - Metadata filtering (by date, institution, document type)
    - Relevance scoring (cosine similarity)
    - Batch operations for efficiency
    """

    # Collection names
    COLLECTION_LEGISLATION = "eu_legislation"
    COLLECTION_MEPS = "mep_profiles"
    COLLECTION_PROCEDURES = "procedures"
    COLLECTION_TERMINOLOGY = "terminology"
    COLLECTION_RSS = "rss_entries"
    COLLECTION_INTERNAL_KNOWLEDGE = "internal_knowledge"  # Templates, guides, reference
    COLLECTION_EPRS_PUBLICATIONS = "eprs_publications"  # Phase 2: EPRS Think Tank publications

    def __init__(
        self,
        persist_directory: str = "./chroma_db",
        embedding_function: Optional[Any] = None
    ):
        """
        Initialize vector store.

        Args:
            persist_directory: Directory for persistent storage
            embedding_function: Custom embedding function (if None, uses default)
        """
        self.persist_directory = persist_directory

        # Initialize ChromaDB client with persistence (new API)
        self.client = chromadb.PersistentClient(
            path=persist_directory
        )

        # Use provided embedding function or hybrid (OpenAI + HF) by default
        # Hybrid intelligently chooses: HF for EU content, OpenAI for general
        self.embedding_function = embedding_function or get_hybrid_embedding_function()

        # Initialize collections
        self.collections = {}
        self._init_collections()

        logger.info(f"Initialized VectorStore at {persist_directory}")

    def _init_collections(self):
        """Initialize all collections with metadata"""
        collection_configs = [
            {
                "name": self.COLLECTION_LEGISLATION,
                "metadata": {
                    "description": "EUR-Lex legislative documents",
                    "hnsw:space": "cosine",
                    "hnsw:construction_ef": 200,
                    "hnsw:M": 16
                }
            },
            {
                "name": self.COLLECTION_MEPS,
                "metadata": {
                    "description": "MEP profiles and voting records",
                    "hnsw:space": "cosine",
                    "hnsw:construction_ef": 200,
                    "hnsw:M": 16
                }
            },
            {
                "name": self.COLLECTION_PROCEDURES,
                "metadata": {
                    "description": "OEIL legislative procedures",
                    "hnsw:space": "cosine",
                    "hnsw:construction_ef": 200,
                    "hnsw:M": 16
                }
            },
            {
                "name": self.COLLECTION_TERMINOLOGY,
                "metadata": {
                    "description": "IATE terminology in 24 languages",
                    "hnsw:space": "cosine",
                    "hnsw:construction_ef": 200,
                    "hnsw:M": 16
                }
            },
            {
                "name": self.COLLECTION_RSS,
                "metadata": {
                    "description": "Recent EU news and updates",
                    "hnsw:space": "cosine",
                    "hnsw:construction_ef": 100,
                    "hnsw:M": 8
                }
            },
            {
                "name": self.COLLECTION_INTERNAL_KNOWLEDGE,
                "metadata": {
                    "description": "Internal knowledge base: templates, guides, reference materials",
                    "hnsw:space": "cosine",
                    "hnsw:construction_ef": 150,
                    "hnsw:M": 12
                }
            },
            {
                "name": self.COLLECTION_EPRS_PUBLICATIONS,
                "metadata": {
                    "description": "EPRS Think Tank publications (briefings, studies, analysis)",
                    "hnsw:space": "cosine",
                    "hnsw:construction_ef": 200,
                    "hnsw:M": 16
                }
            }
        ]

        for config in collection_configs:
            try:
                collection = self.client.get_or_create_collection(
                    name=config["name"],
                    metadata=config["metadata"],
                    embedding_function=self.embedding_function
                )
                self.collections[config["name"]] = collection
                logger.debug(f"Initialized collection: {config['name']}")
            except Exception as e:
                logger.error(f"Failed to initialize collection {config['name']}: {str(e)}")
                raise

        logger.info(f"Initialized {len(self.collections)} collections")

    # =========================================================================
    # Legislation Methods
    # =========================================================================

    def add_legislation(
        self,
        documents: List[Dict[str, Any]],
        embeddings: Optional[List[List[float]]] = None
    ) -> Dict[str, int]:
        """
        Add legislative documents to vector store.

        Args:
            documents: List of documents with:
                - id: Unique identifier (CELEX number)
                - text: Document text (full or chunked)
                - metadata: {
                    title: str,
                    celex: str,
                    document_type: str,
                    date: str (ISO format),
                    subjects: List[str],
                    chunk_index: int (if chunked),
                    total_chunks: int (if chunked)
                  }
            embeddings: Pre-computed embeddings (optional)

        Returns:
            Statistics dict with 'added' count
        """
        collection = self.collections[self.COLLECTION_LEGISLATION]

        ids = [doc["id"] for doc in documents]
        texts = [doc["text"] for doc in documents]
        metadatas = [self._serialize_metadata(doc.get("metadata", {})) for doc in documents]

        try:
            if embeddings:
                collection.add(
                    ids=ids,
                    documents=texts,
                    metadatas=metadatas,
                    embeddings=embeddings
                )
            else:
                collection.add(
                    ids=ids,
                    documents=texts,
                    metadatas=metadatas
                )

            logger.info(f"Added {len(documents)} legislative documents")
            return {"added": len(documents)}

        except Exception as e:
            logger.error(f"Failed to add legislation: {str(e)}")
            raise

    def query_legislation(
        self,
        query_texts: List[str],
        n_results: int = 5,
        document_type: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Query legislative documents.

        Args:
            query_texts: Query strings
            n_results: Number of results per query
            document_type: Filter by type (regulation, directive, etc.)
            date_from: Filter by date (ISO format)
            date_to: Filter by date (ISO format)

        Returns:
            Query results with documents, metadatas, distances
        """
        where = {}
        if document_type:
            where["document_type"] = document_type

        # Note: ChromaDB doesn't support range queries in where clause
        # Date filtering would need to be done post-query

        return self.query(
            self.COLLECTION_LEGISLATION,
            query_texts,
            n_results=n_results,
            where=where if where else None
        )

    # =========================================================================
    # MEP Profile Methods
    # =========================================================================

    def add_mep_profiles(
        self,
        profiles: List[Dict[str, Any]],
        embeddings: Optional[List[List[float]]] = None
    ) -> Dict[str, int]:
        """
        Add MEP profiles to vector store.

        Args:
            profiles: List of MEP profiles with:
                - id: MEP ID
                - text: Combined bio + committee info + voting record summary
                - metadata: {
                    name: str,
                    country: str,
                    political_group: str,
                    committees: List[str],
                    term_start: str,
                    term_end: str
                  }
            embeddings: Pre-computed embeddings (optional)

        Returns:
            Statistics dict
        """
        collection = self.collections[self.COLLECTION_MEPS]

        ids = [profile["id"] for profile in profiles]
        texts = [profile["text"] for profile in profiles]
        metadatas = [self._serialize_metadata(profile.get("metadata", {})) for profile in profiles]

        try:
            if embeddings:
                collection.add(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings)
            else:
                collection.add(ids=ids, documents=texts, metadatas=metadatas)

            logger.info(f"Added {len(profiles)} MEP profiles")
            return {"added": len(profiles)}

        except Exception as e:
            logger.error(f"Failed to add MEP profiles: {str(e)}")
            raise

    def query_meps(
        self,
        query_texts: List[str],
        n_results: int = 5,
        country: Optional[str] = None,
        political_group: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Query MEP profiles.

        Args:
            query_texts: Query strings
            n_results: Number of results
            country: Filter by country
            political_group: Filter by political group

        Returns:
            Query results
        """
        where = {}
        if country:
            where["country"] = country
        if political_group:
            where["political_group"] = political_group

        return self.query(
            self.COLLECTION_MEPS,
            query_texts,
            n_results=n_results,
            where=where if where else None
        )

    # =========================================================================
    # Procedure Methods
    # =========================================================================

    def add_procedures(
        self,
        procedures: List[Dict[str, Any]],
        embeddings: Optional[List[List[float]]] = None
    ) -> Dict[str, int]:
        """
        Add OEIL procedures to vector store.

        Args:
            procedures: List of procedures with:
                - id: Procedure reference (e.g., "2021/0106(COD)")
                - text: Title + summary + timeline events
                - metadata: {
                    reference: str,
                    title: str,
                    stage: str,
                    procedure_type: str,
                    committee: str,
                    rapporteur: str,
                    last_updated: str
                  }
            embeddings: Pre-computed embeddings (optional)

        Returns:
            Statistics dict
        """
        collection = self.collections[self.COLLECTION_PROCEDURES]

        ids = [proc["id"] for proc in procedures]
        texts = [proc["text"] for proc in procedures]
        metadatas = [self._serialize_metadata(proc.get("metadata", {})) for proc in procedures]

        try:
            if embeddings:
                collection.add(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings)
            else:
                collection.add(ids=ids, documents=texts, metadatas=metadatas)

            logger.info(f"Added {len(procedures)} procedures")
            return {"added": len(procedures)}

        except Exception as e:
            logger.error(f"Failed to add procedures: {str(e)}")
            raise

    def query_procedures(
        self,
        query_texts: List[str],
        n_results: int = 5,
        stage: Optional[str] = None
    ) -> Dict[str, Any]:
        """Query OEIL procedures"""
        where = {"stage": stage} if stage else None
        return self.query(self.COLLECTION_PROCEDURES, query_texts, n_results=n_results, where=where)

    # =========================================================================
    # Terminology Methods
    # =========================================================================

    def add_terminology(
        self,
        terms: List[Dict[str, Any]],
        embeddings: Optional[List[List[float]]] = None
    ) -> Dict[str, int]:
        """
        Add IATE terminology to vector store.

        Args:
            terms: List of terms with:
                - id: Entry ID
                - text: Term + definition + translations (all languages)
                - metadata: {
                    term: str,
                    domain: str,
                    reliability: str,
                    languages: List[str]
                  }
            embeddings: Pre-computed embeddings (optional)

        Returns:
            Statistics dict
        """
        collection = self.collections[self.COLLECTION_TERMINOLOGY]

        ids = [term["id"] for term in terms]
        texts = [term["text"] for term in terms]
        metadatas = [self._serialize_metadata(term.get("metadata", {})) for term in terms]

        try:
            if embeddings:
                collection.add(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings)
            else:
                collection.add(ids=ids, documents=texts, metadatas=metadatas)

            logger.info(f"Added {len(terms)} terminology entries")
            return {"added": len(terms)}

        except Exception as e:
            logger.error(f"Failed to add terminology: {str(e)}")
            raise

    def query_terminology(
        self,
        query_texts: List[str],
        n_results: int = 5,
        domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """Query IATE terminology"""
        where = {"domain": domain} if domain else None
        return self.query(self.COLLECTION_TERMINOLOGY, query_texts, n_results=n_results, where=where)

    # =========================================================================
    # RSS Entry Methods
    # =========================================================================

    def add_rss_entries(
        self,
        entries: List[Dict[str, Any]],
        embeddings: Optional[List[List[float]]] = None
    ) -> Dict[str, int]:
        """
        Add RSS entries to vector store.

        Args:
            entries: List of RSS entries with:
                - id: Entry ID
                - text: Title + summary + content
                - metadata: {
                    title: str,
                    source: str,
                    published: str (ISO format),
                    categories: List[str],
                    url: str
                  }
            embeddings: Pre-computed embeddings (optional)

        Returns:
            Statistics dict
        """
        collection = self.collections[self.COLLECTION_RSS]

        ids = [entry["id"] for entry in entries]
        texts = [entry["text"] for entry in entries]
        metadatas = [self._serialize_metadata(entry.get("metadata", {})) for entry in entries]

        try:
            if embeddings:
                collection.add(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings)
            else:
                collection.add(ids=ids, documents=texts, metadatas=metadatas)

            logger.info(f"Added {len(entries)} RSS entries")
            return {"added": len(entries)}

        except Exception as e:
            logger.error(f"Failed to add RSS entries: {str(e)}")
            raise

    def query_rss_entries(
        self,
        query_texts: List[str],
        n_results: int = 5,
        source: Optional[str] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Query RSS entries.

        Args:
            query_texts: Query strings
            n_results: Number of results
            source: Filter by source
            days: Only return entries from last N days

        Returns:
            Query results
        """
        where = {"source": source} if source else None
        # Note: Date filtering would be done post-query
        return self.query(self.COLLECTION_RSS, query_texts, n_results=n_results, where=where)

    # =========================================================================
    # Internal Knowledge Methods
    # =========================================================================

    def add_internal_knowledge(
        self,
        documents: List[Dict[str, Any]],
        embeddings: Optional[List[List[float]]] = None
    ) -> Dict[str, int]:
        """
        Add internal knowledge (templates, guides) to vector store.

        Args:
            documents: List of knowledge documents with:
                - id: Unique identifier (e.g., "template_briefing_note")
                - text: Document content
                - metadata: {
                    type: str (template, guide, reference),
                    name: str,
                    title: str,
                    category: str,
                    source: str
                  }
            embeddings: Pre-computed embeddings (optional)

        Returns:
            Statistics dict with 'added' count
        """
        collection = self.collections[self.COLLECTION_INTERNAL_KNOWLEDGE]

        ids = [doc["id"] for doc in documents]
        texts = [doc["text"] for doc in documents]
        metadatas = [self._serialize_metadata(doc.get("metadata", {})) for doc in documents]

        try:
            if embeddings:
                collection.add(
                    ids=ids,
                    documents=texts,
                    metadatas=metadatas,
                    embeddings=embeddings
                )
            else:
                collection.add(
                    ids=ids,
                    documents=texts,
                    metadatas=metadatas
                )

            logger.info(f"Added {len(documents)} internal knowledge documents")
            return {"added": len(documents)}

        except Exception as e:
            logger.error(f"Failed to add internal knowledge: {str(e)}")
            raise

    def query_internal_knowledge(
        self,
        query_texts: List[str],
        n_results: int = 5,
        knowledge_type: Optional[str] = None,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Query internal knowledge base.

        Args:
            query_texts: Query strings
            n_results: Number of results
            knowledge_type: Filter by type (template, guide, reference)
            category: Filter by category

        Returns:
            Query results
        """
        where = {}
        if knowledge_type:
            where["type"] = knowledge_type
        if category:
            where["category"] = category

        return self.query(
            self.COLLECTION_INTERNAL_KNOWLEDGE,
            query_texts,
            n_results=n_results,
            where=where if where else None
        )

    # =========================================================================
    # Generic Query Methods
    # =========================================================================

    def query(
        self,
        collection_name: str,
        query_texts: List[str],
        n_results: int = 5,
        where: Optional[Dict] = None,
        where_document: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Query a collection.

        Args:
            collection_name: Collection to query
            query_texts: Query strings
            n_results: Number of results per query
            where: Metadata filter (exact match)
            where_document: Document content filter

        Returns:
            Query results with:
                - ids: List of document IDs
                - documents: List of document texts
                - metadatas: List of metadata dicts
                - distances: List of similarity scores (lower = more similar)
        """
        if collection_name not in self.collections:
            raise ValueError(f"Unknown collection: {collection_name}")

        collection = self.collections[collection_name]

        try:
            results = collection.query(
                query_texts=query_texts,
                n_results=n_results,
                where=where,
                where_document=where_document
            )
            return results

        except Exception as e:
            logger.error(f"Query failed for {collection_name}: {str(e)}")
            raise

    # =========================================================================
    # Search Methods (with embeddings)
    # =========================================================================

    def search_legislation(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        where: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Search legislative documents using pre-computed embeddings.

        Args:
            query_embedding: Query embedding vector
            n_results: Number of results
            where: Metadata filter

        Returns:
            Search results
        """
        if self.COLLECTION_LEGISLATION not in self.collections:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        collection = self.collections[self.COLLECTION_LEGISLATION]

        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where
            )
            return results
        except Exception as e:
            logger.error(f"Search failed for legislation: {str(e)}")
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

    def search_mep_profiles(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        where: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Search MEP profiles using pre-computed embeddings."""
        if self.COLLECTION_MEPS not in self.collections:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        collection = self.collections[self.COLLECTION_MEPS]

        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where
            )
            return results
        except Exception as e:
            logger.error(f"Search failed for MEP profiles: {str(e)}")
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

    def search_procedures(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        where: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Search procedures using pre-computed embeddings."""
        if self.COLLECTION_PROCEDURES not in self.collections:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        collection = self.collections[self.COLLECTION_PROCEDURES]

        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where
            )
            return results
        except Exception as e:
            logger.error(f"Search failed for procedures: {str(e)}")
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

    def search_terminology(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        where: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Search terminology using pre-computed embeddings."""
        if self.COLLECTION_TERMINOLOGY not in self.collections:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        collection = self.collections[self.COLLECTION_TERMINOLOGY]

        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where
            )
            return results
        except Exception as e:
            logger.error(f"Search failed for terminology: {str(e)}")
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

    def search_rss_entries(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        where: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Search RSS entries using pre-computed embeddings."""
        if self.COLLECTION_RSS not in self.collections:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        collection = self.collections[self.COLLECTION_RSS]

        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where
            )
            return results
        except Exception as e:
            logger.error(f"Search failed for RSS entries: {str(e)}")
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

    def search_internal_knowledge(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        where: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Search internal knowledge using pre-computed embeddings."""
        if self.COLLECTION_INTERNAL_KNOWLEDGE not in self.collections:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        collection = self.collections[self.COLLECTION_INTERNAL_KNOWLEDGE]

        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where
            )
            return results
        except Exception as e:
            logger.error(f"Search failed for internal knowledge: {str(e)}")
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def _serialize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Serialize metadata for ChromaDB.

        ChromaDB only supports: str, int, float, bool
        Lists must be converted to comma-separated strings.
        """
        serialized = {}
        for key, value in metadata.items():
            if isinstance(value, list):
                # Convert list to comma-separated string
                serialized[key] = ",".join(str(v) for v in value)
            elif isinstance(value, (str, int, float, bool)):
                serialized[key] = value
            elif value is None:
                continue
            else:
                # Convert other types to string
                serialized[key] = str(value)
        return serialized

    def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """Get statistics for a collection"""
        if collection_name not in self.collections:
            raise ValueError(f"Unknown collection: {collection_name}")

        collection = self.collections[collection_name]

        return {
            "name": collection_name,
            "count": collection.count(),
            "metadata": collection.metadata
        }

    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all collections"""
        return {
            "total_collections": len(self.collections),
            "collections": {
                name: self.get_collection_stats(name)
                for name in self.collections.keys()
            },
            "persist_directory": self.persist_directory
        }

    def delete_by_ids(self, collection_name: str, ids: List[str]) -> Dict[str, int]:
        """Delete documents by IDs"""
        if collection_name not in self.collections:
            raise ValueError(f"Unknown collection: {collection_name}")

        collection = self.collections[collection_name]
        collection.delete(ids=ids)

        logger.info(f"Deleted {len(ids)} documents from {collection_name}")
        return {"deleted": len(ids)}

    def update_documents(
        self,
        collection_name: str,
        ids: List[str],
        documents: Optional[List[str]] = None,
        metadatas: Optional[List[Dict]] = None,
        embeddings: Optional[List[List[float]]] = None
    ) -> Dict[str, int]:
        """Update existing documents"""
        if collection_name not in self.collections:
            raise ValueError(f"Unknown collection: {collection_name}")

        collection = self.collections[collection_name]

        # Serialize metadatas if provided
        if metadatas:
            metadatas = [self._serialize_metadata(m) for m in metadatas]

        collection.update(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings
        )

        logger.info(f"Updated {len(ids)} documents in {collection_name}")
        return {"updated": len(ids)}

    def reset_collection(self, collection_name: str):
        """Reset a collection (delete all documents)"""
        if collection_name not in self.collections:
            raise ValueError(f"Unknown collection: {collection_name}")

        self.client.delete_collection(collection_name)
        self._init_collections()

        logger.warning(f"Reset collection: {collection_name}")

    def persist(self):
        """Persist vector store to disk"""
        self.client.persist()
        logger.info("Persisted vector store to disk")


# Global singleton
_vector_store: Optional[VectorStore] = None


def get_vector_store(persist_directory: str = "./chroma_db") -> VectorStore:
    """Get global vector store instance"""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore(persist_directory=persist_directory)
    return _vector_store
