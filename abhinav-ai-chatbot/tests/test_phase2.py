"""
Phase 2 Test Suite — Tests that run WITHOUT any AI API key.
Tests: configuration, database, models, chat service (mock), lead service, security.
"""
from __future__ import annotations

import asyncio
import os
import sys

# Ensure tests run from the backend directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force test environment settings
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_abhinav.db")
os.environ.setdefault("AI_PROVIDER", "mock")
os.environ.setdefault("MDOC_ENABLED", "false")
os.environ.setdefault("CELERY_ENABLED", "false")

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport


# ===========================================================================
# SECTION 1: CONFIGURATION TESTS
# ===========================================================================
class TestConfiguration:
    """Verify that app settings load correctly."""

    def test_settings_load(self):
        from app.core.config import get_settings
        settings = get_settings()
        assert settings is not None

    def test_default_ai_provider_is_mock(self):
        from app.core.config import get_settings
        settings = get_settings()
        assert settings.ai_provider == "mock"

    def test_default_env_is_development(self):
        from app.core.config import get_settings
        settings = get_settings()
        assert settings.app_env == "development"

    def test_database_url_is_sqlite_in_test(self):
        from app.core.config import get_settings
        settings = get_settings()
        assert "sqlite" in settings.database_url

    def test_is_sqlite_property(self):
        from app.core.config import get_settings
        settings = get_settings()
        assert settings.is_sqlite is True
        assert settings.is_postgres is False

    def test_mdoc_disabled_by_default(self):
        from app.core.config import get_settings
        settings = get_settings()
        assert settings.mdoc_enabled is False
        assert settings.mdoc_mode == "mock"

    def test_cors_origins_parsed(self):
        from app.core.config import get_settings
        settings = get_settings()
        origins = settings.cors_origins
        assert isinstance(origins, list)
        assert len(origins) > 0

    def test_allowed_extensions_parsed(self):
        from app.core.config import get_settings
        settings = get_settings()
        exts = settings.allowed_extensions
        assert "pdf" in exts
        assert "jpg" in exts


# ===========================================================================
# SECTION 2: DATABASE TESTS
# ===========================================================================
@pytest.mark.asyncio
class TestDatabase:
    """Verify database connectivity and table creation."""

    async def test_db_connection(self):
        from app.database.session import check_db_connection
        result = await check_db_connection()
        assert result is True, "Database connection failed"

    async def test_tables_created(self):
        from app.database.session import init_db, async_engine
        await init_db()
        from sqlalchemy import inspect, text
        async with async_engine.begin() as conn:
            tables = await conn.run_sync(lambda c: inspect(c).get_table_names())
        expected_tables = [
            "users", "projects", "project_images", "project_documents",
            "knowledge_sources", "knowledge_chunks", "conversations",
            "messages", "leads", "lead_notes", "mdoc_sync_records",
            "documents", "images", "audit_logs"
        ]
        for table in expected_tables:
            assert table in tables, f"Missing table: {table}"

    async def test_db_session_yields_and_commits(self):
        from app.database.session import AsyncSessionLocal
        from app.models.user import User, UserRole
        from app.security.auth import hash_password

        async with AsyncSessionLocal() as session:
            user = User(
                email="test_db@test.com",
                full_name="Test DB User",
                hashed_password=hash_password("test123"),
                role=UserRole.STAFF,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            assert user.id is not None
            # Clean up
            await session.delete(user)
            await session.commit()


# ===========================================================================
# SECTION 3: MODEL TESTS
# ===========================================================================
class TestModels:
    """Verify model instantiation and field defaults."""

    def test_user_model(self):
        from app.models.user import User, UserRole
        from app.security.auth import hash_password
        u = User(
            email="test@abhinavgroup.co.in",
            full_name="Test User",
            hashed_password=hash_password("password123"),
            role=UserRole.STAFF,
        )
        assert u.role == UserRole.STAFF
        assert u.is_active is True

    def test_project_model_defaults(self):
        from app.models.project import Project, ProjectType, ProjectStatus, ApprovalStatus
        p = Project(
            project_id_slug="samsara",
            project_name="Samsara",
            project_type=ProjectType.RESIDENTIAL,
        )
        assert p.project_status == ProjectStatus.UNKNOWN
        assert p.approval_status == ApprovalStatus.PENDING
        assert p.price_verified is False
        assert p.rera_verified is False

    def test_lead_model_defaults(self):
        from app.models.lead import Lead, LeadStatus, MdocSyncStatus
        l = Lead(
            phone="+919890393838",
            phone_normalized="+919890393838",
            consent_to_contact=True,
        )
        assert l.status == LeadStatus.NEW
        assert l.mdoc_sync_status == MdocSyncStatus.PENDING
        assert l.is_duplicate is False

    def test_conversation_model(self):
        from app.models.conversation import Conversation, ConversationStatus
        c = Conversation(session_token="test_token_123")
        assert c.status == ConversationStatus.ACTIVE
        assert c.language == "en"
        assert c.message_count == 0


# ===========================================================================
# SECTION 4: SECURITY TESTS
# ===========================================================================
class TestSecurity:
    """Test password hashing and JWT token operations."""

    def test_password_hash_and_verify(self):
        from app.security.auth import hash_password, verify_password
        password = "SecurePassword123!"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed) is True
        assert verify_password("WrongPassword", hashed) is False

    def test_create_access_token(self):
        from app.security.auth import create_access_token, decode_token
        token = create_access_token("user-123", "developer")
        assert token is not None
        payload = decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["role"] == "developer"
        assert payload["type"] == "access"

    def test_create_refresh_token(self):
        from app.security.auth import create_refresh_token, decode_token
        token = create_refresh_token("user-123")
        payload = decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["type"] == "refresh"

    def test_invalid_token_raises(self):
        import pytest
        from fastapi import HTTPException
        from app.security.auth import decode_token
        with pytest.raises(HTTPException) as exc_info:
            decode_token("not.a.valid.token")
        assert exc_info.value.status_code == 401


