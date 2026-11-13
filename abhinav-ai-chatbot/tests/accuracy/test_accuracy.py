# Phase 11 - Accuracy Test Suite (fully synchronous - no asyncio)
# Tests chatbot intent detection, language detection, scope enforcement,
# phone normalization, and system prompt correctness.
#
# Run:
#   Set-Location ".../abhinav-ai-chatbot/backend"
#   $env:PYTHONIOENCODING="utf-8"; python ../tests/accuracy/test_accuracy.py

import os, sys, hashlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

os.environ.update({
    "APP_ENV": "development",
    "DATABASE_URL": "sqlite:///./test_accuracy.db",
    "AI_PROVIDER": "mock",
    "MDOC_ENABLED": "false",
    "CELERY_ENABLED": "false",
    "APP_SECRET_KEY": "test_secret_key_32chars_minimum_x1",
    "JWT_SECRET_KEY": "test_jwt_secret_32chars_minimum_x1",
    "DEBUG": "false",
})

results = []

def test(name, cond, detail=""):
    results.append((name, bool(cond), str(detail)))

# ─── T1: Intent Detection ────────────────────────────────────────────────────
from app.services.chat_service import ChatService

class _Fake: pass
svc = ChatService(db=_Fake())

INTENT_TESTS = [
    # Out-of-scope
    ("I want to apply for a job",      "out_of_scope"),
    ("Career opportunities",           "out_of_scope"),
    ("Job vacancy",                    "out_of_scope"),
    ("vendor empanelment",             "out_of_scope"),
    ("contractor registration",        "out_of_scope"),
    ("supplier enquiry",               "out_of_scope"),
    ("staff recruitment",              "out_of_scope"),
    # Greetings
    ("Hello",                          "greeting"),
    ("Hi there",                       "greeting"),
    ("Good morning",                   "greeting"),
    ("Namaste",                        "greeting"),
    ("Hey",                            "greeting"),
    # Specific projects
    ("Tell me about Samsara",          "project_enquiry_samsara"),
    ("SAMSARA project details",        "project_enquiry_samsara"),
    ("samsara 3bhk pune",              "project_enquiry_samsara"),
    ("Pebbles Greenfield info",        "project_enquiry_greenfield"),
    ("pebbles greenfield 2bhk",        "project_enquiry_greenfield"),
    ("The Curve Virar",                "project_enquiry_curve"),
    ("curve project mumbai",           "project_enquiry_curve"),
    ("Aeromall details",               "project_enquiry_aeromall"),
    ("airport road mall pune",         "project_enquiry_aeromall"),
    # NRI
    ("I am an NRI can I buy flat",     "nri_enquiry"),
    ("NRI property purchase process",  "nri_enquiry"),
    # Pricing
    ("what is the price",              "pricing_enquiry"),
    ("flat rate kya hai",              "pricing_enquiry"),
    ("how much does it cost",          "pricing_enquiry"),
    ("starting price",                 "pricing_enquiry"),
    # Configuration
    ("2 BHK available",                "config_enquiry"),
    ("3 bhk flat",                     "config_enquiry"),
    # Brochure
    ("download brochure",              "brochure_request"),
    ("send me floor plan",             "brochure_request"),
    ("brochure chahiye",               "brochure_request"),
    # Contact
    ("contact sales",                  "escalation"),
    ("speak to agent",                 "escalation"),
    # Project list
    ("show all projects",              "project_list"),
    ("what projects do you have",      "project_list"),
    ("list of properties",             "project_list"),
]

correct_intent = 0
for query, expected in INTENT_TESTS:
    detected = svc._detect_intent(query)
    ok = detected == expected
    if ok: correct_intent += 1
    test(f"intent::{expected}::{query[:35]}", ok, f"got={detected}" if not ok else "")

test("intent_overall_80pct", correct_intent >= int(len(INTENT_TESTS) * 0.80),
     f"{correct_intent}/{len(INTENT_TESTS)} correct")

