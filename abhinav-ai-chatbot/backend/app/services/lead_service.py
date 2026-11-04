"""
Abhinav Group AI Chatbot — Lead Service
Handles lead creation, deduplication, and Mdoc sync.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.lead import Lead, LeadStatus, MdocSyncStatus, PropertyType

logger = structlog.get_logger(__name__)


class LeadService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_lead(self, data: Dict[str, Any]) -> Lead:
        """Create a new lead with duplicate detection."""
        # Normalize phone number
        phone_normalized = self._normalize_phone(data["phone"])

        # Check for duplicates within the dedup window
        existing = await self._find_duplicate(phone_normalized, data.get("interested_project"))

        lead = Lead(
            name=data.get("name"),
            phone=data["phone"],
            phone_normalized=phone_normalized,
            preferred_language=data.get("preferred_language", "en"),
            property_type=PropertyType(data.get("property_type", "any")),
            interested_project_name=data.get("interested_project"),
            preferred_config=data.get("preferred_config"),
            budget_min=data.get("budget_min"),
            budget_max=data.get("budget_max"),
            preferred_location=data.get("preferred_location"),
            purchase_timeline=data.get("purchase_timeline"),
            enquiry_summary=data.get("enquiry_summary"),
            is_nri=data.get("is_nri", False),
            consent_to_contact=data.get("consent_to_contact", False),
            source_page=data.get("source_page"),
            conversation_id=data.get("session_token"),  # will be linked to conversation
            is_duplicate=existing is not None,
            duplicate_of_id=existing.id if existing else None,
            mdoc_sync_status=MdocSyncStatus.PENDING,
        )
        self.db.add(lead)
        await self.db.flush()  # Get the lead ID

        logger.info(
            "lead_created",
            lead_id=lead.id,
            phone=phone_normalized[-4:],  # Last 4 digits only
            is_duplicate=lead.is_duplicate,
        )

        # Queue Mdoc sync (async, non-blocking)
        if settings.mdoc_enabled and not lead.is_duplicate:
            await self._queue_mdoc_sync(lead.id)
        else:
            lead.mdoc_sync_status = MdocSyncStatus.SKIPPED

        return lead

    def _normalize_phone(self, phone: str) -> str:
        """Normalize to +91XXXXXXXXXX format."""
        cleaned = re.sub(r"[\s\-\(\)]", "", phone)
        if cleaned.startswith("+91"):
            return cleaned
        elif cleaned.startswith("91") and len(cleaned) == 12:
            return "+" + cleaned
        elif cleaned.startswith("0") and len(cleaned) == 11:
            return "+91" + cleaned[1:]  # strip leading 0
        elif len(cleaned) == 10:
            return "+91" + cleaned
        return cleaned

    async def _find_duplicate(self, phone_normalized: str, project_name: str = None) -> Lead | None:
        """Check if a lead with same phone exists within the dedup window."""
        window_start = datetime.now(timezone.utc) - timedelta(
            hours=settings.lead_dedup_window_hours
        )
        query = (
            select(Lead)
            .where(
                Lead.phone_normalized == phone_normalized,
                Lead.created_at >= window_start,
                Lead.is_duplicate == False,  # noqa: E712
            )
            .order_by(Lead.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _queue_mdoc_sync(self, lead_id: str):
        """Queue a Mdoc sync task. Currently logs intent; Phase 8 adds real sync."""
        logger.info("mdoc_sync_queued", lead_id=lead_id, mode=settings.mdoc_mode)
        # Phase 8: This will call the Mdoc integration adapter
        # For now, in mock mode: just log
