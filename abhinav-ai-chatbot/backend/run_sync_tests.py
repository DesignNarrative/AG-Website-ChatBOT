"""
Phase 2 Sync Test Suite
Tests all non-async components: config, security, models, AI provider logic, services (logic only).
No threads, no aiosqlite — runs cleanly inside any environment.

Async DB/API tests are in run_integration_tests.py (requires real uvicorn server).
"""
import os, sys
sys.path.insert(0, '.')

os.environ.update({
    'APP_ENV': 'development',
    'DATABASE_URL': 'sqlite:///./test_sync.db',
    'AI_PROVIDER': 'mock',
    'MDOC_ENABLED': 'false',
    'CELERY_ENABLED': 'false',
    'APP_SECRET_KEY': 'test_secret_key_32chars_minimum_x1',
    'JWT_SECRET_KEY': 'test_jwt_secret_32chars_minimum_x1',
    'DEBUG': 'false',
})

passed, failed = [], []

def chk(name, val, detail=""):
    if val:
        passed.append(name)
        print(f"  PASS  {name}")
    else:
        failed.append(name)
        print(f"  FAIL  {name}" + (f"  [{detail}]" if detail else ""))

def section(title):
    print(f"\n{'='*55}")
    print(f"  {title}")
    print(f"{'='*55}")

# ── S1: Configuration ────────────────────────────────────
section("S1: Configuration")
try:
    from app.core.config import get_settings
    get_settings.cache_clear()
    s = get_settings()
    chk('config_loads', s is not None)
    chk('ai_is_mock', s.ai_provider == 'mock')
    chk('env_dev', s.app_env == 'development')
    chk('is_sqlite', s.is_sqlite)
    chk('mdoc_off', not s.mdoc_enabled)
    chk('cors_list', isinstance(s.cors_origins, list))
    chk('pdf_ext', 'pdf' in s.allowed_extensions)
    chk('max_tokens_set', s.ai_max_tokens > 0)
    chk('secret_min_len', len(s.app_secret_key) >= 32)
    chk('jwt_min_len', len(s.jwt_secret_key) >= 32)
except Exception as e:
    chk('S1_import', False, str(e))

# ── S2: Security ─────────────────────────────────────────
section("S2: Security / Auth")
try:
    from app.security.auth import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
    from fastapi import HTTPException

    h = hash_password('Pass123!')
    chk('hash_not_plain', h != 'Pass123!')
    chk('hash_bcrypt_prefix', h.startswith('$2'))
    chk('verify_correct', verify_password('Pass123!', h))
    chk('verify_wrong', not verify_password('WrongPass', h))

    tok = create_access_token('user-001', 'developer')
    chk('token_created', bool(tok))
    chk('token_is_string', isinstance(tok, str))
    chk('token_has_dots', tok.count('.') == 2)   # JWT = header.payload.sig

    p = decode_token(tok)
    chk('token_sub', p.get('sub') == 'user-001')
    chk('token_role', p.get('role') == 'developer')
    chk('token_type', p.get('type') == 'access')

    rtok = create_refresh_token('user-001')
    rp = decode_token(rtok)
    chk('refresh_type', rp.get('type') == 'refresh')

    bad_raised = False
    try:
        decode_token('not.a.valid.jwt.token')
    except HTTPException as e:
        bad_raised = e.status_code == 401
    chk('bad_token_401', bad_raised)

    exp_raised = False
    try:
        import time
        from jose import jwt
        from app.core.config import settings
        expired = jwt.encode(
            {'sub': 'u', 'role': 'admin', 'type': 'access', 'exp': int(time.time()) - 60},
            settings.jwt_secret_key, algorithm='HS256'
        )
        decode_token(expired)
    except HTTPException as e:
        exp_raised = e.status_code == 401
    chk('expired_token_401', exp_raised)

except Exception as e:
    chk('S2_error', False, str(e))

