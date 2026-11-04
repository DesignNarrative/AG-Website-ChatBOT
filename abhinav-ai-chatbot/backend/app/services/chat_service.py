"""
Abhinav Group AI Chatbot — Chat Service
Orchestrates: language detection → intent → RAG retrieval → AI response → persistence.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.provider import AIMessage, get_ai_provider
from app.core.config import settings
from app.models.conversation import Conversation, Message, MessageRole

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# System Prompt — the core guardrail for the chatbot
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a property sales assistant for Abhinav Group, a real estate developer 
based in Pune, Maharashtra, India.

YOUR ROLE:
- Help customers discover and learn about Abhinav Group's properties and projects
- Answer general real estate educational questions
- Capture customer interest and connect them with the sales team
- Support conversations in both English and Hindi

STRICT RULES — NEVER VIOLATE THESE:
1. ONLY answer questions related to Abhinav Group's properties, real estate concepts, or property purchase process
2. NEVER invent property facts, prices, configurations, or availability
3. NEVER make commitments on behalf of Abhinav Group
4. If you don't have verified information, say so clearly and offer the sales contact
5. NEVER mix up information between different projects
6. Do NOT answer questions about careers, vendors, contractors, or other unrelated topics
7. For unverified pricing, always say "prices may vary — please contact our sales team for current pricing"
8. ALWAYS respond in the same language the customer used (English or Hindi)

ACTIVE PROJECTS:
- Samsara: 3 BHK luxury residences, Mukund Nagar, Pune
- Pebbles Greenfield: 2 & 3 BHK, Tathawade/Wakad, Pune  
- The Curve: 2 & 3 BHK, Virar West, Mumbai MMR
- Aeromall: Commercial complex, Airport Road, Lohegaon, Pune

SALES CONTACT (use when escalating):
Phone: +91 9890393838
Email: sales@abhinavinfra.com
Hours: Monday to Saturday, 10 AM to 7 PM

When you don't have enough information to answer accurately, say:
"For the most accurate and up-to-date information, please contact our sales team at +91 9890393838."
"""


