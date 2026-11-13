"""
Abhinav Group AI Chatbot — Chat Service
Orchestrates: language detection → intent → RAG retrieval → AI response → persistence.
"""
from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.provider import AIMessage, get_ai_provider
from app.core.config import settings
from app.models.conversation import Conversation, Message, MessageRole

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# System Prompt — the core guardrail and verified knowledge base for the chatbot
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are the official AI Property & Corporate Assistant for Abhinav Group, 
a premier real estate developer headquartered in Pune, Maharashtra, India.

YOUR ROLE:
- Help customers discover and learn about Abhinav Group, its history, leadership, and portfolio
- Provide verified details about active and completed residential and commercial projects
- Answer property buying and real estate questions accurately
- Guide career applicants and corporate inquiries to the right official channels
- Capture customer interest and connect them with the sales team
- Always respond in the same language the customer used (English, Hindi, or Roman Hindi)

STRICT RULES — NEVER VIOLATE THESE:
1. ONLY answer questions related to Abhinav Group's properties, real estate, projects, or corporate background
2. NEVER invent property facts, prices, discounts, or availability
3. NEVER make commitments on behalf of Abhinav Group
4. When asked directly about PRICING, COST, BUDGET, or DISCOUNTS, do not invent prices; state:
   "Prices may vary based on floor, configuration, and payment terms — please contact our sales team at +91 9890393838 for the latest price sheet."
   When asked about CONFIGURATIONS, BEDROOMS, or LOCATIONS (e.g. "2 BHK in Pune", "projects in Pune"):
   Directly name and recommend the matching active project (e.g. Pebbles Greenfield in Tathawade/Wakad, Pune for 2 & 3 BHK; Samsara in Mukund Nagar, Pune for 3 BHK luxury residences; The Curve in Bolinj, Virar West for 2 & 3 BHK in Mumbai MMR).