# ===========================================================================
# SECTION 5: AI MOCK PROVIDER TESTS
# ===========================================================================
@pytest.mark.asyncio
class TestMockAIProvider:
    """Verify the mock AI provider works correctly."""

    async def test_mock_provider_returns_response(self):
        from app.ai.provider import MockAIProvider, AIMessage
        provider = MockAIProvider()
        response = await provider.chat(
            messages=[AIMessage(role="user", content="Hello")],
            system_prompt="Test",
        )
        assert response is not None
        assert len(response.content) > 0
        assert response.model == "mock-v1"
        assert response.is_fallback is False

    async def test_mock_greeting_english(self):
        from app.ai.provider import MockAIProvider, AIMessage
        provider = MockAIProvider()
        response = await provider.chat(
            messages=[AIMessage(role="user", content="Hello, I need help")],
            system_prompt="Test",
        )
        assert "Welcome" in response.content or "Hello" in response.content

    async def test_mock_hindi_greeting(self):
        from app.ai.provider import MockAIProvider, AIMessage
        provider = MockAIProvider()
        response = await provider.chat(
            messages=[AIMessage(role="user", content="नमस्ते मुझे मदद चाहिए")],
            system_prompt="Test",
        )
        assert len(response.content) > 0

    async def test_mock_out_of_scope(self):
        from app.ai.provider import MockAIProvider, AIMessage
        provider = MockAIProvider()
        response = await provider.chat(
            messages=[AIMessage(role="user", content="career and job openings")],
            system_prompt="Test",
        )
        # Mock should return a response (scope filtering handled at service level)
        assert len(response.content) > 0

    async def test_mock_embedding_returns_vector(self):
        from app.ai.provider import MockAIProvider
        provider = MockAIProvider()
        embedding = await provider.embed("test text about property")
        assert isinstance(embedding, list)
        assert len(embedding) == MockAIProvider.MOCK_EMBEDDING_DIM
        assert all(isinstance(v, float) for v in embedding)

    async def test_mock_embedding_deterministic(self):
        from app.ai.provider import MockAIProvider
        provider = MockAIProvider()
        emb1 = await provider.embed("Samsara Pune 3 BHK")
        emb2 = await provider.embed("Samsara Pune 3 BHK")
        assert emb1 == emb2  # Same input → same output

    async def test_mock_embedding_different_texts(self):
        from app.ai.provider import MockAIProvider
        provider = MockAIProvider()
        emb1 = await provider.embed("Samsara Mukund Nagar")
        emb2 = await provider.embed("Pebbles Greenfield Tathawade")
        assert emb1 != emb2  # Different inputs → different outputs