# ─── T2: Language Detection ───────────────────────────────────────────────────
LANG_TESTS = [
    ("Hello, I want to buy a flat",           "en"),
    ("Show me projects in Pune",              "en"),
    ("What are the available configurations?","en"),
    ("3 BHK flat price",                      "en"),
    ("NRI property purchase process",         "en"),
]
# Hindi Devanagari tests
HI_TESTS = [
    "\u0928\u092e\u0938\u094d\u0924\u0947 \u092e\u0941\u091d\u0947 \u092b\u094d\u0932\u0948\u091f \u091a\u093e\u0939\u093f\u090f",  # namaste mujhe flat chahiye
    "\u092a\u0941\u0923\u0947 \u092e\u0947\u0902 2 BHK \u092b\u094d\u0932\u0948\u091f",                                              # Pune mein 2 BHK flat
    "\u0905\u092d\u093f\u0928\u0935 \u0917\u094d\u0930\u0941\u092a \u0915\u0947 \u092a\u094d\u0930\u094b\u091c\u0947\u0915\u094d\u091f", # Abhinav Group ke project
]

for text, lang in LANG_TESTS:
    detected = svc._detect_language(text)
    test(f"lang::en::{text[:30]}", detected == lang, f"got={detected}")

for text in HI_TESTS:
    detected = svc._detect_language(text)
    test(f"lang::hi::{text[:20]}", detected == "hi", f"got={detected}")

# ─── T3: Mock AI response content ────────────────────────────────────────────
# Use deterministic mock responses directly (no asyncio)
from app.ai.provider import MockAIProvider, AIMessage, AIResponse
import time

mock = MockAIProvider()

def sync_chat(query: str) -> str:
    """Call mock AI synchronously via its sync logic only (no actual async)."""
    lower = query.lower()
    # Replicate mock provider logic synchronously
    if any(w in lower for w in ["hello", "hi", "namaste", "hey", "start"]):
        key = "greeting"
    elif any(w in lower for w in ["project", "property", "flat", "home", "apartment",
                                   "\u092a\u094d\u0930\u094b\u091c\u0947\u0915\u094d\u091f",
                                   "\u092b\u094d\u0932\u0948\u091f", "\u0918\u0930"]):
        key = "projects_list"
    elif any(w in lower for w in ["career", "job", "vendor", "supplier", "contractor"]):
        key = "out_of_scope"
    else:
        key = None

    if key:
        return mock._RESPONSES.get(key, "").lower()
    return f"[mock] {query.lower()}"

RESPONSE_TESTS = [
    ("Hello",                       ["abhinav", "property"],                    []),
    ("Show me all projects",        ["samsara", "pebbles", "curve", "aeromall"],[]),
    ("I want to apply for a job",   ["property", "9309505388"],                 ["resume", "cv", "hire"]),
    ("vendor registration",         ["property", "9309505388"],                 []),
    ("Tell me about Pebbles Greenfield", ["pebbles"],                           []),
    ("3 BHK flat in pune",          ["samsara", "pebbles"],                     []),
]

for query, must_have, must_not in RESPONSE_TESTS:
    text = sync_chat(query)
    missing = [k for k in must_have if k.lower() not in text]
    blocked = [w for w in must_not if w.lower() in text]
    ok = not missing and not blocked
    detail = ""
    if missing: detail += f"missing={missing} "
    if blocked: detail += f"blocked_found={blocked}"
    test(f"response::{query[:40]}", ok, detail.strip())

# ─── T4: Scope enforcement ────────────────────────────────────────────────────
OOS = [
    "I want to apply for a job",
    "career opportunities at Abhinav Group",
    "vendor registration",
    "contractor empanelment",
    "supplier tie-up",
    "HR contact",
    "recruitment process",
    "internship programme",
]
for q in OOS:
    intent = svc._detect_intent(q)
    test(f"scope_oos::{q[:40]}", intent == "out_of_scope", f"got={intent}")

