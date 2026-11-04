"""
Leads API — Captures and retrieves lead information for sales and admin dashboard.
"""
from __future__ import annotations

import re
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.lead import Lead, LeadStatus, LeadNote
from app.models.user import User
from app.security.auth import require_any_staff
from app.services.lead_service import LeadService

router = APIRouter()


class LeadCreateRequest(BaseModel):
    name: Optional[str] = None
    phone: str
    session_token: Optional[str] = None
    interested_project: Optional[str] = None
    preferred_config: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    preferred_location: Optional[str] = None
    purchase_timeline: Optional[str] = None
    enquiry_summary: Optional[str] = None
    is_nri: bool = False
    consent_to_contact: bool = False
    source_page: Optional[str] = None
    preferred_language: str = "en"

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        cleaned = re.sub(r"[\s\-\(\)]", "", v)
        if re.match(r"^\+?91?[6-9]\d{9}$", cleaned) or re.match(r"^[6-9]\d{9}$", cleaned):
            return cleaned
        raise ValueError("Please provide a valid Indian mobile number.")

    @field_validator("consent_to_contact")
    @classmethod
    def consent_required(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Consent to be contacted is required to capture this enquiry.")
        return v


@router.get("/")
async def list_leads(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = Query(default=None),
    project: Optional[str] = Query(default=None),
    current_user: User = Depends(require_any_staff),
    db: AsyncSession = Depends(get_db),
):
    """List customer leads captured by the AI assistant."""
    query = select(Lead)
    if status and status.upper() != "ALL":
        query = query.where(Lead.status == status.lower())
    if project and project.upper() != "ALL":
        query = query.where(Lead.interested_project_name == project)

    query = query.order_by(desc(Lead.created_at)).offset(offset).limit(limit)
    result = await db.execute(query)
    leads = result.scalars().all()

    return {
        "leads": [
            {
                "id": l.id,
                "name": l.name,
                "phone": l.phone,
                "phone_normalized": l.phone_normalized,
                "interested_project": l.interested_project_name,
                "status": l.status.value.upper() if hasattr(l.status, "value") else str(l.status).upper(),
                "created_at": l.created_at.isoformat() if l.created_at else None,
                "preferred_config": l.preferred_config,
                "preferred_location": l.preferred_location,
                "is_nri": l.is_nri,
                "source_page": l.source_page,
            }
            for l in leads
        ],
        "total": len(leads),
    }


@router.post("/", status_code=201)
async def create_lead(
    body: LeadCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new lead. Validates for duplicates before saving."""
    service = LeadService(db=db)
    lead = await service.create_lead(body.model_dump())
    return {
        "lead_id": lead.id,
        "is_duplicate": lead.is_duplicate,
        "message": (
            "Thank you! Our sales team will contact you shortly."
            if not lead.is_duplicate
            else "We already have your enquiry. Our team will reach out soon."
        ),
    }


@router.get("/{lead_id}")
async def get_lead_detail(
    lead_id: str,
    current_user: User = Depends(require_any_staff),
    db: AsyncSession = Depends(get_db),
):
    """Get full details of a specific customer lead."""
    query = select(Lead).where(Lead.id == lead_id)
    result = await db.execute(query)
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    return {
        "id": lead.id,
        "name": lead.name,
        "phone": lead.phone,
        "phone_normalized": lead.phone_normalized,
        "interested_project": lead.interested_project_name,
        "status": lead.status.value.upper() if hasattr(lead.status, "value") else str(lead.status).upper(),
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "preferred_config": lead.preferred_config,
        "preferred_location": lead.preferred_location,
        "budget_min": lead.budget_min,
        "budget_max": lead.budget_max,
        "is_nri": lead.is_nri,
        "source_page": lead.source_page,
        "enquiry_summary": lead.enquiry_summary,
        "notes": [],
    }


class LeadStatusUpdate(BaseModel):
    status: str


@router.patch("/{lead_id}")
async def update_lead_status(
    lead_id: str,
    body: LeadStatusUpdate,
    current_user: User = Depends(require_any_staff),
    db: AsyncSession = Depends(get_db),
):
    """Update lead status from admin dashboard."""
    query = select(Lead).where(Lead.id == lead_id)
    result = await db.execute(query)
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")
    lead.status = LeadStatus(body.status.lower())
    await db.commit()
    return {"status": "ok", "lead_id": lead.id}


class NoteCreateRequest(BaseModel):
    note: str


@router.post("/{lead_id}/notes")
async def add_lead_note(
    lead_id: str,
    body: NoteCreateRequest,
    current_user: User = Depends(require_any_staff),
    db: AsyncSession = Depends(get_db),
):
    """Add a CRM note to a lead."""
    query = select(Lead).where(Lead.id == lead_id)
    result = await db.execute(query)
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")
    note = LeadNote(
        lead_id=lead.id,
        author_id=current_user.id,
        content=body.note,
    )
    db.add(note)
    await db.commit()
    return {"status": "ok", "note_id": note.id}
