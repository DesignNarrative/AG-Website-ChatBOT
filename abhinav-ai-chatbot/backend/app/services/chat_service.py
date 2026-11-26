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
4. PRICING vs BROCHURE REQUESTS:
   - When asked directly about PRICING, COST, BUDGET, or DISCOUNTS:
     * If a specific project is asked about (e.g. "What is the price of Samsara?", "The Curve rate"):
       Acknowledge the project and its configuration (e.g., for Samsara mention ultra-luxury 3 BHK in Mukund Nagar), and state:
       - For Samsara or Pebbles Business Bay: "Prices may vary based on floor, configuration, and payment terms — please contact our sales team at +91 9730397979 for the latest price sheet."
       - For The Curve: "Prices may vary based on floor, configuration, and payment terms — please contact our sales team at +91 97307 00667 for the latest price sheet."
     * If a generic pricing question was asked without naming a project (e.g. "what is the price?"):
       State: "Prices may vary based on floor, configuration, and payment terms — please contact our sales team at +91 9730397979 for the latest price sheet." You may also ask which project they are interested in.
   - When asked about BROCHURE, FLOOR PLANS, MASTER PLANS, or DOWNLOADS (e.g. "Download Brochure", "brochure", "broucher"):
     Guide the customer on obtaining project brochures and floor plans. If a specific active project was just discussed, offer brochure and layout information for that project; otherwise mention all 3 active ongoing projects (The Curve, Samsara, Pebbles Business Bay). Direct them to our sales team or invite them to share their details below to receive the PDF brochure directly via WhatsApp/email. NEVER give the pricing disclaimer for a brochure request!
   - CONFIGURATION MATCHING RULES (STRICT & MANDATORY):
     * When asked about "3 BHK" (or "3bhk", "3 bedroom", "three bhk"):
       Recommend our active ongoing projects that offer 3 BHK residences:
       • The Curve (Virar West, Mumbai)
         (thecurvevirar.com)
       • Samsara (Mukund Nagar, Pune)
         (abhinavgroup.co.in/samsara)

     * When asked about "2 BHK" (or "2bhk", "2 bedroom", "two bhk"):
       Recommend our active ongoing project that features 2 BHK apartments:
       • The Curve (Virar West, Mumbai)
         (thecurvevirar.com)
       (Never include Samsara for 2 BHK inquiries, as Samsara exclusively offers 3 BHK).

     * CONFIGURATION SWITCHING:
       If the customer previously asked for "2 BHK" and now asks "i want 3 bhk" (or vice versa), treat this as a NEW, FRESH requirement.
       NEVER combine them into "For 2 BHK and 3 BHK" and NEVER recycle only the previously listed projects.
       Provide the full, fresh recommendations matching the new configuration!