# ===========================================================================
# SECTION 6: CHAT SERVICE TESTS
# ===========================================================================
@pytest.mark.asyncio
class TestChatService:
    """Test the chat service pipeline with mock AI."""

    async def test_language_detection_english(self):
        from app.database.session import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            from app.services.chat_service import ChatService
            service = ChatService(db=db)
            assert service._detect_language("Hello, I need help") == "en"
            assert service._detect_language("What is the price of 2 BHK?") == "en"

    async def test_language_detection_hindi(self):
        from app.database.session import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            from app.services.chat_service import ChatService
            service = ChatService(db=db)
            assert service._detect_language("नमस्ते मुझे फ्लैट चाहिए") == "hi"
            assert service._detect_language("मैं 2 BHK देखना चाहता हूं") == "hi"

    async def test_intent_detection_greeting(self):
        from app.database.session import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            from app.services.chat_service import ChatService
            service = ChatService(db=db)
            assert service._detect_intent("Hello there") == "greeting"
            assert service._detect_intent("Hi, I need help") == "greeting"

    async def test_intent_detection_out_of_scope(self):
        from app.database.session import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            from app.services.chat_service import ChatService
            service = ChatService(db=db)
            assert service._detect_intent("I want to apply for a job") == "out_of_scope"
            assert service._detect_intent("vendor registration") == "out_of_scope"
            assert service._detect_intent("career openings") == "out_of_scope"

    async def test_intent_detection_project_enquiry(self):
        from app.database.session import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            from app.services.chat_service import ChatService
            service = ChatService(db=db)
            assert service._detect_intent("Tell me about Samsara") == "project_enquiry_samsara"
            assert service._detect_intent("Pebbles Greenfield details") == "project_enquiry_greenfield"
            assert service._detect_intent("The Curve Virar") == "project_enquiry_curve"

    async def test_process_message_returns_response(self):
        from app.database.session import AsyncSessionLocal, init_db
        await init_db()
        async with AsyncSessionLocal() as db:
            from app.services.chat_service import ChatService
            from app.models.conversation import Conversation
            import secrets
            conv = Conversation(session_token=secrets.token_urlsafe(16))
            db.add(conv)
            await db.flush()

            service = ChatService(db=db)
            result = await service.process_message(conv, "Hello, what projects do you have?")

            assert "reply" in result
            assert len(result["reply"]) > 0
            assert "language" in result
            assert result["language"] in ("en", "hi")
            assert "intent" in result
            assert "is_fallback" in result

    async def test_out_of_scope_blocked(self):
        """Career/vendor queries must be blocked at service level."""
        from app.database.session import AsyncSessionLocal, init_db
        await init_db()
        async with AsyncSessionLocal() as db:
            from app.services.chat_service import ChatService
            from app.models.conversation import Conversation
            import secrets
            conv = Conversation(session_token=secrets.token_urlsafe(16))
            db.add(conv)
            await db.flush()

            service = ChatService(db=db)
            result = await service.process_message(conv, "I want to apply for a job vacancy")

            assert result["intent"] == "out_of_scope"
            # Should NOT contain job-related answers
            assert "resume" not in result["reply"].lower()
            assert "apply" not in result["reply"].lower() or "property" in result["reply"].lower()


# ===========================================================================
# SECTION 7: LEAD SERVICE TESTS
# ===========================================================================
@pytest.mark.asyncio
class TestLeadService:
    """Test lead creation, deduplication, and phone validation."""

    async def test_phone_normalization(self):
        from app.database.session import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            from app.services.lead_service import LeadService
            service = LeadService(db=db)
            assert service._normalize_phone("9890393838") == "+919890393838"
            assert service._normalize_phone("+919890393838") == "+919890393838"
            assert service._normalize_phone("919890393838") == "+919890393838"

    async def test_create_lead_success(self):
        from app.database.session import AsyncSessionLocal, init_db
        await init_db()
        async with AsyncSessionLocal() as db:
            from app.services.lead_service import LeadService
            service = LeadService(db=db)
            lead = await service.create_lead({
                "phone": "9123456789",
                "name": "Test Customer",
                "consent_to_contact": True,
                "interested_project": "Samsara",
            })
            assert lead.id is not None
            assert lead.phone_normalized == "+919123456789"
            assert lead.is_duplicate is False

    async def test_duplicate_lead_detection(self):
        from app.database.session import AsyncSessionLocal, init_db
        await init_db()
        async with AsyncSessionLocal() as db:
            from app.services.lead_service import LeadService
            service = LeadService(db=db)
            # Create first lead
            lead1 = await service.create_lead({
                "phone": "9999988888",
                "name": "First Lead",
                "consent_to_contact": True,
            })
            await db.commit()

        async with AsyncSessionLocal() as db:
            service = LeadService(db=db)
            # Same phone within window = duplicate
            lead2 = await service.create_lead({
                "phone": "9999988888",
                "name": "Same Person Again",
                "consent_to_contact": True,
            })
            assert lead2.is_duplicate is True
            assert lead2.duplicate_of_id == lead1.id


