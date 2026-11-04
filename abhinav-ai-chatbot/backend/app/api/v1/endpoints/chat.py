"""
Chat API — Receives messages and returns AI responses.
"""
from __future__ import annotations

import secrets
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.conversation import Conversation, Message, MessageRole, ConversationStatus
from app.services.chat_service import ChatService

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_token: Optional[str] = None
    source_page: Optional[str] = None


class ChatResponse(BaseModel):
    session_token: str
    reply: str
    language: str
    intent: Optional[str] = None
    quick_replies: Optional[list[str]] = None
    project_cards: Optional[list[dict]] = None
    is_fallback: bool = False


@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: Request,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Main chat endpoint. Accepts a user message and returns an AI-generated response.
    Creates a new conversation session if session_token is not provided.
    """
    if not body.message or not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    if len(body.message) > 2000:
        raise HTTPException(status_code=400, detail="Message too long (max 2000 characters).")

    # Get or create conversation
    session_token = body.session_token
    conversation = None

    if session_token:
        result = await db.execute(
            select(Conversation).where(Conversation.session_token == session_token)
        )
        conversation = result.scalar_one_or_none()

    if not conversation:
        session_token = secrets.token_urlsafe(32)
        conversation = Conversation(
            session_token=session_token,
            source_page=body.source_page,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
        )
        db.add(conversation)
        await db.flush()

    # Process the message through the chat service
    service = ChatService(db=db)
    result = await service.process_message(
        conversation=conversation,
        user_message=body.message.strip(),
    )

    return ChatResponse(
        session_token=session_token,
        reply=result["reply"],
        language=result["language"],
        intent=result.get("intent"),
        quick_replies=result.get("quick_replies"),
        project_cards=result.get("project_cards"),
        is_fallback=result.get("is_fallback", False),
    )


@router.get("/history/{session_token}")
async def get_conversation_history(
    session_token: str,
    db: AsyncSession = Depends(get_db),
):
    """Return the message history for a conversation session."""
    result = await db.execute(
        select(Conversation).where(Conversation.session_token == session_token)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    msgs_result = await db.execute(
        select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at)
    )
    messages = msgs_result.scalars().all()
    return {
        "session_token": session_token,
        "language": conv.language,
        "messages": [
            {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
            for m in messages
        ],
    }
