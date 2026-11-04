"""
Abhinav Group AI Chatbot — Knowledge Base Models
Stores chunked, embedded knowledge for RAG retrieval.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON, Boolean, DateTime, Enum, Float, ForeignKey,
    Integer, String, Text, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class KnowledgeCategory(str, enum.Enum):
    PROJECT_OVERVIEW = "project_overview"
    PROJECT_CONFIGURATION = "project_configuration"
    PROJECT_AMENITIES = "project_amenities"
    PROJECT_LOCATION = "project_location"
    PROJECT_PRICING = "project_pricing"       # Only if verified=True
    PROJECT_RERA = "project_rera"
    PROJECT_POSSESSION = "project_possession"
    PROJECT_FAQ = "project_faq"
    COMPANY_INFO = "company_info"
    NRI_INFO = "nri_info"
    GENERAL_REALESTATE = "general_realestate"
    SALES_CONTACT = "sales_contact"


class KnowledgeSource(Base):
    """Tracks the original source of each piece of knowledge."""
    __tablename__ = "knowledge_sources"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    source_type: Mapped[str] = mapped_column(String(50))
    # Types: website_page, pdf_document, manual_entry, api_response
    source_url: Mapped[Optional[str]] = mapped_column(String(1000))
    source_title: Mapped[Optional[str]] = mapped_column(String(500))
    crawled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[Optional[str]] = mapped_column(String(64))  # SHA256 for dedup
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        "KnowledgeChunk", back_populates="source", cascade="all, delete-orphan"
    )


class KnowledgeChunk(Base):
    """
    A chunk of text with its embedding vector for RAG retrieval.
    Each chunk is project-scoped to prevent cross-project confusion.
    """
    __tablename__ = "knowledge_chunks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("knowledge_sources.id"), nullable=False
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=True
    )
    # NULL project_id = company-wide or general real-estate knowledge

    category: Mapped[KnowledgeCategory] = mapped_column(
        Enum(KnowledgeCategory), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA256 dedup
    language: Mapped[str] = mapped_column(String(10), default="en")
    # 'en' | 'hi' | 'both'

    # --- Embedding ---
    # Stored as JSON list of floats (compatible with both SQLite and Postgres)
    # For PostgreSQL production, we use pgvector Column type (see migration)
    embedding: Mapped[Optional[list]] = mapped_column(JSON)
    embedding_model: Mapped[Optional[str]] = mapped_column(String(100))
    embedding_dim: Mapped[Optional[int]] = mapped_column(Integer)

    # --- Approval & Reliability ---
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_verified_fact: Mapped[bool] = mapped_column(Boolean, default=False)
    # is_verified_fact=False means info from third-party sources — do not publish directly

    # --- Validity ---
    effective_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)

    # --- Metadata ---
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)  # Position in source
    metadata_: Mapped[Optional[dict]] = mapped_column(JSON, name="metadata")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    source: Mapped["KnowledgeSource"] = relationship("KnowledgeSource", back_populates="chunks")

    def __init__(self, **kwargs):
        kwargs.setdefault('id', str(uuid.uuid4()))
        kwargs.setdefault('is_approved', False)
        kwargs.setdefault('is_verified_fact', False)
        kwargs.setdefault('is_archived', False)
        kwargs.setdefault('version', 1)
        kwargs.setdefault('chunk_index', 0)
        kwargs.setdefault('language', 'en')
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return f"<KnowledgeChunk {self.category} [{self.id[:8]}]>"
