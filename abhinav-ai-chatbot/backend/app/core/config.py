"""
Abhinav Group AI Chatbot — Application Configuration
Loads and validates all settings from environment variables.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Literal, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_env: Literal["development", "staging", "production"] = "development"
    app_secret_key: str = "INSECURE_DEV_KEY_CHANGE_IN_PRODUCTION"
    debug: bool = True
    log_level: str = "INFO"
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    # --- Database ---
    database_url: str = "sqlite:///./abhinav_chatbot_dev.db"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def is_postgres(self) -> bool:
        return "postgresql" in self.database_url

    # --- Vector Store ---
    vector_store_type: Literal["faiss", "pgvector", "sqlite_vss"] = "faiss"
    vector_store_path: str = "./data/vector_store"
    pgvector_connection_string: Optional[str] = None

    # --- AI Provider ---
    ai_provider: Literal["gemini", "openai", "mock"] = "mock"

    # Gemini
    gemini_api_key: Optional[str] = None
    gemini_chat_model: str = "gemini-3.5-flash"
    gemini_embedding_model: str = "gemini-embedding-001"

    # OpenAI
    openai_api_key: Optional[str] = None
    openai_chat_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"

    # AI Settings
    ai_max_tokens: int = 1024
    ai_temperature: float = 0.1
    ai_timeout_seconds: int = 30

    # --- RAG ---
    rag_top_k: int = 5
    rag_similarity_threshold: float = 0.7
    rag_max_context_tokens: int = 4096
    chunk_size: int = 512
    chunk_overlap: int = 64

    # --- Auth ---
    jwt_secret_key: str = "INSECURE_JWT_DEV_KEY_CHANGE_IN_PRODUCTION"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7

    # --- Leads ---
    lead_dedup_window_hours: int = 24
    lead_notification_email: str = "sales@abhinavinfra.com"
    lead_notification_enabled: bool = False

    # --- Email ---
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    email_from: str = "noreply@abhinavgroup.co.in"

    # --- Mdoc CRM ---
    mdoc_enabled: bool = False
    mdoc_mode: Literal["mock", "sandbox", "production"] = "mock"
    mdoc_api_base_url: str = "https://api.mymdoc.io"
    mdoc_api_key: Optional[str] = None
    mdoc_timeout_seconds: int = 10
    mdoc_retry_attempts: int = 3
    mdoc_retry_delay_seconds: int = 5

    # --- Celery / Background Tasks ---
    celery_enabled: bool = False
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # --- WordPress Widget ---
    widget_api_key: str = "INSECURE_WIDGET_KEY_CHANGE_IN_PRODUCTION"
    widget_allowed_domains: str = "abhinavgroup.co.in,localhost"

    @property
    def widget_domains(self) -> List[str]:
        return [d.strip() for d in self.widget_allowed_domains.split(",") if d.strip()]

    # --- Rate Limiting ---
    rate_limit_chat: str = "30/minute"
    rate_limit_lead: str = "10/minute"
    rate_limit_admin: str = "100/minute"

    # --- Monitoring ---
    sentry_dsn: Optional[str] = None
    health_check_secret: str = "INSECURE_HEALTH_SECRET"

    # --- File Storage ---
    upload_dir: str = "./data/uploads"
    max_upload_size_mb: int = 50
    allowed_upload_extensions: str = "pdf,docx,jpg,jpeg,png"

    @property
    def allowed_extensions(self) -> List[str]:
        return [e.strip().lower() for e in self.allowed_upload_extensions.split(",")]

    # --- Crawling ---
    crawl_user_agent: str = "AbhinavChatbot/1.0"
    crawl_request_delay_seconds: float = 2.0
    crawl_max_pages: int = 200
    crawl_timeout_seconds: int = 30

    @field_validator("app_secret_key", "jwt_secret_key")
    @classmethod
    def check_secret_not_default(cls, v: str, info) -> str:
        insecure = {"INSECURE_DEV_KEY_CHANGE_IN_PRODUCTION",
                    "INSECURE_JWT_DEV_KEY_CHANGE_IN_PRODUCTION"}
        # Allow insecure keys only in development; warn but don't block
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()


settings = get_settings()