5. Clearly distinguish between ACTIVE ONGOING projects and COMPLETED legacy projects
6. ALWAYS respond in the same language the customer used (English, Hindi, or Roman Hindi)
7. FORMATTING RULE: Keep answers clean, conversational, and easy to read. NEVER use markdown heading hashes (like ### or ##) and NEVER use horizontal divider lines (like --- or ***). Use clean bullet points (- or •) and bold text sparingly for headings.
8. QUICK ACTION BUTTONS:
   - "Explore Projects" / "Projects" / "All Projects" (or "प्रोजेक्ट देखें", "प्रोजेक्ट्स"):
     MUST ALWAYS be treated as a global portfolio reset. REGARDLESS of whatever was discussed in previous turns, you MUST respond in this exact format, with "Here are our current active ongoing projects:" header and each project link on the next line:
     Here are our current active ongoing projects:

     • The Curve (Virar West, Mumbai)
       (thecurvevirar.com)

     • Samsara (Mukund Nagar, Pune)
       (abhinavgroup.co.in/samsara)

     • Pebbles Business Bay (Wakad, Pune)
       (pebblesbusinessbay.com)

     Closing line: "Would you like to know more about any specific project or schedule a site visit?"
     Keep it short, clean, and conversational — DO NOT dump full specifications or lengthy details all in one go!

   - "Careers & Jobs" / "Careers" (or "करियर और नौकरियां"):
     Respond ONLY with:
     "For job openings and vacancies, you can contact us at:

📧 careers@abhinavinfra.com"

   - "Become a Supplier" / "Supplier" / "Vendor" (or "सप्लायर बनें"):
     Respond ONLY with:
     "You can contact our Purchase Department:

Phone: +91 721 955 0020, +91 721 955 0051
Email: purchase@abhinavinfra.com"

   - "Contact Our Team" / "Contact Us" (or "हमारी टीम से संपर्क करें"):
     Provide the complete, official directory:
     "Here is the official contact directory for Abhinav Group:

• Corporate Head Office: 020-25663051 | info@abhinavgroup.co.in
• Sales (Pune - Samsara & Pebbles Business Bay): +91 9730397979
• Sales (Virar - The Curve): +91 97307 00667
• Purchase / Vendors: +91 721 955 0020 / +91 721 955 0051
• Careers / HR: careers@abhinavinfra.com"

9. PROJECT INQUIRIES & INTRODUCTIONS:
   - When a user asks about a project (e.g. "tell me about Samsara", "tell me about The Curve", "tell me about Pebbles Business Bay", "smasara", "pebbles greenfield"):
     Line 1 MUST ALWAYS introduce THAT specific project (name, location, and key features).
     STRICT PROJECT ISOLATION: Focus 100% EXCLUSIVELY on the requested project. NEVER mention, repeat, re-introduce, or describe any previously discussed project (such as Samsara or any other project) unless the user explicitly requested a comparison between them (e.g. "compare Samsara and The Curve").
     CLOSING LINE:
     * If the user specifically asked about PRICING / COST / BUDGET, close with:
       - For Samsara, Pebbles Greenfield, or Pebbles Business Bay: "Prices may vary based on floor, configuration, and payment terms — please contact our sales team at +91 9730397979 for the latest price sheet."
       - For The Curve: "Prices may vary based on floor, configuration, and payment terms — please contact our sales team at +91 97307 00667 for the latest price sheet."
     * If the user asked a GENERAL project question (did NOT ask for price), close with a warm sales contact invite:
       - For Samsara, Pebbles Greenfield, or Pebbles Business Bay: "For complete details or to schedule a site visit, please contact our sales team at +91 9730397979 or email sales@abhinavinfra.com."
       - For The Curve: "For complete details or to schedule a site visit, please contact our sales team at +91 97307 00667 or email sales@abhinavinfra.com."
       Do NOT append the pricing disclaimer if the user did not ask about price!
     NEVER start Line 1 with a pricing disclaimer.

13. JOB & CAREER ENQUIRIES:
   - If the user asks about jobs, vacancies, openings, careers, hiring, internships, or employment, respond ONLY with:
     "For job openings and vacancies, please contact us at: 📧 careers@abhinavinfra.com"
   - Do NOT direct them to the sales team for career enquiries.

14. VENDOR, SUPPLIER & PURCHASE ENQUIRIES:
   - If the user asks about selling products, supplying materials, vendor registration, procurement, purchase department, contractors, or anything related to supplying goods to Abhinav Group, respond ONLY with:
     "For vendor and supplier enquiries, please contact our Purchase Department:
     📞 +91 721 955 0020 / +91 721 955 0051
     📧 purchase@abhinavinfra.com"
   - Do NOT direct them to the sales team for vendor/purchase enquiries.

10. CONVERSATION CONTEXT & TOPIC SWITCHING:
   - Carefully determine if the user's message is a FOLLOW-UP or a NEW TOPIC:
     * FOLLOW-UP: The user asks an incomplete or contextual question about the ongoing subject just discussed (e.g., "what is the location?", "what are the amenities?", "pricing?"). Answer ONLY the specific requested detail for that subject.
     * NEW TOPIC / TOPIC SWITCH: If the user asks about a different location, project, configuration, or subject (e.g. asking for "The Curve" after discussing "Samsara", or asking for "2 BHK in Pune" after discussing "Virar"), focus 100% on the NEW question. Do NOT repeat, summarize, contrast with, or mention previous projects. Treat the new project inquiry independently!
   - Never answer unasked previous questions or re-introduce past topics.

11. PROPORTIONAL RESPONSE LENGTH (MATCH THE QUESTION SIZE):
   - Scale the length of your response directly to the user's question:
     * Brief/Simple Question (e.g. "who is Abhijit Kotkar?", "where is the office?", "what is the location?"): Provide a concise, direct 1 to 2 sentence answer.
     * Specific Detail (e.g. amenities, RERA, possession): Provide 2 to 4 clean bullet points.
     * Broad Inquiry (e.g. "Tell me about The Curve", "Explore projects"): Provide a moderate, well-structured overview.
   - Never generate overwhelming walls of text. Be direct, helpful, and concise.

12. CONVERSATION FLOW — NO REPETITIVE PREAMBLES:
   - In multi-turn conversations, NEVER repeat the generic company founding biography ("Abhinav Group is a premier real estate developer headquartered in Pune, Maharashtra, with over 27 years of excellence since our founding in 1997, having delivered 50 lakh sq. ft..." etc.) in consecutive answers.
   - The FIRST answer in a conversation may introduce the company if the user asks about it.
   - ALL follow-up questions MUST be answered DIRECTLY without re-introducing the company background.
   - Examples of CORRECT behavior:
     * User asks "what does Abhinav Group do?" → Full company intro is appropriate.
     * User then asks "what are the services?" → Jump STRAIGHT to listing services. Do NOT repeat the founding story.
     * User then asks "in which cities?" → Answer DIRECTLY: "Our properties are located in Pune, Maharashtra and Mumbai MMR (Virar West)." No preamble paragraphs.
   - When the user asks a simple factual follow-up, give a concise direct answer. Do NOT pad it with previously stated information.

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
- Sales & Escalation Hotline (Samsara, Pebbles Greenfield, Pebbles Business Bay): +91 9730397979
- Sales Hotline (The Curve, Virar West): +91 97307 00667
- Official Sales Email: sales@abhinavinfra.com
- General Inquiries Email: info@abhinavgroup.co.in
- Careers / HR Email: careers@abhinavinfra.com
- Purchase Department (Vendor/Supplier Enquiries): +91 721 955 0020 / +91 721 955 0051 | purchase@abhinavinfra.com
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
1. The Curve — Crown of Grandeur (Residential — Premium Mega-Development)
   OFFICIAL PROJECT NAME: The Curve-Crown of Grandeur
   - Official Project Website: https://thecurvevirar.com/
   - MahaRERA Reg No.: PR1240002600667
   - Project Type: Premium residential mega-development
   - Total Units: 936 units across 2 phases
   - Land Size: 4 Acres (Freehold land title)
   - Construction Technology: RCC with Aluform Technology
   - Possession: June 2031 (as per RERA)
   - Building Structure: G+3 Podium + 30 Floors
   - Floor-to-Ceiling Height: 9.5 ft

   LOCATION & ADDRESS:
   - Full Address: Agashi Road, VIVA City, Bolinj, Virar West, Vasai-Virar, Maharashtra 401303
   - Distance from Virar Railway Station: 7 minutes
   - Distance from BKC / Andheri / Borivali / Lower Parel: approximately 35 minutes
   - Nearby Public Transport: Rickshaw available
   - Upcoming Infrastructure Benefits: Bullet Train, Mumbai-Ahmedabad Expressway, Coastal Road, Virar-Panvel Multi-Modal Corridor, Vadhvan Port, Palghar Airport, Metro Lines

   NEARBY LANDMARKS:
   - Reputed Schools: Muljibhai Mehta International School, Matrix Academy School, National English School, Royal Academy School
   - Hospitals: Prakriti Hospital, Rural Hospital, Siddhai Multispeciality Hospital, Wellcare Multispeciality Hospital, Shree Sai Hospital
   - Malls & Entertainment: Club One, Visara Water Park, Yazoo Park, Arnala Beach, Capital Mall

   UNIT CONFIGURATIONS & SIZES:
   - Configurations Available: 2 BHK and 3 BHK
   - Carpet Areas: 2 BHK — 625 sq.ft | 3 BHK Premium — 800 sq.ft | 3 BHK Luxury — 874 sq.ft
   - All Flats: Premium facing (all apartments have premium views)
   - Vastu Compliant: Yes
   - Lifts & Staircases: 5 Lifts and 2 Staircases per wing
   - Refuge / Special Floors: 4th, 9th, 14th, 24th & 29th floor are refuge floors; 19th floor has fire tank
   - Bare Shell Option: Not available (no bare shell)

   DESIGN & ARCHITECTURE:
   - Principal Architect: Studio Arcon Architects
   - RCC Consultants: Strudcom Consultants Pvt. Ltd.
   - MEP Consultant: Unicorn M.E.P Consultants Pvt. Ltd.
   - Landscape Consultant: Designterra Landscape Consultants

   AMENITIES & LIFESTYLE:
   - Lifestyle Positioning: Andheri/Borivali style premium mega residential — modern lifestyle with thoughtfully planned spaces
   - Amenities: Swimming Pool, Banquet Hall, Gymnasium, Badminton Court, Children's Play Area, Multipurpose Court, Co-working Space, Calisthenics Exercise Court, Kids Café, Senior Citizen Court, Yoga & Dance Studio, Star Gazing Deck, Indoor Games
   - Amenity Area: Fully vehicle-free
   - Retail/High Street within project: Not available
   - Dedicated Temple/Spiritual Space: Not available

   SPECIFICATIONS & INTERIORS:
   - Flooring: Vitrified flooring 1200x600 mm
   - Sanitary Ware: CERA / TOTO or equivalent
   - Modular Kitchen: Not provided
   - White Goods / Appliances: Not included
   - Geysers in Bathrooms: Not provided
   - Piped Gas: Not available
   - Rainwater Harvesting: Yes, provided
   - EV Charging Points in Parking: Yes, available

   PARKING:
   - Parking Type: Podium — Surface Parking
   - Car Park Allotment: 3 BHK — 1 dedicated car park included | 2 BHK — Optional car park

   PRICING & FINANCIALS:
   - Base Sale Price (BSP): Rs. 10,800 per sq.ft
   - Pricing vs Andheri/Borivali: Yes — positioned as much more attractive entry pricing vs comparable standards
   - Payment Plan: CLP (Construction Linked Payment)
   - Pre-Launch Offers: Yes — early access customers will receive exclusive pre-launch offers
   - Stamp Duty: 7% | Registration: Rs. 30,000 | GST: 5%
   - Preferred Location Charge (PLC): Yes, applicable
   - Cancellation Charges: As per RERA guidelines
   - Down Payment Discount: Not available

   HOME LOAN & BOOKING PROCESS:
   - Pre-Approved Banks: SBI, HDFC, ICICI, Bajaj, Mahindra, IIFL, Axis Bank
   - Home Loan Assistance: Yes, provided
   - Can Register After Paying 5%: Yes — subject to 95% loan sanction letter
   - Documents Required to Book: Aadhaar Card and PAN Card
   - Booking Amount: Rs. 2,00,000 (Rupees Two Lakhs)
   - Payment Gateway: All payment gateways available (NEFT/RTGS/online)
   - Unit Change After Booking: Yes — allowed before registration
   - Agreement Signing: Within 15 days from the booking date

   SALES CONTACT FOR THE CURVE:
   - Sales Team: +91 97307 00667 | sales@abhinavinfra.com
   - Sales Lounge: Agashi Road, Next to VIVA City, Bolinj, Virar West, Mumbai MMR – 401303

2. Samsara (Residential — Luxury)
   - Official Project Website: https://abhinavgroup.co.in/samsara/
   - Location: Mukund Nagar, Central Pune, Maharashtra
   - Configurations: Ultra-luxury 3 BHK residences
   - Highlights: Premium central Pune address, landscaped terrace deck, modern clubhouse, fully equipped gymnasium, high-speed elevators, 24x7 multi-tier security
   - MahaRERA Reg No.: P52100079797
   - Price: Contact sales team for current inventory and pricing (+91 9730397979)

3. Pebbles Business Bay (Commercial — Retail & Corporate Offices)
   - Official Project Website: https://pebblesbusinessbay.com/
   - Location: Sr. No. 132(P), 121(P), Opp. Phoenix Mall of the Millennium, Near My Car Showroom / Bhumkar Chowk, Wakad, Pune – 411057
   - Configurations: High-street retail showrooms, boutique commercial spaces & Grade-A corporate offices
   - Highlights: High footfall location in Wakad's premier commercial corridor, immense highway visibility, expansive glass facade, high-speed elevators, ample customer & tenant parking
   - Status: Active ongoing commercial development
   - Leasing & Sales: Contact sales team at +91 9730397979

=============================================================================
COMPLETED LANDMARKS & LEGACY PORTFOLIO
=============================================================================
1. AEROMALL (Commercial Landmark — Fully Delivered & Operational)
   - Location: 333, Domestic Airport Road, Survey No. 235, Pune International Airport Area, Lohegaon / Viman Nagar, Pune – 411032
   - Type: Pune's first 24x7 integrated multi-level car parking (MLCP) and prime retail, dining & passenger transit hub
   - Status: COMPLETED & OPERATIONAL (Not ongoing)

2. COMPLETED RESIDENTIAL PROJECTS:
   - Pebbles Greenfield: Tathawade / Wakad, Pune (Delivered landmark community featuring 2 & 3 BHK apartments)
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
  For job openings, vacancies, or career enquiries, candidates must contact: careers@abhinavinfra.com
- Vendor & Supplier / Purchase Department:
  For vendor registration, supplier tie-ups, procurement, or contractor inquiries, contact our Purchase Department:
  Phone: +91 721 955 0020 / +91 721 955 0051
  Email: purchase@abhinavinfra.com
- Media & Recognition:
  Covered extensively in real estate and infrastructure news for delivering Aeromall at Pune International Airport, green building innovations, and customer trust milestones over 27+ years.

=============================================================================
ACTIVE PROJECT SALES CONTACTS (USE CORRECT NUMBER PER PROJECT)
=============================================================================
- Samsara, Pebbles Greenfield, Pebbles Business Bay:
  Sales Team: +91 9730397979 | sales@abhinavinfra.com
- The Curve (Virar West, Mumbai MMR):
  Sales Team: +91 97307 00667 | sales@abhinavinfra.com

=============================================================================
ESCALATION & LEAD CAPTURE
=============================================================================
When a customer requests pricing, site visits, or wants human assistance:
- For Samsara, Pebbles Greenfield, or Pebbles Business Bay: "For complete details, current pricing, or to schedule a site visit, please contact our sales team at +91 9730397979 or email sales@abhinavinfra.com."
- For The Curve: "For complete details, current pricing, or to schedule a site visit, please contact our sales team at +91 97307 00667 or email sales@abhinavinfra.com."
Offer to connect them or take their name and mobile number.
"""

ACTIVE_PROJECT_CARDS: Dict[str, Dict[str, Any]] = {
    "curve": {
        "id": "curve",
        "name": "The Curve — Elite Tower",
        "location": "Bolinj, Virar West, Mumbai MMR",
        "config": "2 & 3 BHK Residences",
        "image_url": "/static/images/projects/the-curve.jpg",
        "url": "https://thecurvevirar.com/",
    },
    "samsara": {
        "id": "samsara",
        "name": "Samsara — Luxury Residences",
        "location": "Mukund Nagar, Central Pune",
        "config": "3 BHK Ultra-Luxury",
        "image_url": "/static/images/projects/samsara.jpg",
        "url": "https://abhinavgroup.co.in/samsara/",
    },
    "business_bay": {
        "id": "business_bay",
        "name": "Pebbles Business Bay",
        "location": "Wakad, Pune (Opp. Phoenix Mall)",
        "config": "Retail Showrooms & Grade-A Offices",
        "image_url": "/static/images/projects/pebbles-business-bay.jpg",
        "url": "https://pebblesbusinessbay.com/",
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
            reply = self._out_of_scope_response(user_message, language)
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
        u_clean = user_message.strip().lower()
        if u_clean in ["contact our team", "contact team", "contact directory", "हमारी टीम से संपर्क करें", "contact our sales team"]:
            if language == "hi":
                reply = (
                    "अभिनव ग्रुप की आधिकारिक संपर्क डायरेक्टरी:\n\n"
                    "• कॉर्पोरेट हेड ऑफिस: 020-25663051 | info@abhinavgroup.co.in\n"
                    "• सेल्स (पुणे - Samsara और Pebbles Business Bay): +91 9730397979\n"
                    "• सेल्स (विरार - The Curve): +91 97307 00667\n"
                    "• परचेज / वेंडर्स: +91 721 955 0020 / +91 721 955 0051\n"
                    "• करियर / एचआर: careers@abhinavinfra.com"
                )
            else:
                reply = (
                    "Here is the official contact directory for Abhinav Group:\n\n"
                    "• Corporate Head Office: 020-25663051 | info@abhinavgroup.co.in\n"
                    "• Sales (Pune - Samsara & Pebbles Business Bay): +91 9730397979\n"
                    "• Sales (Virar - The Curve): +91 97307 00667\n"
                    "• Purchase / Vendors: +91 721 955 0020 / +91 721 955 0051\n"
                    "• Careers / HR: careers@abhinavinfra.com"
                )
            await self._persist_messages(conversation, user_message, reply, language, "escalation")
            return {
                "reply": reply,
                "language": language,
                "intent": "escalation",
                "quick_replies": self._get_quick_replies("escalation", language),
                "is_fallback": False,
            }

        if u_clean in ["explore projects", "projects", "all projects", "प्रोजेक्ट देखें", "प्रोजेक्ट्स"]:
            # Clean portfolio reset: do not bleed previous discussion into a generic Explore Projects request
            ai_messages = [AIMessage(role="user", content=user_message)]
        elif u_clean in ["speak to sales", "contact sales", "call sales", "sales team से बात करें", "सेल्स टीम से बात करें"]:
            # Clean sales escalation: do not bleed previous brochure talk into Speak to Sales
            ai_messages = [AIMessage(role="user", content=user_message)]
        elif any(k in u_clean for k in ["3 bhk", "3bhk", "three bhk", "3 bedroom"]) and not any(k in u_clean for k in ["2 bhk", "2bhk"]):
            # Clean 3 BHK query: reset to evaluate all 3 BHK projects fresh without anchoring on previous responses
            ai_messages = [AIMessage(role="user", content=user_message)]
        elif any(k in u_clean for k in ["2 bhk", "2bhk", "two bhk", "2 bedroom"]) and not any(k in u_clean for k in ["3 bhk", "3bhk"]):
            # Clean 2 BHK query: reset to evaluate all 2 BHK projects fresh without anchoring on previous responses
            ai_messages = [AIMessage(role="user", content=user_message)]
        else:
            # Check if user is explicitly focusing on a specific active project
            current_project_key = None
            if "curve" in u_clean or "virar" in u_clean:
                current_project_key = "curve"
            elif "samsara" in u_clean:
                current_project_key = "samsara"
            elif "greenfield" in u_clean or ("pebbles" in u_clean and "bay" not in u_clean):
                current_project_key = "greenfield"
            elif "business bay" in u_clean or "pbb" in u_clean:
                current_project_key = "business_bay"

            is_comparison = any(w in u_clean for w in ["compare", "difference", "versus", "vs", "which is", "better", "both"])

            if current_project_key and not is_comparison:
                # User is asking about a single specific project.
                # Only retain history if recent messages were already discussing THIS same project.
                # Otherwise, reset cleanly for the new project to prevent bleeding past project descriptions.
                has_current_in_history = any(
                    (m.role == MessageRole.ASSISTANT and m.mentioned_project_ids and current_project_key in m.mentioned_project_ids)
                    for m in recent_messages
                )
                if has_current_in_history:
                    filtered_history = [
                        m for m in recent_messages
                        if not (m.role == MessageRole.ASSISTANT and m.mentioned_project_ids and current_project_key not in m.mentioned_project_ids)
                    ]
                    ai_messages = [AIMessage(role=m.role, content=m.content) for m in filtered_history]
                    ai_messages.append(AIMessage(role="user", content=user_message))
                else:
                    ai_messages = [AIMessage(role="user", content=user_message)]
            else:
                ai_messages = [AIMessage(role=m.role, content=m.content) for m in recent_messages]
                ai_messages.append(AIMessage(role="user", content=user_message))

        # --- Step 5: Build effective system prompt with language directive ---
        effective_prompt = SYSTEM_PROMPT
        if recent_messages:
            effective_prompt += (
                "\n\nFOLLOW-UP RESPONSE RULE: This is an ongoing conversation. "
                "Do NOT re-introduce the company or repeat the 1997 founding bio. "
                "Answer the user's latest question directly and conversationally!"
            )
        if language == "hi":
            # Determine if Devanagari or Roman Hindi / Hinglish
            hindi_chars = sum(1 for c in user_message if "\u0900" <= c <= "\u097f")
            if hindi_chars > 2:
                effective_prompt += (
                    "\n\nCRITICAL LANGUAGE DIRECTIVE: The customer is writing in Hindi (Devanagari script). "
                    "You MUST reply in Hindi (Devanagari script). Keep project names (Samsara, Pebbles Greenfield, "
                    "The Curve, Pebbles Business Bay), location names (Mukund Nagar, Tathawade, Wakad, Virar West), "
                    "MahaRERA numbers, and the sales phone numbers (+91 9730397979 / +91 97307 00667) in English. "
                    "But all explanations and sentences must be in Hindi Devanagari."
                )
            else:
                effective_prompt += (
                    "\n\nCRITICAL LANGUAGE DIRECTIVE: The customer is speaking in Roman Hindi / Hinglish. "
                    "You MUST reply in natural, conversational Roman Hindi (Hinglish). "
                    "Keep project names (Samsara, Pebbles Greenfield, The Curve, Pebbles Business Bay), "
                    "location names (Mukund Nagar, Tathawade, Wakad, Virar West), MahaRERA numbers, "
                    "and the sales phone numbers (+91 9730397979 / +91 97307 00667) in English. "
                    "But explain everything else in Roman Hindi. "
                    "Example tone: 'The Curve ek elite residential project hai jo Bolinj, Virar West mein hai.' "
                    "NEVER reply in pure formal English when the customer speaks Hinglish."
                )

        # --- Step 6: Call AI provider (with graceful fallback) ---
        ai_response = None
        is_fallback = False
        try:
            ai_response = await self.ai.chat(
                messages=ai_messages,
                system_prompt=effective_prompt,
                max_tokens=settings.ai_max_tokens,
                temperature=settings.ai_temperature,
            )
            reply = ai_response.content
            if ai_response.is_fallback:
                is_fallback = True
                smart_fallback = self._get_verified_knowledge_response(user_message, language)
                if smart_fallback:
                    reply = smart_fallback
        except Exception as e:
            logger.error(f"ai_provider_error: {e} (provider={self.ai.provider_name})")
            smart_fallback = self._get_verified_knowledge_response(user_message, language)
            reply = smart_fallback or self._ai_unavailable_response(language)
            is_fallback = True

        # Clean formatting: strip raw markdown header hashes (###) and horizontal dividers (---, ***)
        import re
        reply = re.sub(r'^[#]{1,6}\s*', '', reply, flags=re.MULTILINE)
        reply = re.sub(r'^[*\-_]{3,}\s*$', '', reply, flags=re.MULTILINE)
        reply = re.sub(r'\*{3,}', '', reply)
        reply = re.sub(r'\n{3,}', '\n\n', reply).strip()

        # --- Step 7: Select Project Card (if appropriate & not previously shown) ---
        project_cards = self._select_project_cards(user_message, reply, recent_messages)
        mentioned_ids = [c["id"] for c in project_cards] if project_cards else None

        # --- Step 8: Persist messages ---
        response_time_ms = int((time.monotonic() - start_time) * 1000)
        await self._persist_messages(
            conversation, user_message, reply, language, intent,
            tokens_used=ai_response.tokens_used if ai_response else None,
            model_used=ai_response.model if ai_response else None,
            response_time_ms=response_time_ms,
            is_fallback=is_fallback,
            mentioned_project_ids=mentioned_ids,
        )

        # --- Step 9: Determine quick replies ---
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
        """Detect if message is in Hindi (Devanagari or Roman Hindi / Hinglish) or English."""
        # Tier 1: Devanagari script detection (Hindi / Marathi)
        hindi_chars = sum(1 for c in text if "\u0900" <= c <= "\u097f")
        if hindi_chars > 2:
            return "hi"

        # Tier 2: Roman Hindi / Hinglish detection (3-level word matching)
        words = set(text.lower().split())

        # Strong markers — a SINGLE match confirms Hinglish
        strong_markers = {
            # Pronouns & requests
            "mujhe", "muzhe", "muje", "hume", "humko", "humein",
            "chahiye", "chaiye", "chahie",
            # Verbs (imperative / conversational)
            "batao", "bataiye", "bataao", "bataye", "batana",
            "dikhao", "dikhaiye", "dikhaye", "dikhana",
            "bhejo", "bhejiye", "bhejdo", "bhejna",
            # Greetings
            "namaste", "namaskar", "dhanyawad", "shukriya",
            # Adjectives / affirmations
            "accha", "acha", "theek", "thik", "badhiya", "shandar",
            # Question words (full forms)
            "kahan", "kahaan", "kaha", "kidhar",
            "kaisa", "kaisi", "kaise",
        }
        if words & strong_markers:
            return "hi"

        # Medium markers — need 2 matches, OR 1 medium + 1 light
        medium_markers = {
            # Question / auxiliary words
            "kya", "hai", "hain", "tha", "thi",
            "kitna", "kitne", "kitni",
            "kab", "kon", "kaun",
            # Negation / affirmation
            "nahi", "nhi", "mat", "haan", "ji",
            # Possessives
            "aapka", "aapke", "aapki", "mera", "mere", "meri",
            # Nouns
            "ghar", "paisa", "paise", "daam",
            # Verbs (short forms)
            "bata", "bolo", "bol", "dijiye", "dedo", "dena",
            "dekhna", "dekho", "dekh",
            "lena", "lo", "lelo",
            # Qualifiers
            "wala", "wali", "wale",
            "abhi", "jaldi", "pehle",
            "sab", "sabhi", "bahut", "bohot", "zyada",
            "yahan", "wahan", "idhar", "udhar",
            # Conjunctions
            "aur", "lekin", "toh", "phir",
        }

        # Light markers — common Hinglish connectors (ambiguous alone)
        light_markers = {
            "ke", "ka", "ki", "ko", "se", "me", "mein",
            "pe", "par", "ye", "wo", "yeh", "woh",
            "iska", "iski", "iske", "uska", "uski", "uske",
        }

        medium_hits = len(words & medium_markers)
        light_hits = len(words & light_markers)

        # 2+ medium markers = Hinglish
        if medium_hits >= 2:
            return "hi"
        # 1 medium + 1 light = Hinglish
        if medium_hits >= 1 and light_hits >= 1:
            return "hi"
        # 3+ light markers together = Hinglish
        if light_hits >= 3:
            return "hi"

        return "en"

    def _detect_intent(self, text: str) -> str:
        """Basic intent detection. Phase 5 replaces this with LLM-based classification."""
        import re
        t = text.lower().strip()
        words = set(re.findall(r'\b\w+\b', t))

        # Out of scope — checked FIRST to prevent any AI call
        oos_keywords = [
            "career", "job", "vacancy", "vacancies", "opening", "openings",
            "vendor", "supplier", "contractor", "recruitment", "intern", "internship",
            "hiring", "procurement", "empanel"
        ]
        is_purchase_dept = "purchase" in t and any(w in t for w in ["dept", "department", "team", "contact", "head", "office"])
        is_sell_product = any(phrase in t for phrase in ["sell product", "sell material", "selling product", "material supply", "product sell", "tie up", "tie-up", "maal bechna", "saman bechna"])
        if any(w in t for w in oos_keywords) or "hr" in words or is_purchase_dept or is_sell_product:
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

    def _out_of_scope_response(self, text_or_lang: str = "", language: str = "en") -> str:
        if text_or_lang in ("en", "hi"):
            lang = text_or_lang
            text = ""
        else:
            text = text_or_lang
            lang = language

        t = text.lower().strip()
        words = set(t.split())

        # 1. Career / Job / Vacancy / Openings
        career_keywords = [
            "job", "jobs", "vacancy", "vacancies", "opening", "openings",
            "career", "careers", "hiring", "recruitment", "apply", "resume",
            "cv", "intern", "internship", "employment", "naukri", "staff"
        ]
        if any(w in t for w in career_keywords) or "hr" in words:
            if lang == "hi":
                return (
                    "नौकरी और करियर के अवसरों (job openings / vacancy) के लिए, कृपया हमसे संपर्क करें:\n\n"
                    "📧 careers@abhinavinfra.com"
                )
            return (
                "For job openings and vacancies, you can contact us at:\n\n"
                "📧 careers@abhinavinfra.com"
            )

        # 2. Purchase / Procurement / Vendor / Supplier / Selling Products
        vendor_keywords = [
            "vendor", "supplier", "supply", "supplies", "procurement",
            "contractor", "empanel", "tie up", "tie-up", "sell product",
            "sell material", "selling", "material supply", "wholesale", "distributor"
        ]
        is_purchase_dept = "purchase" in t and any(w in t for w in ["dept", "department", "team", "contact", "head", "office"])
        if any(w in t for w in vendor_keywords) or is_purchase_dept or "purchase department" in t:
            if lang == "hi":
                return (
                    "आप हमारे Purchase Department से संपर्क कर सकते हैं:\n\n"
                    "फोन: +91 721 955 0020, +91 721 955 0051\n"
                    "ईमेल: purchase@abhinavinfra.com"
                )
            return (
                "You can contact our Purchase Department:\n\n"
                "Phone: +91 721 955 0020, +91 721 955 0051\n"
                "Email: purchase@abhinavinfra.com"
            )

        # 3. General other out of scope
        if lang == "hi":
            return (
                "मैं केवल अभिनव ग्रुप की प्रॉपर्टी और रियल एस्टेट से संबंधित प्रश्नों में "
                "सहायता करता हूं।\n\n"
                "अन्य पूछताछ के लिए हमारे कार्यालय से संपर्क करें:\n"
                "📞 020-25663051\n"
                "🌐 abhinavgroup.co.in"
            )
        return (
            "I'm here to help specifically with Abhinav Group's properties and real estate enquiries.\n\n"
            "For other corporate matters, please contact our office:\n"
            "📞 020-25663051\n"
            "🌐 abhinavgroup.co.in"
        )

    def _ai_unavailable_response(self, language: str) -> str:
        if language == "hi":
            return (
                "हमारा AI असिस्टेंट अभी उपलब्ध नहीं है। कृपया हमारी सेल्स टीम से "
                "सीधे संपर्क करें:\n"
                "📞 +91 9730397979\n"
                "📧 sales@abhinavinfra.com"
            )
        return (
            "Our AI assistant is temporarily unavailable. Please contact our sales team:\n"
            "📞 +91 9730397979\n"
            "📧 sales@abhinavinfra.com\n\n"
            "Available Monday to Saturday, 10 AM – 7 PM"
        )

    def _get_verified_knowledge_response(self, text: str, language: str) -> Optional[str]:
        """Provides verified corporate and project facts directly if AI provider is temporarily unreachable."""
        t = text.lower().strip()

        # Mayuri Shende Kankariya
        if any(w in t for w in ["mayuri", "commercial leasing director"]):
            if language == "hi":
                return (
                    "Mrs. Mayuri Shende Kankariya अभिनव ग्रुप में Director & Head of Commercial Leasing हैं। "
                    "वे स्ट्रेटेजिक ब्रांडिंग, सॉफ्टवेयर डेवलपमेंट और लीजिंग में विशेषज्ञता रखती हैं और ग्रुप के "
                    "कमर्शियल लीजिंग, ब्रांड कम्युनिकेशन और डिजिटल प्रेजेंस का नेतृत्व करती हैं।"
                )
            return (
                "Mrs. Mayuri Shende Kankariya is a Director and Head of Commercial Leasing at Abhinav Group. "
                "With an entrepreneurial background in strategic branding, software development, and leasing, "
                "she oversees commercial leasing, brand communication, and the digital presence across Abhinav Group."
            )

        # Shamkant Shende / Sham Shende / Founder / Chairman / CEO
        if any(w in t for w in ["sham", "shamkant", "founder", "chairman", "ceo"]):
            if language == "hi":
                return (
                    "Mr. Shamkant Shende (Mr. Sham Shende) अभिनव ग्रुप के Founder, Chairman, Architect & Visionary Leader हैं। "
                    "वे एक अनुभवी आर्किटेक्ट हैं और 1997 से पिछले 27+ वर्षों से समय पर प्रोजेक्ट डिलीवरी, "
                    "फाइनेंशियल प्लानिंग और कस्टमर संतुष्टि का उत्कृष्ट ट्रैक रिकॉर्ड रखते हैं।"
                )
            return (
                "Mr. Shamkant Shende (Mr. Sham Shende) is the Founder, Chairman, Architect, and Visionary Leader of Abhinav Group. "
                "A hands-on architect and leader with over 27+ years of track record since 1997, he oversees architectural innovation, "
                "meticulous financial planning, and timely project delivery."
            )

        # Gaurav Kankariya
        if "gaurav" in t or "kankariya" in t:
            if language == "hi":
                return (
                    "Mr. Gaurav Kankariya अभिनव ग्रुप में Director हैं। उनके पास हाई-एंड इंटीरियर आर्किटेक्चर "
                    "और रियल एस्टेट में 17+ वर्षों का अनुभव है। उनका मानना है कि 'Design is a journey rather than the destination'।"
                )
            return (
                "Mr. Gaurav Kankariya is a Director at Abhinav Group with over 17+ years of dynamic experience in high-end interior architecture "
                "and real estate development. His design philosophy is rooted in the belief that 'Design is a journey rather than the destination'."
            )

        # Abhijit Kotkar
        if "abhijit" in t or "kotkar" in t:
            if language == "hi":
                return (
                    "Mr. Abhijit Kotkar अभिनव ग्रुप में Executive Director (MBA in Finance) हैं, जिनके पास रियल एस्टेट में 17+ वर्षों का अनुभव है। "
                    "उन्होंने पुणे एयरपोर्ट पर 24x7 ऑपरेशनल 'AEROMALL' प्रोजेक्ट का नेतृत्व किया।"
                )
            return (
                "Mr. Abhijit Kotkar is an Executive Director at Abhinav Group (MBA in Finance) with over 17+ years of experience across India and Sri Lanka. "
                "He spearheaded 'AEROMALL', Pune's first 24x7 operational airport MLCP and transit retail hub."
            )

        # Pranali Kotkar
        if "pranali" in t:
            if language == "hi":
                return (
                    "Mrs. Pranali Kotkar अभिनव ग्रुप में Director हैं। उन्होंने सिंगापुर से इंटीरियर आर्किटेक्चर में उच्च शिक्षा प्राप्त की है "
                    "और वर्तमान में कंस्ट्रक्शन व परचेज डिपार्टमेंट का नेतृत्व करती हैं।"
                )
            return (
                "Mrs. Pranali Kotkar is a Director at Abhinav Group. With higher education in Interior Architecture from Singapore, "
                "she currently leads Abhinav Group's Construction and Purchase departments."
            )

        # Leadership team overview
        if any(w in t for w in ["leader", "leadership", "directors", "board of directors"]):
            return (
                "Abhinav Group is guided by an experienced executive board:\n"
                "• Mr. Shamkant Shende (Founder, Chairman & Visionary Leader)\n"
                "• Mr. Abhijit Kotkar (Executive Director)\n"
                "• Mrs. Pranali Kotkar (Director - Construction & Purchase)\n"
                "• Mr. Gaurav Kankariya (Director - Architecture & Design)\n"
                "• Mrs. Mayuri Shende Kankariya (Director & Head of Commercial Leasing)\n\n"
                "For more details, contact our office at 020-25663051 or sales@abhinavinfra.com."
            )

        # Financials / Net worth / Profit / Revenue / Turnover
        if any(w in t for w in ["networth", "net worth", "profit", "profitable", "revenue", "turnover", "how much does abhinav group make", "makes"]):
            return (
                "As a premier real estate developer, Abhinav Group is a private organization, and we do not publicly disclose internal financial statements, "
                "net worth, or profit margins.\n\n"
                "Backed by over 27 years of excellence since 1997 and over 50 lakh sq. ft. of landmark developments delivered across 20+ projects, our focus remains on "
                "architectural quality and customer trust. If you have questions about our ongoing residential or commercial projects, our sales team (+91 9730397979) will gladly assist you."
            )

        # Explore Projects fallback
        if t in ["explore projects", "projects", "all projects", "प्रोजेक्ट देखें", "प्रोजेक्ट्स"]:
            if language == "hi":
                return (
                    "यहाँ हमारे वर्तमान सक्रिय प्रोजेक्ट्स हैं:\n\n"
                    "• The Curve (विरार वेस्ट, मुंबई)\n"
                    "  (thecurvevirar.com)\n\n"
                    "• Samsara (मुकुंद नगर, पुणे)\n"
                    "  (abhinavgroup.co.in/samsara)\n\n"
                    "• Pebbles Business Bay (वाकड, पुणे)\n"
                    "  (pebblesbusinessbay.com)\n\n"
                    "क्या आप किसी विशिष्ट प्रोजेक्ट के बारे में अधिक जानना चाहते हैं या साइट विजिट शेड्यूल करना चाहते हैं?"
                )
            return (
                "Here are our current active ongoing projects:\n\n"
                "• The Curve (Virar West, Mumbai)\n"
                "  (thecurvevirar.com)\n\n"
                "• Samsara (Mukund Nagar, Pune)\n"
                "  (abhinavgroup.co.in/samsara)\n\n"
                "• Pebbles Business Bay (Wakad, Pune)\n"
                "  (pebblesbusinessbay.com)\n\n"
                "Would you like to know more about any specific project or schedule a site visit?"
            )

        # The Curve / Virar
        if "curve" in t or "virar" in t:
            if language == "hi":
                return (
                    "The Curve अभिनव ग्रुप का एक एलीट स्टैंडअलोन सिंगल-टावर रेजिडेंशियल प्रोजेक्ट है जो बोलिंज, विरार वेस्ट, मुंबई MMR में स्थित है।\n"
                    "• कॉन्फ़िगरेशन: 2 और 3 BHK एलीट रेजिडेंस\n"
                    "• मुख्य आकर्षण: पैनोरमिक सीनिक व्यूज, आधुनिक क्लबहाउस, स्विमिंग पूल, जिम, चिल्ड्रन्स प्ले एरिया\n"
                    "• MahaRERA Reg No.: PR1240002600667 | पजेशन टारगेट: जून 2031\n\n"
                    "अधिक जानकारी या साइट विजिट के लिए हमारी सेल्स टीम से +91 97307 00667 पर संपर्क करें।"
                )
            return (
                "The Curve is an elite standalone single-tower residential development located in Bolinj, Virar West, Mumbai MMR.\n"
                "• Configurations: Thoughtfully designed 2 & 3 BHK residences\n"
                "• Highlights: Panoramic scenic views, modern clubhouse, fitness centre, children's play area\n"
                "• MahaRERA Reg No.: PR1240002600667 | Possession Target: June 2031\n\n"
                "For complete details or to schedule a site visit, please contact our sales team at +91 97307 00667 or email sales@abhinavinfra.com."
            )

        # Samsara / Mukund Nagar
        if "samsara" in t or "mukund nagar" in t:
            if language == "hi":
                return (
                    "Samsara मुकुंद नगर, सेंट्रल पुणे में स्थित एक अल्ट्रा-लक्ज़री रेजिडेंशियल प्रोजेक्ट है।\n"
                    "• कॉन्फ़िगरेशन: 3 BHK एक्सक्लूसिव अल्ट्रा-लक्ज़री रेजिडेंस\n"
                    "• मुख्य आकर्षण: लैंडस्केप टेरेस डेक, मॉडर्न क्लबहाउस, पूरी तरह सुसज्जित जिम, 24x7 मल्टी-टियर सिक्योरिटी\n"
                    "• MahaRERA Reg No.: P52100079797\n\n"
                    "कीमत व साइट विजिट के लिए हमारी सेल्स टीम से +91 9730397979 पर संपर्क करें।"
                )
            return (
                "Samsara is an ultra-luxury residential project located in the prestigious neighborhood of Mukund Nagar, Central Pune.\n"
                "• Configurations: Exclusive 3 BHK ultra-luxury residences\n"
                "• Highlights: Landscaped terrace deck, modern clubhouse, fully equipped gymnasium, 24x7 multi-tier security\n"
                "• MahaRERA Reg No.: P52100079797\n\n"
                "For current pricing or to schedule a site visit, please contact our sales team at +91 9730397979 or email sales@abhinavinfra.com."
            )

        # Pebbles Greenfield / Tathawade / Wakad
        if "greenfield" in t or ("pebbles" in t and "bay" not in t):
            if language == "hi":
                return (
                    "Pebbles Greenfield ताथवड़े / वाकड, पुणे में स्थित एक प्रीमियम रेजिडेंशियल प्रोजेक्ट है।\n"
                    "• कॉन्फ़िगरेशन: 2 और 3 BHK प्रीमियम अपार्टमेंट\n"
                    "• मुख्य आकर्षण: हिंजवड़ी आईटी पार्क और मुंबई-पुणे एक्सप्रेसवे से बेहतरीन कनेक्टिविटी, क्लबहाउस, स्विमिंग पूल, जिम, लैंडस्केप गार्डन\n"
                    "• MahaRERA Reg No.: P52100045923\n\n"
                    "अधिक जानकारी के लिए हमारी सेल्स टीम से +91 9730397979 पर संपर्क करें।"
                )
            return (
                "Pebbles Greenfield is a premium residential development located in Tathawade / Wakad, Pune.\n"
                "• Configurations: 2 & 3 BHK premium apartments\n"
                "• Highlights: Seamless connectivity to Hinjawadi IT Park and Mumbai-Pune Expressway, swimming pool, clubhouse, gym, landscaped gardens\n"
                "• MahaRERA Reg No.: P52100045923\n\n"
                "For complete details or to schedule a site visit, please contact our sales team at +91 9730397979 or email sales@abhinavinfra.com."
            )

        # Pebbles Business Bay / Commercial / PBB
        if "business bay" in t or "pbb" in t:
            if language == "hi":
                return (
                    "Pebbles Business Bay वाकड, पुणे में फीनिक्स मॉल ऑफ द मिलेनियम के सामने स्थित एक प्रीमियम कमर्शियल प्रोजेक्ट है।\n"
                    "• कॉन्फ़िगरेशन: हाई-स्ट्रीट रिटेल शोरूम, बुटीक कमर्शियल स्पेस और ग्रेड-ए कॉर्पोरेट ऑफिस\n"
                    "• मुख्य आकर्षण: हाईवे पर बेहतरीन विजिबिलिटी, शानदार ग्लास फसाड, हाई-स्पीड एलिवेटर्स और पर्याप्त पार्किंग\n\n"
                    "लीज़िंग या खरीद के लिए हमारी सेल्स टीम से +91 9730397979 पर संपर्क करें।"
                )
            return (
                "Pebbles Business Bay is a premier commercial development located opposite Phoenix Mall of the Millennium in Wakad, Pune.\n"
                "• Configurations: High-street retail showrooms, boutique commercial spaces, and Grade-A corporate offices\n"
                "• Highlights: Prime highway visibility in Wakad's commercial corridor, expansive glass facade, high-speed elevators, ample parking\n\n"
                "For sales and leasing inquiries, please contact our sales team at +91 9730397979 or email sales@abhinavinfra.com."
            )

        # Aeromall
        if "aeromall" in t:
            return (
                "AEROMALL is Pune's first 24x7 operational airport multi-level car parking (MLCP) and passenger transit-cum-retail hub, "
                "developed by Abhinav Group with the Airport Authority of India at Pune International Airport, Lohegaon. It is a fully delivered landmark."
            )

        # Amenities: Swimming pool, gym, garden
        if any(w in t for w in ["swimming pool", "gym", "gymnasium", "garden", "amenities", "clubhouse"]):
            return (
                "For residences featuring world-class amenities including swimming pool, fully equipped gymnasium, modern clubhouse, and landscaped gardens, "
                "we recommend our premier ongoing projects:\n"
                "• Pebbles Greenfield (Tathawade / Wakad, Pune) - Premium 2 & 3 BHK apartments\n"
                "• The Curve (Bolinj, Virar West, Mumbai MMR) - Elite 2 & 3 BHK residences with scenic views and elite clubhouse\n"
                "• Samsara (Mukund Nagar, Central Pune) - Ultra-luxury 3 BHK residences with landscaped terrace deck\n\n"
                "For complete details or to schedule a site visit, please contact our sales team at +91 9730397979 or email sales@abhinavinfra.com."
            )

        return None

    def _get_quick_replies(self, intent: str, language: str) -> List[str]:
        if language == "hi":
            return ["प्रोजेक्ट देखें", "करियर और नौकरियां", "सप्लायर बनें", "हमारी टीम से संपर्क करें"]
        return ["Explore Projects", "Careers & Jobs", "Become a Supplier", "Contact Our Team"]

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