class ChatService:
    """Processes a user message through the full pipeline."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.ai = get_ai_provider()

    async def process_message(
        self,
        conversation: Conversation,
        user_message: str,
    ) -> Dict[str, Any]:
        """
        Full pipeline:
        1. Detect language
        2. Detect intent
        3. Retrieve knowledge (Phase 5 — RAG)
        4. Build AI messages
        5. Call AI provider
        6. Persist messages
        7. Return structured response
        """
        start_time = time.monotonic()

        # --- Step 1: Language Detection ---
        language = self._detect_language(user_message)

        # --- Step 2: Intent Detection (basic keyword matching for now; LLM-based in Phase 5) ---
        intent = self._detect_intent(user_message)

        # --- Step 3: Safety check — scope filter ---
        if intent == "out_of_scope":
            reply = self._out_of_scope_response(language)
            await self._persist_messages(conversation, user_message, reply, language, intent)
            return {
                "reply": reply,
                "language": language,
                "intent": intent,
                "quick_replies": self._default_quick_replies(language),
                "is_fallback": False,
            }

        # --- Step 4: Build conversation history for AI ---
        recent_messages = await self._get_recent_messages(conversation.id)
        ai_messages = [AIMessage(role=m.role, content=m.content) for m in recent_messages]
        ai_messages.append(AIMessage(role="user", content=user_message))

        # --- Step 5: Call AI provider (with graceful fallback) ---
        ai_response = None
        is_fallback = False
        try:
            ai_response = await self.ai.chat(
                messages=ai_messages,
                system_prompt=SYSTEM_PROMPT,
                max_tokens=settings.ai_max_tokens,
                temperature=settings.ai_temperature,
            )
            reply = ai_response.content
        except Exception as e:
            logger.error("ai_provider_error", error=str(e), provider=self.ai.provider_name)
            reply = self._ai_unavailable_response(language)
            is_fallback = True

        # --- Step 6: Persist messages ---
        response_time_ms = int((time.monotonic() - start_time) * 1000)
        await self._persist_messages(
            conversation, user_message, reply, language, intent,
            tokens_used=ai_response.tokens_used if ai_response else None,
            model_used=ai_response.model if ai_response else None,
            response_time_ms=response_time_ms,
            is_fallback=is_fallback,
        )

        # --- Step 7: Determine quick replies ---
        quick_replies = self._get_quick_replies(intent, language)

        return {
            "reply": reply,
            "language": language,
            "intent": intent,
            "quick_replies": quick_replies,
            "project_cards": None,  # Phase 5: populated from RAG results
            "is_fallback": is_fallback,
        }

    def _detect_language(self, text: str) -> str:
        """Detect if message is in Hindi or English."""
        # Hindi Unicode block: 0900-097F
        hindi_chars = sum(1 for c in text if "\u0900" <= c <= "\u097f")
        if hindi_chars > 2:
            return "hi"
        # Common Roman Hindi words
        roman_hindi_words = {"kya", "hai", "mujhe", "chahiye", "aapka", "paisa",
                             "kitna", "ghar", "flat", "bata", "dijiye"}
        words = set(text.lower().split())
        if len(words & roman_hindi_words) >= 2:
            return "hi"
        return "en"

    def _detect_intent(self, text: str) -> str:
        """Basic intent detection. Phase 5 replaces this with LLM-based classification."""
        import re
        t = text.lower().strip()
        words = set(re.findall(r'\b\w+\b', t))

        # Out of scope — checked FIRST to prevent any AI call
        oos_keywords = ["career", "job", "vacancy", "vendor", "supplier",
                        "contractor", "recruitment", "intern", "internship", "hiring"]
        if any(w in t for w in oos_keywords) or "hr" in words:
            return "out_of_scope"

        # Specific project enquiries — checked BEFORE generic greetings or project_list
        if "samsara" in t:
            return "project_enquiry_samsara"
        if "greenfield" in t or "pebbles" in t:
            return "project_enquiry_greenfield"
        if "curve" in t or "virar" in t:
            return "project_enquiry_curve"
        if "aeromall" in t or "airport road" in t or ("commercial" in t and "project" not in t):
            return "project_enquiry_aeromall"

        # NRI — before generic project list
        if any(w in t for w in ["nri", "abroad", "foreign", "overseas", "repatriate",
                                  "non resident", "non-resident"]):
            return "nri_enquiry"

        # Pricing
        if any(w in t for w in ["price", "cost", "rate", "budget", "afford", "cheap", "kitna",
                                  "कीमत", "दाम", "कितना"]):
            return "pricing_enquiry"

        # Configuration
        if any(w in t for w in ["bhk", "bedroom", "2 bhk", "3 bhk", "1 bhk", "config",
                                  "बीएचके", "कमरे"]):
            return "config_enquiry"

        # Brochure / Floor plans
        if any(w in t for w in ["brochure", "pdf", "download", "document", "floor plan", "floorplan", "ब्रोशर"]):
            return "brochure_request"

        # Contact/Sales/Escalation
        if any(w in t for w in ["contact", "call", "speak", "human", "agent", "sales team",
                                  "फोन", "बात"]):
            return "escalation"

        # Greeting (use word matching for short words like 'hi')
        greetings = {"hello", "hi", "hey", "namaste", "start", "help"}
        if words & greetings or any(p in t for p in ["good morning", "good afternoon", "good evening", "नमस्ते"]):
            return "greeting"

        # Generic project list — checked AFTER specific projects
        if any(w in t for w in ["project", "property", "properties", "all project",
                                  "प्रोजेक्ट", "प्रॉपर्टी"]):
            return "project_list"

        return "general_property_enquiry"

    def _out_of_scope_response(self, language: str) -> str:
        if language == "hi":
            return (
                "मैं केवल अभिनव ग्रुप की प्रॉपर्टी और रियल एस्टेट से संबंधित प्रश्नों में "
                "सहायता करता हूं।\n\n"
                "हमारे सेल्स टीम से संपर्क करें:\n"
                "📞 +91 9890393838\n"
                "🌐 abhinavgroup.co.in"
            )
        return (
            "I'm here to help specifically with Abhinav Group's properties and real estate "
            "enquiries. I'm not able to assist with that topic.\n\n"
            "For other enquiries, please contact:\n"
            "📞 +91 9890393838\n"
            "🌐 abhinavgroup.co.in"
        )

    def _ai_unavailable_response(self, language: str) -> str:
        if language == "hi":
            return (
                "हमारा AI असिस्टेंट अभी उपलब्ध नहीं है। कृपया हमारी सेल्स टीम से "
                "सीधे संपर्क करें:\n"
                "📞 +91 9890393838\n"
                "📧 sales@abhinavinfra.com"
            )
        return (
            "Our AI assistant is temporarily unavailable. Please contact our sales team:\n"
            "📞 +91 9890393838\n"
            "📧 sales@abhinavinfra.com\n\n"
            "Available Monday to Saturday, 10 AM – 7 PM"
        )

    def _get_quick_replies(self, intent: str, language: str) -> List[str]:
        if language == "hi":
            return ["प्रोजेक्ट देखें", "कीमत जानें", "ब्रोशर डाउनलोड करें", "सेल्स टीम से बात करें"]
        return ["Explore Projects", "Check Pricing", "Download Brochure", "Speak to Sales"]

    def _default_quick_replies(self, language: str) -> List[str]:
        return self._get_quick_replies("general", language)

    async def _get_recent_messages(self, conversation_id: str, limit: int = 10) -> List[Message]:
        """Fetch recent conversation history."""
        from sqlalchemy import select
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        messages = result.scalars().all()
        return list(reversed(messages))  # Chronological order

    async def _persist_messages(
        self,
        conversation: Conversation,
        user_message: str,
        ai_reply: str,
        language: str,
        intent: str,
        tokens_used: Optional[int] = None,
        model_used: Optional[str] = None,
        response_time_ms: Optional[int] = None,
        is_fallback: bool = False,
    ):
        """Save both the user message and AI reply to the database."""
        from datetime import datetime, timezone

        user_msg = Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=user_message,
            language=language,
            intent=intent,
        )
        self.db.add(user_msg)

        ai_msg = Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=ai_reply,
            language=language,
            intent=intent,
            ai_model_used=model_used,
            tokens_used=tokens_used,
            response_time_ms=response_time_ms,
            is_fallback=is_fallback,
        )
        self.db.add(ai_msg)

        # Update conversation metadata
        conversation.language = language
        conversation.last_message_at = datetime.now(timezone.utc)
        conversation.message_count = (conversation.message_count or 0) + 2
