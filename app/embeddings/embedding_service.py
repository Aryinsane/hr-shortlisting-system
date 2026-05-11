"""
app/embeddings/embedding_service.py
=====================================
OpenAI text-embedding-3-small + FAISS vector similarity service.

Responsibilities:
- Generate embeddings for JD text, resume text, and skill lists
- Build and manage a FAISS index
- Perform similarity search (resume ↔ JD matching)
- Return similarity scores for scoring pipeline
"""

import os
import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional

from app.utils.logger import get_logger
from app.utils.constants import EMBEDDING_DIMENSION, FAISS_TOP_K

logger = get_logger(__name__)


class EmbeddingService:
    """
    Manages OpenAI embeddings and FAISS vector search.

    Usage:
        service = EmbeddingService()
        jd_embedding = service.embed_text(jd_text)
        service.add_candidate(candidate_id, resume_text)
        results = service.search(jd_text, top_k=5)
    """

    def __init__(self, index_path: Optional[str] = None):
        """
        Initialize the embedding service.

        Args:
            index_path: Optional path to persist/load FAISS index.
        """
        from openai import OpenAI
        from app.config.settings import settings

        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.embedding_model
        self._index_path = index_path or settings.faiss_index_path
        self._dimension = EMBEDDING_DIMENSION

        # FAISS index and candidate ID mapping
        self._index = None
        self._candidate_ids: List[str] = []  # Maps FAISS index position → candidate_id
        self._candidate_embeddings: Dict[str, List[float]] = {}

        # Try to load existing index
        self._load_index()

        logger.info(f"EmbeddingService initialized. Model: {self._model}")

    def embed_text(self, text: str) -> List[float]:
        """
        Generate an embedding vector for a single text string.

        Args:
            text: Input text to embed.

        Returns:
            Embedding vector as a list of floats.

        Raises:
            ValueError: If text is empty.
        """
        if not text or not text.strip():
            raise ValueError("Cannot embed empty text")

        # Truncate to avoid token limit (model max is ~8191 tokens)
        # Rough estimate: 4 chars ≈ 1 token
        max_chars = 32000
        if len(text) > max_chars:
            text = text[:max_chars]
            logger.debug(f"Text truncated to {max_chars} chars for embedding")

        response = self._client.embeddings.create(
            model=self._model,
            input=text,
        )

        embedding = response.data[0].embedding
        logger.debug(f"Generated embedding: dim={len(embedding)}")
        return embedding

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in a single API call.

        Args:
            texts: List of text strings.

        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []

        # Truncate each text
        truncated = [t[:32000] if len(t) > 32000 else t for t in texts]

        response = self._client.embeddings.create(
            model=self._model,
            input=truncated,
        )

        # Sort by index to maintain order
        sorted_data = sorted(response.data, key=lambda x: x.index)
        embeddings = [item.embedding for item in sorted_data]

        logger.info(f"Generated {len(embeddings)} embeddings in batch")
        return embeddings

    def add_candidate(self, candidate_id: str, text: str) -> None:
        """
        Generate embedding for a candidate and add to FAISS index.

        Args:
            candidate_id: Unique candidate identifier.
            text: Candidate's combined resume/LinkedIn text.
        """
        import faiss

        embedding = self.embed_text(text)
        self._candidate_embeddings[candidate_id] = embedding

        # Initialize index if needed
        if self._index is None:
            self._index = faiss.IndexFlatIP(self._dimension)  # Inner product (cosine after normalize)
            logger.info("FAISS index initialized (IndexFlatIP)")

        # Normalize for cosine similarity
        vec = np.array([embedding], dtype=np.float32)
        faiss.normalize_L2(vec)

        self._index.add(vec)
        self._candidate_ids.append(candidate_id)

        logger.debug(f"Added candidate {candidate_id} to FAISS index. Total: {len(self._candidate_ids)}")

    def search(
        self, query_text: str, top_k: int = FAISS_TOP_K
    ) -> List[Tuple[str, float]]:
        """
        Search for most similar candidates to a query (JD text).

        Args:
            query_text: Job description or query text.
            top_k: Number of top results to return.

        Returns:
            List of (candidate_id, similarity_score) sorted by descending score.
        """
        import faiss

        if self._index is None or len(self._candidate_ids) == 0:
            logger.warning("FAISS index is empty — no candidates indexed yet")
            return []

        query_embedding = self.embed_text(query_text)
        vec = np.array([query_embedding], dtype=np.float32)
        faiss.normalize_L2(vec)

        actual_k = min(top_k, len(self._candidate_ids))
        scores, indices = self._index.search(vec, actual_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and idx < len(self._candidate_ids):
                candidate_id = self._candidate_ids[idx]
                # Clamp score to [0, 1]
                similarity = float(max(0.0, min(1.0, score)))
                results.append((candidate_id, similarity))

        logger.info(f"FAISS search returned {len(results)} results")
        return results

    def compute_similarity(self, text_a: str, text_b: str) -> float:
        """
        Compute cosine similarity between two texts.

        Args:
            text_a: First text.
            text_b: Second text.

        Returns:
            Cosine similarity score (0.0 to 1.0).
        """
        import faiss

        embeddings = self.embed_batch([text_a, text_b])
        if len(embeddings) < 2:
            return 0.0

        vec_a = np.array([embeddings[0]], dtype=np.float32)
        vec_b = np.array([embeddings[1]], dtype=np.float32)

        faiss.normalize_L2(vec_a)
        faiss.normalize_L2(vec_b)

        similarity = float(np.dot(vec_a[0], vec_b[0]))
        return max(0.0, min(1.0, similarity))

    def get_candidate_similarity_to_jd(
        self, candidate_id: str, jd_embedding: List[float]
    ) -> float:
        """
        Compute similarity between a specific candidate and JD embedding.

        Args:
            candidate_id: Candidate identifier.
            jd_embedding: Pre-computed JD embedding vector.

        Returns:
            Cosine similarity (0.0 to 1.0).
        """
        import faiss

        candidate_embedding = self._candidate_embeddings.get(candidate_id)
        if candidate_embedding is None:
            logger.warning(f"No embedding found for candidate: {candidate_id}")
            return 0.0

        vec_c = np.array([candidate_embedding], dtype=np.float32)
        vec_j = np.array([jd_embedding], dtype=np.float32)

        faiss.normalize_L2(vec_c)
        faiss.normalize_L2(vec_j)

        similarity = float(np.dot(vec_c[0], vec_j[0]))
        return max(0.0, min(1.0, similarity))

    def _load_index(self) -> None:
        """Load persisted FAISS index and candidate ID mapping if they exist."""
        try:
            import faiss

            index_file = Path(self._index_path) / "index.faiss"
            ids_file = Path(self._index_path) / "candidate_ids.json"
            emb_file = Path(self._index_path) / "embeddings.json"

            if index_file.exists() and ids_file.exists():
                self._index = faiss.read_index(str(index_file))
                self._candidate_ids = json.loads(ids_file.read_text())

                if emb_file.exists():
                    self._candidate_embeddings = json.loads(emb_file.read_text())

                logger.info(
                    f"Loaded FAISS index: {len(self._candidate_ids)} candidates"
                )
        except Exception as e:
            logger.warning(f"Could not load FAISS index: {e}. Starting fresh.")
            self._index = None
            self._candidate_ids = []

    def save_index(self) -> None:
        """Persist the FAISS index and candidate ID mapping to disk."""
        try:
            import faiss

            if self._index is None:
                logger.info("No FAISS index to save")
                return

            index_dir = Path(self._index_path)
            index_dir.mkdir(parents=True, exist_ok=True)

            faiss.write_index(self._index, str(index_dir / "index.faiss"))
            (index_dir / "candidate_ids.json").write_text(
                json.dumps(self._candidate_ids)
            )
            (index_dir / "embeddings.json").write_text(
                json.dumps(self._candidate_embeddings)
            )

            logger.info(
                f"FAISS index saved to {index_dir} "
                f"({len(self._candidate_ids)} candidates)"
            )
        except Exception as e:
            logger.error(f"Failed to save FAISS index: {e}")

    def reset(self) -> None:
        """Clear the in-memory index (used between pipeline sessions)."""
        self._index = None
        self._candidate_ids = []
        self._candidate_embeddings = {}
        logger.info("FAISS index reset")