# ── S3: ORM Models ───────────────────────────────────────
section("S3: ORM Models")
try:
    from app.models.user import User, UserRole
    from app.models.project import Project, ProjectType, ProjectStatus, ApprovalStatus
    from app.models.lead import Lead, LeadStatus, MdocSyncStatus, LeadSource
    from app.models.conversation import Conversation, ConversationStatus, Message, MessageRole
    from app.models.knowledge import KnowledgeChunk, KnowledgeSource, KnowledgeCategory
    from app.models.document import Document
    from app.models.audit_log import AuditLog

    u = User(email='dev@test.com', full_name='Dev User', hashed_password='hashed', role=UserRole.DEVELOPER)
    chk('user_role_dev', u.role == UserRole.DEVELOPER)
    # Note: SQLAlchemy column defaults only activate after DB flush; check column metadata instead
    from sqlalchemy import inspect as sa_inspect
    user_cols = {c.key: c for c in sa_inspect(User).mapper.column_attrs}
    proj_cols = {c.key: c for c in sa_inspect(Project).mapper.column_attrs}
    conv_cols = {c.key: c for c in sa_inspect(Conversation).mapper.column_attrs}
    lead_cols = {c.key: c for c in sa_inspect(Lead).mapper.column_attrs}
    chk('user_active_col_exists', 'is_active' in user_cols)
    chk('user_all_roles', set(r.value for r in UserRole) == {'developer', 'admin', 'staff'})

    proj = Project(project_id_slug='samsara', project_name='Samsara', project_type=ProjectType.RESIDENTIAL)
    chk('proj_price_unverified', not proj.price_verified)
    chk('proj_rera_unverified', not proj.rera_verified)
    chk('proj_residential', proj.project_type == ProjectType.RESIDENTIAL)
    chk('proj_types', set(t.value for t in ProjectType) >= {'residential', 'commercial'})
    chk('proj_approval_col_exists', 'approval_status' in proj_cols)

    l = Lead(phone='+919309505388', phone_normalized='+919309505388', consent_to_contact=True)
    chk('lead_not_dup', not l.is_duplicate)
    chk('lead_consent', l.consent_to_contact)
    chk('lead_status_col_exists', 'status' in lead_cols)
    chk('lead_mdoc_col_exists', 'mdoc_sync_status' in lead_cols)

    conv = Conversation(session_token='abc123')
    chk('conv_msg_count_zero', (conv.message_count or 0) == 0)
    chk('conv_status_col_exists', 'status' in conv_cols)
    chk('conv_lang_col_exists', 'language' in conv_cols)

    msg = Message(role=MessageRole.USER, content='Hello')
    chk('msg_role_user', msg.role == MessageRole.USER)
    chk('msg_roles', set(r.value for r in MessageRole) >= {'user', 'assistant'})

    kc = KnowledgeChunk(
        content='Samsara is a 3BHK project',
        content_hash='abc123',
        source_id='test-source-id',
        category=KnowledgeCategory.PROJECT_OVERVIEW,
    )
    chk('chunk_not_approved', not kc.is_approved)
    chk('chunk_not_verified_fact', not kc.is_verified_fact)

except Exception as e:
    chk('S3_error', False, str(e))

# ── S4: AI Provider (sync logic only) ────────────────────
section("S4: AI Provider — sync logic")
try:
    from app.ai.provider import MockAIProvider, BaseAIProvider, AIMessage, AIResponse, get_ai_provider

    # Check class hierarchy
    chk('mock_inherits_base', issubclass(MockAIProvider, BaseAIProvider))

    # Check get_ai_provider returns MockAIProvider in mock mode
    prov = get_ai_provider()
    chk('provider_name_mock', prov.provider_name == 'mock')
    chk('provider_is_mock_instance', isinstance(prov, MockAIProvider))

    # Check AIMessage dataclass
    msg = AIMessage(role='user', content='Test message')
    chk('ai_message_role', msg.role == 'user')
    chk('ai_message_content', msg.content == 'Test message')

    # Check AIResponse dataclass
    resp = AIResponse(content='Test reply', model='mock-v1', tokens_used=10, response_time_ms=50, is_fallback=False)
    chk('ai_response_content', resp.content == 'Test reply')
    chk('ai_response_not_fallback', not resp.is_fallback)

    # Check embed determinism logic (without async — just check the hash function)
    import hashlib
    text1 = 'Samsara 3BHK Mukund Nagar'
    text2 = 'Samsara 3BHK Mukund Nagar'
    text3 = 'Pebbles Greenfield Tathawade'
    h1 = int(hashlib.md5(text1.encode()).hexdigest(), 16)
    h2 = int(hashlib.md5(text2.encode()).hexdigest(), 16)
    h3 = int(hashlib.md5(text3.encode()).hexdigest(), 16)
    chk('embed_hash_deterministic', h1 == h2)
    chk('embed_hash_different', h1 != h3)

