"""
Tender Vector Database Service

ChromaDB collection for semantic search over EU tenders.
Uses BGE-M3 embeddings for multilingual support (24 EU languages).

Features:
- Index tender titles and descriptions
- Metadata filtering (country, CPV, value range, deadline)
- Semantic similarity search
- Multilingual query support
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import json

import chromadb
from chromadb.config import Settings

from ..vector_db.hf_embedding_function import get_hf_embedding_function

logger = logging.getLogger(__name__)


# Collection name
TENDER_COLLECTION = "eu_tenders"

# Embedding model (multilingual)
EMBEDDING_MODEL = "BAAI/bge-m3"


class TenderVectorDB:
    """
    Vector database service for tender semantic search.

    Uses ChromaDB with BGE-M3 embeddings for:
    - Multilingual semantic search (all 24 EU languages)
    - Metadata filtering (country, CPV, value, deadline)
    - Similar tender discovery
    """

    def __init__(
        self,
        persist_directory: str = "backend/data/chroma_tenders",
        collection_name: str = TENDER_COLLECTION
    ):
        """
        Initialize the vector database.

        Args:
            persist_directory: Directory for persistent storage
            collection_name: Name of the collection
        """
        self.persist_directory = persist_directory
        self.collection_name = collection_name

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        # Get or create collection with embedding function
        self.embedding_fn = get_hf_embedding_function()
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_fn,
            metadata={"description": "EU public procurement tenders"}
        )

        logger.info(f"Initialized tender vector DB: {collection_name}")

    def index_tender(
        self,
        tender_id: str,
        title: str,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Index a single tender in the vector database.

        Args:
            tender_id: Unique tender identifier (publication number)
            title: Tender title
            description: Tender description (optional)
            metadata: Additional metadata for filtering

        Returns:
            True if successful
        """
        try:
            # Combine title and description for embedding
            text = title
            if description:
                text = f"{title}. {description[:2000]}"  # Limit description length

            # Prepare metadata (ChromaDB requires string/int/float/bool values)
            clean_metadata = self._clean_metadata(metadata or {})
            clean_metadata["title"] = title[:500]  # Store truncated title
            clean_metadata["indexed_at"] = datetime.utcnow().isoformat()

            # Upsert to collection
            self.collection.upsert(
                ids=[tender_id],
                documents=[text],
                metadatas=[clean_metadata]
            )

            logger.debug(f"Indexed tender: {tender_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to index tender {tender_id}: {e}")
            return False

    def index_tenders_batch(
        self,
        tenders: List[Dict[str, Any]],
        batch_size: int = 100
    ) -> Dict[str, int]:
        """
        Index multiple tenders in batches.

        Args:
            tenders: List of tender dicts with id, title, description, metadata
            batch_size: Number of tenders per batch

        Returns:
            Statistics dict with indexed and failed counts
        """
        stats = {"indexed": 0, "failed": 0}

        for i in range(0, len(tenders), batch_size):
            batch = tenders[i:i + batch_size]

            ids = []
            documents = []
            metadatas = []

            for tender in batch:
                try:
                    tender_id = tender.get("publication_number") or str(tender.get("id"))
                    title = tender.get("title", "")
                    description = tender.get("description")

                    if not tender_id or not title:
                        stats["failed"] += 1
                        continue

                    # Combine text
                    text = title
                    if description:
                        text = f"{title}. {description[:2000]}"

                    # Clean metadata
                    metadata = self._extract_tender_metadata(tender)

                    ids.append(tender_id)
                    documents.append(text)
                    metadatas.append(metadata)

                except Exception as e:
                    logger.error(f"Error preparing tender for indexing: {e}")
                    stats["failed"] += 1

            # Batch upsert
            if ids:
                try:
                    self.collection.upsert(
                        ids=ids,
                        documents=documents,
                        metadatas=metadatas
                    )
                    stats["indexed"] += len(ids)
                except Exception as e:
                    logger.error(f"Batch upsert failed: {e}")
                    stats["failed"] += len(ids)

            logger.info(f"Indexed batch: {stats['indexed']} total")

        return stats

    def search(
        self,
        query: str,
        n_results: int = 20,
        country: Optional[str] = None,
        cpv_prefix: Optional[str] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        status: Optional[str] = None,
        min_sme_score: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Semantic search over tenders with metadata filtering.

        Supports multilingual queries (searches across all 24 EU languages).

        Args:
            query: Search query (any EU language)
            n_results: Maximum results to return
            country: Filter by country code (e.g., "BE")
            cpv_prefix: Filter by CPV code prefix (e.g., "72")
            min_value: Minimum estimated value
            max_value: Maximum estimated value
            status: Filter by status (open, closed, awarded)
            min_sme_score: Minimum SME suitability score

        Returns:
            List of matching tenders with scores
        """
        try:
            # Build where filter
            where_filter = self._build_where_filter(
                country=country,
                cpv_prefix=cpv_prefix,
                min_value=min_value,
                max_value=max_value,
                status=status,
                min_sme_score=min_sme_score
            )

            # Execute query
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter if where_filter else None,
                include=["documents", "metadatas", "distances"]
            )

            # Format results
            formatted = []
            if results and results["ids"]:
                for i, tender_id in enumerate(results["ids"][0]):
                    formatted.append({
                        "id": tender_id,
                        "title": results["metadatas"][0][i].get("title", ""),
                        "score": 1 - results["distances"][0][i],  # Convert distance to similarity
                        "metadata": results["metadatas"][0][i],
                        "document": results["documents"][0][i] if results["documents"] else None
                    })

            return formatted

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def find_similar(
        self,
        tender_id: str,
        n_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find tenders similar to a given tender.

        Args:
            tender_id: Publication number of the reference tender
            n_results: Number of similar tenders to return

        Returns:
            List of similar tenders with similarity scores
        """
        try:
            # Get the tender's embedding
            existing = self.collection.get(
                ids=[tender_id],
                include=["embeddings", "metadatas"]
            )

            if not existing["embeddings"]:
                logger.warning(f"Tender {tender_id} not found in vector DB")
                return []

            embedding = existing["embeddings"][0]
            metadata = existing["metadatas"][0] if existing["metadatas"] else {}

            # Search for similar (exclude the original)
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=n_results + 1,  # +1 to exclude self
                include=["documents", "metadatas", "distances"]
            )

            # Format and exclude self
            formatted = []
            if results and results["ids"]:
                for i, result_id in enumerate(results["ids"][0]):
                    if result_id != tender_id:
                        formatted.append({
                            "id": result_id,
                            "title": results["metadatas"][0][i].get("title", ""),
                            "score": 1 - results["distances"][0][i],
                            "metadata": results["metadatas"][0][i]
                        })

                        if len(formatted) >= n_results:
                            break

            return formatted

        except Exception as e:
            logger.error(f"Find similar failed: {e}")
            return []

    def delete_tender(self, tender_id: str) -> bool:
        """Delete a tender from the vector database."""
        try:
            self.collection.delete(ids=[tender_id])
            return True
        except Exception as e:
            logger.error(f"Failed to delete tender {tender_id}: {e}")
            return False

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        try:
            count = self.collection.count()
            return {
                "collection_name": self.collection_name,
                "document_count": count,
                "persist_directory": self.persist_directory
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"error": str(e)}

    def _clean_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Clean metadata for ChromaDB (only string/int/float/bool allowed)."""
        cleaned = {}

        for key, value in metadata.items():
            if value is None:
                continue
            elif isinstance(value, (str, int, float, bool)):
                cleaned[key] = value
            elif isinstance(value, datetime):
                cleaned[key] = value.isoformat()
            elif isinstance(value, list):
                # Convert list to comma-separated string
                cleaned[key] = ",".join(str(v) for v in value[:10])
            elif isinstance(value, dict):
                # Convert dict to JSON string
                cleaned[key] = json.dumps(value)[:500]
            else:
                cleaned[key] = str(value)[:500]

        return cleaned

    def _extract_tender_metadata(self, tender: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and clean metadata from a tender dict."""
        metadata = {
            "title": (tender.get("title") or "")[:500],
            "country": tender.get("buyer_country") or tender.get("country"),
            "cpv_main": tender.get("cpv_main") or tender.get("cpv_codes", [""])[0] if tender.get("cpv_codes") else None,
            "status": tender.get("status"),
            "procedure_type": tender.get("procedure_type"),
            "indexed_at": datetime.utcnow().isoformat()
        }

        # Add numeric fields
        if tender.get("estimated_value"):
            metadata["estimated_value"] = float(tender["estimated_value"])

        if tender.get("sme_suitability_score"):
            metadata["sme_score"] = float(tender["sme_suitability_score"])

        if tender.get("publication_date"):
            if isinstance(tender["publication_date"], datetime):
                metadata["publication_date"] = tender["publication_date"].isoformat()
            else:
                metadata["publication_date"] = str(tender["publication_date"])

        if tender.get("submission_deadline"):
            if isinstance(tender["submission_deadline"], datetime):
                metadata["deadline"] = tender["submission_deadline"].isoformat()
            else:
                metadata["deadline"] = str(tender["submission_deadline"])

        return self._clean_metadata(metadata)

    def _build_where_filter(
        self,
        country: Optional[str] = None,
        cpv_prefix: Optional[str] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        status: Optional[str] = None,
        min_sme_score: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """Build ChromaDB where filter from parameters."""
        conditions = []

        if country:
            conditions.append({"country": {"$eq": country}})

        if cpv_prefix:
            # ChromaDB doesn't support LIKE, so we use $eq for exact match
            # For prefix matching, you'd need to store cpv_prefix separately
            conditions.append({"cpv_main": {"$eq": cpv_prefix}})

        if status:
            conditions.append({"status": {"$eq": status}})

        if min_value is not None:
            conditions.append({"estimated_value": {"$gte": min_value}})

        if max_value is not None:
            conditions.append({"estimated_value": {"$lte": max_value}})

        if min_sme_score is not None:
            conditions.append({"sme_score": {"$gte": min_sme_score}})

        if not conditions:
            return None
        elif len(conditions) == 1:
            return conditions[0]
        else:
            return {"$and": conditions}


# Global instance
_tender_vector_db: Optional[TenderVectorDB] = None


def get_tender_vector_db() -> TenderVectorDB:
    """Get or create the global TenderVectorDB instance."""
    global _tender_vector_db
    if _tender_vector_db is None:
        _tender_vector_db = TenderVectorDB()
    return _tender_vector_db


async def index_tender_from_db(tender_id: int) -> bool:
    """
    Index a tender from the database into the vector store.

    Args:
        tender_id: Database ID of the tender

    Returns:
        True if successful
    """
    from backend.core.database import SessionLocal
    from backend.models.tender import Tender

    db = SessionLocal()
    try:
        tender = db.query(Tender).filter(Tender.id == tender_id).first()
        if not tender:
            return False

        vector_db = get_tender_vector_db()
        return vector_db.index_tender(
            tender_id=tender.publication_number,
            title=tender.title,
            description=tender.description,
            metadata={
                "country": tender.buyer_country,
                "cpv_main": tender.cpv_main,
                "estimated_value": tender.estimated_value,
                "status": tender.status,
                "procedure_type": tender.procedure_type,
                "sme_suitability_score": tender.sme_suitability_score,
                "publication_date": tender.publication_date,
                "submission_deadline": tender.submission_deadline
            }
        )
    finally:
        db.close()


async def reindex_all_tenders() -> Dict[str, int]:
    """
    Reindex all tenders from the database into the vector store.

    Returns:
        Statistics dict
    """
    from backend.core.database import SessionLocal
    from backend.models.tender import Tender

    db = SessionLocal()
    try:
        tenders = db.query(Tender).all()

        tender_dicts = []
        for t in tenders:
            tender_dicts.append({
                "publication_number": t.publication_number,
                "title": t.title,
                "description": t.description,
                "buyer_country": t.buyer_country,
                "cpv_main": t.cpv_main,
                "estimated_value": t.estimated_value,
                "status": t.status,
                "procedure_type": t.procedure_type,
                "sme_suitability_score": t.sme_suitability_score,
                "publication_date": t.publication_date,
                "submission_deadline": t.submission_deadline
            })

        vector_db = get_tender_vector_db()
        return vector_db.index_tenders_batch(tender_dicts)

    finally:
        db.close()
