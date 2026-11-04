"""
Abhinav Group AI Chatbot — Conversation and Message Models
Tracks each chat session and its messages for context and analytics.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON, Boolean, DateTime, Enum, ForeignKey,
    Integer, String, Text, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class ConversationStatus(str, enum.Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    ESCALATED = "escalated"      # Handed off to human sales team


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # --- Session ---
    session_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus), default=ConversationStatus.ACTIVE
    )
    language: Mapped[str] = mapped_column(String(10), default="en")
    # 'en' | 'hi' | 'mixed'

    # --- Customer context (collected during conversation) ---
    customer_name: Mapped[Optional[str]] = mapped_column(String(255))
    customer_phone: Mapped[Optional[str]] = mapped_column(String(20))
    budget_min: Mapped[Optional[float]] = mapped_column()
    budget_max: Mapped[Optional[float]] = mapped_column()
    preferred_config: Mapped[Optional[str]] = mapped_column(String(100))
    preferred_location: Mapped[Optional[str]] = mapped_column(String(255))
    property_type_interest: Mapped[Optional[str]] = mapped_column(String(50))
    interested_project_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=True
    )

    # --- Lead association ---
    lead_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("leads.id"), nullable=True
    )

    # --- Source ---
    source_page: Mapped[Optional[str]] = mapped_column(String(1000))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))

    # --- Timestamps ---
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    message_count: Mapped[int] = mapped_column(Integer, default=0)

    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan",
        order_by="Message.created_at"
    )

    def __init__(self, **kwargs):
        kwargs.setdefault('id', str(uuid.uuid4()))
        kwargs.setdefault('status', ConversationStatus.ACTIVE)
        kwargs.setdefault('language', 'en')
        kwargs.setdefault('message_count', 0)
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return f"<Conversation {self.id[:8]} [{self.status}]>"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id"), nullable=False, index=True
    )
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en")

    # --- RAG metadata ---
    retrieved_chunks: Mapped[Optional[dict]] = mapped_column(JSON)
    # Stores which knowledge chunks were used to generate this response
    intent: Mapped[Optional[str]] = mapped_column(String(100))
    # Detected intent: project_enquiry, pricing, brochure_request, lead_capture, escalation, etc.
    mentioned_project_ids: Mapped[Optional[list]] = mapped_column(JSON)

    # --- AI metadata ---
    ai_model_used: Mapped[Optional[str]] = mapped_column(String(100))
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer)
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer)
    is_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    # is_fallback=True when AI was unavailable and a canned response was returned

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