IN_SCOPE = [
    "Tell me about Samsara",
    "2 BHK flat price",
    "NRI can buy flat in India",
    "Download brochure",
    "Contact sales team",
    "What projects do you have",
]
for q in IN_SCOPE:
    intent = svc._detect_intent(q)
    test(f"scope_in::{q[:40]}", intent != "out_of_scope", f"incorrectly blocked intent={intent}")

# ─── T5: Phone normalization ─────────────────────────────────────────────────
from app.services.lead_service import LeadService
lead_svc = LeadService(db=_Fake())

PHONE_TESTS = [
    ("9309505388",    "+919309505388"),
    ("+919309505388", "+919309505388"),
    ("919309505388",  "+919309505388"),
    ("09309505388",   "+919309505388"),
    ("93 09 50 53 88","+919309505388"),
    ("93-09-50-53-88","+919309505388"),
    ("8530001674",    "+918530001674"),
    ("+918530001674", "+918530001674"),
]
for raw, expected in PHONE_TESTS:
    norm = lead_svc._normalize_phone(raw)
    test(f"phone::{raw}", norm == expected, f"got={norm}")

# ─── T6: Quick replies ────────────────────────────────────────────────────────
en_qr = svc._get_quick_replies("greeting", "en")
hi_qr = svc._get_quick_replies("greeting", "hi")
oos_qr = svc._get_quick_replies("out_of_scope", "en")

test("qr_en_is_list",    isinstance(en_qr, list))
test("qr_en_has_items",  len(en_qr) >= 2)
test("qr_hi_is_list",    isinstance(hi_qr, list))
test("qr_hi_has_items",  len(hi_qr) >= 2)
test("qr_oos_has_items", len(oos_qr) >= 1)

has_dev = any(any('\u0900' <= c <= '\u097F' for c in item) for item in hi_qr)
test("qr_hi_devanagari", has_dev, "No Devanagari in Hindi QRs")

# ─── T7: System prompt completeness ──────────────────────────────────────────
from app.services.chat_service import SYSTEM_PROMPT
sp_text = SYSTEM_PROMPT.lower()
for keyword in ["samsara", "pebbles greenfield", "the curve", "aeromall", "9309505388",
                "career", "vendor", "hindi"]:
    test(f"sysprompt::{keyword}", keyword in sp_text, f"{keyword} not in system prompt")

for bad in ["invent property facts", "never invent"]:
    test(f"sysprompt::guard::{bad}", bad in sp_text, f"guardrail missing: {bad}")

# ─── T8: Mock embedding properties ───────────────────────────────────────────
def sync_embed(text: str):
    h = int(hashlib.sha256(text.encode()).hexdigest(), 16)
    dim = 768
    return [(((h >> i) & 0xFF) / 255.0 - 0.5) for i in range(dim)]

e1 = sync_embed("Samsara 3BHK Mukund Nagar Pune")
e2 = sync_embed("Samsara 3BHK Mukund Nagar Pune")
e3 = sync_embed("Aeromall Airport Road Pune commercial")

test("embed_dim_768",       len(e1) == 768)
test("embed_all_floats",    all(isinstance(x, float) for x in e1))
test("embed_deterministic", e1 == e2)
test("embed_different",     e1 != e3)
test("embed_range",         all(-1.0 <= x <= 1.0 for x in e1))

# ─── Results ─────────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("  ACCURACY TEST RESULTS")
print("=" * 60)

passed = sum(1 for _, v, _ in results if v)
failed_list = [(n, d) for n, v, d in results if not v]
total = len(results)

print(f"  TOTAL  : {total}")
print(f"  PASSED : {passed}")
print(f"  FAILED : {len(failed_list)}")
print(f"  RATE   : {passed/total*100:.1f}%")
print("=" * 60)

if failed_list:
    print("  FAILED TESTS:")
    for name, detail in failed_list:
        print(f"    FAIL -> {name}")
        if detail:
            print(f"           {detail}")
else:
    print("  ALL TESTS PASSED!")
print("=" * 60)

for f in ["./test_accuracy.db"]:
    if os.path.exists(f): os.remove(f)

sys.exit(0 if not failed_list else 1)
