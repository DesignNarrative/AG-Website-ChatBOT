"""
Abhinav Group AI Chatbot — FAISS Vector Store (Phase 4)
Local development uses FAISS in-memory index.
Production uses pgvector (PostgreSQL) — same interface.

Usage:
    store = FAISSVectorStore(dim=768)
    store.add(chunk_id="uuid", vector=[0.1, 0.2, ...], metadata={...})
    results = store.search(query_vector=[...], top_k=5)
"""
from __future__ import annotations

import json
import os
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Optional FAISS import — falls back to numpy brute-force if not available
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False


VECTOR_DIM = 768          # Matches MockAIProvider; Gemini text-embedding-004 = 768
INDEX_PATH = Path(__file__).parent.parent.parent.parent / "data" / "vector-index"


class VectorSearchResult:
    """Single result from a vector similarity search."""

    def __init__(
        self,
        chunk_id: str,
        score: float,
        metadata: Dict[str, Any],
    ):
        self.chunk_id = chunk_id
        self.score    = score        # Cosine similarity (higher = more relevant)
        self.metadata = metadata

    def __repr__(self) -> str:
        return f"<VectorSearchResult [{self.score:.3f}] {self.chunk_id[:8]}>"


class FAISSVectorStore:
    """
    In-memory FAISS vector store for local development.
    Persists index to disk between runs.

    For production, this is replaced by pgvector queries.
    The interface is identical — only the backend changes.
    """

    def __init__(self, dim: int = VECTOR_DIM, index_dir: Optional[Path] = None):
        self.dim       = dim
        self.index_dir = index_dir or INDEX_PATH
        self.index_dir.mkdir(parents=True, exist_ok=True)

        # chunk_id → metadata mapping
        self._id_map: List[str]              = []
        self._meta_map: List[Dict[str, Any]] = []

        # Build or load index
        if FAISS_AVAILABLE:
            self._index = faiss.IndexFlatIP(dim)   # Inner product = cosine if L2-normalized
        else:
            self._vectors: List[np.ndarray] = []   # Fallback: brute-force numpy

        self._load_if_exists()

    # ── Write operations ──────────────────────────────────────

    def add(self, chunk_id: str, vector: List[float], metadata: Dict[str, Any]) -> None:
        """Add a single chunk to the index."""
        vec = self._normalize(np.array(vector, dtype=np.float32))

        self._id_map.append(chunk_id)
        self._meta_map.append(metadata)

        if FAISS_AVAILABLE:
            self._index.add(vec.reshape(1, -1))
        else:
            self._vectors.append(vec)

    def add_batch(
        self,
        chunk_ids: List[str],
        vectors: List[List[float]],
        metadatas: List[Dict[str, Any]],
    ) -> None:
        """Add multiple chunks at once (more efficient for FAISS)."""
        if not chunk_ids:
            return
        vecs = np.array(vectors, dtype=np.float32)
        # Normalize each row
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        vecs = vecs / norms

        self._id_map.extend(chunk_ids)
        self._meta_map.extend(metadatas)

        if FAISS_AVAILABLE:
            self._index.add(vecs)
        else:
            self._vectors.extend(list(vecs))

    def remove(self, chunk_id: str) -> bool:
        """Remove a chunk from the index. Returns True if found."""
        if chunk_id not in self._id_map:
            return False
        idx = self._id_map.index(chunk_id)
        self._id_map.pop(idx)
        self._meta_map.pop(idx)

        if FAISS_AVAILABLE:
            # FAISS IndexFlatIP doesn't support removal — rebuild index
            self._rebuild_faiss()
        else:
            self._vectors.pop(idx)
        return True

    def clear(self) -> None:
        """Remove all vectors from the index."""
        self._id_map.clear()
        self._meta_map.clear()
        if FAISS_AVAILABLE:
            self._index.reset()
        else:
            self._vectors.clear()

    # ── Search operations ─────────────────────────────────────

    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        project_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
        approved_only: bool = True,
        min_score: float = 0.3,
    ) -> List[VectorSearchResult]:
        """
        Find the most similar chunks to query_vector.

        Args:
            query_vector:    Embedding of the user query.
            top_k:           Number of results to return.
            project_filter:  Only return chunks from this project (None = all).
            category_filter: Only return chunks of this category.
            approved_only:   If True, only return chunks with is_approved=True.
            min_score:       Minimum cosine similarity threshold (0-1).
        """
        if not self._id_map:
            return []

        qvec = self._normalize(np.array(query_vector, dtype=np.float32))
        fetch_k = min(top_k * 5, len(self._id_map))  # Over-fetch to allow filtering

        if FAISS_AVAILABLE:
            scores, indices = self._index.search(qvec.reshape(1, -1), fetch_k)
            raw = [(float(scores[0][i]), int(indices[0][i])) for i in range(len(indices[0])) if indices[0][i] >= 0]
        else:
            raw = self._numpy_search(qvec, fetch_k)

        results = []
        for score, idx in raw:
            if score < min_score:
                continue
            if idx >= len(self._id_map):
                continue
            meta = self._meta_map[idx]
            # Apply filters
            if approved_only and not meta.get("is_approved", False):
                continue
            if project_filter and meta.get("project") != project_filter:
                continue
            if category_filter and meta.get("category") != category_filter:
                continue
            results.append(VectorSearchResult(
                chunk_id=self._id_map[idx],
                score=score,
                metadata=meta,
            ))
            if len(results) >= top_k:
                break

        return results

    def count(self) -> int:
        """Return total number of indexed vectors."""
        return len(self._id_map)

    # ── Persistence ───────────────────────────────────────────

    def save(self) -> None:
        """Persist index to disk."""
        meta_path = self.index_dir / "metadata.pkl"
        with open(meta_path, "wb") as f:
            pickle.dump({"ids": self._id_map, "metas": self._meta_map}, f)

        if FAISS_AVAILABLE:
            faiss.write_index(self._index, str(self.index_dir / "index.faiss"))
        else:
            vec_path = self.index_dir / "vectors.npy"
            np.save(str(vec_path), np.array(self._vectors, dtype=np.float32) if self._vectors else np.empty((0, self.dim)))

    def _load_if_exists(self) -> None:
        """Load a previously saved index if available."""
        meta_path = self.index_dir / "metadata.pkl"
        if not meta_path.exists():
            return
        try:
            with open(meta_path, "rb") as f:
                data = pickle.load(f)
            self._id_map   = data["ids"]
            self._meta_map = data["metas"]

            if FAISS_AVAILABLE:
                idx_path = self.index_dir / "index.faiss"
                if idx_path.exists():
                    self._index = faiss.read_index(str(idx_path))
            else:
                vec_path = self.index_dir / "vectors.npy"
                if vec_path.exists():
                    vecs = np.load(str(vec_path))
                    self._vectors = list(vecs)
        except Exception as e:
            print(f"[VectorStore] Could not load saved index: {e} — starting fresh")

    def _rebuild_faiss(self) -> None:
        """Rebuild FAISS index from scratch (needed after deletion)."""
        if not FAISS_AVAILABLE:
            return
        self._index = faiss.IndexFlatIP(self.dim)
        # This requires vectors to be re-added — for now log a warning
        print("[VectorStore] Warning: FAISS rebuild after deletion not fully supported. Re-index to fix.")

    # ── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _normalize(vec: np.ndarray) -> np.ndarray:
        """L2-normalize vector for cosine similarity via inner product."""
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

    def _numpy_search(self, qvec: np.ndarray, top_k: int) -> List[Tuple[float, int]]:
        """Brute-force cosine similarity search using numpy (no FAISS)."""
        if not self._vectors:
            return []
        matrix = np.array(self._vectors, dtype=np.float32)
        scores = matrix @ qvec  # Dot product of normalized vectors = cosine similarity
        indices = np.argsort(scores)[::-1][:top_k]
        return [(float(scores[i]), int(i)) for i in indices]
