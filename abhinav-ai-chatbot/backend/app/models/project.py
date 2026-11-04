"""
Abhinav Group AI Chatbot — Project Model
Stores verified project data. Each field tracks its source and approval status.
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


class ProjectType(str, enum.Enum):
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    MIXED = "mixed"


class ProjectStatus(str, enum.Enum):
    ONGOING = "ongoing"
    COMPLETED = "completed"
    UPCOMING = "upcoming"
    UNKNOWN = "unknown"           # Requires manual verification


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"           # Extracted but not verified
    APPROVED = "approved"         # Verified by developer/admin
    REJECTED = "rejected"         # Flagged as incorrect
    NEEDS_REVIEW = "needs_review" # Conflicting or outdated


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # --- Identity ---
    project_id_slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    project_type: Mapped[ProjectType] = mapped_column(Enum(ProjectType), nullable=False)
    project_status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus), nullable=False, default=ProjectStatus.UNKNOWN
    )

    # --- Location ---
    location: Mapped[Optional[str]] = mapped_column(String(500))
    address: Mapped[Optional[str]] = mapped_column(Text)
    city: Mapped[str] = mapped_column(String(100), default="Pune")
    state: Mapped[str] = mapped_column(String(100), default="Maharashtra")
    pincode: Mapped[Optional[str]] = mapped_column(String(10))

    # --- Description ---
    description: Mapped[Optional[str]] = mapped_column(Text)
    tagline: Mapped[Optional[str]] = mapped_column(String(500))

    # --- Configurations (stored as JSON for flexibility) ---
    configurations: Mapped[Optional[dict]] = mapped_column(JSON)
    # Example: [{"type": "2 BHK", "carpet_area_sqft": 736, "price_min": 9000000}]

    # --- Specifications ---
    total_units: Mapped[Optional[int]] = mapped_column(Integer)
    total_floors: Mapped[Optional[int]] = mapped_column(Integer)
    land_area: Mapped[Optional[str]] = mapped_column(String(100))
    amenities: Mapped[Optional[dict]] = mapped_column(JSON)
    specifications: Mapped[Optional[dict]] = mapped_column(JSON)

    # --- RERA ---
    rera_number: Mapped[Optional[str]] = mapped_column(String(100))
    rera_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # --- Pricing (indicative — MUST be verified before publishing) ---
    price_min: Mapped[Optional[float]] = mapped_column(Float)
    price_max: Mapped[Optional[float]] = mapped_column(Float)
    price_per_sqft_min: Mapped[Optional[float]] = mapped_column(Float)
    price_per_sqft_max: Mapped[Optional[float]] = mapped_column(Float)
    price_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    # IMPORTANT: False means pricing is from third-party and must NOT be published as official

    # --- Possession ---
    possession_date: Mapped[Optional[str]] = mapped_column(String(100))
    possession_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # --- Links ---
    official_url: Mapped[Optional[str]] = mapped_column(String(500))
    microsite_urls: Mapped[Optional[dict]] = mapped_column(JSON)
    brochure_urls: Mapped[Optional[dict]] = mapped_column(JSON)

    # --- Connectivity & Nearby ---
    connectivity: Mapped[Optional[dict]] = mapped_column(JSON)
    nearby_facilities: Mapped[Optional[dict]] = mapped_column(JSON)

    # --- Knowledge Management ---
    approval_status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus), nullable=False, default=ApprovalStatus.PENDING
    )
    approved_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    notes: Mapped[Optional[str]] = mapped_column(Text)  # Developer notes

    # --- Source Tracking ---
    source_urls: Mapped[Optional[dict]] = mapped_column(JSON)
    last_crawled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # --- Relationships ---
    images: Mapped[list["ProjectImage"]] = relationship(
        "ProjectImage", back_populates="project", cascade="all, delete-orphan"
    )
    documents: Mapped[list["ProjectDocument"]] = relationship(
        "ProjectDocument", back_populates="project", cascade="all, delete-orphan"
    )

    def __init__(self, **kwargs):
        kwargs.setdefault('id', str(uuid.uuid4()))
        kwargs.setdefault('project_status', ProjectStatus.UNKNOWN)
        kwargs.setdefault('approval_status', ApprovalStatus.PENDING)
        kwargs.setdefault('price_verified', False)
        kwargs.setdefault('rera_verified', False)
        kwargs.setdefault('possession_verified', False)
        kwargs.setdefault('is_active', True)
        kwargs.setdefault('is_featured', False)
        kwargs.setdefault('version', 1)
        kwargs.setdefault('city', 'Pune')
        kwargs.setdefault('state', 'Maharashtra')
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return f"<Project {self.project_name} [{self.project_status}]>"


class ProjectImage(Base):
    __tablename__ = "project_images"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    original_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_page_url: Mapped[Optional[str]] = mapped_column(String(1000))
    filename: Mapped[Optional[str]] = mapped_column(String(255))
    alt_text: Mapped[Optional[str]] = mapped_column(String(500))
    caption: Mapped[Optional[str]] = mapped_column(Text)
    width: Mapped[Optional[int]] = mapped_column(Integer)
    height: Mapped[Optional[int]] = mapped_column(Integer)
    category: Mapped[Optional[str]] = mapped_column(String(100))
    # Categories: gallery, exterior, interior, floor_plan, amenity, location, logo
    is_accessible: Mapped[bool] = mapped_column(Boolean, default=True)
    retrieval_status: Mapped[Optional[str]] = mapped_column(String(50))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    project: Mapped["Project"] = relationship("Project", back_populates="images")


class ProjectDocument(Base):
    __tablename__ = "project_documents"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50))
    # Types: brochure, floor_plan, specification, price_list, faq, other
    title: Mapped[Optional[str]] = mapped_column(String(255))
    original_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    local_path: Mapped[Optional[str]] = mapped_column(String(500))
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    is_accessible: Mapped[bool] = mapped_column(Boolean, default=True)
    text_extracted: Mapped[bool] = mapped_column(Boolean, default=False)
    extraction_status: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    project: Mapped["Project"] = relationship("Project", back_populates="documents")
