"""
Abhinav Group AI Chatbot — RAG Retriever (Phase 4)
Retrieves the most relevant knowledge chunks for a given query.

Usage:
    retriever = RAGRetriever(vector_store, ai_provider)
    results = await retriever.retrieve("Samsara 3BHK price", project="Samsara")
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.ai.provider import BaseAIProvider
from app.rag.vector_store import FAISSVectorStore, VectorSearchResult


# Project name normalization map
PROJECT_ALIASES: Dict[str, str] = {
    "samsara":        "Samsara",
    "pebbles":        "Pebbles Greenfield",
    "greenfield":     "Pebbles Greenfield",
    "pebbles greenfield": "Pebbles Greenfield",
    "curve":          "The Curve",
    "virar":          "The Curve",
    "the curve":      "The Curve",
    "aeromall":       "Aeromall",
    "aero mall":      "Aeromall",
    "vatvriksha":     "Vatvriksha",
    "avaanti":        "Avaanti Residences",
}


class RetrievalResult:
    """A retrieved knowledge chunk with its context."""

    def __init__(
        self,
        chunk_id: str,
        content: str,
        score: float,
        project: Optional[str],
        category: str,
        is_verified: bool,
    ):
        self.chunk_id    = chunk_id
        self.content     = content
        self.score       = score
        self.project     = project
        self.category    = category
        self.is_verified = is_verified

    def to_context_string(self) -> str:
        """Format for injection into AI system prompt."""
        verification = "[VERIFIED]" if self.is_verified else "[UNVERIFIED — do not quote as official]"
        project_tag  = f"[{self.project}]" if self.project else "[General]"
        return f"{project_tag} {verification}\n{self.content}"

    def __repr__(self) -> str:
        return f"<RetrievalResult [{self.score:.3f}] {self.project} {self.category}>"


class RAGRetriever:
    """
    Two-stage retriever:
    1. Dense retrieval: embed query → search vector store → top-K chunks
    2. Post-filter: apply project scope, verification status, relevance threshold

    In Phase 5, this will also integrate keyword search (BM25) as a hybrid.
    """

    def __init__(
        self,
        vector_store: FAISSVectorStore,
        ai_provider: BaseAIProvider,
        top_k: int = 5,
        min_score: float = 0.3,
    ):
        self.vector_store = vector_store
        self.ai_provider  = ai_provider
        self.top_k        = top_k
        self.min_score    = min_score

    async def retrieve(
        self,
        query: str,
        project_filter: Optional[str] = None,
        language: str = "en",
        include_unverified: bool = True,
    ) -> List[RetrievalResult]:
        """
        Main retrieval method.

        Args:
            query:              User's natural language query.
            project_filter:     Restrict to a specific project (optional).
            language:           Query language for context.
            include_unverified: If False, only return is_verified_fact=True chunks.
        """
        if not query or not query.strip():
            return []

        # Detect project from query if not explicitly provided
        if project_filter is None:
            project_filter = self._detect_project_from_query(query)

        # Stage 1: Embed query
        try:
            query_vector = await self.ai_provider.embed(query)
        except Exception as e:
            # If embedding fails, return empty (graceful degradation)
            return []

        # Stage 2: Vector search
        raw_results = self.vector_store.search(
            query_vector=query_vector,
            top_k=self.top_k * 3,     # Over-fetch for filtering
            project_filter=project_filter,
            approved_only=True,
            min_score=self.min_score,
        )

        # Stage 3: Rank and filter
        results = []
        seen_content_hashes = set()

        for r in raw_results:
            meta = r.metadata

            # Skip exact duplicates
            content_hash = meta.get("content_hash", "")
            if content_hash and content_hash in seen_content_hashes:
                continue
            if content_hash:
                seen_content_hashes.add(content_hash)

            # Skip unverified if strict mode
            is_verified = meta.get("is_verified_fact", False)
            if not include_unverified and not is_verified:
                continue

            results.append(RetrievalResult(
                chunk_id   = r.chunk_id,
                content    = meta.get("content", ""),
                score      = r.score,
                project    = meta.get("project"),
                category   = meta.get("category", "general"),
                is_verified = is_verified,
            ))

            if len(results) >= self.top_k:
                break

        return results

    def format_context(self, results: List[RetrievalResult]) -> str:
        """
        Format retrieval results into a context string for the AI system prompt.
        Called by ChatService before building the AI messages list.
        """
        if not results:
            return ""

        lines = ["## Relevant Knowledge Base Context\n"]
        lines.append("Use ONLY the following verified information to answer. Do not invent facts.\n")

        verified = [r for r in results if r.is_verified]
        unverified = [r for r in results if not r.is_verified]

        if verified:
            lines.append("### Verified Information")
            for r in verified:
                lines.append(r.to_context_string())
                lines.append("")

        if unverified:
            lines.append("### Reference Information (not independently verified — mention to contact sales team for confirmation)")
            for r in unverified:
                lines.append(r.to_context_string())
                lines.append("")

        return "\n".join(lines)

    def _detect_project_from_query(self, query: str) -> Optional[str]:
        """Detect which project the query is about."""
        q = query.lower()
        for alias, project_name in PROJECT_ALIASES.items():
            if alias in q:
                return project_name
        return None


# ── Singleton accessor ──────────────────────────────────────

_retriever_instance: Optional[RAGRetriever] = None


def get_retriever() -> Optional[RAGRetriever]:
    """Return the global retriever instance. None if not yet initialized."""
    return _retriever_instance


def init_retriever(vector_store: FAISSVectorStore, ai_provider: BaseAIProvider) -> RAGRetriever:
    """Initialize the global retriever. Called at application startup."""
    global _retriever_instance
    _retriever_instance = RAGRetriever(
        vector_store=vector_store,
        ai_provider=ai_provider,
    )
    return _retriever_instance
