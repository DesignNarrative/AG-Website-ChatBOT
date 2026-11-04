"""
Mdoc CRM Integration Adapter
Currently in MOCK mode — no real API calls are made.
Phase 8 will implement real API calls when credentials and documentation are provided.
"""
from __future__ import annotations

import structlog
from app.core.config import settings

logger = structlog.get_logger(__name__)


class MdocAdapter:
    """
    Adapter for the Mdoc CRM API.
    
    Status: MOCK MODE — no real API calls.
    
    To enable real integration:
    1. Set MDOC_ENABLED=true in .env
    2. Set MDOC_MODE=sandbox or production
    3. Set MDOC_API_KEY and MDOC_API_BASE_URL
    4. Contact Mak SoftBox (info@maksoftbox.com) for API documentation
    
    Expected endpoints (based on Mdoc documentation research):
    - POST /leads — Create a new lead
    - GET /inventory — Pull inventory (optional)
    """

    async def push_lead(self, lead_data: dict) -> dict:
        """
        Push a lead to Mdoc CRM.
        Returns a result dict with status and mdoc_lead_id.
        """
        if not settings.mdoc_enabled:
            logger.info("mdoc_skipped_disabled")
            return {"status": "skipped", "reason": "MDOC_ENABLED=false"}

        if settings.mdoc_mode == "mock":
            return await self._mock_push_lead(lead_data)
        elif settings.mdoc_mode == "sandbox":
            return await self._real_push_lead(lead_data, sandbox=True)
        else:
            return await self._real_push_lead(lead_data, sandbox=False)

    async def _mock_push_lead(self, lead_data: dict) -> dict:
        """Simulate a successful Mdoc API call for testing."""
        import uuid
        mock_mdoc_id = f"MOCK-{str(uuid.uuid4())[:8].upper()}"
        logger.info("mdoc_mock_push", mdoc_lead_id=mock_mdoc_id, phone=lead_data.get("phone", "")[-4:])
        return {
            "status": "success",
            "mdoc_lead_id": mock_mdoc_id,
            "mode": "mock",
        }

    async def _real_push_lead(self, lead_data: dict, sandbox: bool = True) -> dict:
        """
        Real Mdoc API call — NOT YET IMPLEMENTED.
        
        BLOCKED: Waiting for Mdoc API documentation and credentials.
        Contact: info@maksoftbox.com or your Mdoc account manager.
        
        Required fields (estimated based on Mdoc research):
        - name, phone, email (optional)
        - project_name, configuration
        - source (website_chatbot)
        - enquiry_note
        """
        logger.error(
            "mdoc_real_integration_not_implemented",
            message="Real Mdoc API integration requires API documentation and credentials. "
                    "Contact Mak SoftBox at info@maksoftbox.com",
        )
        raise NotImplementedError(
            "Real Mdoc API integration not yet implemented. "
            "Set MDOC_MODE=mock for testing."
        )

    @staticmethod
    def map_lead_to_mdoc_payload(lead) -> dict:
        """
        Map our internal lead model to Mdoc's expected format.
        Field names are estimated — will be corrected when official docs arrive.
        """
        return {
            "name": lead.name or "Website Enquiry",
            "mobile": lead.phone_normalized.lstrip("+"),
            "project": lead.interested_project_name or "",
            "configuration": lead.preferred_config or "",
            "budget": f"{lead.budget_min or ''}-{lead.budget_max or ''}",
            "enquiry": lead.enquiry_summary or "",
            "source": "Website Chatbot",
            "language": lead.preferred_language,
            "is_nri": lead.is_nri,
        }


# Convenience alias used in tests and dependency injection
MockMdocAdapter = MdocAdapter
MockMdocAdapter.is_mock = True  # type: ignore[attr-defined]
