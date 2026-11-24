"""
Abhinav Group AI Chatbot — Lead Service
Handles lead creation, deduplication, and Mdoc sync.
"""
from __future__ import annotations

import asyncio
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

        summary = data.get("enquiry_summary") or ""
        if data.get("email"):
            summary = f"Email: {data.get('email')} | {summary}".strip(" |")

        # Resolve conversation foreign key safely
        conversation_fk = None
        conv_lookup = data.get("session_token") or data.get("conversation_id")
        conv_found = None
        if conv_lookup:
            from app.models.conversation import Conversation
            res = await self.db.execute(select(Conversation).where(Conversation.session_token == conv_lookup))
            conv_found = res.scalar_one_or_none()
            if not conv_found:
                res = await self.db.execute(select(Conversation).where(Conversation.id == conv_lookup))
                conv_found = res.scalar_one_or_none()
            if conv_found:
                conversation_fk = conv_found.id

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
            enquiry_summary=summary or None,
            is_nri=data.get("is_nri", False),
            consent_to_contact=data.get("consent_to_contact", False),
            source_page=data.get("source_page"),
            conversation_id=conversation_fk,
            is_duplicate=existing is not None,
            duplicate_of_id=existing.id if existing else None,
            mdoc_sync_status=MdocSyncStatus.PENDING,
        )
        self.db.add(lead)
        await self.db.flush()  # Get the lead ID

        if conv_found:
            conv_found.lead_id = lead.id
            if lead.name and not conv_found.customer_name:
                conv_found.customer_name = lead.name
            if lead.phone_normalized and not conv_found.customer_phone:
                conv_found.customer_phone = lead.phone_normalized

        await self.db.commit()

        logger.info(
            "lead_created",
            lead_id=lead.id,
            phone=phone_normalized[-4:] if phone_normalized else "????",
            is_duplicate=lead.is_duplicate,
        )

        # Queue Mdoc sync (async, non-blocking) — every enquiry is pushed so MDoc tracks new leads & re-engagements
        if settings.mdoc_enabled:
            await self._queue_mdoc_sync(lead.id)
        else:
            lead.mdoc_sync_status = MdocSyncStatus.SKIPPED

        return lead

    def _normalize_phone(self, phone: str) -> str | None:
        """Normalize to +91XXXXXXXXXX format. Returns None if invalid."""
        cleaned = re.sub(r"[\s\-\(\)]", "", str(phone or ""))
        digits = cleaned[1:] if cleaned.startswith("+") else cleaned
        if not digits.isdigit():
            return None
        if cleaned.startswith("+91") and len(cleaned) == 13:
            return cleaned
        elif cleaned.startswith("91") and len(cleaned) == 12:
            return "+" + cleaned
        elif cleaned.startswith("0") and len(cleaned) == 11:
            return "+91" + cleaned[1:]  # strip leading 0
        elif len(cleaned) == 10:
            return "+91" + cleaned
        return None

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
        """Queue and trigger Mdoc CRM sync asynchronously in the background."""
        import asyncio
        logger.info("mdoc_sync_queued", lead_id=lead_id, mode=settings.mdoc_mode)
        try:
            asyncio.create_task(self.sync_lead_to_mdoc(lead_id))
        except Exception as e:
            logger.error("mdoc_queue_task_failed", lead_id=lead_id, error=str(e))

    @classmethod
    async def sync_lead_to_mdoc(cls, lead_id: str) -> dict:
        """
        Background worker that syncs a single lead to Mdoc CRM.
        Operates with an isolated AsyncSessionLocal to prevent blocking the request pipeline.
        """
        from app.database.session import AsyncSessionLocal
        from app.integrations.mdoc.adapter import MdocAdapter
        from app.models.lead import MdocSyncRecord

        adapter = MdocAdapter()
        async with AsyncSessionLocal() as session:
            try:
                lead = None
                for _ in range(5):
                    res = await session.execute(select(Lead).where(Lead.id == lead_id))
                    lead = res.scalar_one_or_none()
                    if lead:
                        break
                    await asyncio.sleep(0.2)

                if not lead:
                    logger.error("mdoc_sync_lead_not_found", lead_id=lead_id)
                    return {"status": "failed", "reason": "Lead not found"}

                lead.mdoc_sync_attempts = (lead.mdoc_sync_attempts or 0) + 1
                result = await adapter.push_lead(lead)

                # Record sync attempt in audit log
                record = MdocSyncRecord(
                    lead_id=lead.id,
                    attempt_number=lead.mdoc_sync_attempts,
                    status=MdocSyncStatus.SUCCESS if result.get("status") == "success" else MdocSyncStatus.FAILED,
                    request_payload=result.get("request_payload"),
                    response_code=result.get("response_code"),
                    response_body=result.get("response_body"),
                    error_message=result.get("error"),
                    mdoc_lead_id=result.get("mdoc_lead_id"),
                )
                session.add(record)

                if result.get("status") == "success":
                    lead.mdoc_sync_status = MdocSyncStatus.SUCCESS
                    lead.mdoc_lead_id = result.get("mdoc_lead_id")
                    lead.mdoc_synced_at = datetime.now(timezone.utc)
                    lead.mdoc_last_error = None
                    logger.info("mdoc_sync_success", lead_id=lead.id, mdoc_id=lead.mdoc_lead_id)
                elif result.get("status") == "skipped":
                    lead.mdoc_sync_status = MdocSyncStatus.SKIPPED
                else:
                    lead.mdoc_sync_status = MdocSyncStatus.FAILED
                    lead.mdoc_last_error = str(result.get("error") or "Sync failed")
                    logger.warning("mdoc_sync_failed", lead_id=lead.id, error=lead.mdoc_last_error)

                await session.commit()
                return result

            except Exception as e:
                logger.error("mdoc_sync_exception", lead_id=lead_id, error=str(e), exc_info=True)
                try:
                    res = await session.execute(select(Lead).where(Lead.id == lead_id))
                    lead = res.scalar_one_or_none()
                    if lead:
                        lead.mdoc_sync_status = MdocSyncStatus.FAILED
                        lead.mdoc_last_error = str(e)
                        await session.commit()
                except Exception:
                    pass
                return {"status": "failed", "error": str(e)}
