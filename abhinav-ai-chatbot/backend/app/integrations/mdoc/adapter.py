"""
Mdoc CRM Integration Adapter
Official Push API Integration for Mak SoftBox MDOC CRM.
"""
from __future__ import annotations

import re
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
import structlog
from app.core.config import settings

logger = structlog.get_logger(__name__)

# Project-wise API keys from official MDOC Push API Documentation
MDOC_PROJECT_API_KEYS = {
    "Pebbles Business Bay": "f1170d61-6e3d-454a-8dd3-044aa099c644",
    "PEBBLES GREENFIELDS": "8938bf3e-5082-4d6f-b4af-c6a38a0d6804",
    "SAMSARA": "5858842a-fa8e-4144-acbc-6c94a99d0915",
    "THE CURVE": "132b5197-bff7-4aa5-89f4-3c0cab7f6a45",
}

DEFAULT_MDOC_ENDPOINT = "https://abhinav.maksoftbox.com/MDocBoxAPI/MdocAddEnquiryORTeleCalling/"
DEFAULT_PROJECT_KEY = "5858842a-fa8e-4144-acbc-6c94a99d0915"  # Samsara / Primary


class MdocAdapter:
    """
    Adapter for MDOC CRM Push API (Mak SoftBox).
    """

    @classmethod
    def get_api_key_for_project(cls, project_name: Optional[str]) -> str:
        """Resolve the official MDOC API key for the given project name."""
        if not project_name:
            return DEFAULT_PROJECT_KEY

        p_lower = str(project_name).lower().strip()
        if "business bay" in p_lower:
            return MDOC_PROJECT_API_KEYS["Pebbles Business Bay"]
        elif "greenfield" in p_lower:
            return MDOC_PROJECT_API_KEYS["PEBBLES GREENFIELDS"]
        elif "curve" in p_lower:
            return MDOC_PROJECT_API_KEYS["THE CURVE"]
        elif "samsara" in p_lower:
            return MDOC_PROJECT_API_KEYS["SAMSARA"]

        return DEFAULT_PROJECT_KEY

    @classmethod
    def map_lead_to_mdoc_payload(cls, lead: Any) -> Dict[str, str]:
        """
        Map internal lead model or dict to the official MDOC Push API parameters.
        """
        if hasattr(lead, "name"):
            name = lead.name or ""
            phone = lead.phone_normalized or lead.phone or ""
            project_name = lead.interested_project_name or ""
            summary = lead.enquiry_summary or ""
            pref_config = lead.preferred_config or ""
            pref_loc = lead.preferred_location or ""
            lang = lead.preferred_language or "en"
            source_page = getattr(lead, "source_page", "") or ""
        else:
            name = lead.get("name", "")
            phone = lead.get("phone_normalized") or lead.get("phone", "")
            project_name = lead.get("interested_project_name") or lead.get("interested_project", "")
            summary = lead.get("enquiry_summary", "")
            pref_config = lead.get("preferred_config", "")
            pref_loc = lead.get("preferred_location", "")
            lang = lead.get("preferred_language", "en")
            source_page = lead.get("source_page", "")

        # 1. First & Last name parsing
        clean_name = re.sub(r"[^a-zA-Z\s]", "", str(name)).strip()
        parts = clean_name.split()
        first_name = parts[0][:50] if parts else "Customer"
        last_name = " ".join(parts[1:])[:50] if len(parts) > 1 else ""

        # 2. 10-digit mobile number
        mobile = re.sub(r"\D", "", str(phone))[-10:]

        # 3. Extract email if present
        email = None
        if hasattr(lead, "email") and lead.email:
            email = lead.email
        elif isinstance(lead, dict) and lead.get("email"):
            email = lead["email"]
        elif summary and "Email:" in summary:
            m = re.search(r"Email:\s*([^\s|]+)", summary)
            if m:
                email = m.group(1).strip()

        if not email or "@" not in email:
            # MDOC requires valid email format
            email = f"lead-{mobile}@abhinavgroup.co.in"

        # 4. Resolve Project-wise ApiKey
        api_key = cls.get_api_key_for_project(project_name)

        # 5. City & Location
        city = "Mumbai" if "curve" in project_name.lower() else "Pune"

        # 6. Remarks
        remark_text = f"Abhinav Group AI Website Chatbot Enquiry | Project: {project_name or 'General Enquiry'} | Lang: {lang}"
        if summary:
            remark_text += f" | {summary}"
        if source_page:
            remark_text += f" | Page: {source_page}"
        remark = remark_text[:500]

        # 7. Construct payload according to official MDOC API documentation
        payload = {
            "DataFrom": "T",
            "ApiKey": api_key,
            "EnquiryDate": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "Salutation": "",
            "FirstName": first_name,
            "MiddleName": "",
            "LastName": last_name,
            "DOB": "",
            "AgeRange": "",
            "PanNo": "",
            "MobileNo": mobile,
            "WhatsAppNo": "",
            "AlternativeMobileNo": "",
            "Email": email,
            "Source": "Digitals",
            "SourceDetail": "WebSite",
            "SourceDescription": "Website AI Chatbot",
            "Remark": remark,
            "Preferences": pref_config or "",
            "Budget": "",
            "PossessionReq": "",
            "BuyingPurpose": "",
            "BookingPlanWithin": "",
            "PreferredBankForLoan": "",
            "PreferredLocation": pref_loc or "",
            "CurrentLivingPlace": city,
            "NativePlace": city,
            "Industry": "",
            "CompanyName": "",
            "Country": "India",
            "State": "Maharashtra",
            "City": city,
            "PinCode": "",
            "DigitalAgencyName": "",
            "Udf1": "",
            "Udf2": "",
            "Udf3": "",
            "Udf4": "",
            "Udf5": "",
            "Udf6": "",
            "Udf7": "",
            "Udf8": "",
            "Udf9": "",
            "Udf10": "",
            "UtmCampaignSource": "",
            "UtmCampaignName": "",
            "UtmCampaignId": "",
            "UtmCampaignAdId": "",
            "UtmCampaignAdsetId": "",
            "UtmCampaignMedium": "",
            "UtmCampaignContent": "",
            "UtmCampaignTerm": "",
            "UtmCampaignCountry": "",
            "UtmCampaignState": "",
            "UtmCampaignCity": "",
            "UtmCampaignPincode": "",
            "UtmAdGroup": "",
            "UtmProjectId": "",
            "UtmDevice": "",
            "UtmDeviceModel": "",
            "UtmExtensionId": "",
        }
        return payload

    async def push_lead(self, lead_data: Any) -> dict:
        """
        Push a lead to MDOC CRM.
        Handles mock and live integration modes.
        """
        if not settings.mdoc_enabled:
            logger.info("mdoc_skipped_disabled")
            return {"status": "skipped", "reason": "MDOC_ENABLED=false"}

        if settings.mdoc_mode == "mock":
            return await self._mock_push_lead(lead_data)
        else:
            return await self._real_push_lead(lead_data)

    async def _mock_push_lead(self, lead_data: Any) -> dict:
        """Simulate a successful MDOC API call for testing."""
        import uuid
        mock_id = f"MOCK-{str(uuid.uuid4())[:8].upper()}"
        payload = self.map_lead_to_mdoc_payload(lead_data)
        logger.info("mdoc_mock_push", mdoc_lead_id=mock_id, phone=payload.get("MobileNo", "")[-4:])
        return {
            "status": "success",
            "mdoc_lead_id": mock_id,
            "mode": "mock",
            "request_payload": payload,
            "response_code": 200,
            "response_body": f'{{"code": 200, "status": "success", "id": "{mock_id}"}}',
        }

    async def _real_push_lead(self, lead_data: Any) -> dict:
        """
        Execute real HTTP POST push to MDOC Box API.
        """
        endpoint = getattr(settings, "mdoc_endpoint_url", DEFAULT_MDOC_ENDPOINT) or DEFAULT_MDOC_ENDPOINT
        payload = self.map_lead_to_mdoc_payload(lead_data)

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
        }

        timeout = getattr(settings, "mdoc_timeout_seconds", 15)

        logger.info(
            "mdoc_push_initiating",
            endpoint=endpoint,
            project_key=payload.get("ApiKey"),
            mobile=payload.get("MobileNo", "")[-4:],
            name=payload.get("FirstName"),
        )

        try:
            async with httpx.AsyncClient(timeout=timeout, verify=True) as client:
                resp = await client.post(endpoint, data=payload, headers=headers)
                status_code = resp.status_code
                body_text = resp.text

                logger.info("mdoc_push_response", status_code=status_code, body=body_text[:200])

                # Parse JSON response
                try:
                    data = resp.json()
                except Exception:
                    data = {}

                # Check success conditions from MDOC doc:
                # {"code": 200, "status": "success", "message": "Successfully added", "id": "101"}
                is_success = (
                    status_code == 200
                    and (
                        data.get("status") == "success"
                        or data.get("code") == 200
                        or "successfully" in str(data.get("message", "")).lower()
                    )
                )

                if is_success:
                    mdoc_id = str(data.get("id") or data.get("mdoc_lead_id") or "101")
                    return {
                        "status": "success",
                        "mdoc_lead_id": mdoc_id,
                        "response_code": status_code,
                        "response_body": body_text[:500],
                        "request_payload": payload,
                    }
                else:
                    err_msg = data.get("message") or f"HTTP {status_code}: {body_text[:200]}"
                    return {
                        "status": "failed",
                        "error": err_msg,
                        "response_code": status_code,
                        "response_body": body_text[:500],
                        "request_payload": payload,
                    }

        except httpx.TimeoutException as exc:
            logger.warning("mdoc_push_timeout", error=str(exc))
            return {
                "status": "failed",
                "error": f"Request timeout after {timeout}s: {exc}",
                "response_code": 408,
                "request_payload": payload,
            }
        except Exception as exc:
            logger.error("mdoc_push_error", error=str(exc), exc_info=True)
            return {
                "status": "failed",
                "error": str(exc),
                "response_code": 500,
                "request_payload": payload,
            }


# Convenience alias used in tests and dependency injection
MockMdocAdapter = MdocAdapter
MockMdocAdapter.is_mock = True  # type: ignore[attr-defined]