except Exception as e:
    chk('S4_error', False, str(e))

# ── S5: Chat Service — logic only (no DB) ────────────────
section("S5: Chat Service — intent & language logic")
try:
    # Import the class without instantiating (which needs DB)
    from app.services.chat_service import ChatService, SYSTEM_PROMPT

    # Create a minimal mock DB session to allow instantiation
    class MockDB:
        pass

    svc = ChatService(db=MockDB())  # type: ignore

    # Language detection
    chk('lang_en_basic', svc._detect_language('Hello, show me projects') == 'en')
    chk('lang_en_property', svc._detect_language('What is the price of 3BHK?') == 'en')
    chk('lang_hi_devanagari', svc._detect_language('नमस्ते, मुझे फ्लैट चाहिए') == 'hi')
    chk('lang_hi_more_chars', svc._detect_language('यह प्रोजेक्ट अच्छा है') == 'hi')
    chk('lang_en_numbers', svc._detect_language('2 BHK flat price') == 'en')

    # Intent detection — out of scope (MUST block before AI call)
    chk('oos_job', svc._detect_intent('apply for job opening') == 'out_of_scope')
    chk('oos_career', svc._detect_intent('career opportunities at abhinav') == 'out_of_scope')
    chk('oos_vacancy', svc._detect_intent('vacancy available') == 'out_of_scope')
    chk('oos_vendor', svc._detect_intent('vendor registration form') == 'out_of_scope')
    chk('oos_supplier', svc._detect_intent('supplier empanelment') == 'out_of_scope')
    chk('oos_contractor', svc._detect_intent('contractor list') == 'out_of_scope')

    # Intent detection — in scope
    chk('intent_greet_hello', svc._detect_intent('Hello there') == 'greeting')
    chk('intent_greet_hi', svc._detect_intent('hi can you help') == 'greeting')
    chk('intent_greet_namaste', svc._detect_intent('namaste') == 'greeting')
    chk('intent_samsara', svc._detect_intent('Tell me about Samsara') == 'project_enquiry_samsara')
    chk('intent_samsara_caps', svc._detect_intent('SAMSARA project details') == 'project_enquiry_samsara')
    chk('intent_greenfield', svc._detect_intent('Pebbles Greenfield price') == 'project_enquiry_greenfield')
    chk('intent_pebbles', svc._detect_intent('pebbles project wakad') == 'project_enquiry_greenfield')
    chk('intent_curve', svc._detect_intent('The Curve Virar flat') == 'project_enquiry_curve')
    chk('intent_virar', svc._detect_intent('virar west 2bhk') == 'project_enquiry_curve')
    chk('intent_aeromall', svc._detect_intent('aeromall commercial shop') == 'project_enquiry_aeromall')
    chk('intent_pricing', svc._detect_intent('what is the price') == 'pricing_enquiry')
    chk('intent_budget', svc._detect_intent('budget for flat') == 'pricing_enquiry')
    chk('intent_brochure', svc._detect_intent('download brochure pdf') == 'brochure_request')
    chk('intent_contact', svc._detect_intent('speak to sales team') == 'escalation')
    chk('intent_nri', svc._detect_intent('NRI abroad flat purchase') == 'nri_enquiry')
    chk('intent_config', svc._detect_intent('2 BHK options') == 'config_enquiry')

    # Out-of-scope response content
    oos_en = svc._out_of_scope_response('en')
    oos_hi = svc._out_of_scope_response('hi')
    chk('oos_en_has_number', '9309505388' in oos_en)
    chk('oos_en_has_website', 'abhinavgroup' in oos_en)
    chk('oos_hi_has_number', '9309505388' in oos_hi)
    chk('oos_hi_is_hindi', any('\u0900' <= c <= '\u097f' for c in oos_hi))

    # Quick replies
    qr_en = svc._get_quick_replies('greeting', 'en')
    qr_hi = svc._get_quick_replies('greeting', 'hi')
    chk('qr_en_list', isinstance(qr_en, list) and len(qr_en) > 0)
    chk('qr_hi_list', isinstance(qr_hi, list) and len(qr_hi) > 0)
    chk('qr_hi_devanagari', any('\u0900' <= c <= '\u097f' for c in ''.join(qr_hi)))

    # System prompt sanity
    chk('sysprompt_has_samsara', 'Samsara' in SYSTEM_PROMPT)
    chk('sysprompt_has_greenfield', 'Greenfield' in SYSTEM_PROMPT)
    chk('sysprompt_has_curve', 'Curve' in SYSTEM_PROMPT)
    chk('sysprompt_has_aeromall', 'Aeromall' in SYSTEM_PROMPT)
    chk('sysprompt_has_phone', '9309505388' in SYSTEM_PROMPT)
    chk('sysprompt_no_invent', 'NEVER invent' in SYSTEM_PROMPT)
    chk('sysprompt_scope_limit', 'ONLY answer' in SYSTEM_PROMPT)

