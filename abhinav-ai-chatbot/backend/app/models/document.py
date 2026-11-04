"""
Abhinav Group AI Chatbot — Document Model (extracted PDFs and files)
"""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, Integer, String, Text, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database.session import Base


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("projects.id"), nullable=True)
    document_type: Mapped[str] = mapped_column(String(50), default="brochure")
    title: Mapped[Optional[str]] = mapped_column(String(255))
    original_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    local_path: Mapped[Optional[str]] = mapped_column(String(500))
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    page_count: Mapped[Optional[int]] = mapped_column(Integer)
    extracted_text: Mapped[Optional[str]] = mapped_column(Text)
    is_accessible: Mapped[bool] = mapped_column(Boolean, default=True)
    text_extracted: Mapped[bool] = mapped_column(Boolean, default=False)
    is_indexed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class Image(Base):
    __tablename__ = "images"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("projects.id"), nullable=True)
    original_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_page_url: Mapped[Optional[str]] = mapped_column(String(1000))
    filename: Mapped[Optional[str]] = mapped_column(String(255))
    alt_text: Mapped[Optional[str]] = mapped_column(String(500))
    category: Mapped[Optional[str]] = mapped_column(String(100))
    is_accessible: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
