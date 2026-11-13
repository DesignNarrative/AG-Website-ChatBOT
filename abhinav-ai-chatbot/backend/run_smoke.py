"""
Phase 2 Smoke Test — runs synchronously, no hanging async fixtures.
"""
import os, sys, asyncio
sys.path.insert(0, '.')

os.environ.update({
    'APP_ENV': 'development',
    'DATABASE_URL': 'sqlite:///./smoke_test.db',
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
        print(f"  ✓ {name}")
    else:
        failed.append(name)
        print(f"  ✗ {name}" + (f" — {detail}" if detail else ""))

print("\n── S1: Configuration ──────────────────────")
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
except Exception as e:
    chk('S1_import', False, str(e))

print("\n── S2: Security ────────────────────────────")
try:
    from app.security.auth import hash_password, verify_password, create_access_token, decode_token
    from fastapi import HTTPException
    h = hash_password('Pass123!')
    tok = create_access_token('u1', 'developer')
    p = decode_token(tok)
    bad = False
    try:
        decode_token('bad.token')
    except HTTPException as e:
        bad = e.status_code == 401
    chk('hash_works', h != 'Pass123!')
    chk('verify_ok', verify_password('Pass123!', h))
    chk('verify_bad', not verify_password('Wrong', h))
    chk('token_sub', p['sub'] == 'u1')
    chk('token_role', p['role'] == 'developer')
    chk('bad_token_401', bad)
except Exception as e:
    chk('S2_import', False, str(e))

print("\n── S3: Models ──────────────────────────────")
try:
    from app.models.user import User, UserRole
    from app.models.project import Project, ProjectType, ApprovalStatus
    from app.models.lead import Lead, LeadStatus, MdocSyncStatus
    from app.models.conversation import Conversation, ConversationStatus
    u = User(email='t@t.com', full_name='T', hashed_password='x', role=UserRole.DEVELOPER)
    proj = Project(project_id_slug='s', project_name='S', project_type=ProjectType.RESIDENTIAL)
    l = Lead(phone='+91x', phone_normalized='+91x', consent_to_contact=True)
    c = Conversation(session_token='t')
    chk('user_active', u.is_active)
    chk('proj_pending', proj.approval_status == ApprovalStatus.PENDING)
    chk('proj_no_price', not proj.price_verified)
    chk('lead_new', l.status == LeadStatus.NEW)
    chk('lead_mdoc_pending', l.mdoc_sync_status == MdocSyncStatus.PENDING)
    chk('conv_active', c.status == ConversationStatus.ACTIVE)
    chk('conv_lang_en', c.language == 'en')
except Exception as e:
    chk('S3_import', False, str(e))

print("\n── S4: AI Provider ─────────────────────────")
async def test_ai():
    try:
        from app.ai.provider import MockAIProvider, AIMessage, get_ai_provider
        p = MockAIProvider()
        r = await p.chat([AIMessage(role='user', content='Hello')], 'sys')
        e1 = await p.embed('Samsara 3BHK')
        e2 = await p.embed('Samsara 3BHK')
        e3 = await p.embed('Pebbles Greenfield')
        batch = await p.embed_batch(['a', 'b'])
        prov = get_ai_provider()
        chk('ai_response', len(r.content) > 0)
        chk('ai_model_mock', r.model == 'mock-v1')
        chk('ai_not_fallback', not r.is_fallback)
        chk('embed_768', len(e1) == 768)
        chk('embed_floats', all(isinstance(x, float) for x in e1))
        chk('embed_det', e1 == e2)
        chk('embed_diff', e1 != e3)
        chk('embed_batch2', len(batch) == 2)
        chk('provider_mock', prov.provider_name == 'mock')
    except Exception as e:
        chk('S4_error', False, str(e))
asyncio.run(test_ai())

print("\n── S5: Database & Tables ───────────────────")
async def test_db():
    try:
        from app.database.session import check_db_connection, init_db, async_engine
        from sqlalchemy import inspect as si
        chk('db_connect', await check_db_connection())
        await init_db()
        async with async_engine.begin() as conn:
            tbls = await conn.run_sync(lambda c: si(c).get_table_names())
        expected = [
            'users','projects','knowledge_chunks','conversations','messages',
            'leads','audit_logs','project_images','project_documents',
            'knowledge_sources','lead_notes','mdoc_sync_records','documents','images'
        ]
        for t in expected:
            chk(f'table_{t}', t in tbls, f"missing from {tbls}")
    except Exception as e:
        chk('S5_error', False, str(e))
asyncio.run(test_db())

print("\n── S6: Chat Service ────────────────────────")
async def test_chat():
    try:
        from app.database.session import AsyncSessionLocal, init_db
        await init_db()
        from app.services.chat_service import ChatService
        from app.models.conversation import Conversation
        import secrets
        async with AsyncSessionLocal() as db:
            svc = ChatService(db=db)
            chk('lang_en', svc._detect_language('Hello projects') == 'en')
            chk('lang_hi', svc._detect_language('नमस्ते फ्लैट') == 'hi')
            chk('intent_greet', svc._detect_intent('Hello there') == 'greeting')
            chk('intent_oos_job', svc._detect_intent('apply for job') == 'out_of_scope')
            chk('intent_oos_vendor', svc._detect_intent('vendor registration') == 'out_of_scope')
            chk('intent_samsara', svc._detect_intent('Tell me about Samsara') == 'project_enquiry_samsara')
            chk('intent_greenfield', svc._detect_intent('Pebbles Greenfield price') == 'project_enquiry_greenfield')
            chk('intent_pricing', svc._detect_intent('what is price') == 'pricing_enquiry')
            chk('intent_brochure', svc._detect_intent('download brochure') == 'brochure_request')
            cv = Conversation(session_token=secrets.token_urlsafe(16))
            db.add(cv); await db.flush()
            res = await svc.process_message(cv, 'Hello show me projects')
            chk('proc_reply', len(res['reply']) > 0)
            chk('proc_lang', res['language'] in ('en', 'hi'))
            chk('proc_intent', 'intent' in res)
            chk('proc_quick_replies', isinstance(res.get('quick_replies'), list))
            cv2 = Conversation(session_token=secrets.token_urlsafe(16))
            db.add(cv2); await db.flush()
            oos = await svc.process_message(cv2, 'I want to apply for a job')
            rlo = oos['reply'].lower()
            chk('oos_intent', oos['intent'] == 'out_of_scope')
            chk('oos_redirects', any(w in rlo for w in ['property', 'real estate', 'contact', '9309505388']))
    except Exception as e:
        chk('S6_error', False, str(e))
asyncio.run(test_chat())

print("\n── S7: Lead Service ────────────────────────")
async def test_leads():
    try:
        from app.database.session import AsyncSessionLocal, init_db
        await init_db()
        from app.services.lead_service import LeadService
        async with AsyncSessionLocal() as db:
            svc = LeadService(db=db)
            chk('norm_10', svc._normalize_phone('9309505388') == '+919309505388')
            chk('norm_p91', svc._normalize_phone('+919309505388') == '+919309505388')
            chk('norm_91', svc._normalize_phone('919309505388') == '+919309505388')
            l1 = await svc.create_lead({'phone': '9800012345', 'name': 'Test', 'consent_to_contact': True, 'interested_project': 'Samsara'})
            await db.commit()
            chk('lead_created', l1.id is not None)
            chk('lead_norm', l1.phone_normalized == '+919800012345')
            chk('lead_not_dup', not l1.is_duplicate)
        async with AsyncSessionLocal() as db:
            svc = LeadService(db=db)
            l2 = await svc.create_lead({'phone': '9800012345', 'name': 'Same', 'consent_to_contact': True})
            chk('dup_detected', l2.is_duplicate)
            chk('dup_ref', l2.duplicate_of_id == l1.id)
    except Exception as e:
        chk('S7_error', False, str(e))
asyncio.run(test_leads())

print("\n── S8: HTTP API ────────────────────────────")
async def test_api():
    try:
        from app.database.session import init_db
        await init_db()
        from app.main import app
        from httpx import AsyncClient, ASGITransport
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as c:
            h = await c.get('/health')
            d = h.json()
            chk('health_200', h.status_code == 200)
            chk('health_mock', d.get('ai_provider') == 'mock')
            chk('health_db', d.get('database') == 'connected')
            rr = await c.get('/')
            chk('root_200', rr.status_code == 200)
            cm = await c.post('/api/v1/chat/message', json={'message': 'Hello show me projects'})
            cd = cm.json()
            tok = cd.get('session_token', '')
            chk('chat_200', cm.status_code == 200)
            chk('chat_token', bool(tok))
            chk('chat_reply', len(cd.get('reply', '')) > 0)
            chk('chat_lang', cd.get('language') in ('en', 'hi'))
            cm2 = await c.post('/api/v1/chat/message', json={'message': 'Tell me about Samsara', 'session_token': tok})
            chk('chat_session', cm2.json().get('session_token') == tok)
            chk('chat_empty_400', (await c.post('/api/v1/chat/message', json={'message': ''})).status_code == 400)
            chk('chat_long_400', (await c.post('/api/v1/chat/message', json={'message': 'x'*2001})).status_code == 400)
            oos = await c.post('/api/v1/chat/message', json={'message': 'career openings vacancy'})
            chk('chat_oos', oos.json().get('intent') == 'out_of_scope')
            hi = await c.post('/api/v1/chat/message', json={'message': 'नमस्ते 2 BHK चाहिए'})
            chk('hindi_200', hi.status_code == 200)
            chk('hindi_reply', len(hi.json().get('reply', '')) > 0)
            lr = await c.post('/api/v1/leads/', json={'phone': '9876509999', 'name': 'APITest', 'consent_to_contact': True})
            chk('lead_201', lr.status_code == 201)
            chk('lead_id', 'lead_id' in lr.json())
            chk('lead_bad_phone', (await c.post('/api/v1/leads/', json={'phone': '123', 'consent_to_contact': True})).status_code == 422)
            chk('lead_no_consent', (await c.post('/api/v1/leads/', json={'phone': '9876509999', 'consent_to_contact': False})).status_code == 422)
            chk('admin_no_auth', (await c.get('/api/v1/admin/overview')).status_code == 403)
            chk('projects_200', (await c.get('/api/v1/projects/')).status_code == 200)
            hist = await c.get(f'/api/v1/chat/history/{tok}')
            chk('history_200', hist.status_code == 200)
    except Exception as e:
        chk('S8_error', False, str(e))
asyncio.run(test_api())

# ── Results ──
print()
print('=' * 55)
print('  PHASE 2 SMOKE TEST RESULTS')
print('=' * 55)
print(f'  TOTAL  : {len(passed) + len(failed)}')
print(f'  PASSED : {len(passed)}')
print(f'  FAILED : {len(failed)}')
print('=' * 55)
if failed:
    print('  FAILED TESTS:')
    for f in failed:
        print(f'    ✗ {f}')
else:
    print('  ✅ ALL TESTS PASSED!')
print('=' * 55)

import os
for f in ['./smoke_test.db']:
    if os.path.exists(f):
        os.remove(f)

sys.exit(0 if not failed else 1)