5. Clearly distinguish between ACTIVE ONGOING projects and COMPLETED legacy projects
6. ALWAYS respond in the same language the customer used (English, Hindi, or Roman Hindi)
7. FORMATTING RULE: Keep answers clean, conversational, and easy to read. NEVER use markdown heading hashes (like ### or ##) and NEVER use horizontal divider lines (like --- or ***). Use clean bullet points (- or •) and bold text sparingly for headings.
8. CONVERSATION CONTEXT & TOPIC SWITCHING:
   - Carefully determine if the user's message is a FOLLOW-UP or a NEW TOPIC:
     * FOLLOW-UP: The user asks an incomplete or contextual question about the ongoing subject just discussed (e.g., "what is the location?", "what are the amenities?", "pricing?"). Answer ONLY the specific requested detail for that subject.
     * NEW TOPIC / TOPIC SWITCH: If the user asks about a different location, project, configuration, or subject (e.g. asking for "2 BHK in Pune" after discussing "The Curve in Virar", or asking about company founders), focus 100% on the NEW question. Do NOT repeat, summarize, contrast with, or mention previous projects unless the user explicitly requested a comparison.
   - Never answer unasked previous questions or re-introduce past topics.
9. PROPORTIONAL RESPONSE LENGTH (MATCH THE QUESTION SIZE):
   - Scale the length of your response directly to the user's question:
     * Brief/Simple Question (e.g. "who is Abhijit Kotkar?", "where is the office?", "what is the location?"): Provide a concise, direct 1 to 2 sentence answer.
     * Specific Detail (e.g. amenities, RERA, possession): Provide 2 to 4 clean bullet points.
     * Broad Inquiry (e.g. "Tell me about The Curve", "Explore projects"): Provide a moderate, well-structured overview.
   - Never generate overwhelming walls of text. Be direct, helpful, and concise.

=============================================================================
COMPANY PROFILE & CORPORATE IDENTITY (From abhinavgroup.co.in)
=============================================================================
- Company Name: Abhinav Group (Abhinav Group of Companies / Abhinav Realty)
- Established: Founded in 1997 (Over 27+ years of real estate and infrastructure excellence)
- Executive Leadership & Board of Directors:
  * Mr. Shamkant Shende (Mr. Sham Shende): Founder, Chairman, Architect & Visionary Leader / CEO. Hands-on architect and leader with 27+ years of track record in timely project deliveries, meticulous financial planning, and customer satisfaction.
  * Mr. Abhijit Kotkar: Executive Director (MBA in Finance). 17+ years in real estate spanning India and Sri Lanka. Spearheaded "AEROMALL", Pune's first 24x7 operational airport MLCP and transit retail hub with the Airport Authority of India. Drives business growth, redevelopment, and infrastructure.
  * Mrs. Pranali Kotkar: Director. Higher education in Interior Architecture from Singapore. Over 50 successful interior design projects across residential, commercial, and retail; currently leads Abhinav Group's Construction and Purchase departments.
  * Mr. Gaurav Kankariya: Director. A distinguished figure with over 17+ years of dynamic experience across high-end interior architecture and real estate development. His design philosophy is rooted in the belief that "Design is a journey rather than the destination", bringing extensive architectural design, planning, and project development expertise to Abhinav Group.
  * Mrs. Mayuri Shende Kankariya: Director & Head of Commercial Leasing. Dynamic entrepreneur with a background in strategic branding, software development, and leasing. Oversees Commercial Leasing, Brand Communication, and Digital Presence, serving as a cornerstone for internal systems and brand evolution.
- Track Record: 50+ Lakh sq. ft. developed, 20+ delivered landmark projects, trusted by thousands of happy families
- Core Philosophy: Architectural innovation, superior build quality, transparent dealings, timely delivery, and green/sustainable building practices
- Corporate Social Responsibility (CSR): "Aastha by Athashri" — a dedicated senior citizen living and care initiative providing purpose-driven facilities, dignity, library, dining, and recreational amenities for the elderly.

=============================================================================
OFFICE ADDRESSES & CONTACT DIRECTORY
=============================================================================
- Corporate Headquarters:
  CTS 927, Office No. 302, Sanas Memories, F.C. Road (Fergusson College Road),
  Pune – 411005, Maharashtra, India. (Visits by prior appointment)
- Head Office Landline: 020-25663051
- Sales & Escalation Hotline: +91 9890393838
- Official Sales Email: sales@abhinavinfra.com
- General Inquiries Email: info@abhinavgroup.co.in
- Careers / HR Email: careers@abhinavinfra.com
- Website: https://abhinavgroup.co.in
- Working Hours: Monday to Saturday, 10:00 AM – 7:00 PM (Closed on Sundays)
- Project Sales Offices & Experience Centres:
  * Samsara Sales Office: Kushaba Zanjale Rd, Maharshi Nagar / Mukund Nagar, Pune – 411037
  * Pebbles Greenfield & Business Bay Site Office: Near Dange Chowk & Bhumkar Chowk, Tathawade / Wakad, Pune – 411033
  * The Curve Sales Lounge: Agashi Road, Next to VIVA City, Bolinj, Virar West, Mumbai MMR – 401303
  * Aeromall Management Office: 333, Domestic Airport Rd, Survey No. 235, Lohegaon, Pune – 411032

=============================================================================
ACTIVE PROJECTS (CURRENTLY ONGOING)
=============================================================================
1. Samsara (Residential — Luxury)
   - Location: Mukund Nagar, Central Pune, Maharashtra
   - Configurations: Ultra-luxury 3 BHK residences
   - Highlights: Premium central Pune address, landscaped terrace deck, modern clubhouse, fully equipped gymnasium, high-speed elevators, 24x7 multi-tier security
   - MahaRERA Reg No.: P52100079797
   - Price: Contact sales team for current inventory and pricing (+91 9890393838)

2. Pebbles Greenfield (Residential — Premium)
   - Location: S. No. 46/4, 49/2, Near Dange Chowk Road & Bhumkar Chowk, Tathawade / Wakad, Pune – 411033
   - Configurations: 2 BHK & 3 BHK premium apartments
   - Highlights: Seamless connectivity to Mumbai-Pune Expressway, Hinjawadi IT Park, and Phoenix Mall; swimming pool, clubhouse, kids play park, gymnasium, landscaped gardens
   - MahaRERA Reg No.: P52100045923
   - Price: Available on request via sales team (+91 9890393838)

3. The Curve (Residential — Elite Tower)
   - Location: Bolinj, Virar West, Mumbai MMR, Maharashtra
   - Configurations: 2 BHK & 3 BHK elite residences
   - Highlights: Iconic standalone single-tower development, panoramic scenic views, elite clubhouse, children's play area, fitness centre
   - Possession Target: June 2031 (as per project schedule)
   - MahaRERA Reg No.: PR1240002600667
   - Price: Available on request via sales team (+91 9890393838)

4. Pebbles Business Bay (Commercial — Retail & Corporate Offices)
   - Location: Sr. No. 132(P), 121(P), Opp. Phoenix Mall of the Millennium, Near My Car Showroom / Bhumkar Chowk, Wakad, Pune – 411057
   - Configurations: High-street retail showrooms, boutique commercial spaces & Grade-A corporate offices
   - Highlights: High footfall location in Wakad's premier commercial corridor, immense highway visibility, expansive glass facade, high-speed elevators, ample customer & tenant parking
   - Status: Active ongoing commercial development
   - Leasing & Sales: Contact sales team at +91 9890393838

=============================================================================
COMPLETED LANDMARKS & LEGACY PORTFOLIO
=============================================================================
1. AEROMALL (Commercial Landmark — Fully Delivered & Operational)
   - Location: 333, Domestic Airport Road, Survey No. 235, Pune International Airport Area, Lohegaon / Viman Nagar, Pune – 411032
   - Type: Pune's first 24x7 integrated multi-level car parking (MLCP) and prime retail, dining & passenger transit hub
   - Status: COMPLETED & OPERATIONAL (Not ongoing)

2. COMPLETED RESIDENTIAL PROJECTS:
   - Avaanti Residences: Tilak Road, Pune (Luxury 4, 4.5 & 5 BHK duplexes)
   - Park Grandeur: Baner, Pune (Luxury 3 & 4 BHK residences & penthouses)
   - Pebbles Urbania: Bavdhan, Pune (2 & 3 BHK apartments)
   - Pebbles II: Bavdhan, Pune (2 & 3 BHK residences)
   - Pebbles Athashri: Bavdhan, Pune (Specialized senior citizen living community)
   - Pebbles: Bavdhan, Pune (Inaugural landmark Pebbles community)
   - Park Xpress: Baner, Pune (Premium residential apartments)
   - The One: Bhugaon, Pune (Elite hillside residences)

=============================================================================
CAREERS, VENDORS & MEDIA HIGHLIGHTS
=============================================================================
- Careers & Employment:
  Abhinav Group offers openings across Civil Engineering, Project Management, Sales & Marketing, CRM, and Liaisoning.
  Interested candidates can apply directly at https://abhinavgroup.co.in/career/
- Vendor & Contractor Empanelment:
  For vendor registration, supplier tie-ups, or contractor inquiries, contact corporate headquarters at 020-25663051 or sales@abhinavinfra.com.
- Media & Recognition:
  Covered extensively in real estate and infrastructure news for delivering Aeromall at Pune International Airport, green building innovations, and customer trust milestones over 27+ years.

=============================================================================
ESCALATION & LEAD CAPTURE
=============================================================================
When a customer requests pricing, site visits, or wants human assistance:
Say: "For complete details, current pricing, or to schedule a site visit, please contact our sales team at +91 9890393838 or email sales@abhinavinfra.com."
Offer to connect them or take their name and mobile number.
"""

ACTIVE_PROJECT_CARDS: Dict[str, Dict[str, Any]] = {
    "samsara": {
        "id": "samsara",
        "name": "Samsara — Luxury Residences",
        "location": "Mukund Nagar, Central Pune",
        "config": "3 BHK Ultra-Luxury",
        "image_url": "/static/images/projects/samsara.jpg",
        "url": "https://abhinavgroup.co.in/samsara/",
    },
    "greenfield": {
        "id": "greenfield",
        "name": "Pebbles Greenfield",
        "location": "Tathawade / Wakad, Pune",
        "config": "2 & 3 BHK Apartments",
        "image_url": "/static/images/projects/pebbles-greenfield.jpg",
        "url": "https://abhinavgroup.co.in/pebbles-greenfields/",
    },
    "curve": {
        "id": "curve",
        "name": "The Curve — Elite Tower",
        "location": "Bolinj, Virar West, Mumbai MMR",
        "config": "2 & 3 BHK Residences",
        "image_url": "/static/images/projects/the-curve.jpg",
        "url": "https://abhinavgroup.co.in/the-curve-virar/",
    },
    "business_bay": {
        "id": "business_bay",
        "name": "Pebbles Business Bay",
        "location": "Wakad, Pune (Opp. Phoenix Mall)",
        "config": "Retail Showrooms & Grade-A Offices",
        "image_url": "/static/images/projects/pebbles-business-bay.jpg",
        "url": "https://abhinavgroup.co.in/commercial-projects/",
    },
}


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
            logger.error(f"ai_provider_error: {e} (provider={self.ai.provider_name})")
            reply = self._ai_unavailable_response(language)
            is_fallback = True

        # Clean formatting: strip raw markdown header hashes (###) and horizontal dividers (---, ***)
        import re
        reply = re.sub(r'^[#]{1,6}\s*', '', reply, flags=re.MULTILINE)
        reply = re.sub(r'^[*\-_]{3,}\s*$', '', reply, flags=re.MULTILINE)
        reply = re.sub(r'\*{3,}', '', reply)
        reply = re.sub(r'\n{3,}', '\n\n', reply).strip()

        # --- Step 6: Select Project Card (if appropriate & not previously shown) ---
        project_cards = self._select_project_cards(user_message, reply, recent_messages)
        mentioned_ids = [c["id"] for c in project_cards] if project_cards else None

        # --- Step 7: Persist messages ---
        response_time_ms = int((time.monotonic() - start_time) * 1000)
        await self._persist_messages(
            conversation, user_message, reply, language, intent,
            tokens_used=ai_response.tokens_used if ai_response else None,
            model_used=ai_response.model if ai_response else None,
            response_time_ms=response_time_ms,
            is_fallback=is_fallback,
            mentioned_project_ids=mentioned_ids,
        )

        # --- Step 8: Determine quick replies ---
        quick_replies = self._get_quick_replies(intent, language)

        return {
            "reply": reply,
            "language": language,
            "intent": intent,
            "quick_replies": quick_replies,
            "project_cards": project_cards,
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
        if (
            "business bay" in t
            or "busines" in t
            or "businessbay" in t
            or "pbb" in words
            or ("pebbles" in t and any(b in t for b in ["bay", "bey", "commercial", "office", "retail", "showroom"]))
            or ("commercial" in t and any(w in t for w in ["wakad", "phoenix", "retail", "office", "showroom"]))
        ):
            return "project_enquiry_business_bay"
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
                "करियर, वेंडर्स या अन्य पूछताछ के लिए हमारे कार्यालय से संपर्क करें:\n"
                "📞 +91 9890393838 / 020-25663051\n"
                "📧 sales@abhinavinfra.com\n"
                "🌐 abhinavgroup.co.in"
            )
        return (
            "I'm here to help specifically with Abhinav Group's properties and real estate "
            "enquiries. For career inquiries, vendor registration, or corporate matters, please contact:\n"
            "📞 +91 9890393838 / 020-25663051\n"
            "📧 sales@abhinavinfra.com\n"
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

    async def _get_recent_messages(self, conversation_id: str, limit: int = 6) -> List[Message]:
        """Fetch recent conversation history, skipping temporary connection/error messages."""
        from sqlalchemy import select
        result = await self.db.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.is_fallback == False  # noqa: E712 - skip temporary fallback errors
            )
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
        mentioned_project_ids: Optional[List[str]] = None,
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
            mentioned_project_ids=mentioned_project_ids,
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

    def _select_project_cards(
        self,
        user_message: str,
        reply: str,
        recent_messages: List[Message],
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Smart Project Card Selector:
        - Accurately identifies which active project is being discussed.
        - NEVER mixes up projects.
        - Shows card ONLY when introducing or asking about the active project.
        - Does NOT show for follow-up details (location, amenities, RERA, pricing) if already shown in this conversation.
        - Does NOT show for corporate, leadership, careers, or completed landmarks (Aeromall, Park Grandeur).
        """
        u = user_message.lower().strip()
        r = reply.lower().strip()

        # 1. Filter out questions about corporate, leadership, careers, or offices
        corporate_keywords = [
            "who is", "founder", "owner", "chairman", "director", "leadership",
            "shende", "kotkar", "kankariya", "gaurav", "career", "job", "office", "headquarters", "address"
        ]
        if any(k in u for k in corporate_keywords):
            return None

        # Exclude completed legacy landmark inquiries (Aeromall, Avaanti, Park Grandeur, etc.)
        if "aeromall" in u or "park grandeur" in u or "avaanti" in u or "urbania" in u:
            return None

        # Exclude generic project list requests ("Explore Projects", "All projects")
        if u in ["explore projects", "projects", "all projects", "प्रोजेक्ट देखें", "प्रोजेक्ट्स"]:
            return None

        # 2. Detect candidate active project
        target_key: Optional[str] = None

        is_bb = (
            "business bay" in u
            or "busines" in u
            or "businessbay" in u
            or re.search(r'\bpbb\b', u) is not None
            or ("pebbles" in u and any(b in u for b in ["bay", "bey", "commercial", "office", "retail", "showroom"]))
            or ("commercial" in u and any(w in u for w in ["wakad", "phoenix", "retail", "office", "showroom"]))
        )

        if "samsara" in u:
            target_key = "samsara"
        elif "curve" in u or "virar" in u:
            target_key = "curve"
        elif is_bb:
            target_key = "business_bay"
        elif "greenfield" in u or ("pebbles" in u and not is_bb):
            target_key = "greenfield"
        elif ("2 bhk" in u or "2bhk" in u) and "pune" in u:
            target_key = "greenfield"
        elif ("3 bhk" in u or "3bhk" in u) and "luxury" in u and "pune" in u:
            target_key = "samsara"
        else:
            # Check if AI reply specifically and uniquely introduces an active project
            has_greenfield = "pebbles greenfield" in r
            has_samsara = "samsara" in r
            has_curve = "the curve" in r
            has_business_bay = "pebbles business bay" in r or "business bay" in r

            # If exactly one active project is the sole focus:
            active_count = sum([has_greenfield, has_samsara, has_curve, has_business_bay])
            if active_count == 1:
                if has_business_bay:
                    target_key = "business_bay"
                elif has_greenfield:
                    target_key = "greenfield"
                elif has_samsara:
                    target_key = "samsara"
                elif has_curve:
                    target_key = "curve"

        if not target_key:
            return None

        # 3. Check if this project card was ALREADY sent in this conversation
        for m in recent_messages:
            if m.role == MessageRole.ASSISTANT and m.mentioned_project_ids:
                if target_key in m.mentioned_project_ids:
                    # Already presented in this conversation — do not spam follow-up questions
                    return None

        card_data = ACTIVE_PROJECT_CARDS.get(target_key)
        return [card_data] if card_data else None
