"""
Vector Search Service

Fast semantic search using FAISS for requirements and laws.
"""

import logging
import pickle
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import numpy as np
import faiss
from sqlalchemy.orm import Session

from ...models.eu_law import EULaw, LawRequirement
from .embedding_service import get_embedding_service

logger = logging.getLogger(__name__)


class VectorSearchService:
    """
    Service for fast semantic search using FAISS vector index.

    Maintains separate indexes for:
    - Law requirements (primary use case)
    - EU laws
    """

    def __init__(self, db: Session):
        """
        Initialize vector search service.

        Args:
            db: Database session
        """
        self.db = db
        self.embedding_service = get_embedding_service()

        # FAISS indexes
        self.requirement_index: Optional[faiss.Index] = None
        self.law_index: Optional[faiss.Index] = None

        # ID mappings (FAISS uses sequential IDs, we map to database IDs)
        self.requirement_id_map: List[int] = []  # [faiss_id] -> db_id
        self.law_id_map: List[int] = []  # [faiss_id] -> db_id

        # Cache directory
        self.cache_dir = Path("backend/cache/vector_indexes")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def build_requirement_index(
        self,
        cluster_id: Optional[int] = None,
        force_rebuild: bool = False
    ) -> int:
        """
        Build FAISS index for requirements.

        Args:
            cluster_id: Optional cluster ID to build index for specific cluster
            force_rebuild: Force rebuild even if cache exists

        Returns:
            Number of requirements indexed
        """
        cache_file = self.cache_dir / f"requirements_cluster_{cluster_id or 'all'}.index"
        map_file = self.cache_dir / f"requirements_cluster_{cluster_id or 'all'}.map"

        # Try loading from cache
        if not force_rebuild and cache_file.exists() and map_file.exists():
            logger.info(f"Loading requirement index from cache: {cache_file}")
            try:
                self.requirement_index = faiss.read_index(str(cache_file))
                with open(map_file, 'rb') as f:
                    self.requirement_id_map = pickle.load(f)
                logger.info(f"Loaded index with {len(self.requirement_id_map)} requirements")
                return len(self.requirement_id_map)
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}. Rebuilding index.")

        # Build fresh index
        logger.info("Building requirement index...")

        # Query requirements
        query = self.db.query(LawRequirement)
        if cluster_id:
            query = query.filter(LawRequirement.cluster_id == cluster_id)

        requirements = query.all()

        if not requirements:
            logger.warning("No requirements found to index")
            return 0

        # Generate embeddings
        logger.info(f"Generating embeddings for {len(requirements)} requirements...")
        texts = [req.requirement_text for req in requirements]
        embeddings = self.embedding_service.encode_texts(texts)

        # Create FAISS index
        dimension = embeddings.shape[1]
        logger.info(f"Creating FAISS index with dimension {dimension}")

        # Use IndexFlatIP (Inner Product) for cosine similarity
        # Note: sentence-transformers embeddings are normalized, so IP = cosine similarity
        self.requirement_index = faiss.IndexFlatIP(dimension)

        # Normalize embeddings for cosine similarity
        faiss.normalize_L2(embeddings)

        # Add to index
        self.requirement_index.add(embeddings.astype(np.float32))

        # Build ID mapping
        self.requirement_id_map = [req.id for req in requirements]

        # Save to cache
        logger.info(f"Saving index to cache: {cache_file}")
        faiss.write_index(self.requirement_index, str(cache_file))
        with open(map_file, 'wb') as f:
            pickle.dump(self.requirement_id_map, f)

        logger.info(f"✓ Built requirement index with {len(requirements)} requirements")
        return len(requirements)

    def build_law_index(
        self,
        cluster_id: Optional[int] = None,
        force_rebuild: bool = False
    ) -> int:
        """
        Build FAISS index for laws.

        Args:
            cluster_id: Optional cluster ID to build index for specific cluster
            force_rebuild: Force rebuild even if cache exists

        Returns:
            Number of laws indexed
        """
        cache_file = self.cache_dir / f"laws_cluster_{cluster_id or 'all'}.index"
        map_file = self.cache_dir / f"laws_cluster_{cluster_id or 'all'}.map"

        # Try loading from cache
        if not force_rebuild and cache_file.exists() and map_file.exists():
            logger.info(f"Loading law index from cache: {cache_file}")
            try:
                self.law_index = faiss.read_index(str(cache_file))
                with open(map_file, 'rb') as f:
                    self.law_id_map = pickle.load(f)
                logger.info(f"Loaded index with {len(self.law_id_map)} laws")
                return len(self.law_id_map)
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}. Rebuilding index.")

        # Build fresh index
        logger.info("Building law index...")

        # Query laws
        if cluster_id:
            from ...models.eu_law import ClusterLaw
            cluster_law_ids = self.db.query(ClusterLaw.law_id).filter(
                ClusterLaw.cluster_id == cluster_id
            ).all()
            law_ids = [cl[0] for cl in cluster_law_ids]
            laws = self.db.query(EULaw).filter(EULaw.id.in_(law_ids)).all()
        else:
            laws = self.db.query(EULaw).all()

        if not laws:
            logger.warning("No laws found to index")
            return 0

        # Generate embeddings
        logger.info(f"Generating embeddings for {len(laws)} laws...")
        embeddings_list = []
        for law in laws:
            embedding = self.embedding_service.encode_law(law)
            embeddings_list.append(embedding)

        embeddings = np.array(embeddings_list)

        # Create FAISS index
        dimension = embeddings.shape[1]
        logger.info(f"Creating FAISS index with dimension {dimension}")

        self.law_index = faiss.IndexFlatIP(dimension)

        # Normalize embeddings
        faiss.normalize_L2(embeddings)

        # Add to index
        self.law_index.add(embeddings.astype(np.float32))

        # Build ID mapping
        self.law_id_map = [law.id for law in laws]

        # Save to cache
        logger.info(f"Saving index to cache: {cache_file}")
        faiss.write_index(self.law_index, str(cache_file))
        with open(map_file, 'wb') as f:
            pickle.dump(self.law_id_map, f)

        logger.info(f"✓ Built law index with {len(laws)} laws")
        return len(laws)

    def search_requirements(
        self,
        query: str,
        top_k: int = 10,
        cluster_id: Optional[int] = None,
        min_score: float = 0.5
    ) -> List[Dict]:
        """
        Search for similar requirements.

        Args:
            query: Search query text
            top_k: Number of results to return
            cluster_id: Optional cluster to search within
            min_score: Minimum similarity score (0-1)

        Returns:
            List of dicts with requirement data and scores
        """
        # Ensure index is built
        if self.requirement_index is None:
            logger.info("Requirement index not loaded, building...")
            self.build_requirement_index(cluster_id=cluster_id)

        if self.requirement_index is None or self.requirement_index.ntotal == 0:
            logger.warning("No requirements indexed")
            return []

        # Generate query embedding
        query_embedding = self.embedding_service.encode_text(query)
        query_embedding = query_embedding.reshape(1, -1).astype(np.float32)

        # Normalize for cosine similarity
        faiss.normalize_L2(query_embedding)

        # Search
        scores, indices = self.requirement_index.search(query_embedding, top_k)

        # Build results
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if score < min_score:
                continue

            # Get requirement from database
            db_id = self.requirement_id_map[idx]
            requirement = self.db.query(LawRequirement).filter(
                LawRequirement.id == db_id
            ).first()

            if requirement:
                results.append({
                    'requirement': requirement,
                    'score': float(score),
                    'requirement_id': requirement.id,
                    'requirement_text': requirement.requirement_text,
                    'article': requirement.article,
                    'criticality': requirement.criticality,
                    'applicable_entity': requirement.applicable_entity
                })

        return results

    def search_laws(
        self,
        query: str,
        top_k: int = 10,
        cluster_id: Optional[int] = None,
        min_score: float = 0.5
    ) -> List[Dict]:
        """
        Search for similar laws.

        Args:
            query: Search query text
            top_k: Number of results to return
            cluster_id: Optional cluster to search within
            min_score: Minimum similarity score (0-1)

        Returns:
            List of dicts with law data and scores
        """
        # Ensure index is built
        if self.law_index is None:
            logger.info("Law index not loaded, building...")
            self.build_law_index(cluster_id=cluster_id)

        if self.law_index is None or self.law_index.ntotal == 0:
            logger.warning("No laws indexed")
            return []

        # Generate query embedding
        query_embedding = self.embedding_service.encode_text(query)
        query_embedding = query_embedding.reshape(1, -1).astype(np.float32)

        # Normalize for cosine similarity
        faiss.normalize_L2(query_embedding)

        # Search
        scores, indices = self.law_index.search(query_embedding, top_k)

        # Build results
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if score < min_score:
                continue

            # Get law from database
            db_id = self.law_id_map[idx]
            law = self.db.query(EULaw).filter(EULaw.id == db_id).first()

            if law:
                results.append({
                    'law': law,
                    'score': float(score),
                    'law_id': law.id,
                    'celex': law.celex,
                    'title': law.title,
                    'policy_area': law.policy_area
                })

        return results

    def find_similar_requirements(
        self,
        requirement_id: int,
        top_k: int = 10,
        min_score: float = 0.6
    ) -> List[Dict]:
        """
        Find requirements similar to a given requirement.

        Args:
            requirement_id: ID of the requirement to compare
            top_k: Number of results to return
            min_score: Minimum similarity score

        Returns:
            List of similar requirements with scores
        """
        # Get the requirement
        requirement = self.db.query(LawRequirement).filter(
            LawRequirement.id == requirement_id
        ).first()

        if not requirement:
            logger.warning(f"Requirement {requirement_id} not found")
            return []

        # Search using requirement text
        return self.search_requirements(
            query=requirement.requirement_text,
            top_k=top_k + 1,  # +1 to account for self-match
            min_score=min_score
        )[1:]  # Exclude first result (self-match)
