"""
Leads API — Captures and retrieves lead information.
"""
from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
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
        # Strip spaces and dashes for validation
        cleaned = re.sub(r"[\s\-\(\)]", "", v)
        # Indian mobile: 10 digits, or with country code +91
        if re.match(r"^\+?91?[6-9]\d{9}$", cleaned) or re.match(r"^[6-9]\d{9}$", cleaned):
            return cleaned
        raise ValueError("Please provide a valid Indian mobile number.")

    @field_validator("consent_to_contact")
    @classmethod
    def consent_required(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Consent to be contacted is required to capture this enquiry.")
        return v


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