# ===========================================================================
# SECTION 8: API ENDPOINT TESTS (using TestClient)
# ===========================================================================
@pytest.mark.asyncio
class TestAPIEndpoints:
    """Integration tests for the FastAPI endpoints."""

    @pytest_asyncio.fixture
    async def client(self):
        from app.database.session import init_db
        await init_db()
        from app.main import app
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c

    async def test_health_check(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("healthy", "degraded")
        assert data["ai_provider"] == "mock"

    async def test_root_endpoint(self, client):
        response = await client.get("/")
        assert response.status_code == 200

    async def test_chat_message_endpoint(self, client):
        response = await client.post("/api/v1/chat/message", json={
            "message": "Hello, what projects do you have?",
        })
        assert response.status_code == 200
        data = response.json()
        assert "session_token" in data
        assert "reply" in data
        assert len(data["reply"]) > 0

    async def test_chat_session_continuation(self, client):
        # First message
        r1 = await client.post("/api/v1/chat/message", json={"message": "Hello"})
        token = r1.json()["session_token"]
        # Second message with same token
        r2 = await client.post("/api/v1/chat/message", json={
            "message": "Tell me about Samsara",
            "session_token": token,
        })
        assert r2.status_code == 200
        assert r2.json()["session_token"] == token

    async def test_chat_empty_message_rejected(self, client):
        response = await client.post("/api/v1/chat/message", json={"message": ""})
        assert response.status_code == 400

    async def test_chat_too_long_message_rejected(self, client):
        response = await client.post("/api/v1/chat/message", json={"message": "x" * 2001})
        assert response.status_code == 400

    async def test_lead_creation(self, client):
        response = await client.post("/api/v1/leads/", json={
            "phone": "9876543210",
            "name": "API Test Customer",
            "consent_to_contact": True,
            "interested_project": "Pebbles Greenfield",
        })
        assert response.status_code == 201
        data = response.json()
        assert "lead_id" in data

    async def test_lead_invalid_phone_rejected(self, client):
        response = await client.post("/api/v1/leads/", json={
            "phone": "12345",
            "consent_to_contact": True,
        })
        assert response.status_code == 422

    async def test_lead_no_consent_rejected(self, client):
        response = await client.post("/api/v1/leads/", json={
            "phone": "9876543210",
            "consent_to_contact": False,
        })
        assert response.status_code == 422

    async def test_admin_requires_auth(self, client):
        response = await client.get("/api/v1/admin/overview")
        assert response.status_code == 403  # No token = forbidden

    async def test_knowledge_reindex_requires_developer(self, client):
        response = await client.post("/api/v1/knowledge/reindex")
        assert response.status_code == 403


# ===========================================================================
# SECTION 9: SCOPE RESTRICTION TESTS
# ===========================================================================
@pytest.mark.asyncio
class TestScopeRestrictions:
    """Ensure the chatbot refuses out-of-scope queries."""

    @pytest_asyncio.fixture
    async def client(self):
        from app.database.session import init_db
        await init_db()
        from app.main import app
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c

    @pytest.mark.parametrize("message", [
        "I want to apply for a job",
        "career openings at Abhinav Group",
        "how do I register as a vendor",
        "contractor registration",
        "supplier empanelment",
    ])
    async def test_out_of_scope_messages(self, client, message):
        response = await client.post("/api/v1/chat/message", json={"message": message})
        assert response.status_code == 200
        data = response.json()
        assert data["intent"] == "out_of_scope"
        # Reply must redirect to contact info, not answer the query
        reply = data["reply"].lower()
        assert any(phrase in reply for phrase in [
            "property", "real estate", "9890393838", "abhinavgroup", "contact"
        ]), f"Out-of-scope reply did not redirect properly: {data['reply']}"
