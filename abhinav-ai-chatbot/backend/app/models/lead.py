"""
Abhinav Group AI Chatbot — Lead Model
Captures potential buyer information with Mdoc sync tracking.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON, Boolean, DateTime, Enum, ForeignKey,
    Integer, String, Text, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class LeadSource(str, enum.Enum):
    WEBSITE_CHATBOT = "website_chatbot"
    DIRECT_CALL = "direct_call"
    WALK_IN = "walk_in"
    REFERRAL = "referral"
    OTHER = "other"


class LeadStatus(str, enum.Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    CONVERTED = "converted"
    LOST = "lost"


class PropertyType(str, enum.Enum):
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    ANY = "any"


class MdocSyncStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"      # Mdoc disabled or mock mode


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # --- Contact Details ---
    name: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    phone_normalized: Mapped[str] = mapped_column(String(20), nullable=False)
    # phone_normalized = E.164 format for dedup

    # --- Preferences ---
    preferred_language: Mapped[str] = mapped_column(String(10), default="en")
    property_type: Mapped[PropertyType] = mapped_column(
        Enum(PropertyType), default=PropertyType.ANY
    )
    interested_project_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=True
    )
    interested_project_name: Mapped[Optional[str]] = mapped_column(String(255))
    preferred_config: Mapped[Optional[str]] = mapped_column(String(100))
    # e.g. "2 BHK", "3 BHK"
    budget_min: Mapped[Optional[float]] = mapped_column()
    budget_max: Mapped[Optional[float]] = mapped_column()
    preferred_location: Mapped[Optional[str]] = mapped_column(String(255))
    purchase_timeline: Mapped[Optional[str]] = mapped_column(String(100))
    # e.g. "immediately", "3-6 months", "6-12 months"

    # --- Enquiry ---
    enquiry_summary: Mapped[Optional[str]] = mapped_column(Text)
    is_nri: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_to_contact: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # --- Source ---
    conversation_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("conversations.id"), nullable=True
    )
    source_page: Mapped[Optional[str]] = mapped_column(String(1000))
    source_channel: Mapped[str] = mapped_column(String(50), default="website_chatbot")

    # --- Status ---
    status: Mapped[LeadStatus] = mapped_column(Enum(LeadStatus), default=LeadStatus.NEW)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("leads.id"), nullable=True
    )

    # --- Mdoc CRM Sync ---
    mdoc_sync_status: Mapped[MdocSyncStatus] = mapped_column(
        Enum(MdocSyncStatus), default=MdocSyncStatus.PENDING
    )
    mdoc_lead_id: Mapped[Optional[str]] = mapped_column(String(255))
    mdoc_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    mdoc_sync_attempts: Mapped[int] = mapped_column(Integer, default=0)
    mdoc_last_error: Mapped[Optional[str]] = mapped_column(Text)

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    notes: Mapped[list["LeadNote"]] = relationship(
        "LeadNote", back_populates="lead", cascade="all, delete-orphan"
    )
    mdoc_sync_records: Mapped[list["MdocSyncRecord"]] = relationship(
        "MdocSyncRecord", back_populates="lead", cascade="all, delete-orphan"
    )

    def __init__(self, **kwargs):
        kwargs.setdefault('id', str(uuid.uuid4()))
        kwargs.setdefault('status', LeadStatus.NEW)
        kwargs.setdefault('is_duplicate', False)
        kwargs.setdefault('mdoc_sync_status', MdocSyncStatus.PENDING)
        kwargs.setdefault('mdoc_sync_attempts', 0)
        kwargs.setdefault('preferred_language', 'en')
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return f"<Lead {self.name or 'Anonymous'} {self.phone_normalized} [{self.status}]>"


class LeadNote(Base):
    __tablename__ = "lead_notes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    lead_id: Mapped[str] = mapped_column(String(36), ForeignKey("leads.id"), nullable=False)
    author_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    lead: Mapped["Lead"] = relationship("Lead", back_populates="notes")


class MdocSyncRecord(Base):
    """Audit log of every Mdoc sync attempt for a lead."""
    __tablename__ = "mdoc_sync_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    lead_id: Mapped[str] = mapped_column(String(36), ForeignKey("leads.id"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[MdocSyncStatus] = mapped_column(Enum(MdocSyncStatus), nullable=False)
    request_payload: Mapped[Optional[dict]] = mapped_column(JSON)
    response_code: Mapped[Optional[int]] = mapped_column(Integer)
    response_body: Mapped[Optional[str]] = mapped_column(Text)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    mdoc_lead_id: Mapped[Optional[str]] = mapped_column(String(255))
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    lead: Mapped["Lead"] = relationship("Lead", back_populates="mdoc_sync_records")