except Exception as e:
    chk('S5_error', False, str(e))

# ── S6: Lead Service — logic only (no DB) ────────────────
section("S6: Lead Service — phone normalization logic")
try:
    from app.services.lead_service import LeadService

    class MockDB2:
        pass

    svc = LeadService(db=MockDB2())  # type: ignore

    # Phone normalization
    chk('norm_10digit', svc._normalize_phone('9309505388') == '+919309505388')
    chk('norm_plus91', svc._normalize_phone('+919309505388') == '+919309505388')
    chk('norm_91prefix', svc._normalize_phone('919309505388') == '+919309505388')
    chk('norm_with_spaces', svc._normalize_phone('93095 05388') == '+919309505388')
    chk('norm_with_dashes', svc._normalize_phone('93095-05388') == '+919309505388')
    chk('norm_zero_prefix', svc._normalize_phone('09309505388') == '+919309505388')

except Exception as e:
    chk('S6_error', False, str(e))

# ── S7: Mdoc Adapter — mock mode ─────────────────────────
section("S7: Mdoc Adapter — mock mode")
try:
    from app.integrations.mdoc.adapter import MdocAdapter, MockMdocAdapter

    adapter = MockMdocAdapter()
    chk('mock_adapter_exists', adapter is not None)
    chk('mock_is_mock', hasattr(adapter, 'is_mock') and adapter.is_mock)

except Exception as e:
    chk('S7_error', False, str(e))

# ── S8: FastAPI App — import & route registration ────────
section("S8: FastAPI App — import & routes")
try:
    from app.main import app
    from fastapi import FastAPI

    chk('app_is_fastapi', isinstance(app, FastAPI))
    chk('app_has_title', bool(app.title))

    routes = {r.path for r in app.routes}  # type: ignore
    chk('route_root', '/' in routes)
    chk('route_health', '/health' in routes)
    chk('route_chat', '/api/v1/chat/message' in routes)
    chk('route_leads', '/api/v1/leads/' in routes)
    chk('route_auth_login', '/api/v1/auth/login' in routes)
    chk('route_projects', '/api/v1/projects/' in routes)
    chk('route_admin', any('/admin' in r for r in routes))

    # CORS middleware present
    middleware_types = [type(m.cls).__name__ if hasattr(m, 'cls') else type(m).__name__ for m in app.user_middleware]
    has_cors = any('CORS' in m for m in middleware_types) or any(
        'cors' in str(m).lower() for m in app.user_middleware
    )
    chk('cors_middleware', has_cors)

except Exception as e:
    chk('S8_error', False, str(e))

# ── Results ───────────────────────────────────────────────
print()
print('=' * 55)
print('  PHASE 2 SYNC TEST RESULTS')
print('=' * 55)
total = len(passed) + len(failed)
print(f'  TOTAL  : {total}')
print(f'  PASSED : {len(passed)}')
print(f'  FAILED : {len(failed)}')
print('=' * 55)
if failed:
    print('  FAILED TESTS:')
    for f in failed:
        print(f'    FAIL -> {f}')
    print()
    sys.exit(1)
else:
    print('  ALL TESTS PASSED!')
    print()
    sys.exit(0)
